# -*- coding: utf-8 -*-
"""TRACK A -- external-validity benchmark on the pure Vallada R|s_ijk|C_max instances.

Scope:
  - Data: valladapure, ALL 5 sizes, setup asymmetry ONLY S1-99, 10 instances per size = 50 inst.
  - HLBB : locked config IDENTICAL to paper/Track B (hlbb_hm.run_integrated_sr, kmach=3/arc_k=5),
           pure JSON (elig+ready OFF), 200s, single seed (deterministic; same rationale as Track B).
  - SA   : the ORIGINAL (not re-implemented) Santos-SA INSIDE the capsule. Reads the SAME
           valladapure JSON as all methods (niche_bridge -> .nbin -> run_one.jl). In pure JSON
           ready=0 + elig=full, so the niche guards are no-ops -> BIT-IDENTICAL to the raw
           .txt SA (verified: 50_20/i1 41=41, 150_15/i3 163=163). 200s, 3 SEEDS (stochastic).
  - CP   : same pure JSON, generous 600s, single seed (deterministic).

SINGLE SOURCE OF TRUTH: all three methods read the same valladapure/{n_m}/S1-99/instance_{r}.json
(no txt/json inconsistency risk).

Fair comparison: SA/HLBB 200s, CP 600s; the makespan definition is IDENTICAL across methods
(same instance).
RPD = (Cmax - B)/B*100, B = per-instance min(BKS2009, SA_all, HLBB, CP)  [Rolim/Adan metric].
RESUMABLE: every result goes to the CSV immediately; completed (method,size,rep,seed) are skipped.
ONE run at a time (shared LKH directory).

Usage:
  python3 track_a_benchmark.py                       # full: 50 inst, SA 200s x3seed + HLBB 200s + CP 600s
  python3 track_a_benchmark.py --wall 200 --cp-wall 600 --seeds 0,1,2
  python3 track_a_benchmark.py --smoke               # 1 size (50_20) x 2 inst x short budget
  python3 track_a_benchmark.py --summary             # only summarize the existing CSV
"""
import argparse, csv, json, os, re, subprocess, sys, time
from collections import defaultdict
from statistics import mean, pstdev

import feas_hook   # SHARED feasibility checker hook

_HERE = os.path.dirname(os.path.abspath(__file__))
# RELEASE ADAPTATION: can be overridden via environment variable; the default is the
# recorded path of the original runs.
JULIA = os.environ.get("HLBB_JULIA", "/home/sarp/julia_install/julia-1.7.0/bin/julia")
DEPOT = os.environ.get("JULIA_DEPOT_PATH", "/home/sarp/julia_install/depot")
CODE = os.path.join(_HERE, "rolim_capsule/code")
RUN_ONE = os.path.join(CODE, "run_one.jl")
ENV = {**os.environ, "JULIA_DEPOT_PATH": DEPOT}
JSON_DIR = os.path.join(_HERE, "valladapure")            # ALL methods read this pure JSON
BKS = json.load(open(os.path.join(_HERE, "vallada_bks.json")))["bks"]
CSV_PATH = os.path.join(_HERE, "results", "track_a.csv")
SEV = "1-99"                                             # ONLY the 1-99 setup asymmetry
FIELDS = ["method", "size", "sev", "rep", "seed", "n", "m",
          "makespan", "bks", "wall_real", "tbest", "budget"]

SIZES = [  # (label, valladapure folder = n_m, n, m)
    ("50x20",  "50_20",  50, 20),
    ("100x20", "100_20", 100, 20),
    ("150x15", "150_15", 150, 15),
    ("200x15", "200_15", 200, 15),
    ("250x10", "250_10", 250, 10),
]


# ----------------------------- CSV helpers -----------------------------
def load_done():
    done = set()
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="") as f:
            for row in csv.DictReader(f):
                if not all(row.get(k, "") != "" for k in ("method", "size", "rep", "seed")):
                    continue
                done.add((row["method"], row["size"], int(row["rep"]), int(row["seed"])))
    return done


