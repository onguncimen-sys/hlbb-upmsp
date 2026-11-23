# -*- coding: utf-8 -*-
"""PHASE-3 NICHE BENCHMARK: SA / HGA / GA / HLBB (+optional CP), shared wall clock, 2x2 niche.

2x2 CONTROLLED ABLATION: elig{off,on} x ready{off,on}, SHARED base instance -> isolated
marginal effect of each feature + interaction. 4 regimes:
  eoff/r0  = pure*  (NO elig+ready, a clean baseline on our own instances)
  e50/r0   = eligibility only
  eoff/ron = ready only
  e50/ron  = FULL NICHE (elig+ready)

Fair comparison: every method on the SAME instance with the SAME wall budget. The makespan
definition is IDENTICAL across all methods.
  - SA/HGA/GA : capsule (run_one.jl + .nbin bridge), niche-VALID (equiv+feas).
  - HLBB      : run_integrated_sr, LOCKED config.
  - CP        : optional (--cp), CP Optimizer, same wall.

RESUMABLE: every result is written to the CSV immediately; completed (method,instance,seed)
triples are skipped.
Usage:
  python3 niche_benchmark.py                 # wall=200s reps=1: 8 sizes x 4 regimes = 32 inst x 4 = 128 runs (~7 h)
  python3 niche_benchmark.py --wall 180      # ~6.4 h
  python3 niche_benchmark.py --reps 3 --wall 300   # larger
  python3 niche_benchmark.py --cp            # add CP as well (slow, separate pass)
  python3 niche_benchmark.py --smoke         # orchestration smoke test (~2 min)
  python3 niche_benchmark.py --summary       # summary of the existing CSV only

SINGLE run (no other hlbb/capsule run may run AT THE SAME TIME -> shared LKH directory).
"""
import argparse
import csv
import os
import subprocess
import sys
import time
from collections import defaultdict
from statistics import mean, pstdev

import feas_hook   # SHARED feasibility checker hook

# RELEASE ADAPTATION: overridable via environment variable; default = the recorded run path.
JULIA = os.environ.get("HLBB_JULIA", "/home/sarp/julia_install/julia-1.7.0/bin/julia")
_HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(_HERE, "rolim_capsule/code")
# Julia SINGLE-threaded (-t 1; the old -t auto was a fairness defect) and rival lock:
# DELTAINS_FIX=1 (HGA/GA correctness fix; no effect on SA), niche-line settings
# HGA_DINS=0.9, GA_PM=0.3 (Appendix A; SA is fully as published, takes no variable).
ENV = {**os.environ,
       "JULIA_DEPOT_PATH": os.environ.get("JULIA_DEPOT_PATH", "/home/sarp/julia_install/depot"),
       "DELTAINS_FIX": "1", "HGA_DINS": "0.9", "GA_PM": "0.3"}
CSV_PATH = os.path.join(_HERE, "results", "niche_bench.csv")
# HLBB arc ranking and row label. DEFAULT = production ("cost", label "HLBB") -> the old
# behavior is preserved exactly. With --arc-rank rc the label automatically becomes
# "HLBB_rc", so it does NOT MIX with old HLBB rows in the same CSV and the resume logic
# (method,inst,seed) works correctly.
ARC_RANK = "cost"
HLBB_LABEL = "HLBB"
# HLBB_ARMS: [(label, arc_rank)] — several HLBB arms WITHIN THE SAME PROCESS. Empty -> the
# single arm (ARC_RANK/HLBB_LABEL) is used = old behavior. Multiple arms run interleaved
# (in turn for each instance+seed), so both arms see the SAME memory/directory state -- the
# bias from day/process differences disappears. Rationale: _ARC_CACHE grows without bound
# (RSS 188->883 MB over 4 runs), so two arms measured in SEPARATE runs are not comparable.
HLBB_ARMS = []
FIELDS = ["method", "size", "elig", "rho", "rep", "seed", "n", "m",
          "makespan", "wall_real", "tbest", "budget"]

