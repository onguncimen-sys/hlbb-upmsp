# -*- coding: utf-8 -*-
"""IN-BENCHMARK FEASIBILITY HOOK — feeds every produced solution to the SHARED
`feasibility.py`.

RULE (2026-07-31): whichever algorithm is run, every solution must pass one shared
feasibility checker. `verify_all.py` was a separate pass, so the guarantee relied on
discipline; this hook makes the guarantee AUTOMATIC.

WHY A SEPARATE FILE + SEPARATE LOG (instead of adding a column):
  The existing benchmark CSVs are resumable and APPENDED to. Adding a header column would
  write misaligned rows into files carrying the old header -> corrupting completed data.
  The check result is therefore written to a SIDE FILE (`results/feasibility_log.csv`);
  the production CSV schemas do not change. Violations are also printed LOUDLY to screen.

WHAT IS CHECKED (the cheap ones; exact-ATSP is NOT here -- that is in `verify_all.py`):
  kapsama   every job exactly once                 O(n)
  uygunluk  job only on l in L_i[i]                O(n)
  seq_ok    claim == makespan of the GIVEN order   O(n)  -- only for ORDERED solutions
  route_ok  re-route the assignment, lkh_mk <= claim     -- catches phantom objectives

CARDINALITY is not checked: the constraint was removed from the problem.
The check runs AFTER the run ends -> it steals nothing from the algorithm's time budget.
"""
import csv
import os
import threading

from feasibility import sequence_makespan
from lbbd_optcut_try import route_per_machine

_HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(_HERE, "results", "feasibility_log.csv")
LOG_COLS = ["bench", "method", "inst", "seed", "claimed", "lkh_mk",
            "kapsama", "uygunluk", "seq_ok", "route_ok"]
_lock = threading.Lock()


def check(bench, method, inst, seed, assign, data, claimed, ordered=False, verbose=True):
    """Check the solution, write to the side log, print on violation. Returns: True=clean,
    False=violation, None=uncheckable (no solution). No exception leaks out -- the check
    NEVER brings the benchmark down; on trouble it records 'denetlenemedi' (uncheckable)."""
    if assign is None:
        _write(bench, method, inst, seed, claimed, None, "cozum-yok", "-", "-", "-")
        return None
    try:
        nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = data

        cnt = [0] * nJob; bad_idx = 0
        for l in range(nM):
            for j in assign[l]:
                if 0 <= j < nJob:
                    cnt[j] += 1
                else:
                    bad_idx += 1
        n_cov = bad_idx + sum(1 for c in cnt if c != 1)
        n_elig = sum(1 for l in range(nM) for j in assign[l]
                     if 0 <= j < nJob and l not in L_i[j])

        tol = max(1.0, 0.005 * float(claimed))
        s_seq = "n/a"
        if ordered:
            seq = max((sequence_makespan(assign[l], l, rt, pt, st) for l in range(nM)), default=0.0)
            s_seq = "OK" if abs(seq - float(claimed)) <= tol else "SAPMA"
        lkh_mk = max(route_per_machine(assign, rt, pt, st, 1))
        s_route = "OK" if lkh_mk <= float(claimed) + tol else "BOZUK"

        s_cov = "OK" if n_cov == 0 else f"{n_cov} IHLAL"
        s_el = "OK" if n_elig == 0 else f"{n_elig} IHLAL"
        _write(bench, method, inst, seed, claimed, round(lkh_mk, 1), s_cov, s_el, s_seq, s_route)
        ok = (n_cov == 0 and n_elig == 0 and s_route == "OK" and s_seq != "SAPMA")
        if not ok and verbose:
            print(f"    [!!! FEASIBILITY] {method} {inst} seed={seed}: kapsama={s_cov} "
                  f"uygunluk={s_el} seq={s_seq} route={s_route} "
                  f"(iddia={claimed}, yeniden-rota={lkh_mk:.1f}) -- BU SONUC RAPORLANAMAZ",
                  flush=True)
        return ok
    except Exception as e:                       # the check never brings the benchmark down
        if verbose:
            print(f"    [feas] {method} {inst} denetlenemedi: {e}", flush=True)
        _write(bench, method, inst, seed, claimed, None, "denetlenemedi", "-", "-", "-")
        return None


def _write(bench, method, inst, seed, claimed, lkh, cov, el, seq, route):
    with _lock:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        new = not os.path.exists(LOG_PATH)
        with open(LOG_PATH, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(LOG_COLS)
            w.writerow([bench, method, inst, seed, claimed, lkh, cov, el, seq, route])


def summary(bench=None):
    """Log summary: how many checks, how many violations. Printed at the end of a benchmark."""
    if not os.path.exists(LOG_PATH):
        return "  [feas] denetim logu yok"
    rows = [r for r in csv.DictReader(open(LOG_PATH))
            if bench is None or r["bench"] == bench]
    # IHLAL = a positive defect finding; 'denetlenemedi/cozum-yok' are counted separately (unchecked)
    bad = [r for r in rows if "IHLAL" in r["kapsama"] or "IHLAL" in r["uygunluk"]
           or r["route_ok"] == "BOZUK" or r["seq_ok"] == "SAPMA"]
    unchecked = [r for r in rows if r["kapsama"] in ("cozum-yok", "denetlenemedi")]
    s = (f"  [feas] {len(rows)} denetim, {len(bad)} IHLAL, {len(unchecked)} denetlenemedi "
         f"-> {os.path.relpath(LOG_PATH)}")
    for r in bad[:10]:
        s += (f"\n     ! {r['method']} {r['inst']} seed={r['seed']}: kapsama={r['kapsama']} "
              f"uygunluk={r['uygunluk']} seq={r['seq_ok']} route={r['route_ok']}")
    return s
