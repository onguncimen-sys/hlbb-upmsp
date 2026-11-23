# -*- coding: utf-8 -*-
"""RESERVE FORMULA DIAGNOSIS — how far off R is, and how it changes with size.

QUESTION. The loop stops at T-R to leave room for SPP, computing

    R = rt_ema * spp_cap * 1.2 + _MIP_PAY(12) + 2,   lower 10, upper 0.30*T

This formula has THREE known weaknesses, and all three accumulate in the SAME direction
(excess reserve):
  Z1  it always assumes 250 even when the pool is smaller than `spp_cap`
  Z2  it does not know SPP's route_cache (harvested solutions are neighbors of the
      incumbent -> most of their machines are already measured, never go to LKH)
  Z3  the 12 and 2 are CONSTANTS, not measured (paper §3.4 says "inputs are measured
      in-run"; only ONE of the three terms is measured)

Result: 10-21 seconds of the 200s contract stay idle (indirect measurement). This run
turns that indirect inference into a DIRECT measurement.

MEASURED. In each run (all from hlbb_hm.SUPPLY / spp_recombine.LAST, none estimated):
    reserve                          the R set aside by the formula
    spp_route_s / spp_build_s / spp_mip_s   ACTUAL times of the SPP phase
    spp_n_uniq / spp_n_routed        distinct pool and assignments actually routed
    route_s / loop_s                 routing share in the loop (the 0.5%/2.7% of paper §3.3)
    tl_req / tl_eff                  spp_tl requested vs what is ACTUALLY left for the MIP
    mip_st / mip_gap                 did the MIP PROVE optimality (paper §3.4 "exactly")
Derived: DEVIATION = reserve - (spp_route_s + spp_build_s + spp_mip_s)

⭐ CALLS THE PRODUCTION CODE DIRECTLY (hlbb_hm.run_integrated_sr). No copied rig, no
fidelity question arises. NO ALGORITHM FLAG IS CHANGED -- the single arm = production.

DATA. TRACK B (new_dataset_niche_v2) -- THE reported test set itself, eight sizes x
five instances x three runs, cell structure IDENTICAL to the benchmark
(results/niche_bench_v3.csv).
Why NOT a separate training set: this run SELECTS no parameter, it measures the existing
algorithm; the "tuned on test" objection does not arise. In return, Track B gives a free
REGRESSION CHECK: does the instrumented version still reproduce the known makespans
(report section 6).

ROBUSTNESS
  - each run is a SEPARATE PROCESS (no _ARC_CACHE memory leak + Gurobi/LKH state build-up)
  - resumable: cells already in the CSV are not rerun
  - every solution passes through the shared checker

USAGE:
    python3 _reserve_probe.py gen        # generate missing sizes (once, ~1 min)
    python3 _reserve_probe.py plan       # how many runs, how long (no Gurobi needed)
    python3 _reserve_probe.py run        # the actual run (resumable)
    python3 _reserve_probe.py report     # analysis
"""
import csv
import glob
import os
import statistics as st
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(_HERE, "new_dataset_niche_v2")   # TRACK B — the reported test set
CSV_PATH = os.path.join(_HERE, "results", "reserve.csv")
BUDGET = 200
SIZES = [(50, 10), (100, 15), (150, 15), (200, 20), (250, 20), (400, 20), (640, 25), (800, 30)]
INSTS = ["1", "2", "3", "4", "5"]
REPS = 3                          # cell structure IDENTICAL to the benchmark (seed 0/1/2)
# ⚠️ `seed` is DEAD in production: inside hlbb_hm it only reaches the ils(...) call, and
# ILS is off. So 0/1/2 do not give different SEARCHES; the variance comes from the
# master's wall-clock cap (run-to-run variation; 100_20: 77/79/80/78). Still, the values
# the benchmark passed are passed unchanged -> identical cell structure, 1:1 comparison.

COLS = ["size", "inst", "rep", "makespan", "iters", "total_s", "feas",
        "reserve", "spp_route_s", "spp_build_s", "spp_mip_s", "spp_n_uniq", "spp_n_routed",
        "route_s", "loop_s", "tl_req", "tl_eff", "mip_st", "mip_gap",
        "pool_n", "pool_distinct", "harvest"]
SUP = COLS[7:]                    # fields from SUPPLY/LAST; SAME order on the RESULT line