SIZES = [  # (label, folder prefix, n, m)
    ("50x10",  "50_10_1-99",  50, 10),
    ("100x15", "100_15_1-99", 100, 15),
    ("150x15", "150_15_1-99", 150, 15),
    ("200x20", "200_20_1-99", 200, 20),
    ("250x20", "250_20_1-99", 250, 20),
    ("400x20", "400_20_1-99", 400, 20),
    ("640x25", "640_25_1-99", 640, 25),
    ("800x30", "800_30_1-99", 800, 30),
    # B3 (controlled constraint-advantage experiment): same n/m as the two configurations
    # Track A LOSES (2.5 and 5). Exists only in new_dataset_niche_b3; other datasets lack
    # the folder -> the os.path.exists guard below skips it.
    ("50x20",  "50_20_1-99",  50, 20),
    ("100x20", "100_20_1-99", 100, 20),
]
ELIGS = ["eoff", "e50"]     # eligibility on/off
RHOS = ["r0", "ron"]        # ready on/off
CAPSULE = ["SA"]                    # changed via --algos (default SA; SA,HGA,GA selectable)
DATASET_DIR = "new_dataset_niche"   # overridden in main via --dataset (for the v2 run)


def cell_label(elig, rho):
    return {("eoff", "r0"): "pure*", ("e50", "r0"): "elig", ("eoff", "ron"): "ready",
            ("e50", "ron"): "TAM"}[(elig, rho)]


# ----------------------------- CSV helpers -----------------------------
def _excl_path():
    return os.path.splitext(CSV_PATH)[0] + ".dislanan.csv"


def _exclude(key, neden):
    """PERMANENT exclusion record for a job that failed both attempts (pre-registered
    failure rule). The main CSV schema is unchanged (old consumers keep working); the
    resume mechanism does NOT reopen exclusions (otherwise repeated restarts would turn
    into 'retry until it succeeds' selection)."""
    yeni = not os.path.exists(_excl_path())
    with open(_excl_path(), "a", newline="") as f:
        w = csv.writer(f)
        if yeni:
            w.writerow(["zaman", "method", "size", "elig", "rho", "rep", "seed", "neden"])
        w.writerow([time.strftime("%F %T")] + list(key) + [neden])
    print(f"  *** DISLANDI: {key} ({neden}) ***", flush=True)


def load_done():
    done = set()
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="") as f:
            for row in csv.DictReader(f):
                if not all(k in row and row[k] != "" for k in
                           ("method", "size", "elig", "rho", "rep", "seed")):
                    continue   # old/incompatible schema row -> skip (will be re-run)
                done.add((row["method"], row["size"], row["elig"], row["rho"],
                          int(row["rep"]), int(row["seed"])))
    if os.path.exists(_excl_path()):       # permanent exclusions also count as "done"
        with open(_excl_path(), newline="") as f:
            for row in csv.DictReader(f):
                done.add((row["method"], row["size"], row["elig"], row["rho"],
                          int(row["rep"]), int(row["seed"])))
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
def run_capsule(algo, json_path, wall, seed):
    from niche_bridge import ensure_bin
    from readproblem import readproblem
    bp = ensure_bin(json_path)
    out = subprocess.run([JULIA, "-t", "1", f"{CODE}/run_one.jl", algo, bp, str(wall), str(seed)],
                         capture_output=True, text=True, env=ENV, timeout=int(wall) * 6 + 600)
    res = sol = None
    for ln in out.stdout.splitlines():
        if ln.startswith("RESULT"):
            res = ln.split()
        elif ln.startswith("SOL "):
            # Julia 1-indexed -> Python 0-indexed (bridge verified with bridge_test.py)
            sol = [[int(x) - 1 for x in seg.split(",") if x.strip()]
                   for seg in ln[4:].split("|")]
    if res is None:
        raise RuntimeError(f"RESULT yok ({algo} {json_path}):\nERR:{out.stderr[-700:]}")
    d = readproblem(json_path, consider_compatibility=True, consider_workload=True)
    # the capsule schedule is ORDERED -> seq_ok is valid
    feas_hook.check("niche", algo, os.path.basename(os.path.dirname(json_path)) + "/"
                    + os.path.basename(json_path), seed, sol, d, float(res[2]), ordered=True)
    return float(res[2]), float(res[5]), float(res[6])


