# -*- coding: utf-8 -*-
"""PHASE 1 — INTENSIFICATION (local search): improves the arc-LBBD construction with an
inter-machine MOVE + SWAP neighborhood. The gap where HLBB was weak and SA was winning.

Mechanism (hill climb, first improvement):
  - Bottleneck machine b = latest finishing (max completion).
  - MOVE: move a job from b to another machine that is eligible (j in I_l[m]) and has
    room (c2).
  - SWAP: swap j on b with k on another machine (eligibility both ways, cardinality fixed).
  - Re-route only the AFFECTED machines (fast). ACCEPT if the makespan drops.
  - Eligibility (I_l) + cardinality (c1/c2) are preserved at EVERY move (feasibility
    guaranteed).

Seed = arc-LBBD construction (solve_master_arc, cut-free iteration 0 = a known good start).
Comparison: seed makespan vs intensified vs (arc_relax json / SA / GA).

Run:  python3 intensify.py [instance_no=12] [budget_sn=60]
"""
import time
import sys
import math
import random
import multiprocessing as mp

from readproblem import readproblem
from lbbd_arc_relax import solve_master_arc
from lbbd_optcut_try import route_per_machine
from HLBB import (clear_environment, _close_lkh_pool,
                  solveSingleLKH, JobsOnMachinesDistMat)

ROUTE_TL = 0.3     # single-machine LKH time during search (short; final full route separate)
K_MACH = 5         # MOVE/SWAP targets: only the K LIGHTEST machines (heavy targets cannot help)
K_JOBS = 10        # SWAP: the K smallest jobs tried on the target machine (combinatorial pruning)
EJ_MACH = 3        # EJECTION CHAIN: how many lightest machines for m1 and m2 (pruning)
EJ_JOBS = 5        # EJECTION CHAIN: how many smallest jobs tried as the k ejected from m1 (pruning)
RAB_SRC = 3        # RABADI: how many heaviest machines as source (multi-bottleneck, not one max)


def route_one(jobs, m, readyTime, processTime, setupTime, tl=ROUTE_TL):
    """FAST APPROXIMATE completion (nearest neighbor; no subprocess -> microseconds).
    For in-search candidate SCANNING. LKH is too expensive (subprocess ~30ms x thousands of
    calls); the NN approximation is used throughout the search, and the TRUE makespan is
    verified at the end with LKH (route_per_machine). Start = shortest processing, then
    always the nearest (setup) successor. tl is ignored."""
    if not jobs:
        return 0.0
    jobs = list(jobs)
    if len(jobs) == 1:
        return readyTime[m] + processTime[m][jobs[0]]
    unvisited = set(jobs)
    cur = min(jobs, key=lambda j: processTime[m][j])
    unvisited.discard(cur)
    total = readyTime[m] + processTime[m][cur]
    while unvisited:
        nxt = min(unvisited, key=lambda j: setupTime[m][cur][j])
        total += setupTime[m][cur][nxt] + processTime[m][nxt]
        cur = nxt; unvisited.discard(nxt)
    return total


