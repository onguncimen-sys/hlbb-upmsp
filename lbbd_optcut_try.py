"""TRUE LBBD attempt: OPTIMALITY CUTS are added to the master (existing code UNCHANGED).

PROBLEM (prior diagnosis): the HLBB master's objective is a flat plateau because of
estSetup (51851 on instance_12), since the inflated estimate of the forced machine 14
pins the max. The master cannot see the true bottleneck (e.g. machine 11 = 42870) ->
the search is blind -> it stalls at 42870 (while CP 35893 / SA 34329).

IDEA: without changing the master objective, feed the TRUE per-machine routing cost
of every evaluated assignment back to the master as an OPTIMALITY CUT:

   cmax >= h_l * (1 - sum_{i in S_l}(1 - y_il))      (Hooker optimality cut)

"If machine l keeps all jobs of S_l, then cmax >= h_l." Adding jobs only increases
the completion time, so the bound is valid; removing a job relaxes the cut. The
master thus learns that machine 11 really costs 42870 and can shift load away ->
the plateau breaks.

This file DOES NOT MODIFY HLBB.py / methods.py; it only imports helper functions
and builds its own LBBD loop. Comparison: same instance, same 300 s / TL=1 budget.

NOTE (honesty): with LKH time_limit=1, h_l is an upper bound on the TRUE optimal
route of S_l; the cut is not "fully valid" but consistent within HLBB's own
heuristic cost world. This is Heuristic-LBBD anyway; the goal is to steer the
master, not to prove optimality.

Run:  python3 lbbd_optcut_try.py
"""
import time
import multiprocessing as mp

from gurobipy import GRB, Model, quicksum

from readproblem import readproblem
from methods import env
from HLBB import (clear_environment, _get_lkh_pool, _close_lkh_pool,
                  solveSingleLKH, JobsOnMachinesDistMat)

ESKI_HLBB = 42870.0
CP = 35893.0
SA = 34329.0


def route_per_machine(assignment_list, readyTime, processTime, setupTime, time_limit):
    """Same as HLBB.solveParallelLKH; ONLY returns the PER-MACHINE list instead of the max.
    [FIX] LKH ATSP crashes below 2 nodes (DIMENSION<3 error). With small subproblems and
    relaxed cardinality, machines may get 0/1/2 jobs -> compute 0/1/2-job machines DIRECTLY,
    send only >=3-job machines to LKH (>=3 behaviour UNCHANGED). Pool size is FIXED
    (reuse preserved)."""
    nM = len(assignment_list)
    result = [0.0] * nM
    to_solve = []; idx = []
    for m, sel in enumerate(assignment_list):
        sel = list(set(sel))
        if len(sel) == 0:
            result[m] = 0.0                                    # empty machine -> no contribution
        elif len(sel) == 1:
            result[m] = readyTime[m] + processTime[m][sel[0]]  # single job: no setup/order
        elif len(sel) == 2:
            a, b = sel                                         # 2 jobs: best of both orders (exact)
            v = min(processTime[m][a] + setupTime[m][a][b] + processTime[m][b],
                    processTime[m][b] + setupTime[m][b][a] + processTime[m][a])
            result[m] = readyTime[m] + v
        else:
            to_solve.append(JobsOnMachinesDistMat(processTime, setupTime, sel, m)); idx.append(m)
    if to_solve:
        pool = _get_lkh_pool(nM)                               # FIXED size -> pool reuse preserved
        costs = pool.map(solveSingleLKH, zip(to_solve, [time_limit] * len(to_solve)))
        for k, m in enumerate(idx):
            result[m] = readyTime[m] + costs[k]
    return result   # h_l, for each machine