def make_hlbb_runner(label, rank):
    """Runner closing over label+ranking (for multi-arm use)."""
    def _run(json_path, wall, seed):
        return run_hlbb(json_path, wall, seed, rank=rank, label=label)
    return _run


def run_hlbb(json_path, wall, seed, rank=None, label=None):
    from readproblem import readproblem
    from hlbb_hm import run_integrated_sr
    d = readproblem(json_path, consider_compatibility=True, consider_workload=True)
    nJob, nMachine, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
    t0 = time.time()
    # return_solution: ONLY a return-path flag, adds no computation (best_assign is already
    # kept for the warm start). The audit runs AFTER the run ends -> steals no budget.
    best, best_time, iters, assign = run_integrated_sr(
        nJob, nMachine, c1, c2, rt, pt, st, I_l, L_i,
        total_time_limit=wall, kmach=3, arc_k=5, seed=seed, return_solution=True,
        arc_rank=rank or ARC_RANK)
    wall_real = time.time() - t0     # THE CLOCK STOPS HERE: paper 4.2 "reported times exclude ...
                                     # the independent feasibility verification performed after
                                     # it returns" -- capsule-side Julia measures the same way.
    # SEQUENCE AUDIT: HLBB kept no sequence -> rivals were audited via seq_ok, HLBB only via
    # route_ok (we verified our own method LESS). tour_capture solves the final assignment
    # in order once; outside the budget, not fed back into the result.
    ordered = None
    try:
        from tour_capture import sequence_solution
        if assign:
            ordered = sequence_solution(assign, pt, st)
    except Exception as e:
        print(f"    [tour] sira cikarilamadi: {e}", flush=True)
    feas_hook.check("niche", label or HLBB_LABEL, os.path.basename(os.path.dirname(json_path)) + "/"
                    + os.path.basename(json_path), seed, ordered or assign, d, float(best),
                    ordered=ordered is not None)
    return float(best), wall_real, float(best_time)


def run_cp(json_path, wall, seed):
    from readproblem import readproblem
    from CP_model import CP as CP_solve
    d = readproblem(json_path, consider_compatibility=True, consider_workload=True)
    nJob, nMachine, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
    t0 = time.time()
    obj, gap, assign = CP_solve(nJob, nMachine, c1, c2, rt, pt, st, I_l, L_i,
                                time_limit=wall, return_solution=True)
    # CP returns the schedule ordered by START TIME -> seq_ok valid (phantom-objective test)
    wall_real = time.time() - t0     # see run_hlbb: the audit is NOT included in the time
    feas_hook.check("niche", "CP", os.path.basename(os.path.dirname(json_path)) + "/"
                    + os.path.basename(json_path), seed, assign, d, float(obj), ordered=True)
    return float(obj), wall_real, -1.0