def intensify(assign, comp, readyTime, processTime, setupTime, I_l, c1, c2,
              tl=ROUTE_TL, budget=60, use_swap=True, use_ejection=True, rabadi=False):
    """Bottleneck-focused MOVE -> EJECTION CHAIN -> (opt) SWAP hill climb (ACCELERATED).
    use_ejection: when MOVE stalls, tries a depth-2 ejection (j:b->m1, k:m1->m2) -> finds
    improvements a single move cannot reach out of the compatibility-constrained basin.
    use_swap=False -> SWAP is skipped. assign/comp in place; returns
    (assign, comp, n_move, n_swap, n_eject)."""
    start = time.time()
    nM = len(assign)
    comp = list(comp)
    n_move = n_swap = n_eject = 0
    improved = True
    while improved and time.time() - start < budget:
        improved = False
        mk = max(comp)
        b = comp.index(mk)
        # targets = K_MACH lightest machines (excl. b); only light ones can lower the makespan
        targets = sorted((m for m in range(nM) if m != b), key=lambda m: comp[m])[:K_MACH]

        if rabadi:
            # --- RABADI MOVE: multi-bottleneck source (RAB_SRC heaviest) + BEST-IMPROVEMENT ---
            # (Rabadi CEH: apply the move that lowers the makespan MOST, not the first improving)
            src_list = sorted(range(nM), key=lambda m: -comp[m])[:RAB_SRC]
            best_gain = 1e-6; best_apply = None
            for src in src_list:
                if len(assign[src]) - 1 < c1[str(src)]:
                    continue
                tgt = sorted((m for m in range(nM) if m != src), key=lambda m: comp[m])[:K_MACH]
                for j in assign[src]:
                    nb = route_one([x for x in assign[src] if x != j], src, readyTime, processTime, setupTime, tl)
                    for m in tgt:
                        if j not in I_l[m] or len(assign[m]) + 1 > c2[str(m)]:
                            continue
                        nm = route_one(list(assign[m]) + [j], m, readyTime, processTime, setupTime, tl)
                        nc = comp[:]; nc[src] = nb; nc[m] = nm
                        gain = mk - max(nc)
                        if gain > best_gain:
                            best_gain = gain; best_apply = (src, j, m, nc)
            if best_apply:
                src, j, m, nc = best_apply
                assign[src].remove(j); assign[m].append(j); comp = nc
                improved = True; n_move += 1
                continue
        else:
            # --- MOVE: move a job from b to a light machine (first improvement) ---
            for j in list(assign[b]):
                if len(assign[b]) - 1 < c1[str(b)]:
                    break  # cannot drop b below c1
                # nb does NOT depend on the target machine -> one evaluation per j (HOISTED)
                nb = route_one([x for x in assign[b] if x != j], b, readyTime, processTime, setupTime, tl)
                for m in targets:
                    if j not in I_l[m] or len(assign[m]) + 1 > c2[str(m)]:
                        continue
                    nm = route_one(list(assign[m]) + [j], m, readyTime, processTime, setupTime, tl)
                    new_comp = comp[:]; new_comp[b] = nb; new_comp[m] = nm
                    if max(new_comp) < mk - 1e-6:
                        assign[b].remove(j); assign[m].append(j)
                        comp = new_comp; improved = True; n_move += 1
                        break
                if improved:
                    break
            if improved:
                continue

        # --- EJECTION CHAIN (depth 2): move j: b->m1, eject some k from m1 to m2 ---
        # MOVE stalled (m1 becomes the new bottleneck when it takes j alone). Resolve by
        # extending the chain to m2.
        if use_ejection:
            ej_targets = sorted((m for m in range(nM) if m != b), key=lambda m: comp[m])[:EJ_MACH]
            for j in list(assign[b]):
                if len(assign[b]) - 1 < c1[str(b)]:
                    break
                nb = route_one([x for x in assign[b] if x != j], b, readyTime, processTime, setupTime, tl)
                for m1 in ej_targets:
                    if j not in I_l[m1]:
                        continue
                    cand_k = sorted(assign[m1], key=lambda k: processTime[m1][k])[:EJ_JOBS]
                    for k in cand_k:
                        # m1 final state: +j -k (count unchanged -> c2[m1] preserved)
                        n_m1 = route_one([x for x in assign[m1] if x != k] + [j], m1,
                                         readyTime, processTime, setupTime, tl)
                        m2s = sorted((mm for mm in range(nM) if mm != b and mm != m1
                                      and k in I_l[mm] and len(assign[mm]) + 1 <= c2[str(mm)]),
                                     key=lambda mm: comp[mm])[:EJ_MACH]
                        for m2 in m2s:
                            n_m2 = route_one(list(assign[m2]) + [k], m2,
                                             readyTime, processTime, setupTime, tl)
                            new_comp = comp[:]; new_comp[b] = nb; new_comp[m1] = n_m1; new_comp[m2] = n_m2
                            if max(new_comp) < mk - 1e-6:
                                assign[b].remove(j); assign[m1].append(j)
                                assign[m1].remove(k); assign[m2].append(k)
                                comp = new_comp; improved = True; n_eject += 1
                                break
                        if improved:
                            break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                continue

        if not use_swap:
            break   # MOVE+ejection found no improvement -> local optimum, exit

        # --- SWAP: j on b <-> k among the K_JOBS smallest jobs on a light machine ---
        for j in list(assign[b]):
            for m in targets:
                if j not in I_l[m]:
                    continue
                # try the K_JOBS smallest eligible (I_l[b]) jobs on the target machine
                cand_k = sorted((k for k in assign[m] if k in I_l[b]),
                                key=lambda k: processTime[m][k])[:K_JOBS]
                for k in cand_k:
                    nb = route_one([x for x in assign[b] if x != j] + [k], b, readyTime, processTime, setupTime, tl)
                    nm = route_one([x for x in assign[m] if x != k] + [j], m, readyTime, processTime, setupTime, tl)
                    new_comp = comp[:]; new_comp[b] = nb; new_comp[m] = nm
                    if max(new_comp) < mk - 1e-6:
                        assign[b].remove(j); assign[b].append(k)
                        assign[m].remove(k); assign[m].append(j)
                        comp = new_comp; improved = True; n_swap += 1
                        break
                if improved:
                    break
            if improved:
                break
    return assign, comp, n_move, n_swap, n_eject


