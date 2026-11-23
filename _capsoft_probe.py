# -*- coding: utf-8 -*-
"""SOFT CAP (cap_soft) A/B — does converting idle budget into COLUMNS pay off?

QUESTION. results/reserve.csv (120 runs) showed two things at once:
  (a) SPP routes only 22-54% of the pool (`spp_cap=250` truncates),
  (b) on average 14.7 s of the 200 s contract is NEVER USED (the reserve over-allocates).
In SIX of the eight sizes, the ENTIRE discarded pool could have been routed within the
idle time.

ARM. `spp_cap_soft=True`: the cap becomes an ORDERING, not a TRUNCATION.
  - the first 250 elements are IDENTICAL to before (equally spaced sample; verified by
    a unit test)
  - the rest are appended AFTER them; routing already stops at `deadline - 12`
  - `_cap_eff` (the RESERVE base) STAYS at 250 -> the loop does not shorten, iteration
    count unchanged
  => the worst case is TODAY'S behaviour; with spare time, extra columns get priced.

⚠️ WHY `cap400` DID NOT ANSWER THIS QUESTION: there `spp_cap` was both the routing cap
and the RESERVE base; 250->400 also grew the reserve and STOLE from the loop (400_20:
iter 51.5->47.2, idle time 20.8->37.9 s). So the extra columns were paid for out of the
loop. This arm BREAKS that link.

RISK. The MIP grows (a column set of ~900 assignments instead of 250) and may choke.
The harm is BOUNDED: the SPP result is accepted only if BETTER than the incumbent and
the loop is unaffected -> the worst case is "SPP contributes no more than today".
The `mip_st`/`mip_gap`/`spp_mip_s` columns show choking DIRECTLY, no guessing.

DESIGN
  - PAIRED and INTERLEAVED: in each (size, instance, repeat) cell `prod` then `capsoft`
    run BACK TO BACK -> environment drift affects both arms EQUALLY.
  - Track B data, benchmark cell structure (seed = repeat-1).
  - Calls the production code DIRECTLY (hlbb_hm.run_integrated_sr); no copied test bench.
  - Each run is a separate process, every solution passes the shared checker, resumable.

USAGE (the USER starts the run):
    python3 _capsoft_probe.py plan
    python3 _capsoft_probe.py run
    python3 _capsoft_probe.py report
"""
import csv
import glob
import math
import os
import statistics as st
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(_HERE, "new_dataset_niche_v2")
CSV_PATH = os.path.join(_HERE, "results", "capsoft.csv")
BUDGET = 200
SIZES = [(50, 10), (100, 15), (150, 15), (200, 20), (250, 20), (400, 20), (640, 25), (800, 30)]
INSTS = ["1", "2", "3"]
REPS = 3
ARMS = {"prod": {}, "capsoft": {"spp_cap_soft": True}}     # a SINGLE change from production

COLS = ["size", "inst", "rep", "arm", "makespan", "iters", "total_s", "feas",
        "reserve", "spp_route_s", "spp_build_s", "spp_mip_s", "spp_n_uniq", "spp_n_routed",
        "route_s", "loop_s", "tl_req", "tl_eff", "mip_st", "mip_gap",
        "pool_n", "pool_distinct", "harvest"]
SUP = COLS[8:]


def _clean_lkh_scratch():
    """Empty the LKH scratch directory (a measured bias; same routine as in sensitivity_run)."""
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
def worker(size, inst, arm, budget, seed=0):
    import hlbb_hm as HM
    import feas_hook
    d = _load(size, inst)
    nJob, nM, c1, c2, rt, pt, stp, mx, I_l, L_i, es = d
    t0 = time.time()
    best, best_time, iters, assign = HM.run_integrated_sr(
        nJob, nM, c1, c2, rt, pt, stp, I_l, L_i, total_time_limit=budget, seed=seed,
        return_solution=True, verbose=False, **ARMS[arm])
    total_s = time.time() - t0
    import spp_recombine as SR
    ordered = None
    try:
        from tour_capture import sequence_solution
        if assign:
            ordered = sequence_solution(assign, pt, stp)
    except Exception as e:
        print(f"    [tour] sira cikarilamadi: {e}", flush=True)
    ok = feas_hook.check("capsoft", arm, f"trackB/{size}/i{inst}", seed,
                         ordered or assign, d, float(best), ordered=ordered is not None)
    vals = {"tl_req": SR.LAST.get("tl_req"), "tl_eff": SR.LAST.get("tl_eff")}
    for k in SUP:
        if k not in vals:
            vals[k] = HM.SUPPLY.get(k)
    print("RESULT " + "|".join(str(x) for x in
                               [best, iters, round(total_s, 1),
                                {True: 1, False: 0, None: -1}[ok]] + [vals[k] for k in SUP]))


def _spawn(size, inst, arm, budget, seed=0):
    cmd = [sys.executable, os.path.abspath(__file__), "worker", size, inst, arm,
           str(budget), str(seed)]
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
    print((p.stdout or p.stderr)[-1500:], flush=True)
    return None