# ----------------------------- main run -----------------------------
def bench(wall, reps, seeds, use_cp, cp_wall=None, single_seed=("CP",)):
    """seeds = a list; STOCHASTIC methods run every instance on ALL seeds (reliability).
    Methods in single_seed (deterministic) run ONCE, on the first seed only (no waste).
    Default: CP is deterministic; if a probe finds HLBB deterministic, pass 'CP,HLBB'."""
    cp_wall = cp_wall or wall
    if isinstance(seeds, int):
        seeds = [seeds]
    single_seed = set(single_seed)
    s0 = seeds[0]
    hl = [lb for lb, _ in HLBB_ARMS] or [HLBB_LABEL]
    methods = CAPSULE + hl + (["CP"] if use_cp else [])
    done = load_done()
    n_inst = len(SIZES) * len(ELIGS) * len(RHOS) * reps
    # run count: stochastic -> n_inst*seeds; single_seed -> n_inst*1
    stoch = [m for m in methods if m not in single_seed]
    det = [m for m in methods if m in single_seed]
    total = n_inst * len(stoch) * len(seeds) + n_inst * len(det)
    print(f"### NIS BENCHMARK | wall={wall}s (CP {cp_wall}s) | reps={reps} | seeds={seeds} | yontemler={methods} | toplam {total} kosu ###")
    print(f"### {len(SIZES)} boyut x {len(ELIGS)}x{len(RHOS)} rejim x {reps} instance x seed{seeds} "
          f"| SA/HLBB={len(stoch)*len(seeds)}/hucre, CP=1/hucre | tamamlanan(CSV)={len(done)} ###\n", flush=True)

    runners = {"CP": run_cp}
    if HLBB_ARMS:
        runners.update({lb: make_hlbb_runner(lb, rk) for lb, rk in HLBB_ARMS})
    else:
        runners[HLBB_LABEL] = run_hlbb
    # for the ETA: total budget of pending runs (completed ones are subtracted on resume)
    bud_pend = n_pend = 0
    for size_lbl, _prefix, _, _ in SIZES:
        for elig in ELIGS:
            for rho in RHOS:
                for rep in range(1, reps + 1):
                    # the ETA must count only cells that will ACTUALLY run: the main loop
                    # skipped missing folders but this count did not -> the ETA inflated.
                    if not os.path.exists(f"{DATASET_DIR}/{_prefix}_{elig}_{rho}/instance_{rep}.json"):
                        continue
                    for sd in seeds:
                        for meth in methods:
                            if meth in single_seed and sd != s0:
                                continue
                            if (meth, size_lbl, elig, rho, rep, sd) in done:
                                continue
                            bud_pend += cp_wall if meth == "CP" else wall
                            n_pend += 1
    t_start = time.time()
    n_run = 0
    bud_done = 0
    for size_lbl, prefix, n, m in SIZES:
        for elig in ELIGS:
            for rho in RHOS:
                for rep in range(1, reps + 1):
                    jf = f"{DATASET_DIR}/{prefix}_{elig}_{rho}/instance_{rep}.json"
                    if not os.path.exists(jf):
                        print(f"  ! EKSIK: {jf}", flush=True)
                        continue
                    for sd in seeds:
                        for meth in methods:
                            if meth in single_seed and sd != s0:
                                continue                     # deterministic -> single seed
                            key = (meth, size_lbl, elig, rho, rep, sd)
                            if key in done:
                                continue
                            mwall = cp_wall if meth == "CP" else wall
                            # failure rule (pre-registered): one retry with the same key,
                            # permanent exclusion on the second failure (see _exclude).
                            res = None
                            for deneme in (1, 2):
                                try:
                                    if meth in CAPSULE:
                                        res = run_capsule(meth, jf, mwall, sd)
                                    else:
                                        res = runners[meth](jf, mwall, sd)
                                    break
                                except Exception as e:
                                    print(f"  HATA({deneme}/2) {meth} {size_lbl}/{elig}/{rho}/"
                                          f"rep{rep}/sd{sd}: {str(e)[:200]}", flush=True)
                            if res is None:
                                _exclude(key, "iki deneme basarisiz")
                                continue
                            mk, wr, tb = res
                            append_row(dict(method=meth, size=size_lbl, elig=elig, rho=rho, rep=rep,
                                            seed=sd, n=n, m=m, makespan=int(mk),
                                            wall_real=round(wr, 1), tbest=round(tb, 1), budget=mwall))
                            n_run += 1
                            bud_done += mwall
                            el = time.time() - t_start
                            # remaining ~ pending budget x (elapsed / completed budget):
                            # learns the loading/audit share automatically
                            eta = (bud_pend - bud_done) * (el / bud_done)
                            # the regime label is informative only in a multi-regime run
                            cell = f"{cell_label(elig,rho):5s} " if len(ELIGS) * len(RHOS) > 1 else ""
                            print(f"  [{n_run:3d}/{n_pend}] {meth:5s} {size_lbl:7s} "
                                  f"{cell}rep{rep} sd{sd} -> mk={int(mk):6d} "
                                  f"wall={wr:5.1f}s | gecen {el/3600:5.2f}sa | kalan ~{eta/3600:4.1f}sa",
                                  flush=True)

    print(f"\n=== KOSU BITTI ({n_run} yeni kosu, {(time.time()-t_start)/3600:.2f} sa) ===", flush=True)
    summarize()


