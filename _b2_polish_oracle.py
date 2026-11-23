# -*- coding: utf-8 -*-
"""B2 ORACLE — POST-SPP TRUE-EVALUATION POLISH ("terminal polish").
ILS/fast-LS were always tested INSIDE THE LOOP (negative); local search on the FINAL
solution with true LKH costs was never measured = an untried final placement. The oracle
is generous (60 s, offline): job-move + job-swap moves from the bottleneck machine of
the final solution, each move evaluated with TRUE routing (only the 2 changed machines
are re-routed). Pre-registered criterion: >=2 units of improvement on 640/800; otherwise
DEAD. Time-to-first-improvement is also reported (an in-run version must fit the ~5-8 s
slack). The __main__ guard is REQUIRED."""
import sys
import time

import ablation_run as AR
from ab_cut_bneck import _load
from lbbd_optcut_try import route_per_machine
from HLBB import clear_environment

LS_BUDGET = 60.0


def spans_of(assign, nM, rt, pt, st):
    return route_per_machine(assign, rt, pt, st, 1)


def polish(assign, h, nJob, nM, c2, L_i, rt, pt, st, budget):
    """Bottleneck-focused first-improvement: move (b*->t) then swap (b* <-> t).
    cache: (l, frozenset) -> cost. Returns: (new_mk, n_eval, n_improved, t_first)."""
    cache = {}
    for l in range(nM):
        cache[(l, frozenset(assign[l]))] = h[l]

    def cost(l, S):
        k = (l, frozenset(S))
        if k not in cache:
            batch = [[] for _ in range(nM)]; batch[l] = list(S)
            cache[k] = route_per_machine(batch, rt, pt, st, 1)[l]
        return cache[k]

    t0 = time.time(); n_ev = 0; n_imp = 0; t_first = None
    cur = [list(m) for m in assign]; hh = list(h)
    while time.time() - t0 < budget:
        mk = max(hh); b = max(range(nM), key=lambda l: hh[l])
        improved = False
        # --- MOVE: a job from the bottleneck to another machine ---
        for i in sorted(cur[b], key=lambda i_: -pt[b][i_]):
            for t in sorted((t_ for t_ in L_i[i] if t_ != b), key=lambda t_: hh[t_]):
                if len(cur[t]) + 1 > int(c2[str(t)]) or time.time() - t0 >= budget:
                    continue
                n_ev += 1
                hb = cost(b, [x for x in cur[b] if x != i])
                ht = cost(t, cur[t] + [i])
                nm = max(max((hh[l] for l in range(nM) if l not in (b, t)), default=0), hb, ht)
                if nm < mk - 1e-6:
                    cur[b] = [x for x in cur[b] if x != i]; cur[t] = cur[t] + [i]
                    hh[b], hh[t] = hb, ht
                    n_imp += 1; t_first = t_first or (time.time() - t0)
                    improved = True; break
            if improved or time.time() - t0 >= budget:
                break
        if improved:
            continue
        # --- SWAP: a bottleneck job <-> another machine's job ---
        for i in sorted(cur[b], key=lambda i_: -pt[b][i_]):
            for t in sorted((t_ for t_ in range(nM) if t_ != b), key=lambda t_: hh[t_]):
                for j in cur[t]:
                    if b not in L_i[j] or t not in L_i[i] or time.time() - t0 >= budget:
                        continue
                    n_ev += 1
                    hb = cost(b, [x for x in cur[b] if x != i] + [j])
                    ht = cost(t, [x for x in cur[t] if x != j] + [i])
                    nm = max(max((hh[l] for l in range(nM) if l not in (b, t)), default=0), hb, ht)
                    if nm < mk - 1e-6:
                        cur[b] = [x for x in cur[b] if x != i] + [j]
                        cur[t] = [x for x in cur[t] if x != j] + [i]
                        hh[b], hh[t] = hb, ht
                        n_imp += 1; t_first = t_first or (time.time() - t0)
                        improved = True; break
                if improved:
                    break
            if improved:
                break
        if not improved:
            break                        # full neighbourhood scanned, no improvement -> local optimum
    return max(hh), n_ev, n_imp, t_first


if __name__ == "__main__":
    cells = ([tuple(x.split(":")) for x in sys.argv[1:]]
             if len(sys.argv) > 1 else [("640_25", "1"), ("800_30", "1"),
                                        ("640_25", "2"), ("800_30", "2")])
    for size, inst in cells:
        nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = _load(size, inst, "niche_v2")
        r = AR.run_abl(nJob, nM, c1, c2, rt, pt, st, I_l, L_i,
                       total_time_limit=200, master_tl=3, kmach=3, arc_k=5, seed=0,
                       pool_mode=1, pool_k=20, spp_cap=250, inside=True)
        A = r["assign"]
        h = spans_of(A, nM, rt, pt, st)
        mk0 = max(h)
        clear_environment()
        mk1, n_ev, n_imp, t_first = polish(A, h, nJob, nM, c2, L_i, rt, pt, st, LS_BUDGET)
        tf = f"{t_first:.1f}s" if t_first is not None else "-"
        print(f"== {size} i{inst}: kosu mk={r['best']:.0f} -> cila {mk0:.0f}->{mk1:.0f} "
              f"({n_imp} iyilesme / {n_ev} degerlendirme, ilk-iyilesme {tf}) "
              f"{'*** IYILESME ' + format(mk0-mk1,'.0f') if mk1 < mk0 - 1e-6 else 'IYILESME YOK'}",
              flush=True)
        clear_environment()
