# -*- coding: utf-8 -*-
"""STEP 0 — Large-subproblem validation & scaling test.

Goal (answer 3 questions with a single experiment):
  Q1) Does CP REALLY struggle as jobs per machine grow? (despite a high budget)
  Q2) Does exact DFJ routing STAY cheap (ms) at 25->40->50 jobs/machine, and where
      does it hit the wall?
  Q3) HLBB-LKH vs HLBB-exact: what is the difference in primal quality and routing time?

Method: take the available ekici 150x15 instance and reduce the machine count to raise
jobs per machine.
  M=6 -> ~25 jobs/machine,  M=4 -> ~38,  M=3 -> ~50.  (the max-13 case = M=15 already
  exists, NOT RUN.)
  Compatibility & cardinality are RELAXED (every job on every machine, no caps) -> a clean
  jobs-per-machine sweep; subproblem size ~ nJob/M through makespan balancing.

3 methods compared:  CP (monolithic) | HLBB-arc (LKH routing) | HLBB-arc (exact-DFJ routing)
Also: exact-DFJ per-call routing time vs subproblem size (the core measurement of Q2).
The feasibility checker is EMBEDDED (all solutions are verified).

Run:      python3 scaling_test.py [instances=12] [cp_tl=1800] [hlbb_tl=300]
Example:  python3 scaling_test.py 12,15 1800 300
"""
import os
import sys
import json
import time
import multiprocessing as mp

from readproblem import readproblem
from CP_model import CP as CP_solve
from lbbd_arc_relax import run as arc_run, route_per_machine_exact
from HLBB import JobsOnMachinesDistMat
from exact_atsp import exact_atsp_dfj
from feasibility import verify_solution

DDIR = "new_dataset_ekici/150_15"
OUT = "json/scaling_test_results.json"
M_SWEEP = [6, 4, 3]          # -> ~25, ~38, ~50 jobs/machine
ROUTE_TL = 60.0              # exact DFJ per-call cap; hitting it marks a "wall"


def build_relaxed(data, M):
    """Use the first M machines; relax compatibility & cardinality -> jobs/machine = nJob/M."""
    (nJob, nMachine, c1, c2, readyTime, processTime, setupTime, matrix, I_l, L_i, estSetup) = data
    assert M <= nMachine
    proc = [processTime[l] for l in range(M)]
    setup = [setupTime[l] for l in range(M)]
    ready = list(readyTime[:M])
    L_i2 = [list(range(M)) for _ in range(nJob)]      # every job compatible with all kept machines
    I_l2 = [list(range(nJob)) for _ in range(M)]
    c1n = {str(l): 0 for l in range(M)}               # no lower cap
    c2n = {str(l): nJob for l in range(M)}            # no upper cap -> makespan balances
    est2 = [[estSetup[i][l] for l in range(M)] for i in range(nJob)]  # unused, but kept valid
    return (nJob, M, c1n, c2n, ready, proc, setup, matrix[:M], I_l2, L_i2, est2)


def record_feas(rec, key, name, assign, data, claimed):
    """verify_solution + record. RELIABLE signal: feasible (hard constraints) + obj_valid
    (exact_makespan <= claim -> the claim is genuinely attainable; NOT phantom-optimal).
    An 'OBJ-TUTARSIZ' seq-order violation is benign for large subproblems (when exact_mk
    confirms it) -> do not raise an alarm."""
    fz = verify_solution(name, assign, data, claimed, verbose=False)
    ex = fz.get("exact_makespan")
    obj_valid = (ex is None) or (claimed is None) or (ex <= claimed + 1.0)
    rec[f"{key}_feasible"] = fz["feasible"]; rec[f"{key}_nviol"] = fz["n_violations"]
    rec[f"{key}_exact_mk"] = round(ex, 1) if ex is not None else None
    rec[f"{key}_obj_valid"] = bool(obj_valid)
    return fz["feasible"] and obj_valid