def _clean_lkh_scratch():
    """Empty the LKH scratch directory. BEFORE EVERY RUN, in the main process (no worker).
    ⛔ MANDATORY -- MEASURED BIAS: `getCost` calls glob.glob on every routing, and glob is
    O(N) in directory size (0 files 0.31 ms -> 9000 files 3.55 ms). If the directory grows
    monotonically across runs, LATER runs always work in a slower environment; the signal
    we seek (reserve deviation) is on the order of seconds, and this bias has the same
    magnitude. Recipe and measurement: sensitivity_run._clean_lkh_scratch (same procedure).
    ⚠️ If another suite runs in parallel, this also deletes its live files."""
    n = 0
    for pat in ("*.atsp", "*.par", "*.tour", "*.cand"):
        for f in glob.glob(os.path.join(_HERE, "LKH-3.0.7", "ATSP", pat)):
            try:
                os.remove(f); n += 1
            except OSError:
                pass
    return n


def _dirname(n, m):
    return os.path.join(DATA_ROOT, f"{n}_{m}_1-99_e50_ron")


def _load(size, inst):
    n, m = size.split("_")
    jf = os.path.join(_dirname(int(n), int(m)), f"instance_{inst}.json")
    if not os.path.exists(jf):
        raise SystemExit(f"EKSIK: {jf}")
    from readproblem import readproblem
    return readproblem(jf, consider_compatibility=True, consider_workload=True)


# =============================================================================== worker
def worker(size, inst, budget, seed=0):
    import hlbb_hm as HM
    import feas_hook
    from feasibility import verify_solution                              # noqa: F401
    d = _load(size, inst)
    nJob, nM, c1, c2, rt, pt, stp, mx, I_l, L_i, es = d
    t0 = time.time()
    best, best_time, iters, assign = HM.run_integrated_sr(
        nJob, nM, c1, c2, rt, pt, stp, I_l, L_i,
        total_time_limit=budget, seed=seed, return_solution=True, verbose=False)
    total_s = time.time() - t0
    import spp_recombine as SR
    ordered = None
    try:
        from tour_capture import sequence_solution
        if assign:
            ordered = sequence_solution(assign, pt, stp)
    except Exception as e:
        print(f"    [tour] sira cikarilamadi: {e}", flush=True)
    ok = feas_hook.check("reserve", "prod", f"trackB/{size}/i{inst}", seed,
                         ordered or assign, d, float(best), ordered=ordered is not None)
    vals = {"tl_req": SR.LAST.get("tl_req"), "tl_eff": SR.LAST.get("tl_eff")}
    for k in SUP:
        if k not in vals:
            vals[k] = HM.SUPPLY.get(k)
    print("RESULT " + "|".join(str(x) for x in
                               [best, iters, round(total_s, 1),
                                {True: 1, False: 0, None: -1}[ok]] + [vals[k] for k in SUP]))


def _spawn(size, inst, budget, seed=0):
    cmd = [sys.executable, os.path.abspath(__file__), "worker", size, inst, str(budget),
           str(seed)]
    try:
        p = subprocess.run(cmd, cwd=_HERE, capture_output=True, text=True, timeout=budget + 900)
    except subprocess.TimeoutExpired:
        return None
    for line in p.stdout.splitlines():
        if line.startswith("RESULT "):
            f = line[7:].split("|")
            g = lambda s: None if s in ("None", "") else float(s)      # noqa: E731
            out = dict(best=float(f[0]), iters=int(f[1]), total_s=float(f[2]), feas=int(f[3]))
            for q, k in enumerate(SUP):
                out[k] = g(f[4 + q]) if len(f) > 4 + q else None
            return out
    print(p.stdout[-1500:] or p.stderr[-1500:], flush=True)
    return None


# =============================================================================== plan
def _jobs(reps):
    got = set()
    if os.path.exists(CSV_PATH):
        for r in csv.DictReader(open(CSV_PATH)):
            got.add((r["size"], r["inst"], r["rep"]))
    jobs = [(f"{n}_{m}", i, str(r)) for (n, m) in SIZES for i in INSTS
            for r in range(1, reps + 1) if (f"{n}_{m}", i, str(r)) not in got]
    return jobs, len(SIZES) * len(INSTS) * reps


