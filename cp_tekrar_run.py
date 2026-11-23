# -*- coding: utf-8 -*-
"""PACKAGE 7 — ADDITIONAL CP REPEATS (reviewer item 11: CP comparison under-documented).

WHAT IT DOES: with the CP settings of the niche comparison (same model, same 1000 s budget,
Workers=Auto), runs CP 2 more times each on 10 selected instances and records solver
information NOT CAPTURED so far: status, lower bound, % gap, effective workers, solver time.
Production files (CP_model.py, niche_benchmark.py) are UNTOUCHED: run_cp is called as is,
solver info is captured by wrapping CpoModel.solve at run time (the onecore pattern).

WHY: (1) the paper's sentence "CP is deterministic, run once" is an unmeasured assumption;
the run-to-run spread of a wall-clock-limited solver can only be measured by repeats.
(2) The reviewer asks for bound/gap/status/worker records; the existing CSV has only
the makespan.

INSTANCE SELECTION (PRE-REGISTERED, without looking at results): instance 1 of every size
(8) + instance 2 of the two largest sizes (640x25/2, 800x30/2) = 10 instances. 3 NEW runs
per instance (the old v4-era CP row left worker count/environment UNRECORDED, so it cannot
be verified and does NOT count as a repeat; it is cited only as a historical cross-check).
The CP stack has not changed since the first commit (git); what is measured is RUN-TO-RUN
variability under fixed input + identical settings (no seed parameter; wall-clock-limited
solver).

OUTPUT: results/cp_tekrar.csv (+ .manifest.txt + _feaslog.csv + .dislanan.csv failure rule).
Resumable. Finish marker: "kosu bitti" at the end of the log.

USAGE (the USER starts the run; ~30 x 1000 s ~= 8.4 h):
  cd /home/sarp/HLBB && nohup ./venv/bin/python3 -u cp_tekrar_run.py > cp_tekrar.log 2>&1 &
"""
import csv
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(_HERE, "results", "cp_tekrar.csv")
COLS = ["size", "inst", "rep", "makespan", "bound", "gap_pct", "status", "workers",
        "solve_s", "wall_real", "budget"]
BUDGET = 1000          # SAME as the niche-comparison CP budget (results/niche_bench_v4.csv budget=1000)
CELLS = [("50_10", 1), ("100_15", 1), ("150_15", 1), ("200_20", 1), ("250_20", 1),
         ("400_20", 1), ("640_25", 1), ("800_30", 1), ("640_25", 2), ("800_30", 2)]
REPS = (1, 2, 3)       # three NEW runs (the old row does not count as a repeat; see docstring)

# ---- solver info capture: CpoModel.solve is wrapped, production files UNCHANGED ----
LAST = {}


def _patch_solve():
    from docplex.cp.model import CpoModel
    _orig = CpoModel.solve

    def _solve(self, **kw):
        sol = _orig(self, **kw)
        LAST.clear()
        try:
            LAST["status"] = str(sol.get_solve_status()) if sol else "cozum_yok"
            LAST["bound"] = sol.get_objective_bound() if sol else None
            inf = sol.get_solver_infos() if sol else {}
            LAST["workers"] = inf.get("EffectiveWorkers")
            LAST["solve_s"] = inf.get("TotalTime")
        except Exception as e:                       # if info cannot be read the run does NOT stop
            LAST["status"] = f"okunamadi:{type(e).__name__}"
        return sol

    CpoModel.solve = _solve


def _done():
    got = set()
    if os.path.exists(CSV_PATH):
        for r in csv.DictReader(open(CSV_PATH)):
            got.add((r["size"], r["inst"], r["rep"]))
    xp = CSV_PATH + ".dislanan.csv"
    if os.path.exists(xp):
        for r in csv.DictReader(open(xp)):
            got.add((r["size"], r["inst"], r["rep"]))
    return got


def _exclude(key, neden):
    xp = CSV_PATH + ".dislanan.csv"
    new = not os.path.exists(xp)
    with open(xp, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["size", "inst", "rep", "neden", "zaman"])
        w.writerow(list(key) + [neden, time.strftime("%F %T")])


def main():
    _patch_solve()
    import feas_hook
    feas_hook.LOG_PATH = CSV_PATH[:-4] + "_feaslog.csv"   # keep the main log uncontaminated
    import niche_benchmark as nb

    try:
        git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_HERE,
                             capture_output=True, text=True).stdout.strip()
    except Exception:
        git = "?"
    try:
        import docplex
        from CP_model import CP_OPTIMIZER_EXEC
        cozucu = f"docplex={docplex.__version__} exec={CP_OPTIMIZER_EXEC}"
    except Exception:
        cozucu = "?"
    got = _done()
    jobs = [(s, i, r) for (s, i) in CELLS for r in REPS if (s, str(i), str(r)) not in got]
    with open(CSV_PATH[:-4] + ".manifest.txt", "a") as mf:
        mf.write(f"{time.strftime('%F %T')} git={git} budget={BUDGET}s hucre={len(CELLS)} "
                 f"rep={list(REPS)} bekleyen={len(jobs)} secim=her-boyut-1 + 640/800-2 "
                 f"(on-kayit, docstring) istenen_isci=Auto {cozucu}\n")
    new = not os.path.exists(CSV_PATH)
    fh = open(CSV_PATH, "a", newline="")
    w = csv.writer(fh)
    if new:
        w.writerow(COLS)
    print(f"### CP TEKRARLARI | {len(CELLS)} ornek x {len(REPS)} yeni kosu = "
          f"{len(CELLS)*len(REPS)} ({len(jobs)} kalan) | butce {BUDGET}s | git {git} ###", flush=True)
    t0 = time.time()
    for k, (s, i, r) in enumerate(jobs, 1):
        n, m = s.split("_")
        jp = os.path.join(_HERE, "new_dataset_niche_v2", f"{n}_{m}_1-99_e50_ron",
                          f"instance_{i}.json")
        res = None
        for deneme in (1, 2):                        # failure rule (protocol §9)
            try:
                res = nb.run_cp(jp, BUDGET, 0)
                break
            except Exception as e:
                print(f"    [ariza] deneme {deneme}: {type(e).__name__}: {e}", flush=True)
                res = None
        if res is None:
            _exclude((s, i, r), "iki deneme basarisiz")
            print(f"[{k}/{len(jobs)}] {s} i{i} r{r}  *** DISLANDI ***", flush=True)
            continue
        obj, wall_real, _ = res
        bound = LAST.get("bound")
        gap = (abs(obj - bound) / obj * 100) if (bound is not None and obj > 0) else ""
        row = [s, i, r, obj, bound if bound is not None else "",
               (f"{gap:.2f}" if gap != "" else ""), LAST.get("status", ""),
               LAST.get("workers", ""), LAST.get("solve_s", ""),
               round(wall_real, 1), BUDGET]
        assert len(row) == len(COLS)
        w.writerow(row)
        fh.flush()
        el = time.time() - t0
        eta = el / k * (len(jobs) - k)
        print(f"[{k}/{len(jobs)}] {s:>7} i{i} r{r}  mk={obj:7.0f} sinir={bound} "
              f"durum={LAST.get('status','?'):>10} isci={LAST.get('workers','?')}"
              f"  [{el/3600:.1f}sa gecti, ~{eta/3600:.1f}sa kaldi]", flush=True)
    fh.close()
    print("kosu bitti", flush=True)


if __name__ == "__main__":
    main()