def routing_microbench(assign, data):
    """Route the given assignment machine by machine with EXACT DFJ: collect (size, time,
    hit-the-cap). The core measurement of Q2: how does exact routing time grow with
    subproblem size?"""
    (nJob, nMachine, c1, c2, readyTime, processTime, setupTime, matrix, I_l, L_i, estSetup) = data
    rows = []
    for l, sel in enumerate(assign):
        if not sel:
            continue
        dist = JobsOnMachinesDistMat(processTime, setupTime, sel, l)
        t0 = time.time()
        val, proven = exact_atsp_dfj(dist, ROUTE_TL, return_proven=True)
        dt = time.time() - t0
        rows.append({"size": len(sel), "dfj_time": round(dt, 3),
                     "proven": bool(proven), "wall": dt >= ROUTE_TL - 1})
    return rows


def run_config(base_inst, M, cp_tl, hlbb_tl):
    base = readproblem(f"{DDIR}/instance_{base_inst}.json",
                       consider_compatibility=True, consider_workload=True)
    data = build_relaxed(base, M)
    nJob, nMachine = data[0], data[1]
    jpm = nJob / nMachine
    print(f"\n########## base=inst{base_inst}  M={M}  (~{jpm:.0f} is/makine) ##########", flush=True)
    rec = {"base": base_inst, "M": M, "jobs_per_machine": round(jpm, 1)}

    # --- 1) CP (monolithic, high budget) ---
    print(f"--- CP (butce={cp_tl}s) ---", flush=True)
    t0 = time.time()
    try:
        cobj, cgap, cassign = CP_solve(data[0], data[1], data[2], data[3], data[4],
                                       data[5], data[6], data[8], data[9],
                                       time_limit=cp_tl, return_solution=True)
        ct = time.time() - t0
        cstatus = "OPT" if (cobj is not None and cobj < 1e6 and 0 <= cgap <= 0.01) else "FEAS"
        if cobj is None or cobj >= 1e6:
            cobj, cstatus, cassign = None, "FAIL", None
    except Exception as e:
        print(f"  CP HATA: {str(e)[:120]}", flush=True)
        cobj, cgap, cassign, ct, cstatus = None, -100, None, time.time() - t0, "FAIL"
    rec["cp_obj"] = round(cobj, 1) if cobj else None
    rec["cp_gap"] = round(cgap, 2) if cobj else None
    rec["cp_time"] = round(ct, 1); rec["cp_status"] = cstatus
    cp_ok = record_feas(rec, "cp", "CP", cassign, data, cobj)
    print(f"  -> CP obj={cobj} gap={rec['cp_gap']}% status={cstatus} t={ct:.0f}s "
          f"gecerli={cp_ok} (exact_mk={rec['cp_exact_mk']})", flush=True)

    # --- 2) HLBB-arc LKH ---
    print(f"--- HLBB-arc (LKH routing, {hlbb_tl}s) ---", flush=True)
    lb, lt, li, lassign = arc_run(*_arc_args(data), total_time_limit=hlbb_tl, time_limit=1,
                                  router="LKH", return_solution=True)
    rec["lkh_obj"] = round(lb, 1); rec["lkh_tbest"] = round(lt, 1); rec["lkh_iters"] = li
    lkh_ok = record_feas(rec, "lkh", "HLBB-LKH", lassign, data, lb)
    print(f"  -> HLBB-LKH best={lb:.0f} iters={li} gecerli={lkh_ok}", flush=True)

    # --- 3) HLBB-arc exact DFJ ---
    print(f"--- HLBB-arc (exact-DFJ routing, {hlbb_tl}s) ---", flush=True)
    eb, et, ei, eassign = arc_run(*_arc_args(data), total_time_limit=hlbb_tl, time_limit=1,
                                  router="exact", route_tl=ROUTE_TL, return_solution=True)
    rec["exact_obj"] = round(eb, 1); rec["exact_tbest"] = round(et, 1); rec["exact_iters"] = ei
    exact_ok = record_feas(rec, "exact", "HLBB-exact", eassign, data, eb)
    print(f"  -> HLBB-exact best={eb:.0f} iters={ei} gecerli={exact_ok}", flush=True)

    # --- 4) routing scaling micro-test (exact per-call on the LKH-best assignment) ---
    micro = routing_microbench(lassign if lassign else eassign, data)
    if micro:
        mx = max(r["dfj_time"] for r in micro)
        walls = sum(1 for r in micro if r["wall"])
        avg_size = sum(r["size"] for r in micro) / len(micro)
        rec["dfj_max_call_s"] = round(mx, 3); rec["dfj_walls"] = walls
        rec["dfj_avg_size"] = round(avg_size, 1); rec["dfj_calls"] = micro
        print(f"  -> exact-DFJ routing: ort_boyut~{avg_size:.0f} is, EN YAVAS cagri={mx:.3f}s, "
              f"tavana-carpan={walls}/{len(micro)}", flush=True)

    # best (feasible only) + RPD
    cands = [(k, v) for k, v in (("cp", rec.get("cp_obj")), ("lkh", rec.get("lkh_obj")),
             ("exact", rec.get("exact_obj")))
             if v is not None and rec.get(f"{k}_feasible") is not False
             and rec.get(f"{k}_obj_valid") is not False]
    best = min(v for _, v in cands) if cands else None
    rec["best"] = round(best, 1) if best else None
    for k in ("cp", "lkh", "exact"):
        v = rec.get(f"{k}_obj")
        rec[f"{k}_rpd"] = round(100 * (v - best) / best, 2) if (v and best) else None
    return rec