def cmd_plan():
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else REPS
    jobs, tot = _jobs(reps)
    eta = len(jobs) * (BUDGET + 25) / 3600.0           # +25s: loading/check/process overhead
    print(f"\n### REZERV TESHISI — {len(SIZES)} boyut x {len(INSTS)} inst x {reps} tekrar "
          f"= {tot} kosu x {BUDGET}s ###")
    print(f"### tamamlanan {tot - len(jobs)}, kalan {len(jobs)}  ->  ~{eta:.1f} saat ###")
    eksik = [f"{n}x{m}" for (n, m) in SIZES if not os.path.isdir(_dirname(n, m))]
    if eksik:
        print(f"\n⛔ VERI EKSIK: {', '.join(eksik)}  ->  new_dataset_niche_v2 eksik")
        return False
    print(f"### -> {os.path.relpath(CSV_PATH)}   (tek kol = URETIM, bayrak degisikligi YOK) ###\n")
    return True


# =============================================================================== run
def cmd_run():
    if not cmd_plan():
        return
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else REPS
    jobs, _ = _jobs(reps)
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    new = not os.path.exists(CSV_PATH)
    fh = open(CSV_PATH, "a", newline="")
    w = csv.writer(fh)
    if new:
        w.writerow(COLS)
    t0 = time.time()
    for k, (s, i, r) in enumerate(jobs, 1):
        _clean_lkh_scratch()            # every run starts in the SAME environment (see note)
        res = _spawn(s, i, BUDGET, seed=int(r) - 1)      # rep 1/2/3 -> seed 0/1/2
        if res is None:
            print(f"[{k}/{len(jobs)}] {s} i{i} r{r}  *** BASARISIZ ***", flush=True)
            continue
        row = [s, i, r, res["best"], res["iters"], res["total_s"], res["feas"]] \
            + [res.get(c) for c in SUP]
        assert len(row) == len(COLS), f"CSV hizasi bozuk: {len(row)} != {len(COLS)}"
        w.writerow(row); fh.flush()
        harc = sum(res.get(c) or 0.0 for c in ("spp_route_s", "spp_build_s", "spp_mip_s"))
        sas = (res.get("reserve") or 0.0) - harc
        flag = "" if res["feas"] == 1 else ("  *** IHLAL ***" if res["feas"] == 0
                                            else "  (denetlenemedi)")
        el = time.time() - t0
        print(f"[{k}/{len(jobs)}] {s:>7} i{i} r{r}  mk={res['best']:7.1f} "
              f"R={res.get('reserve')}  harcanan={harc:5.2f}  SASMA={sas:+6.2f}s  "
              f"rotalanan={res.get('spp_n_routed')}/{res.get('spp_n_uniq')}  "
              f"tot={res['total_s']:.0f}s{flag}"
              f"  [{el/3600:.1f}sa gecti, ~{el/k*(len(jobs)-k)/3600:.1f}sa kaldi]", flush=True)
    fh.close()
    print("\nkosu bitti — `python3 _reserve_probe.py report`", flush=True)


# =============================================================================== report
def _f(r, k):
    v = r.get(k)
    return None if v in (None, "", "None") else float(v)