def append_row(row):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
        f.flush()


# ----------------------------- method runners -----------------------------
def run_capsule_sa(json_path, wall, seed):
    """ORIGINAL capsule SA (Santos). Reads the SAME pure JSON as all methods: converted to
    .nbin via niche_bridge; in pure data ready=0 + elig=full -> guards are no-ops ->
    bit-identical to the raw .txt SA.
    RESULT <algo> <Cmax> <iter> <eval> <wall> <tbest> <tlim>."""
    from niche_bridge import ensure_bin
    bp = ensure_bin(json_path)
    out = subprocess.run([JULIA, "-t", "auto", RUN_ONE, "SA", os.path.abspath(bp), str(wall), str(seed)],
                         cwd=CODE, capture_output=True, text=True, env=ENV,
                         timeout=int(wall) * 6 + 600)
    m = re.search(r"^RESULT\s+\S+\s+(\d+)\s+\d+\s+\d+\s+(\S+)\s+(\S+)\s+(\S+)", out.stdout, re.M)
    if m:
        from readproblem import readproblem
        ms = re.search(r"^SOL\s+(.*)$", out.stdout, re.M)
        sol = ([[int(x) - 1 for x in seg.split(",") if x.strip()]
                for seg in ms.group(1).split("|")] if ms else None)
        d = readproblem(json_path, consider_compatibility=False, consider_workload=False)  # PURE
        feas_hook.check("trackA", "SA", os.path.basename(json_path), seed, sol, d,
                        float(m.group(1)), ordered=True)
        return int(m.group(1)), float(m.group(2)), float(m.group(3))  # Cmax, wall, tbest
    raise RuntimeError(f"RESULT yok (SA {json_path}):\nERR:{out.stderr[-700:]}")


def run_hlbb(json_path, wall, seed):
    from readproblem import readproblem
    from hlbb_hm import run_integrated_sr
    d = readproblem(json_path, consider_compatibility=False, consider_workload=False)  # PURE
    nJob, nMachine, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
    t0 = time.time()
    best, best_time, iters, assign = run_integrated_sr(
        nJob, nMachine, c1, c2, rt, pt, st, I_l, L_i,
        total_time_limit=wall, kmach=3, arc_k=5, seed=seed, return_solution=True)
    wall_real = time.time() - t0     # THE CLOCK STOPS HERE: paper 4.2 "reported times exclude ...
                                     # the independent feasibility verification performed after
                                     # it returns" -- the capsule methods' Julia timing already
                                     # measures it this way.
    # ORDERED CHECK: rivals were checked with seq_ok, HLBB only with route_ok.
    # tour_capture orders the final assignment once; outside the budget, never fed back.
    ordered = None
    try:
        from tour_capture import sequence_solution
        if assign:
            ordered = sequence_solution(assign, pt, st)
    except Exception as e:
        print(f"    [tour] sira cikarilamadi: {e}", flush=True)
    feas_hook.check("trackA", "HLBB", os.path.basename(json_path), seed, ordered or assign, d,
                    float(best), ordered=ordered is not None)
    return float(best), wall_real, float(best_time)


def run_cp(json_path, wall, seed):
    from readproblem import readproblem
    from CP_model import CP as CP_solve
    d = readproblem(json_path, consider_compatibility=False, consider_workload=False)  # PURE
    nJob, nMachine, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
    t0 = time.time()
    obj, gap, assign = CP_solve(nJob, nMachine, c1, c2, rt, pt, st, I_l, L_i,
                                time_limit=wall, return_solution=True)
    wall_real = time.time() - t0     # see run_hlbb: verification NOT included in the time
    feas_hook.check("trackA", "CP", os.path.basename(json_path), seed, assign, d,
                    float(obj), ordered=True)
    return float(obj), wall_real, -1.0