def perturb(assign, comp, readyTime, processTime, setupTime, I_l, c1, c2, tl, kick=3):
    """ESCAPE: apply kick RANDOM feasible MOVEs (diversification; improvement NOT required,
    the aim is to leave the local-optimum basin). NOT bottleneck-focused -> random
    source/target. Eligibility (I_l) + cardinality (c1/c2) preserved. assign/comp updated
    in place."""
    nM = len(assign)
    done = tries = 0
    while done < kick and tries < 50 * kick:
        tries += 1
        src = random.randrange(nM)
        if not assign[src] or len(assign[src]) - 1 < c1[str(src)]:
            continue
        j = random.choice(assign[src])
        cands = [m for m in range(nM) if m != src and j in I_l[m] and len(assign[m]) + 1 <= c2[str(m)]]
        if not cands:
            continue
        m = random.choice(cands)
        assign[src].remove(j); assign[m].append(j)     # NO improvement CHECK (deliberate)
        comp[src] = route_one(assign[src], src, readyTime, processTime, setupTime, tl)
        comp[m] = route_one(assign[m], m, readyTime, processTime, setupTime, tl)
        done += 1
    return assign, comp, done


def _lkh_makespan(assign, readyTime, processTime, setupTime, tl=1):
    """True makespan = per-machine route with LKH, max completion."""
    return max(route_per_machine(assign, readyTime, processTime, setupTime, tl))