def cmd_report():
    if not os.path.exists(CSV_PATH):
        print("sonuc yok"); return
    R = list(csv.DictReader(open(CSV_PATH)))
    sizes = sorted({r["size"] for r in R}, key=lambda s: int(s.split("_")[0]))
    ih = sum(1 for r in R if r["feas"] == "0")
    print(f"\n{len(R)} kosu | fizibilite ihlali: {ih}"
          + ("  ⛔ SONUCLARI KULLANMA" if ih else "  (temiz)"))

    print("\n--- 1) REZERV: formulun ayirdigi vs GERCEKLESEN ---")
    print(f"{'boyut':>8} {'R':>7} {'rotala':>7} {'model':>6} {'mip':>6} {'harcanan':>9}"
          f" {'SASMA':>8} {'bos butce':>10}")
    for s in sizes:
        rs = [r for r in R if r["size"] == s]
        g = lambda k: st.mean([_f(r, k) or 0.0 for r in rs])            # noqa: E731
        harc = g("spp_route_s") + g("spp_build_s") + g("spp_mip_s")
        print(f"{s:>8} {g('reserve'):7.1f} {g('spp_route_s'):7.2f} {g('spp_build_s'):6.2f}"
              f" {g('spp_mip_s'):6.2f} {harc:9.2f} {g('reserve')-harc:+8.2f}"
              f" {BUDGET-g('total_s'):10.1f}")

    print("\n--- 2) Z1: formul 250 varsayiyor, gercekte kac atama rotalaniyor ---")
    print(f"{'boyut':>8} {'ayrik havuz':>12} {'rotalanan':>10} {'formul':>7} {'fazla kat':>10}")
    for s in sizes:
        rs = [r for r in R if r["size"] == s]
        u = st.mean([_f(r, "spp_n_uniq") or 0.0 for r in rs])
        n = st.mean([_f(r, "spp_n_routed") or 0.0 for r in rs])
        print(f"{s:>8} {u:12.0f} {n:10.0f} {250:7d} {250/max(n,1):10.2f}x")

    print("\n--- 3) Z2: rotalama tahmini vs gerceklesen (onbellegin etkisi) ---")
    print(f"{'boyut':>8} {'R-14 = tahmin':>14} {'gerceklesen':>12} {'oran':>7}")
    for s in sizes:
        rs = [r for r in R if r["size"] == s]
        tah = st.mean([(_f(r, "reserve") or 0.0) - 14.0 for r in rs])
        ger = st.mean([_f(r, "spp_route_s") or 0.0 for r in rs])
        print(f"{s:>8} {tah:14.2f} {ger:12.2f} {ger/max(tah,1e-9):7.2f}")

    print("\n--- 4) paper §3.3: rotalamanin dongudeki payi ---")
    for s in sizes:
        rs = [r for r in R if r["size"] == s]
        p = st.mean([100.0 * (_f(r, "route_s") or 0.0) / max(_f(r, "loop_s") or 1.0, 1e-9)
                     for r in rs])
        print(f"  {s:>8}  {p:5.2f}%")

    print("\n--- 5) paper §3.4 'exactly': MIP optimali kanitladi mi ---")
    for s in sizes:
        rs = [r for r in R if r["size"] == s]
        stl = [_f(r, "mip_st") for r in rs if _f(r, "mip_st") is not None]
        opt = sum(1 for x in stl if int(x) == 2)
        gp = [_f(r, "mip_gap") for r in rs if _f(r, "mip_gap") is not None]
        tq = st.mean([_f(r, "tl_req") or 0.0 for r in rs])
        te = st.mean([_f(r, "tl_eff") or 0.0 for r in rs])
        print(f"  {s:>8}  OPTIMAL {opt}/{len(stl)}   ort gap {st.mean(gp) if gp else float('nan'):.4f}"
              f"   spp_tl istenen {tq:.1f}s -> etkin {te:.1f}s")

    print("\n--- 6) REGRESYON: olcum eklenmis surum benchmark'i yeniden uretiyor mu ---")
    bpath = os.path.join(_HERE, "results", "niche_bench_v3.csv")
    if not os.path.exists(bpath):
        print("  niche_bench_v3.csv yok, kiyas atlandi"); return
    B = {}
    for r in csv.DictReader(open(bpath)):
        if r["method"] != "HLBB":
            continue
        B.setdefault((r["size"].replace("x", "_"), r["rep"]), []).append(float(r["makespan"]))
    print(f"{'boyut':>8} {'benchmark':>10} {'bu kosu':>9} {'fark':>8} {'fark %':>8}")
    tum = []
    for s in sizes:
        rs = [r for r in R if r["size"] == s]
        pairs = []
        for i in sorted({r["inst"] for r in rs}):
            eski = B.get((s, i))
            yeni = [_f(r, "makespan") for r in rs if r["inst"] == i]
            if eski and yeni:
                pairs.append((st.mean(eski), st.mean(yeni)))
        if not pairs:
            continue
        e, y = st.mean([a for a, _ in pairs]), st.mean([b for _, b in pairs])
        d = [100.0 * (b - a) / a for a, b in pairs]
        tum += d
        print(f"{s:>8} {e:10.1f} {y:9.1f} {y-e:+8.1f} {st.mean(d):+8.2f}")
    if tum:
        se = st.stdev(tum) / (len(tum) ** 0.5) if len(tum) > 1 else 0.0
        print(f"{'GENEL':>8} {'':>10} {'':>9} {'':>8} {st.mean(tum):+8.2f} +- {se:.2f} (SE)")
        print("  yorum: algoritma DEGISMEDI; fark run-to-run oynamadan (~%1.6) buyukse"
              "\n         olcum eklemesi bir seyi bozmus demektir -> DUR ve incele.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "worker":
        worker(sys.argv[2], sys.argv[3], int(sys.argv[4]),
               seed=int(sys.argv[5]) if len(sys.argv) > 5 else 0)
    elif cmd == "plan":
        cmd_plan()
    elif cmd == "run":
        cmd_run()
    elif cmd == "report":
        cmd_report()
    else:
        sys.exit(__doc__)