def _arc_args(data):
    """Argument order (nJob,nMachine,c1,c2,readyTime,processTime,setupTime,I_l,L_i) for arc_run."""
    nJob, nMachine, c1, c2, readyTime, processTime, setupTime, matrix, I_l, L_i, estSetup = data
    return (nJob, nMachine, c1, c2, readyTime, processTime, setupTime, I_l, L_i)


def main():
    instances = (sys.argv[1] if len(sys.argv) > 1 else "12").split(",")
    cp_tl = int(sys.argv[2]) if len(sys.argv) > 2 else 1800
    hlbb_tl = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    os.makedirs("json", exist_ok=True)
    print(f"### ADIM 0 olcekleme testi | instances={instances} | CP={cp_tl}s HLBB={hlbb_tl}s "
          f"| M sweep={M_SWEEP} ###", flush=True)

    rows = []
    for inst in instances:
        for M in M_SWEEP:
            rec = run_config(inst.strip(), M, cp_tl, hlbb_tl)
            rows.append(rec)
            json.dump(rows, open(OUT, "w"), indent=2)   # save after every config

    # summary table
    print("\n\n================= OZET =================", flush=True)
    print(f"{'base':>4} {'M':>3} {'is/mak':>7} | {'CP':>8} {'stat':>5} {'gap%':>6} {'t':>5} | "
          f"{'LKH':>8} {'exact':>8} | {'DFJ_max':>8} {'duvar':>6}", flush=True)
    for r in rows:
        print(f"{r['base']:>4} {r['M']:>3} {r['jobs_per_machine']:>7} | "
              f"{str(r.get('cp_obj')):>8} {str(r.get('cp_status')):>5} {str(r.get('cp_gap')):>6} "
              f"{str(r.get('cp_time')):>5} | {str(r.get('lkh_obj')):>8} {str(r.get('exact_obj')):>8} | "
              f"{str(r.get('dfj_max_call_s')):>8} {str(r.get('dfj_walls')):>6}", flush=True)
    print(f"\nJSON: {OUT}", flush=True)
    print("Yorum ipucu: CP status=FEAS/gap yuksek + DFJ_max kucuk kalirsa -> premise DOGRU, "
          "LKH gereksiz (exact her yerde). DFJ_max buyur/duvara carparsa -> LKH gerekli.", flush=True)


if __name__ == "__main__":
    mp.set_start_method("spawn")
    main()