# ----------------------------- summary -----------------------------
def summarize():
    if not os.path.exists(CSV_PATH):
        print("CSV yok."); return
    rows = list(csv.DictReader(open(CSV_PATH, newline="")))
    if not rows:
        print("CSV bos."); return
    for r in rows:
        r["makespan"] = int(r["makespan"])
    methods = sorted({r["method"] for r in rows})
    best = {}
    for r in rows:
        k = (r["size"], r["elig"], r["rho"], r["rep"])
        best[k] = min(best.get(k, 1e18), r["makespan"])

    def rpd(r):
        b = best[(r["size"], r["elig"], r["rho"], r["rep"])]
        return 100.0 * (r["makespan"] - b) / b

    print("\n" + "=" * 80)
    print("2x2 REJIM x YONTEM -- ortalama RPD %% (best-known'a gore; DUSUK=iyi)")
    print("  (pure*=elig+ready YOK | elig=yalniz elig | ready=yalniz ready | TAM=elig+ready)\n")
    cells = [("eoff", "r0"), ("e50", "r0"), ("eoff", "ron"), ("e50", "ron")]
    print(f"  {'rejim':16s} " + " ".join(f"{mth:>8s}" for mth in methods))
    for (e, r) in cells:
        lbl = f"{cell_label(e,r)}({e}/{r})"
        vals = []
        for mth in methods:
            rp = [rpd(x) for x in rows if x["elig"] == e and x["rho"] == r and x["method"] == mth]
            vals.append(f"{sum(rp)/len(rp):7.2f}" if rp else f"{'-':>7s}")
        print(f"  {lbl:16s} " + " ".join(f"{v:>8s}" for v in vals))

    print("\nBOYUT x YONTEM -- RPD %% ort+-std (TAM nis rejiminde: e50/ron)")
    print(f"  {'boyut':8s} " + " ".join(f"{mth:>13s}" for mth in methods))
    for sz, _, _, _ in SIZES:
        vals = []
        for mth in methods:
            rp = [rpd(x) for x in rows if x["size"] == sz and x["elig"] == "e50"
                  and x["rho"] == "ron" and x["method"] == mth]
            vals.append(f"{mean(rp):6.2f}+-{pstdev(rp):4.2f}" if rp else f"{'-':>12s}")
        print(f"  {sz:8s} " + " ".join(f"{v:>13s}" for v in vals))

    print("\nMAKESPAN ort (boyut x yontem, TUM rejim ortalamasi) -- [n]")
    print(f"  {'boyut':8s} " + " ".join(f"{mth:>11s}" for mth in methods))
    for sz, _, _, _ in SIZES:
        vals = []
        for mth in methods:
            v = [x["makespan"] for x in rows if x["size"] == sz and x["method"] == mth]
            vals.append(f"{mean(v):8.1f}[{len(v)}]" if v else f"{'-':>11s}")
        print(f"  {sz:8s} " + " ".join(f"{v:>11s}" for v in vals))

    print("\nKAZANMA (instance basi en dusuk makespan; beraberlik dahil):")
    wins = defaultdict(int)
    for k in {(r["size"], r["elig"], r["rho"], r["rep"]) for r in rows}:
        gr = [r for r in rows if (r["size"], r["elig"], r["rho"], r["rep"]) == k]
        mn = min(r["makespan"] for r in gr)
        for w in {r["method"] for r in gr if r["makespan"] == mn}:
            wins[w] += 1
    for mth in methods:
        print(f"  {mth:6s}: {wins[mth]:3d}")

    # ---- time/contract: size x method wall mean [max] + budget overrun ----
    for r in rows:
        r["wall_real"] = float(r["wall_real"])
        r["tbest"] = float(r["tbest"])
        r["budget"] = float(r["budget"])
    print("\nWALL ort[max] sn (boyut x yontem) -- kontrat: wall <= butce (+%5 tolerans)")
    print(f"  {'boyut':8s} " + " ".join(f"{mth:>13s}" for mth in methods))
    for sz, _, _, _ in SIZES:
        vals = []
        for mth in methods:
            v = [x["wall_real"] for x in rows if x["size"] == sz and x["method"] == mth]
            vals.append(f"{mean(v):5.0f}[{max(v):4.0f}]" if v else f"{'-':>11s}")
        print(f"  {sz:8s} " + " ".join(f"{v:>13s}" for v in vals))
    viol = defaultdict(int)
    for r in rows:
        if r["wall_real"] > r["budget"] * 1.05:
            viol[r["method"]] += 1
    print("  butce-asimi (>%5): " + (", ".join(f"{m}={c}" for m, c in sorted(viol.items()))
                                     if viol else "YOK"))

    print("\nT-BEST ort sn (boyut x yontem; son iyilesme ani -- raporlamayanlar '-')")
    print(f"  {'boyut':8s} " + " ".join(f"{mth:>8s}" for mth in methods))
    for sz, _, _, _ in SIZES:
        vals = []
        for mth in methods:
            v = [x["tbest"] for x in rows if x["size"] == sz and x["method"] == mth
                 and x["tbest"] >= 0]
            vals.append(f"{mean(v):7.0f}" if v else f"{'-':>7s}")
        print(f"  {sz:8s} " + " ".join(f"{v:>8s}" for v in vals))

    # ---- seed spread: across seeds on the same instance (max-min) ----
    print("\nSEED YAYILIMI (ayni instance, seed'ler arasi max-min makespan; ort birim)")
    stoch = [m for m in methods
             if len({r["seed"] for r in rows if r["method"] == m}) > 1]
    print(f"  {'boyut':8s} " + " ".join(f"{mth:>8s}" for mth in stoch))
    for sz, _, _, _ in SIZES:
        vals = []
        for mth in stoch:
            sp = []
            for k in {(r["elig"], r["rho"], r["rep"]) for r in rows if r["size"] == sz}:
                v = [r["makespan"] for r in rows if r["method"] == mth and r["size"] == sz
                     and (r["elig"], r["rho"], r["rep"]) == k]
                if len(v) > 1:
                    sp.append(max(v) - min(v))
            vals.append(f"{mean(sp):7.1f}" if sp else f"{'-':>7s}")
        print(f"  {sz:8s} " + " ".join(f"{v:>8s}" for v in vals))

    # ---- per-instance detail: best mk / mean wall / mean tbest ----
    print("\nINSTANCE DETAYI (hucre: en-iyi-mk | wall-ort | tbest-ort; seed'ler uzerinden)")
    print(f"  {'instance':16s} " + " ".join(f"{mth:>19s}" for mth in methods))
    for sz, _, _, _ in SIZES:
        for k in sorted({(r["elig"], r["rho"], int(r["rep"])) for r in rows if r["size"] == sz}):
            lbl = f"{sz}/{cell_label(k[0], k[1])}/i{k[2]}"
            vals = []
            for mth in methods:
                v = [r for r in rows if r["method"] == mth and r["size"] == sz
                     and (r["elig"], r["rho"], int(r["rep"])) == k]
                if not v:
                    vals.append(f"{'-':>19s}"); continue
                tb = [x["tbest"] for x in v if x["tbest"] >= 0]
                tbs = f"{mean(tb):4.0f}" if tb else "   -"
                vals.append(f"{min(x['makespan'] for x in v):5d}|{mean(x['wall_real'] for x in v):5.0f}s|{tbs}s")
            print(f"  {lbl:16s} " + " ".join(f"{v:>19s}" for v in vals))

    # ---- completeness: expected key set from the observed sizes ----
    print("\nEKSIKSIZLIK (yontemin kendi seed-kumesi x tum instance'lar; eksik = HATA'yla dusen)")
    insts = {(r["size"], r["elig"], r["rho"], r["rep"]) for r in rows}
    n_miss = 0
    for mth in methods:
        sds = sorted({r["seed"] for r in rows if r["method"] == mth})
        have = {(r["size"], r["elig"], r["rho"], r["rep"], r["seed"])
                for r in rows if r["method"] == mth}
        miss = [(i, s) for i in insts for s in sds if (*i, s) not in have]
        n_miss += len(miss)
        st = "TAMAM" if not miss else "; ".join(f"{i[0]}/i{i[3]}/sd{s}" for i, s in miss[:6]) \
            + (f" ... +{len(miss)-6}" if len(miss) > 6 else "")
        print(f"  {mth:6s} [{len(have):3d} kosu, seed{sds}]: {st}")
    if n_miss:
        print(f"  !! toplam {n_miss} eksik kosu -- ayni komut resume ile tamamlar")

    print("\n" + feas_hook.summary("niche"))
    print("=" * 80, flush=True)