def ils(assign, comp, readyTime, processTime, setupTime, I_l, c1, c2,
        tl=ROUTE_TL, budget=120, kick=3, seed=0, use_swap=True, pool_k=15, anchor=None,
        use_ejection=True, rabadi=False, accept="best", accept_t0=0.02):
    """ILS (NN search) + CHEAP hybrid verification.
    No LKH during the search (the budget cannot afford it) -> the best pool_k NN local
    optima are kept in a pool; AT THE END the whole pool is verified with LKH and the true
    LKH-best is returned. The search thus runs at full speed, and the returned solution is
    LKH-true, the small NN bias corrected by picking the best of the pool.

    ACCEPTANCE CRITERION (Rolim's SA-SOTA lesson: worse-acceptance to deepen
    intensification):
      accept="best"       : OLD behavior. Perturb ALWAYS from best (descent+restart),
                            accept only improvements.
      accept="threshold"  : perturb from the WALK pointer; accept if the new local optimum
                            is <=(1+threshold) of WALK. Threshold =
                            accept_t0 * (1 - elapsed/budget) -> anneals (pure descent at
                            the end).
      accept="metropolis" : SA-style. Accept a worse move with p=exp(-Delta/T).
                            T = accept_t0*best_mk*(1-elapsed/budget).
    best_* ALWAYS holds the global best (independent of the acceptance criterion).
    accept_t0 = the only new parameter.
    Returns: dict (lkh_best_* = pool-LKH-best; nn_best_* + nn_best_lkh = NN trajectory;
    counters + n_worse)."""
    random.seed(seed)
    start = time.time()
    comp = [route_one(assign[m], m, readyTime, processTime, setupTime, tl) for m in range(len(assign))]
    assign, comp, nm0, ns0, ne0 = intensify(assign, comp, readyTime, processTime, setupTime,
                                            I_l, c1, c2, tl, budget, use_swap, use_ejection, rabadi)
    best_assign = [list(x) for x in assign]; best_comp = list(comp); best_mk = max(comp)
    # WALK pointer: the acceptance criterion perturbs from here (separate from best).
    # In "best" mode it is always pulled back to best.
    base_assign = [list(x) for x in best_assign]; base_comp = list(best_comp); base_mk = best_mk
    pool = []
    def pool_add(nn_val, a):
        pool.append((nn_val, [list(x) for x in a], time.time() - start))  # tstamp: for t-best
        pool.sort(key=lambda t: t[0]); del pool[pool_k:]
    pool_add(best_mk, best_assign)
    tot_move, tot_swap, tot_eject, n_restart, n_accept, n_worse = nm0, ns0, ne0, 0, 0, 0
    while time.time() - start < budget:
        cur = [list(x) for x in base_assign]; cur_comp = list(base_comp)   # perturb from WALK
        perturb(cur, cur_comp, readyTime, processTime, setupTime, I_l, c1, c2, tl, kick)
        remain = budget - (time.time() - start)
        if remain <= 0.5:
            break
        cur, cur_comp, nm, ns, ne = intensify(cur, cur_comp, readyTime, processTime, setupTime,
                                              I_l, c1, c2, tl, remain, use_swap, use_ejection, rabadi)
        tot_move += nm; tot_swap += ns; tot_eject += ne; n_restart += 1
        cur_nn = max(cur_comp)
        pool_add(cur_nn, cur)
        # (1) update the GLOBAL best -- INDEPENDENT of the acceptance criterion
        if cur_nn < best_mk - 1e-6:
            best_assign = [list(x) for x in cur]; best_comp = list(cur_comp); best_mk = cur_nn; n_accept += 1
        # (2) update the WALK pointer by the acceptance criterion
        if accept == "best":
            base_assign = [list(x) for x in best_assign]; base_comp = list(best_comp); base_mk = best_mk
        else:
            take = cur_nn < base_mk - 1e-6
            if not take and accept == "threshold":
                frac = accept_t0 * max(0.0, 1.0 - (time.time() - start) / budget)
                take = cur_nn <= base_mk * (1.0 + frac)
            elif not take and accept == "metropolis":
                T = accept_t0 * best_mk * max(1e-9, 1.0 - (time.time() - start) / budget)
                take = random.random() < math.exp(-(cur_nn - base_mk) / T)
            if take:
                if cur_nn > base_mk + 1e-6:
                    n_worse += 1
                base_assign = [list(x) for x in cur]; base_comp = list(cur_comp); base_mk = cur_nn
    # AT THE END: verify the pool with LKH (not in-search) -> true LKH-best
    lkh_best_mk = float("inf"); lkh_best_assign = best_assign; lkh_best_t = 0.0
    pool_lkh = []   # for SPP recombination: LKH-verified diverse local optima
    for nn_val, a, ts in pool:
        v = _lkh_makespan(a, readyTime, processTime, setupTime)
        pool_lkh.append([list(x) for x in a])
        if v < lkh_best_mk:
            lkh_best_mk = v; lkh_best_assign = a; lkh_best_t = ts   # t-best = when this was found
    if anchor is not None:   # ANCHOR: raw A is a candidate -> ILS never returns worse than A
        v = _lkh_makespan(anchor, readyTime, processTime, setupTime)
        if v < lkh_best_mk:
            lkh_best_mk = v; lkh_best_assign = [list(x) for x in anchor]; lkh_best_t = 0.0
    nn_best_lkh = _lkh_makespan(best_assign, readyTime, processTime, setupTime)  # NN-best's own LKH
    return {"lkh_best_assign": lkh_best_assign, "lkh_best_mk": lkh_best_mk,
            "nn_best_assign": best_assign, "nn_best_mk": best_mk, "nn_best_lkh": nn_best_lkh,
            "ils_tbest": round(lkh_best_t, 1),
            "n_move": tot_move, "n_swap": tot_swap, "n_eject": tot_eject, "n_restart": n_restart,
            "n_accept": n_accept, "n_worse": n_worse, "n_verify": len(pool), "pool_lkh": pool_lkh}


