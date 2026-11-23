# -*- coding: utf-8 -*-
"""SINGLE CORE runner -- reviewer Major concern 4 (processor resources not controlled).

WHAT IT DOES: without ANY change to `niche_benchmark.py`, runs all methods restricted to
the same SINGLE logical processor and writes each run's CPU time to a side file.
Production code (hlbb_hm.py, spp_recombine.py, the capsule) is UNCHANGED; the algorithm is
the same algorithm, only the processor resource given to it changes.

  1) The process must be pinned to ONE processor via `taskset -c <cpu>`; otherwise it
     REFUSES to run. Affinity is inherited by children: LKH workers and Julia share the core.
  2) Gurobi: Threads=1 in the shared environment (both the main model and the
     recombination model use this environment).
  3) Julia: the benchmark script calls it with `-t auto`; here it becomes `-t 1`.
  4) The feasibility check is logged SEPARATELY (`<csv>_feaslog.csv`) -> the main
     benchmark log stays clean.
  5) RUN RECORD: `<csv>.manifest.json` (code version, command, processor, solver version,
     data digest).
  6) CPU TIME: `<csv>_cpu.csv` -- core-seconds per run (process + children).
     ⚠️ The measurement also includes the post-run feasibility check (off-budget, small).

USAGE (the USER starts the run):
  ./run_trackb_1core.sh 2>&1 | tee trackb_1core.log
Directly:
  taskset -c 0 python3 onecore_run.py --dataset new_dataset_niche_v2 \
      --csv results/niche_bench_1core.csv --eligs e50 --rhos ron \
      --wall 200 --reps 5 --seeds 0,1,2 --algos SA
"""
import csv
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))


def _arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default


def _cpu_now():
    s = resource.getrusage(resource.RUSAGE_SELF)
    c = resource.getrusage(resource.RUSAGE_CHILDREN)
    return s.ru_utime + s.ru_stime + c.ru_utime + c.ru_stime


def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=_HERE, capture_output=True, text=True).stdout.strip()
    except Exception:
        return "?"


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def main():
    aff = sorted(os.sched_getaffinity(0))
    if len(aff) != 1:
        sys.exit(f"DURDU: surec {len(aff)} islemciye acik ({aff}). Tek cekirdek kosusu icin\n"
                 f"  taskset -c 0 python3 onecore_run.py ...   ile baslatin.")
    csv_arg = _arg("--csv")
    if not csv_arg:
        sys.exit("DURDU: --csv verilmeli (ana kiyas dosyasinin uzerine yazilmasin).")
    csv_path = csv_arg if os.path.isabs(csv_arg) else os.path.join(_HERE, csv_arg)
    base = csv_path[:-4] if csv_path.endswith(".csv") else csv_path
    cpu_path, man_path, feas_path = base + "_cpu.csv", base + ".manifest.json", base + "_feaslog.csv"

    # ---- run record (BEFORE the patches: git calls use the original subprocess.run) ----
    import gurobipy
    dataset = _arg("--dataset", "new_dataset_niche")
    files = []
    droot = os.path.join(_HERE, dataset)
    for dp, _dn, fn in sorted(os.walk(droot)):
        for f in sorted(fn):
            if f.startswith("instance_") and f.endswith(".json") and "_e50_ron" in dp:
                files.append(os.path.join(dp, f))
    man = {
        "baslangic": time.strftime("%Y-%m-%d %H:%M:%S"),
        "komut": sys.argv,
        "git_commit": _git("rev-parse", "HEAD"),
        "git_kirli_dosyalar": [l for l in _git("status", "--short").splitlines() if l.strip()],
        "islemci_baglilik": aff,
        "islemci": platform.processor() or platform.machine(),
        "makine": platform.node(),
        "mantiksal_islemci_sayisi": os.cpu_count(),
        "gurobi_surum": ".".join(str(x) for x in gurobipy.gurobi.version()),
        "gurobi_threads": 1,
        "julia_is_parcacigi": 1,
        "lkh_isci": "makine basina bir surec (uretimle ayni), hepsi ayni islemciye bagli",
        "veri_klasoru": dataset,
        "veri_sha256": {os.path.relpath(f, _HERE): _sha(f) for f in files},
    }
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    if os.path.exists(man_path):                      # resume: do NOT delete the old record, append
        old = json.load(open(man_path))
        runs = old if isinstance(old, list) else [old]
    else:
        runs = []
    runs.append(man)
    json.dump(runs, open(man_path, "w"), indent=1, ensure_ascii=False)

    # ---- resource restrictions ----
    import methods
    methods.env.setParam("Threads", 1)
    import feas_hook
    feas_hook.LOG_PATH = feas_path
    import niche_benchmark as nb

    _orig_run = subprocess.run

    def _run(cmd, *a, **k):
        if isinstance(cmd, list) and cmd and cmd[0] == nb.JULIA:
            cmd = ["1" if (x == "auto" and i > 0 and cmd[i - 1] == "-t") else x
                   for i, x in enumerate(cmd)]
        return _orig_run(cmd, *a, **k)

    subprocess.run = _run

    # ---- CPU time measurement ----
    def _log(method, inst, seed, budget, wall, cpu):
        new = not os.path.exists(cpu_path)
        with open(cpu_path, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["method", "inst", "seed", "budget", "wall_total_s", "cpu_s", "ort_cekirdek"])
            w.writerow([method, inst, seed, budget, round(wall, 1), round(cpu, 1),
                        round(cpu / wall, 3) if wall > 0 else ""])

    def _rel(p):
        return os.path.join(os.path.basename(os.path.dirname(p)), os.path.basename(p))

    _cap, _hl = nb.run_capsule, nb.run_hlbb

    def run_capsule(algo, json_path, wall, seed):
        c0, t0 = _cpu_now(), time.time()
        out = _cap(algo, json_path, wall, seed)
        _log(algo, _rel(json_path), seed, wall, time.time() - t0, _cpu_now() - c0)
        return out

    def run_hlbb(json_path, wall, seed, *a, **k):
        c0, t0 = _cpu_now(), time.time()
        out = _hl(json_path, wall, seed, *a, **k)
        _log("HLBB", _rel(json_path), seed, wall, time.time() - t0, _cpu_now() - c0)
        return out

    nb.run_capsule, nb.run_hlbb = run_capsule, run_hlbb

    print(f"### TEK CEKIRDEK: islemci {aff[0]} | Gurobi Threads=1 | Julia -t 1 | "
          f"commit {man['git_commit'][:7]} | kayit {os.path.relpath(man_path, _HERE)} ###", flush=True)
    nb.main()


if __name__ == "__main__":
    main()