# ----------------------------- main run -----------------------------
def bench(wall, cp_wall, seeds, reps=10):
    """SA and HLBB on all seeds (HLBB varies run to run; the 'deterministic single run'
    claim proved WRONG -> 3 repeats); CP is deterministic -> first seed only."""
    s0 = seeds[0]
    done = load_done()
    n_inst = len(SIZES) * reps
    total = n_inst * len(seeds) * 2 + n_inst      # SA seeds + HLBB seeds + CP(1)
    print(f"### TRACK A (pure Vallada S1-99) | SA {wall}s x{len(seeds)}seed + HLBB {wall}s x{len(seeds)}seed + CP {cp_wall}s "
          f"| {len(SIZES)} boyut x 10 inst = {n_inst} | toplam {total} kosu | tamamlanan(CSV)={len(done)} ###\n",
          flush=True)
    t_start = time.time()
    n_run = 0
    for size_lbl, folder, n, m in SIZES:
        for rep in range(1, reps + 1):
            jf = os.path.join(JSON_DIR, folder, f"S{SEV}", f"instance_{rep}.json")
            bks = BKS.get(f"{folder}/S{SEV}/instance_{rep}")
            if not os.path.exists(jf):
                print(f"  ! EKSIK json: {jf}", flush=True); continue
            for sd in seeds:
                for meth in ("SA", "HLBB", "CP"):
                    if meth == "CP" and sd != s0:
                        continue                     # CP deterministic -> single seed; HLBB all seeds
                    key = (meth, size_lbl, rep, sd)
                    if key in done:
                        continue
                    mwall = cp_wall if meth == "CP" else wall
                    try:
                        if meth == "SA":
                            mk, wr, tb = run_capsule_sa(jf, mwall, sd)
                        elif meth == "HLBB":
                            mk, wr, tb = run_hlbb(jf, mwall, sd)
                        else:
                            mk, wr, tb = run_cp(jf, mwall, sd)
                    except Exception as e:
                        print(f"  HATA {meth} {size_lbl}/rep{rep}/sd{sd}: {e}", flush=True)
                        continue
                    append_row(dict(method=meth, size=size_lbl, sev=SEV, rep=rep, seed=sd,
                                    n=n, m=m, makespan=int(mk), bks=bks,
                                    wall_real=round(wr, 1), tbest=round(tb, 1), budget=mwall))
                    n_run += 1
                    el = time.time() - t_start
                    print(f"  [{n_run:3d}] {meth:4s} {size_lbl:7s} rep{rep:<2d} sd{sd} -> "
                          f"mk={int(mk):6d} (BKS={bks}) wall={wr:5.1f}s (gecen {el/3600:.2f}sa)", flush=True)

    print(f"\n=== KOSU BITTI ({n_run} yeni kosu, {(time.time()-t_start)/3600:.2f} sa) ===", flush=True)
    summarize()