def main():
    global CSV_PATH, SIZES, DATASET_DIR, ELIGS, RHOS, CAPSULE, ARC_RANK, HLBB_LABEL, HLBB_ARMS
    ap = argparse.ArgumentParser()
    ap.add_argument("--wall", type=int, default=200, help="SA/HLBB per-instance sn")
    ap.add_argument("--reps", type=int, default=5, help="cell-basi instance sayisi (farkli problem verisi)")
    ap.add_argument("--seeds", default="0,1,2", help="stokastik seed listesi (SA/HLBB her instance'i bu seed'lerde; CP tek)")
    ap.add_argument("--cp", action="store_true", help="CP'yi de kos")
    ap.add_argument("--cp-wall", type=int, default=None, help="CP icin ayri butce (None=wall ile ayni)")
    ap.add_argument("--algos", default="SA", help="kapsul metasezgiselleri (or. 'SA,HGA,GA'); run_one.jl nis modu yalniz bu ucunu kabul eder")
    ap.add_argument("--dataset", default="new_dataset_niche", help="instance klasoru (v2 icin degistir)")
    ap.add_argument("--csv", default=None, help="cikti CSV yolu (None=results/niche_bench.csv)")
    ap.add_argument("--eligs", default=None, help="rejim filtresi (or. 'e50'); None=hepsi (eoff,e50)")
    ap.add_argument("--rhos", default=None, help="rejim filtresi (or. 'ron'); None=hepsi (r0,ron)")
    ap.add_argument("--single-seed-methods", default="CP",
                    help="deterministik (tek-seed) yontemler; probe HLBB'yi det bulursa 'CP,HLBB'")
    ap.add_argument("--arc-rank", default="cost",
                    help="HLBB ark-siralamasi: cost(uretim) | rc | ap | alpha | rcfix | costfix")
    ap.add_argument("--label", default=None, help="HLBB satir etiketi (None=otomatik)")
    ap.add_argument("--hlbb-arms", default=None,
                    help="AYNI surecte coklu HLBB kolu: 'etiket:rank,etiket:rank' "
                         "(or. 'ctl:cost,rc:rc'); ic ice kosar -> gun/surec yanliligi yok")
    ap.add_argument("--sizes", default=None, help="boyut filtresi (or. '640x25,800x30')")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    seeds = [int(x) for x in a.seeds.split(",")]
    ARC_RANK = a.arc_rank
    HLBB_LABEL = a.label or ("HLBB" if ARC_RANK == "cost" else f"HLBB_{ARC_RANK}")
    if a.hlbb_arms:
        HLBB_ARMS = [(f"HLBB_{x.split(':')[0]}", x.split(":")[1]) for x in a.hlbb_arms.split(",") if x]
    if a.sizes:
        keep = set(a.sizes.split(","))
        SIZES = [t for t in SIZES if t[0] in keep]
        assert SIZES, f"boyut filtresi hicbir seye uymadi: {keep}"
    single_seed = tuple(a.single_seed_methods.split(",")) if a.single_seed_methods else ()
    CAPSULE = [x for x in a.algos.split(",") if x]
    DATASET_DIR = a.dataset
    if a.csv:
        CSV_PATH = a.csv if os.path.isabs(a.csv) else os.path.join(_HERE, a.csv)
    if a.eligs:
        ELIGS = a.eligs.split(",")
    if a.rhos:
        RHOS = a.rhos.split(",")
    if a.summary:
        summarize()
    elif a.smoke:
        CSV_PATH = os.path.join(_HERE, "results", "smoke.csv")
        SIZES = SIZES[:1]     # 50x10 x 4 regimes
        print("### SMOKE (orkestrasyon; kalite DEGIL): 1 boyut x 4 rejim x wall=8s ###", flush=True)
        bench(8, 1, seeds[:1], a.cp, a.cp_wall, single_seed)
    else:
        bench(a.wall, a.reps, seeds, a.cp, a.cp_wall, single_seed)


if __name__ == "__main__":
    main()