# =============================================================================== plan
def _jobs(reps):
    got = set()
    if os.path.exists(CSV_PATH):
        for r in csv.DictReader(open(CSV_PATH)):
            got.add((r["size"], r["inst"], r["rep"], r["arm"]))
    # INTERLEAVED: per cell first prod then capsoft (environment drift hits both arms EQUALLY)
    jobs = []
    for (n, m) in SIZES:
        for i in INSTS:
            for r in range(1, reps + 1):
                for a in ARMS:
                    if (f"{n}_{m}", i, str(r), a) not in got:
                        jobs.append((f"{n}_{m}", i, str(r), a))
    return jobs, len(SIZES) * len(INSTS) * reps * len(ARMS)


def cmd_plan():
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else REPS
    jobs, tot = _jobs(reps)
    eta = len(jobs) * (BUDGET + 25) / 3600.0
    print(f"\n### YUMUSAK KAPAK A/B — {len(ARMS)} kol x {len(SIZES)} boyut x {len(INSTS)} inst "
          f"x {reps} tekrar = {tot} kosu x {BUDGET}s ###")
    print(f"### tamamlanan {tot - len(jobs)}, kalan {len(jobs)}  ->  ~{eta:.1f} saat ###")
    eksik = [f"{n}x{m}" for (n, m) in SIZES if not os.path.isdir(_dirname(n, m))]
    if eksik:
        print(f"\n⛔ VERI EKSIK: {', '.join(eksik)}")
        return False
    print(f"### -> {os.path.relpath(CSV_PATH)}   (esli + ic ice; rezerv DEGISMEZ) ###\n")
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
    for k, (s, i, r, a) in enumerate(jobs, 1):
        _clean_lkh_scratch()
        res = _spawn(s, i, a, BUDGET, seed=int(r) - 1)
        if res is None:
            print(f"[{k}/{len(jobs)}] {s} i{i} r{r} {a:>8}  *** BASARISIZ ***", flush=True)
            continue
        row = [s, i, r, a, res["best"], res["iters"], res["total_s"], res["feas"]] \
            + [res.get(c) for c in SUP]
        assert len(row) == len(COLS), f"CSV hizasi bozuk: {len(row)} != {len(COLS)}"
        w.writerow(row); fh.flush()
        flag = "" if res["feas"] == 1 else ("  *** IHLAL ***" if res["feas"] == 0
                                            else "  (denetlenemedi)")
        el = time.time() - t0
        print(f"[{k}/{len(jobs)}] {s:>7} i{i} r{r} {a:>8}  mk={res['best']:7.1f} "
              f"iter={res['iters']:3d} rotalanan={res.get('spp_n_routed')}/{res.get('spp_n_uniq')} "
              f"mip={res.get('spp_mip_s')}s st={res.get('mip_st')} tot={res['total_s']:.0f}s{flag}"
              f"  [{el/3600:.1f}sa gecti, ~{el/k*(len(jobs)-k)/3600:.1f}sa kaldi]", flush=True)
    fh.close()
    print("\nkosu bitti — `python3 _capsoft_probe.py report`", flush=True)


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
    print(f"\n{len(R)} kosu | feas!=1: {ih}"
          + ("  (route_ok artigi olabilir -- feasibility_log'a bak)" if ih else "  (temiz)"))

    D = {}
    for r in R:
        D[(r["size"], r["inst"], r["rep"], r["arm"])] = r

    print("\n--- 1) KALITE: capsoft vs prod (esli, hucre basina) ---")
    print(f"{'boyut':>8} {'prod':>8} {'capsoft':>8} {'dRPD%':>8} {'+-SE':>6} {'W/T/L':>9}")
    allr = []
    for s in sizes:
        d = []
        wtl = [0, 0, 0]
        for i in INSTS:
            for rp in [str(x) for x in range(1, REPS + 1)]:
                a, b = D.get((s, i, rp, "prod")), D.get((s, i, rp, "capsoft"))
                if not (a and b):
                    continue
                pa, pb = _f(a, "makespan"), _f(b, "makespan")
                d.append(100.0 * (pb - pa) / pa)
                wtl[0 if pb < pa else (1 if pb == pa else 2)] += 1
        if not d:
            continue
        allr += d
        se = st.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else 0.0
        g = lambda arm, k: st.mean([_f(D[(s, i, rp, arm)], k)                      # noqa: E731
                                    for i in INSTS for rp in [str(x) for x in range(1, REPS+1)]
                                    if (s, i, rp, arm) in D])
        print(f"{s:>8} {g('prod','makespan'):8.1f} {g('capsoft','makespan'):8.1f} "
              f"{st.mean(d):+8.2f} {se:6.2f} {wtl[0]:>3}/{wtl[1]}/{wtl[2]}")
    if allr:
        se = st.stdev(allr) / math.sqrt(len(allr))
        print(f"{'GENEL':>8} {'':>8} {'':>8} {st.mean(allr):+8.2f} {se:6.2f}   n={len(allr)}"
              f"   2SE gecti mi: {abs(st.mean(allr)) > 2*se}")

    print("\n--- 2) MEKANIZMA: gercekten daha cok sutun fiyatlandi mi ---")
    print(f"{'boyut':>8} {'ayrik':>7} | {'prod rotalanan':>14} {'capsoft rotalanan':>17} {'kat':>5}")
    for s in sizes:
        g = lambda arm, k: st.mean([_f(D[(s, i, rp, arm)], k)                      # noqa: E731
                                    for i in INSTS for rp in [str(x) for x in range(1, REPS+1)]
                                    if (s, i, rp, arm) in D])
        try:
            a, b = g("prod", "spp_n_routed"), g("capsoft", "spp_n_routed")
            print(f"{s:>8} {g('prod','spp_n_uniq'):7.0f} | {a:14.0f} {b:17.0f} {b/max(a,1):5.2f}x")
        except Exception:
            continue

    print("\n--- 3) MIP BOGULDU MU (asil risk) ---")
    print(f"{'boyut':>8} | {'prod OPT':>9} {'gap%':>6} {'mip_s':>6} | {'capsoft OPT':>12} {'gap%':>6} {'mip_s':>6}")
    for s in sizes:
        out = [f"{s:>8} |"]
        for arm in ("prod", "capsoft"):
            rs = [D[(s, i, rp, arm)] for i in INSTS for rp in [str(x) for x in range(1, REPS+1)]
                  if (s, i, rp, arm) in D]
            stl = [_f(r, "mip_st") for r in rs if _f(r, "mip_st") is not None]
            opt = sum(1 for x in stl if int(x) == 2)
            gp = [_f(r, "mip_gap") or 0.0 for r in rs]
            ms = [_f(r, "spp_mip_s") or 0.0 for r in rs]
            out.append(f" {opt:>4}/{len(stl):<4} {100*st.mean(gp) if gp else 0:6.2f} "
                       f"{st.mean(ms) if ms else 0:6.2f} |")
        print("".join(out))

    print("\n--- 4) R BAGLIYOR MU: rotalama havuzu BITIRDI mi, SAAT mi kesti ---")
    print(f"{'boyut':>8} | {'capsoft: bitirdi':>17} {'saat kesti':>11} | {'rotalanan/ayrik':>16}"
          f" {'route_s':>8} {'R':>6}")
    bit_t = kes_t = 0
    for s in sizes:
        rs = [D[(s, i, rp, "capsoft")] for i in INSTS for rp in [str(x) for x in range(1, REPS+1)]
              if (s, i, rp, "capsoft") in D]
        if not rs:
            continue
        bit = sum(1 for r in rs if (_f(r, "spp_n_routed") or 0) >= (_f(r, "spp_n_uniq") or 0) - 0.5)
        bit_t += bit; kes_t += len(rs) - bit
        nr = st.mean([_f(r, "spp_n_routed") or 0 for r in rs])
        nu = st.mean([_f(r, "spp_n_uniq") or 0 for r in rs])
        print(f"{s:>8} | {bit:>17}/{len(rs):<3} {len(rs)-bit:>11} | {nr:7.0f}/{nu:<8.0f}"
              f" {st.mean([_f(r,'spp_route_s') or 0 for r in rs]):8.2f}"
              f" {st.mean([_f(r,'reserve') or 0 for r in rs]):6.1f}")
    print(f"{'TOPLAM':>8} | {bit_t:>17} {kes_t:>11}")
    print("  yorum: 'bitirdi' baskinsa R hala comert -> R sorusu KAPANIR."
          "\n         'saat kesti' baskinsa rotalama artik saat-bagimli -> R sorusu ACILIR"
          "\n         (daha buyuk R daha cok sutun alir, ama donguden calar).")

    print("\n--- 5) DONGU KORUNDU MU (kisalmamali) ---")
    print(f"{'boyut':>8} {'prod iter':>10} {'capsoft iter':>13} {'prod R':>8} {'capsoft R':>10} {'bos prod':>9} {'bos cs':>7}")
    for s in sizes:
        g = lambda arm, k: st.mean([_f(D[(s, i, rp, arm)], k)                      # noqa: E731
                                    for i in INSTS for rp in [str(x) for x in range(1, REPS+1)]
                                    if (s, i, rp, arm) in D])
        try:
            print(f"{s:>8} {g('prod','iters'):10.1f} {g('capsoft','iters'):13.1f} "
                  f"{g('prod','reserve'):8.1f} {g('capsoft','reserve'):10.1f} "
                  f"{200-g('prod','total_s'):9.1f} {200-g('capsoft','total_s'):7.1f}")
        except Exception:
            continue


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "worker":
        worker(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]),
               seed=int(sys.argv[6]) if len(sys.argv) > 6 else 0)
    elif cmd == "plan":
        cmd_plan()
    elif cmd == "run":
        cmd_run()
    elif cmd == "report":
        cmd_report()
    else:
        sys.exit(__doc__)