# ----------------------------- summary -----------------------------
def summarize():
    if not os.path.exists(CSV_PATH):
        print("CSV yok."); return
    rows = [r for r in csv.DictReader(open(CSV_PATH, newline="")) if r.get("makespan")]
    if not rows:
        print("CSV bos."); return
    for r in rows:
        r["makespan"] = int(r["makespan"]); r["rep"] = int(r["rep"])
        r["bks"] = int(r["bks"]) if r.get("bks") not in ("", None, "None") else None

    # SA and HLBB: per-instance average over seeds (multiple seeds); CP: single value.
    # (The old code treated HLBB as single-valued and kept the LAST seed under multiple
    #  seeds — silently wrong once we moved to 3 repeats; the general aggregator applies
    #  the same rule to all methods.)
    inst = defaultdict(dict)   # (size,rep) -> {method: seed average}
    _acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        _acc[(r["size"], r["rep"])][r["method"]].append(r["makespan"])
    for k, mm in _acc.items():
        for mth, v in mm.items():
            inst[k][mth] = mean(v)
    bks_of = {(r["size"], r["rep"]): r["bks"] for r in rows if r["bks"] is not None}

    def B(sz, rep):
        cand = [inst[(sz, rep)].get(x) for x in ("SA", "HLBB", "CP")]
        cand = [c for c in cand if c is not None]
        b = bks_of.get((sz, rep))
        if b is not None:
            cand.append(b)
        return min(cand) if cand else None

    print("\n" + "=" * 76)
    print("TRACK A -- ortalama RPD %% (B=per-instance min(BKS,SA,HLBB,CP); DUSUK=iyi)\n")
    print(f"  {'boyut':8s} {'#':>3s} | {'SA':>10s} {'HLBB':>10s} {'CP':>10s} {'BKS09':>8s}")
    def rpd(v, b): return 100.0 * (v - b) / b if (v is not None and b) else None
    for sz, _, _, _ in SIZES:
        reps = [rep for rep in range(1, 11) if (sz, rep) in inst]
        cols = {}
        for mth in ("SA", "HLBB", "CP"):
            vals = [rpd(inst[(sz, rep)].get(mth), B(sz, rep)) for rep in reps]
            vals = [v for v in vals if v is not None]
            cols[mth] = f"{mean(vals):.2f}±{pstdev(vals):.2f}" if vals else "-"
        bvals = [rpd(bks_of.get((sz, rep)), B(sz, rep)) for rep in reps if bks_of.get((sz, rep))]
        bvals = [v for v in bvals if v is not None]
        bcol = f"{mean(bvals):.2f}" if bvals else "-"
        print(f"  {sz:8s} {len(reps):>3d} | {cols['SA']:>10s} {cols['HLBB']:>10s} {cols['CP']:>10s} {bcol:>8s}")

    # overall
    allrpd = defaultdict(list)
    for sz, _, _, _ in SIZES:
        for rep in range(1, 11):
            if (sz, rep) not in inst:
                continue
            b = B(sz, rep)
            for mth in ("SA", "HLBB", "CP"):
                v = rpd(inst[(sz, rep)].get(mth), b)
                if v is not None:
                    allrpd[mth].append(v)
    print("  " + "-" * 62)
    gcols = {m: (f"{mean(allrpd[m]):.2f}±{pstdev(allrpd[m]):.2f}" if allrpd[m] else "-") for m in ("SA", "HLBB", "CP")}
    print(f"  {'GENEL':8s} {len(allrpd['HLBB']):>3d} | "
          f"{gcols['SA']:>10s} {gcols['HLBB']:>10s} {gcols['CP']:>10s}")

    # wins
    print("\nKAZANMA (instance-basi en dusuk; SA=seed-ort):")
    wins = defaultdict(float)
    for k in inst:
        vals = {m: inst[k][m] for m in ("SA", "HLBB", "CP") if m in inst[k]}
        if not vals:
            continue
        mn = min(vals.values()); w = [m for m in vals if abs(vals[m] - mn) < 1e-9]
        for m in w:
            wins[m] += 1 / len(w)
    for m in ("SA", "HLBB", "CP"):
        print(f"  {m:5s}: {wins[m]:.1f} / {len(inst)}")
    print("=" * 76, flush=True)


def main():
    global CSV_PATH, SIZES
    ap = argparse.ArgumentParser()
    ap.add_argument("--wall", type=int, default=200, help="SA/HLBB per-instance sn")
    ap.add_argument("--cp-wall", type=int, default=600, help="CP per-instance sn")
    ap.add_argument("--seeds", default="0,1,2", help="SA seed listesi (HLBB/CP yalniz ilk)")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if a.csv:
        CSV_PATH = a.csv if os.path.isabs(a.csv) else os.path.join(_HERE, a.csv)
    seeds = [int(x) for x in a.seeds.split(",")]
    if a.summary:
        summarize()
    elif a.smoke:
        CSV_PATH = os.path.join(_HERE, "results", "track_a_smoke.csv")
        SIZES = [SIZES[0]]
        print("### SMOKE (orkestrasyon; kalite DEGIL): 50_20 x 2 inst x 8s ###", flush=True)
        bench(8, 8, seeds[:1], reps=2)
    else:
        bench(a.wall, a.cp_wall, seeds)


if __name__ == "__main__":
    main()
