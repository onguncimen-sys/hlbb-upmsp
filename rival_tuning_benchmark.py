#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RIVAL RE-TUNING RUN — selection rule follows the pre-registration protocol, item 4.

27 arms = 3 published baselines + 24 one-change arms (SA 6, HGA 8, GA 10). Training set
(DISJOINT, niche): new_dataset_sens {100_15, 250_20, 400_20, 800_30}_1-99_e50_ron
x instance_{1,2,3} x <reps> repeats.
- HGA/GA arms run with DELTAINS_FIX=1 (correctness gate passed 2026-10-10; the fix is NOT a
  tuning candidate, it is fixed to match the published definition exactly). No effect on SA.
- Julia runs with explicit `-t 1` (fairness protocol; the old `-t auto` flaw is not repeated).
- Every solution passes the shared feasibility hook (feas_hook -> feasibility.py).
- RESUME: rows (arm, size, instance, seed) already in results/rival_tuning.csv are skipped.
- Selection rule (POST-RUN analysis, protocol item 4): a one-change arm is adopted only if its
  mean improvement over the published baseline minus 2 SE is > 0; otherwise the published
  value stays.

Usage:  python3 rival_tuning_benchmark.py [wall=200] [reps=2]
Smoke:  python3 rival_tuning_benchmark.py 5 1          (short budget, single repeat)
Estimated duration (full): 27 arms x 12 instances x 2 repeats x 200 s ~ 36 h.
"""
import csv
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import feas_hook
from niche_bridge import ensure_bin
from readproblem import readproblem

# RELEASE ADAPTATION: overridable via environment variable; default = the recorded run path.
JULIA = os.environ.get("HLBB_JULIA", "/home/sarp/julia_install/julia-1.7.0/bin/julia")
CODE = os.path.join(_HERE, "rolim_capsule/code")
ENVB = {**os.environ,
        "JULIA_DEPOT_PATH": os.environ.get("JULIA_DEPOT_PATH", "/home/sarp/julia_install/depot")}
CSV_PATH = os.path.join(_HERE, "results/rival_tuning.csv")
FIELDS = ["kol", "algo", "param", "deger", "boyut", "ornek", "tohum",
          "makespan", "iter", "eval", "tbest", "wall_fiili", "wall", "fix"]

SIZES = ["100_15", "250_20", "400_20", "800_30"]
INSTS = [1, 2, 3]

# one-change values (protocol item 4; published: SA SAmax=1176628/alpha=0.96/T0=1,
# HGA P=15/dnn=dins=dswap=0.8, GA Psize=80/Pc=Pm=0.5/Pls=1.0/Pressure=10)
TEK = {
    "SA":  {"SA_SAMAX": ["588314", "2353256"], "SA_ALPHA": ["0.90", "0.98"], "SA_T0": ["0.5", "2"]},
    # upper d* candidate is 0.9 (NOT 1.0): the code sets ngh=floor(m*d) and loops access
    # l[1+ngh] -> d=1.0 overruns the index (BoundsError). floor(m*0.9)<=m-1 is safe.
    "HGA": {"HGA_P": ["10", "25"], "HGA_DNN": ["0.6", "0.9"],
            "HGA_DINS": ["0.6", "0.9"], "HGA_DSWAP": ["0.6", "0.9"]},
    # upper Psize candidate is 120 (NOT 160): the published code declares Psize::Int8 (max
    # 127); 160 overflows at parse time (OverflowError). 120 = 1.5x published, within the type.
    "GA":  {"GA_PSIZE": ["40", "120"], "GA_PC": ["0.3", "0.7"], "GA_PM": ["0.3", "0.7"],
            "GA_PLS": ["0.6", "0.8"], "GA_PRESSURE": ["5", "20"]},
}


def arms():
    A = [("SA_taban", "SA", "-", "-", {}),
         ("HGA_taban", "HGA", "-", "-", {}),
         ("GA_taban", "GA", "-", "-", {})]
    for algo in ("SA", "HGA", "GA"):
        for var, vals in TEK[algo].items():
            for v in vals:
                A.append((f"{algo}_{var}={v}", algo, var, v, {var: v}))
    return A


def done_keys():
    if not os.path.exists(CSV_PATH):
        return set()
    with open(CSV_PATH) as f:
        return {(r["kol"], r["boyut"], r["ornek"], r["tohum"]) for r in csv.DictReader(f)}


def append_row(row):
    new = not os.path.exists(CSV_PATH)
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
        f.flush()


def run_arm(algo, extra_env, json_path, wall, seed):
    bp = ensure_bin(json_path)
    env = {**ENVB, **extra_env}
    fix = "0"
    if algo in ("HGA", "GA"):
        env["DELTAINS_FIX"] = "1"           # gate-approved fix; not a tuning candidate
        fix = "1"
    out = subprocess.run([JULIA, "-t", "1", f"{CODE}/run_one.jl", algo, bp, str(wall), str(seed)],
                         capture_output=True, text=True, env=env, timeout=int(wall) * 6 + 600)
    res = sol = None
    for ln in out.stdout.splitlines():
        if ln.startswith("RESULT"):
            res = ln.split()
        elif ln.startswith("SOL "):
            sol = [[int(x) - 1 for x in seg.split(",") if x.strip()]
                   for seg in ln[4:].split("|")]
    if res is None:
        raise RuntimeError(f"RESULT yok ({algo} {json_path}):\nERR:{out.stderr[-700:]}")
    d = readproblem(json_path, consider_compatibility=True, consider_workload=True)
    feas_hook.check("tuning", algo, os.path.basename(os.path.dirname(json_path)) + "/"
                    + os.path.basename(json_path), seed, sol, d, float(res[2]), ordered=True)
    # RESULT format (run_one.jl:126): RESULT algo OF I NI wall_real tbest tlim
    # -> res[3]=iterations, res[4]=evaluations, res[5]=actual duration, res[6]=time-of-best.
    return float(res[2]), float(res[3]), float(res[4]), float(res[6]), float(res[5]), fix


def main():
    wall = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    A = arms()
    seen = done_keys()
    toplam = len(A) * len(SIZES) * len(INSTS) * reps
    print(f"kol={len(A)} boyut={len(SIZES)} ornek={len(INSTS)} tekrar={reps} "
          f"-> {toplam} kosu x {wall} sn (tamamlanan {len(seen)} atlanir)")
    k = 0
    for kol, algo, param, deger, extra in A:
        for sz in SIZES:
            for i in INSTS:
                jp = os.path.join(_HERE, f"new_dataset_sens/{sz}_1-99_e50_ron/instance_{i}.json")
                for seed in range(1, reps + 1):
                    k += 1
                    key = (kol, sz, str(i), str(seed))
                    if key in seen:
                        continue
                    # failure rule (pre-registration protocol item 9): retry once with the same
                    # seed; if it fails again, the (instance, method) pair is excluded and
                    # listed in the report.
                    try:
                        mk, it, ev, tb, wf, fix = run_arm(algo, extra, jp, wall, seed)
                    except Exception as e1:
                        print(f"[{k}/{toplam}] {kol} {sz} inst{i} s{seed} HATA, tekrar deneniyor: "
                              f"{str(e1)[:300]}", flush=True)
                        try:
                            mk, it, ev, tb, wf, fix = run_arm(algo, extra, jp, wall, seed)
                        except Exception as e2:
                            print(f"[{k}/{toplam}] {kol} {sz} inst{i} s{seed} IKINCI HATA -> "
                                  f"DISLANDI: {str(e2)[:300]}", flush=True)
                            append_row({"kol": kol, "algo": algo, "param": param, "deger": deger,
                                        "boyut": sz, "ornek": i, "tohum": seed, "makespan": "HATA",
                                        "iter": "", "eval": "", "tbest": "", "wall_fiili": "",
                                        "wall": wall, "fix": ""})
                            continue
                    append_row({"kol": kol, "algo": algo, "param": param, "deger": deger,
                                "boyut": sz, "ornek": i, "tohum": seed, "makespan": mk,
                                "iter": it, "eval": ev, "tbest": tb, "wall_fiili": wf,
                                "wall": wall, "fix": fix})
                    print(f"[{k}/{toplam}] {kol} {sz} inst{i} s{seed} -> {mk:.0f}", flush=True)
    print("\n### KOSU BITTI ###")
    print(feas_hook.summary("tuning"))
    # quick per-arm summary (the selection analysis is done separately; this is a glance only)
    with open(CSV_PATH) as f:
        rows = [r for r in csv.DictReader(f) if r["wall"] == str(wall) and r["makespan"] != "HATA"]
    from collections import defaultdict
    acc = defaultdict(list)
    for r in rows:
        acc[r["kol"]].append(float(r["makespan"]))
    for kol in sorted(acc):
        v = acc[kol]
        print(f"{kol:28s} n={len(v):3d} ort={sum(v)/len(v):9.1f}")


if __name__ == "__main__":
    main()