# Known reference values for the priority-1 de-risk test (scaling_test, relaxed inst12):
#   M=6 (~25 jobs/machine): CP=17815, HLBB-LKH-best=20465
#   M=4 (~38 jobs/machine): CP=25417, HLBB-LKH-best=30744
#   M=3 (~50 jobs/machine): CP=35376, HLBB-LKH-best=37906
_REF = {6: (17815, 20465), 4: (25417, 30744), 3: (35376, 37906)}


def main():
    inst = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    M = int(sys.argv[3]) if len(sys.argv) > 3 else 0   # 0 = original (unrelaxed); 6/4/3 = relaxed
    kick = int(sys.argv[4]) if len(sys.argv) > 4 else 3   # ILS perturbation strength
    use_swap = (len(sys.argv) <= 5 or sys.argv[5] != "0")  # SWAP default ON; "0" -> off
    jf = f"new_dataset_ekici/150_15/instance_{inst}.json"
    d = readproblem(jf, consider_compatibility=True, consider_workload=True)
    if M and M < d[1]:
        from scaling_test import build_relaxed
        d = build_relaxed(d, M)
    nJob, nMachine, c1, c2, readyTime, processTime, setupTime, matrix, I_l, L_i, estSetup = d

    clear_environment(); _close_lkh_pool()
    tag = f"M={M} (~{nJob/nMachine:.0f} is/mak)" if M else "orijinal (15 makine)"
    print(f"### intensify+ILS | instance_{inst} | {tag} | budget={budget}s | kick={kick} "
          f"| SWAP={'ACIK' if use_swap else 'kapali'} ###", flush=True)

    # 1) SEED: arc-LBBD construction (cut-free iteration 0)
    assign, S_list, mcmax = solve_master_arc(nJob, nMachine, c1, c2, processTime,
                                             setupTime, I_l, L_i, [], [])
    if assign is None:
        print("HATA: master infeasible (seed uretilemedi)", flush=True)
        _close_lkh_pool(); clear_environment(); return
    comp = route_per_machine(assign, readyTime, processTime, setupTime, 1)
    seed_mk = max(comp)
    print(f"seed (arc construction) makespan = {seed_mk:.0f}", flush=True)

    # 2) ILS + CHEAP hybrid LKH verification (pool at the end)
    res = ils(assign, comp, readyTime, processTime, setupTime, I_l, c1, c2,
              budget=budget, kick=kick, use_swap=use_swap)
    final_mk = res["lkh_best_mk"]     # pool-LKH-best
    nn_best_lkh = res["nn_best_lkh"]  # the single NN-best's LKH (WITHOUT the hybrid)

    _close_lkh_pool(); clear_environment()
    print(f"ILS+hibrit makespan = {final_mk:.0f}  (MOVE={res['n_move']}, SWAP={res['n_swap']}, "
          f"restart={res['n_restart']}, kabul={res['n_accept']}, LKH-dogrulama={res['n_verify']})", flush=True)
    gain = seed_mk - final_mk
    print(f"kazanc (seed->ILS) = {gain:.0f} ({100*gain/seed_mk:.1f}%)", flush=True)
    print(f"HIBRIT etkisi: NN-best'in LKH degeri={nn_best_lkh:.0f} -> hibrit-best={final_mk:.0f} "
          f"(hibrit {nn_best_lkh-final_mk:+.0f} kazandirdi -> proxy sapmasi {'VAR, duzeltildi' if nn_best_lkh-final_mk>1 else 'ihmal edilebilir'})", flush=True)
    if M in _REF:
        cp, hlbb = _REF[M]
        print(f"--- KIYAS (relaxed inst{inst} M={M}) ---", flush=True)
        print(f"  ILS+hibrit={final_mk:.0f} | HLBB-LKH-best={hlbb} ({100*(final_mk-hlbb)/hlbb:+.1f}%) "
              f"| CP={cp} ({100*(final_mk-cp)/cp:+.1f}%)", flush=True)


if __name__ == "__main__":
    mp.set_start_method("spawn")
    main()