def solve_master(nJob, nMachine, c1, c2, processTime, I_l, L_i, estSetup,
                 opt_cuts, nogoods):
    """Same base model as methods.MIP_Assignment + OPTIMALITY CUTS.
    opt_cuts: [(h_list, S_list)]  -> h_list[l] true route, S_list[l] jobs on that machine
    nogoods : [S_list]            -> do not reproduce the same assignment (single aggregate
                                     Hamming cut)
    Returns: (assignments_per_machine, S_list, master_cmax)  or (None, None, None)."""
    mdl = Model("MIP-A-optcut", env=env)
    y = mdl.addVars(range(nJob), range(nMachine), vtype=GRB.BINARY, name="y")
    s = mdl.addVars(range(nMachine), vtype=GRB.CONTINUOUS, name="s")
    cmax = mdl.addVar(vtype=GRB.CONTINUOUS, name="cmax")
    mdl.setObjective(cmax, GRB.MINIMIZE)

    # estSetup-based lower bound (same as the original master)
    mdl.addConstrs(cmax >= s[l] for l in range(nMachine))
    mdl.addConstrs(
        s[l] >= quicksum(processTime[l][i] * y[i, l] for i in I_l[l]) +
                quicksum(estSetup[i][l] * y[i, l] for i in I_l[l])
        for l in range(nMachine))

    # --- OPTIMALITY CUTS: tie the true routing cost into the master ---
    for (h_list, S_list) in opt_cuts:
        for l in range(nMachine):
            if S_list[l]:
                mdl.addConstr(
                    cmax >= h_list[l] * (1 - quicksum(1 - y[i, l] for i in S_list[l])))

    # --- no-good (single aggregate): do not reproduce the same assignment ---
    for S_list in nogoods:
        mdl.addConstr(
            quicksum(
                quicksum(1 - y[i, l] for i in S_list[l]) +
                quicksum(y[i, l] for i in I_l[l] if i not in set(S_list[l]))
                for l in range(nMachine)
            ) >= 1)

    mdl.addConstrs(quicksum(y[i, l] for l in L_i[i]) == 1 for i in range(nJob))
    mdl.addConstrs(quicksum(y[i, l] for i in I_l[l]) >= c1[str(l)] for l in range(nMachine))
    mdl.addConstrs(quicksum(y[i, l] for i in I_l[l]) <= c2[str(l)] for l in range(nMachine))

    mdl.Params.TimeLimit = 5
    mdl.setParam("OutputFlag", 0)
    mdl.setParam("Seed", 1)
    mdl.optimize()

    try:
        assign = []
        S_list = []
        for l in range(nMachine):
            on_l = [i for i in range(nJob) if y[i, l].X > 0.5]
            assign.append(on_l)
            S_list.append(on_l)
        return assign, S_list, cmax.X
    except AttributeError:
        return None, None, None


def lbbd_optcut(nJob, nMachine, c1, c2, readyTime, processTime, setupTime,
                I_l, L_i, estSetup, total_time_limit=300, time_limit=1, max_iter=200):
    clear_environment()
    _close_lkh_pool()
    start = time.time()
    best = 1e6
    best_time = 0.0
    opt_cuts = []     # [(h_list, S_list)]
    nogoods = []      # [S_list]
    iters = 0

    for it in range(max_iter):
        if time.time() - start >= total_time_limit:
            print(f"[optcut] sure butcesi ({total_time_limit}s) doldu, iter {it}")
            break
        clear_environment()
        assign, S_list, mcmax = solve_master(nJob, nMachine, c1, c2, processTime,
                                             I_l, L_i, estSetup, opt_cuts, nogoods)
        if assign is None:
            print(f"[optcut] master infeasible, iter {it} -> dur")
            break

        h_list = route_per_machine(assign, readyTime, processTime, setupTime, time_limit)
        real = max(h_list)
        bind = h_list.index(real)   # true bottleneck machine
        if real < best:
            best = real
            best_time = time.time() - start
            print(f"  >>> iyilesme: {real:.0f}  (iter {it}, master_tahmin={mcmax:.0f}, "
                  f"gercek_darbogaz=makine {bind})")
        else:
            print(f"  iter {it}: real={real:.0f} (best={best:.0f}, master_tahmin={mcmax:.0f}, "
                  f"darbogaz=makine {bind})")

        # add the cuts: optimality (steer) + no-good (prevent repeats)
        opt_cuts.append((h_list, S_list))
        nogoods.append(S_list)
        iters = it + 1

    _close_lkh_pool()
    clear_environment()
    print(f"\n[optcut] toplam iter={iters}, wall={time.time()-start:.0f}s, "
          f"best={best:.0f}, t-best={best_time:.0f}s")
    return best, best_time, iters


def main():
    jf = "new_dataset_ekici/150_15/instance_12.json"
    d = readproblem(jf, consider_compatibility=True, consider_workload=True)
    nJob, nMachine, c1, c2, readyTime, processTime, setupTime, matrix, I_l, L_i, estSetup = d
    print(f"### LBBD + OPTIMALITY CUT | instance_12 | hedef: 42870'in altina inmek "
          f"(CP={CP}, SA={SA}) ###", flush=True)
    best, bt, iters = lbbd_optcut(nJob, nMachine, c1, c2, readyTime, processTime,
                                  setupTime, I_l, L_i, estSetup,
                                  total_time_limit=300, time_limit=1)
    dt = "DAHA IYI ✅" if best < ESKI_HLBB else ("AYNI" if best == ESKI_HLBB else "DAHA KOTU")
    print(f"\nSONUC: optcut-best={best:.0f}  (orijinal HLBB {ESKI_HLBB} -> {dt}) | "
          f"t-best={bt:.0f}s, iter={iters}", flush=True)
    print(f"       referans: CP={CP}, SA={SA}", flush=True)


if __name__ == "__main__":
    mp.set_start_method("spawn")
    main()
