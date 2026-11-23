# -*- coding: utf-8 -*-
"""THE SINGLE EXTERNAL FEASIBILITY VERIFIER — HLBB, CP, SA, HGA and GA all pass through
the SAME checker.

ARCHITECTURE: the checker is embedded in NO algorithm. A single, method-INDEPENDENT
verifier (`feasibility.py`) audits them all -> no method certifies itself. One sentence
in the paper.

WHY IT WAS NEEDED: `feasibility.py` was wired only to scaling_test / ls_benchmark /
card_relax_benchmark. On the NICHE line (niche_benchmark, capsule_bench, ablation_run,
track_a_benchmark) no solution was checked -- those calls did not even export the
solution. CP is exactly the method where such a bug was caught
(CP_model.py:73 "inst 12: phantom +82 -> 35893 vs true 35688").

HOW THE JULIA METHODS WERE WIRED:
  SA.jl / HGA.jl / GA.jl  -> the Main_* functions also return `best_sol` (5th value).
  run_one.jl              -> prints the schedule as a `SOL <m1jobs>|<m2jobs>|...` line (1-indexed).
  this file               -> converts to 0-index and feeds the same `check_assignment`.
  The added code is OUTSIDE THE TIMED LOOP, read-only, draws no RNG -> search behavior and
  runtime are IDENTICAL. (Note: `equiv_*_test.jl` does not call Main_*, it calls LocalSearch
  directly; so equivalence does NOT cover this change -- the guarantee comes from the
  structure, not from the test.)

TESTS (which one is MEANINGFUL depends on the method's solution form):
  kapsama   (coverage)    each job exactly once                -- all
  uygunluk  (eligibility) job only on l in L_i[i]              -- all
  seq_ok    claim == makespan of the GIVEN ORDER               -- ORDERED solutions (CP, SA, HGA, GA)
  route_ok  re-route the assignment -> lkh_mk <= claim         -- all
  exact_ok  EXACT best route <= claim (impossibly low claim)   -- all, when PROVEN optimal
  readyTime r_l is counted exactly once on both sides.

  WHY seq_ok IS ABSENT FOR HLBB: the assignment returned by SPP is UNORDERED
  (spp_recombine.py, `assign[g[0]] = list(g[1])`, frozenset -> list). The claim is the cost
  of the ORDER found by LKH but the list does not carry that order -> false negative. The
  other methods deliver the schedule ORDERED.

  exact_ok SAFETY: if `exact_atsp_dfj` hits the time limit it returns its incumbent (which
  may be poor), and 1e6 if it finds no solution -> a naive `exact_mk <= claim` test raises
  FALSE ALARMS at LARGE sizes. Here it is called with `return_proven=True` and the flag is
  acted on only when OPTIMALITY IS PROVEN; otherwise 'kanitsiz' (= unproven) is written.
  At those sizes the real anchor is `route_ok`.

CARDINALITY IS NOT REPORTED: the constraint was removed from the problem (not in the paper).

Usage:
  python3 verify_all.py                                   # HLBB+CP+SA+HGA+GA, 4 sizes x inst1
  python3 verify_all.py --insts 1 2 3                     # full audit
  python3 verify_all.py --methods hlbb sa --sizes 50_10
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import time

import numpy as np

from HLBB import JobsOnMachinesDistMat
from ab_cut_bneck import _load
from exact_atsp import exact_atsp_dfj
from feasibility import check_assignment, sequence_makespan
from lbbd_optcut_try import route_per_machine
from niche_bridge import ensure_bin

_HERE = os.path.dirname(os.path.abspath(__file__))
# RELEASE ADAPTATION: can be overridden via environment variable; the default is the
# recorded path of the original runs.
JULIA = os.environ.get("HLBB_JULIA", "/home/sarp/julia_install/julia-1.7.0/bin/julia")
CODE = os.path.join(_HERE, "rolim_capsule/code")
DEPOT = os.environ.get("JULIA_DEPOT_PATH", "/home/sarp/julia_install/depot")
RUN_ONE = os.path.join(CODE, "run_one.jl")

DEF_SIZES = ["50_10", "100_15", "400_20", "800_30"]
ALL_METHODS = ["hlbb", "cp", "sa", "hga", "ga"]
JULIA_METHODS = {"sa": "SA", "hga": "HGA", "ga": "GA"}

# RESUMABILITY: every row is written to the CSV immediately; completed
# (track,size,inst,method) cells are skipped. If the run is interrupted, the same command
# resumes where it left off. The summary is produced from the WHOLE CSV -> rows from
# earlier sessions enter the report too.
CSV_PATH = os.path.join(_HERE, "results", "verify_all.csv")
CSV_COLS = ["track", "size", "inst", "method", "claimed", "lkh_mk", "exact_mk",
            "kapsama", "uygunluk", "seq_ok", "route_ok", "exact_ok", "wall"]


def load_done():
    """Completed cells + the rows needed for the summary."""
    rows = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH) as f:
            rows = list(csv.DictReader(f))
    return {(r["track"], r["size"], r["inst"], r["method"]) for r in rows}, rows


def json_path(size, inst, track):
    """SAME path rules as _load (ab_cut_bneck.py:305-317) -- so Julia gets the same instance."""
    if track in ("niche", "niche_v2"):
        root = "new_dataset_niche_v2" if track == "niche_v2" else "new_dataset_niche"
        n, m = size.split("_")
        return os.path.join(_HERE, root, f"{n}_{m}_1-99_e50_ron", f"instance_{inst}.json")
    raise SystemExit(f"bu track icin Julia koprusu yok: {track}")


# ------------------------------------------------------------------ solvers
def solve_hlbb(d, jp, wall, seed):
    """SAME call as niche_benchmark.py:108-110 + return_solution. Solution UNORDERED (SPP)."""
    from hlbb_hm import run_integrated_sr
    nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
    best, _bt, iters, assign = run_integrated_sr(
        nJob, nM, c1, c2, rt, pt, st, I_l, L_i,
        total_time_limit=wall, kmach=3, arc_k=5, seed=seed, return_solution=True)
    return float(best), assign, iters, False


def solve_cp(d, jp, wall, seed):
    """SAME call as niche_benchmark.py:118 + return_solution. Solution ORDERED (start-time)."""
    from CP_model import CP as CP_solve
    nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
    obj, _gap, assign = CP_solve(nJob, nM, c1, c2, rt, pt, st, I_l, L_i,
                                 time_limit=wall, return_solution=True)
    return float(obj), assign, -1, True


def solve_julia(algo):
    """SAME call as capsule_bench.py:38-45; additionally reads the SOL line.
    Julia is 1-indexed -> converted to Python 0-index (see bridge_test.py, verified match)."""
    def _run(d, jp, wall, seed):
        nJob, nM = d[0], d[1]
        binp = ensure_bin(jp)
        env = dict(os.environ, JULIA_DEPOT_PATH=DEPOT)
        proc = subprocess.run([JULIA, "-t", "auto", RUN_ONE, algo, os.path.abspath(binp), str(wall), str(seed)],
                              cwd=CODE, env=env, capture_output=True, text=True,
                              timeout=wall + 600)
        mr = re.search(r"^RESULT\s+\S+\s+(\d+)\s", proc.stdout, re.M)
        ms = re.search(r"^SOL\s+(.*)$", proc.stdout, re.M)
        if not mr:
            raise RuntimeError(f"{algo}: RESULT yok. stderr: {proc.stderr.strip()[-400:]}")
        if not ms:
            raise RuntimeError(f"{algo}: SOL satiri yok -- Main_{algo} cizelge donduruyor mu? "
                               f"stderr: {proc.stderr.strip()[-400:]}")
        parts = ms.group(1).split("|")
        if len(parts) != nM:
            raise RuntimeError(f"{algo}: SOL {len(parts)} makine icerdi, {nM} bekleniyordu")
        assign = [[int(t) - 1 for t in seg.split(",") if t.strip()] for seg in parts]
        return float(mr.group(1)), assign, -1, True
    return _run


SOLVERS = {"hlbb": solve_hlbb, "cp": solve_cp,
           **{k: solve_julia(v) for k, v in JULIA_METHODS.items()}}


def exact_check(assign, d, claimed, ex_tl):
    """Is the EXACT best route <= claim? Gives a verdict ONLY when optimality is PROVEN.
    Returns: (exact_mk, verdict) -- verdict in {'OK','BOZUK','kanitsiz'}
    ('BOZUK' = broken, 'kanitsiz' = unproven)."""
    nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
    tot = 0.0; all_proven = True
    for l in range(nM):
        if not assign[l]:
            continue
        dm = JobsOnMachinesDistMat(pt, st, assign[l], l)
        obj, proven = exact_atsp_dfj(dm, ex_tl, return_proven=True)
        all_proven = all_proven and proven
        tot = max(tot, float(rt[l]) + obj)
    if not all_proven:
        return tot, "kanitsiz"        # hit the TL -> no verdict possible; route_ok decides
    return tot, ("OK" if tot <= claimed + max(1.0, 0.005 * claimed) else "BOZUK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", nargs="+", default=ALL_METHODS, choices=ALL_METHODS)
    ap.add_argument("--track", default="niche_v2")
    ap.add_argument("--sizes", nargs="+", default=DEF_SIZES)
    ap.add_argument("--insts", nargs="+", default=["1"])
    ap.add_argument("--wall", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--extl", type=float, default=5.0,
                    help="makine basina EXACT-ATSP zaman limiti (sn)")
    a = ap.parse_args()

    done, _ = load_done()
    todo = [(s, i, m) for s in a.sizes for i in a.insts for m in a.methods
            if (a.track, s, i, m) not in done]
    tot = len(a.sizes) * len(a.insts) * len(a.methods)
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    new_file = not os.path.exists(CSV_PATH)
    fh = open(CSV_PATH, "a", newline="")
    wcsv = csv.writer(fh)
    if new_file:
        wcsv.writerow(CSV_COLS)

    print(f"\n### TEK DIS FEASIBILITY DENETIMI — track={a.track}  wall={a.wall}s  exact_tl={a.extl}s ###")
    print(f"yontemler: {', '.join(m.upper() for m in a.methods)}   "
          f"denetleyici: feasibility.py (hepsi icin AYNI)")
    print(f"{tot} kosu: {tot - len(todo)} zaten var (atlanacak), {len(todo)} kalan   "
          f"-> {os.path.relpath(CSV_PATH)}\n", flush=True)
    hdr = (f"{'yontem':>6} {'boyut':>8} {'i':>2} {'iddia':>9} {'lkh_mk':>9} {'exact_mk':>9} "
           f"{'kapsama':>8} {'uygunluk':>9} {'seq_ok':>7} {'route_ok':>9} {'exact_ok':>9}")
    print(hdr); print("-" * len(hdr), flush=True)

    bad = []; err = []
    t_run = time.time(); k = 0
    for size in a.sizes:
        for inst in a.insts:
            if not any(s == size and i == inst for (s, i, _m) in todo):
                continue                       # all methods of this cell already done
            d = _load(size, inst, a.track)
            jp = json_path(size, inst, a.track)
            nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
            for meth in a.methods:
                if (a.track, size, inst, meth) in done:
                    continue
                k += 1
                t0 = time.time()
                try:
                    claimed, assign, iters, ordered = SOLVERS[meth](d, jp, a.wall, a.seed)
                except Exception as e:
                    print(f"{meth.upper():>6} {size:>8} {inst:>2}  *** HATA: {e} ***", flush=True)
                    err.append((meth, size, inst, str(e)))
                    continue
                if assign is None:
                    print(f"{meth.upper():>6} {size:>8} {inst:>2}  *** COZUM YOK (atlandi) ***", flush=True)
                    continue

                r = check_assignment(assign, d, claimed, ex_tl=0.01)   # constraints; exact apart
                V = [v for v in r["violations"] if not v.startswith("KARDINALITE")]
                kap = [v for v in V if v.startswith("KAPSAMA")]
                uyg = [v for v in V if v.startswith("UYGUNLUK")]

                # For ORDERED solutions: is the claim the true makespan of the GIVEN order?
                seq_ok = None
                if ordered:
                    seq_mk = max((sequence_makespan(assign[l], l, rt, pt, st) for l in range(nM)),
                                 default=0.0)
                    seq_ok = abs(seq_mk - claimed) <= max(1.0, 0.005 * claimed)

                # re-routing: the error signal is ONE-SIDED (lkh_mk > claim = impossibly low claim)
                lkh_mk = max(route_per_machine(assign, rt, pt, st, 1))
                route_ok = lkh_mk <= claimed + max(1.0, 0.005 * claimed)

                ex_mk, ex_v = exact_check(assign, d, claimed, a.extl)

                s_kap = "OK" if not kap else f"{len(kap)} IHLAL"
                s_uyg = "OK" if not uyg else f"{len(uyg)} IHLAL"
                s_seq = "n/a" if seq_ok is None else ("OK" if seq_ok else "SAPMA")
                s_rt = "OK" if route_ok else "BOZUK"
                wall = round(time.time() - t0, 1)
                wcsv.writerow([a.track, size, inst, meth, claimed, round(lkh_mk, 1),
                               round(ex_mk, 1), s_kap, s_uyg, s_seq, s_rt, ex_v, wall])
                fh.flush()                      # write IMMEDIATELY: survive an interrupted run
                el = time.time() - t_run
                eta = el / k * (len(todo) - k)
                print(f"{meth.upper():>6} {size:>8} {inst:>2} {claimed:9.1f} {lkh_mk:9.1f} "
                      f"{ex_mk:9.1f} {s_kap:>8} {s_uyg:>9} {s_seq:>7} {s_rt:>9} {ex_v:>9}"
                      f"   [{k}/{len(todo)}, {wall:.0f}s"
                      + (f", {iters} iter" if iters >= 0 else "")
                      + f", ~{eta/3600:.1f}sa kaldi]", flush=True)
                if kap or uyg or not route_ok or ex_v == "BOZUK" or seq_ok is False:
                    bad.append((meth, size, inst, V[:4], lkh_mk, claimed, seq_ok, ex_v))

    fh.close()

    # SUMMARY FROM THE WHOLE CSV (include rows from earlier sessions too)
    _, rows = load_done()
    scope = [r for r in rows if r["track"] == a.track and r["size"] in a.sizes
             and r["inst"] in a.insts and r["method"] in a.methods]
    csv_bad = [r for r in scope if r["kapsama"] != "OK" or r["uygunluk"] != "OK"
               or r["route_ok"] != "OK" or r["exact_ok"] == "BOZUK" or r["seq_ok"] == "SAPMA"]
    unproven = [r for r in scope if r["exact_ok"] == "kanitsiz"]
    print(f"\n--- CSV toplami: {len(scope)} kosu denetlendi "
          f"({len(csv_bad)} sorunlu, {len(unproven)} satirda exact kanitsiz) ---")
    for r in csv_bad:
        print(f"  ! {r['method'].upper():>4} {r['size']:>8} i{r['inst']}: "
              f"kapsama={r['kapsama']} uygunluk={r['uygunluk']} seq={r['seq_ok']} "
              f"route={r['route_ok']} exact={r['exact_ok']}")

    print("\n" + "=" * 95)
    if not csv_bad and not err:
        print("SONUC: TUM YONTEMLERIN COZUMLERI FIZIBIL ve iddia edilen makespan'ler GERCEK.")
        print("       seq_ok=n/a  -> HLBB (SPP atamasi sirasiz; o test bu yontemde anlamsiz)")
        print("       exact_ok=kanitsiz -> DFJ zaman limitine takildi, HUKUM YOK; o satirda")
        print("                            dayanak route_ok'tur (hata degildir).")
    else:
        if csv_bad:
            print(f"{len(csv_bad)} kosuda SORUN VAR -- bu sonuclar bu haliyle raporlanamaz.")
            for meth, size, inst, V, lm, cl, sq, ev in bad:   # violation texts (this session)
                print(f"  {meth.upper()} {size} i{inst}: iddia={cl} lkh={lm:.1f} seq_ok={sq} exact={ev}")
                for v in V:
                    print(f"      - {v}")
        if err:
            print(f"\n{len(err)} kosu HATA verdi (denetim yapilamadi):")
            for meth, size, inst, e in err:
                print(f"  {meth.upper()} {size} i{inst}: {e}")
    print("=" * 95, flush=True)
    return 1 if (csv_bad or err) else 0


if __name__ == "__main__":
    sys.exit(main())
