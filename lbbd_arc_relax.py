"""LBBD with a CLUSTER-AWARE relaxation in the master (existing code UNCHANGED).

PRIOR FINDING: the per-job average estSetup cannot carry the cluster-dependent
routing cost (separable/linear) -> the master plateaus and stops steering.

IDEA (ML-free, principled LBBD): embed the ATSP ASSIGNMENT RELAXATION of the
routing subproblem inside the master. Instead of an average, the master picks a
PREDECESSOR for each assigned job and charges the setup against that predecessor:

   x[j,i,l]=1 -> on machine l, j is the predecessor of i (among assigned jobs only)
   each assigned job has exactly 1 predecessor:  sum_j x[j,i,l] + xd[i,l] = y[i,l]
   the predecessor must be assigned:             x[j,i,l] <= y[j,l]
   at most 1 depot start per machine: sum_i xd[i,l] <= 1   (forces k-1 real setups)
   s_l >= sum proc*y + sum setup[j->i]*x[j,i,l]

This is a LOWER BOUND on the true tour length (subtours allowed) and CLUSTER-AWARE:
the master can now see "placing these two high-setup jobs next to each other makes
the predecessor cost high". Hypothesis: master_estimate no longer FREEZES at 35688,
it CHANGES from assignment to assignment (plateau broken) and best drops below 37924.

x is continuous (the assignment relaxation is naturally integral) -> the master does
not get much heavier. The candidate predecessor set is sparsified to the cheapest
K=30 (tractability; in practice it covers all jobs within a cluster).

Run:  python3 lbbd_arc_relax.py
"""
import time
import multiprocessing as mp

from gurobipy import GRB, Model, quicksum

from readproblem import readproblem
from methods import env
from HLBB import clear_environment, _close_lkh_pool, JobsOnMachinesDistMat
from lbbd_optcut_try import route_per_machine, ESKI_HLBB, CP, SA
from exact_atsp import exact_atsp_dfj

# valid-LB diagnostics from the last solve_master_arc call (ObjBound = proven dual bound)
LAST_OBJBOUND = None
LAST_MIPGAP = None
LAST_STATUS = None
LAST_S = None

ONCEKI_OPTCUT = 37924.0   # tight-estSetup + optcut result (for comparison)


def route_per_machine_exact(assignment_list, readyTime, processTime, setupTime, route_tl=30.0):
    """SAME output as route_per_machine (the h_l list) but the routing is EXACT (DFJ lazy
    subtour), NOT LKH. True subproblem optimum -> the cuts become valid (for a valid LB)."""
    return [readyTime[m] + exact_atsp_dfj(JobsOnMachinesDistMat(processTime, setupTime, sel, m), route_tl)
            for m, sel in enumerate(assignment_list)]
K = 30                    # number of candidate predecessors per (job, machine)


def solve_master_arc(nJob, nMachine, c1, c2, processTime, setupTime,
                     I_l, L_i, opt_cuts, nogoods, master_tl=10, readyTime=None, subtour=False,
                     bias=None, K=K):
    mdl = Model("MIP-A-arc", env=env)
    y = mdl.addVars(range(nJob), range(nMachine), vtype=GRB.BINARY, name="y")
    s = mdl.addVars(range(nMachine), vtype=GRB.CONTINUOUS, name="s")
    cmax = mdl.addVar(vtype=GRB.CONTINUOUS, name="cmax")
    mdl.setObjective(cmax, GRB.MINIMIZE)
    mdl.addConstrs(cmax >= s[l] for l in range(nMachine))
    # machine-used indicator u[l] (for readyTime + primal routing bias): loaded -> u=1, empty -> u=0
    u = None
    if readyTime is not None or bias is not None:
        u = mdl.addVars(range(nMachine), vtype=GRB.BINARY, name="u")
        for l in range(nMachine):
            if I_l[l]:
                mdl.addConstr(quicksum(y[i, l] for i in I_l[l]) <= len(I_l[l]) * u[l])

    # --- sparse candidate predecessor arcs: the cheapest K predecessors for each (i,l) ---
    arcs = {l: {} for l in range(nMachine)}
    x = {}
    xd = {}
    for l in range(nMachine):
        jobs = I_l[l]
        for i in jobs:
            cand = sorted((j for j in jobs if j != i),
                          key=lambda j: setupTime[l][j][i])[:K]
            arcs[l][i] = cand
            for j in cand:
                x[j, i, l] = mdl.addVar(lb=0, ub=1, vtype=GRB.CONTINUOUS,
                                        name=f"x_{j}_{i}_{l}")
            xd[i, l] = mdl.addVar(lb=0, ub=1, vtype=GRB.CONTINUOUS, name=f"xd_{i}_{l}")

    # each assigned job: exactly 1 predecessor (an assigned job or the depot)
    for l in range(nMachine):
        for i in I_l[l]:
            mdl.addConstr(quicksum(x[j, i, l] for j in arcs[l][i]) + xd[i, l] == y[i, l])
            for j in arcs[l][i]:
                mdl.addConstr(x[j, i, l] <= y[j, l])   # the predecessor must be assigned
    # at most 1 depot start per machine -> k-1 real setups
    for l in range(nMachine):
        if I_l[l]:
            mdl.addConstr(quicksum(xd[i, l] for i in I_l[l]) <= 1)
    # s_l: processing + selected predecessor setups (cluster-aware lower bound)
    for l in range(nMachine):
        ready_term = readyTime[l] * u[l] if readyTime is not None else 0
        # PRIMAL routing-feedback bias (learning): the master sees l's true routing excess ->
        # it unloads that machine -> genuinely balanced assignment. Guarded by u (so an empty
        # machine is not inflated).
        bias_term = bias[l] * u[l] if bias is not None else 0
        mdl.addConstr(
            s[l] >= ready_term + bias_term +
                    quicksum(processTime[l][i] * y[i, l] for i in I_l[l]) +
                    quicksum(setupTime[l][j][i] * x[j, i, l]
                             for i in I_l[l] for j in arcs[l][i]))

    # --- ② MTZ/DL subtour elimination (Peyro): STATIC constraints -> root LP tightens -> LB rises ---
    if subtour:
        n = nJob
        U = mdl.addVars(range(nJob), lb=0.0, ub=n, vtype=GRB.CONTINUOUS, name="U")  # job position (rank within machine)
        for l in range(nMachine):
            for i in I_l[l]:
                for j in arcs[l][i]:                 # arc j->i (j is the predecessor of i)
                    # MTZ: x[j,i,l]=1 -> U_i >= U_j + 1 (breaks cycles)
                    if (i, j, l) in x:               # if the reverse arc exists, DL (Peyro 11, strong form)
                        mdl.addConstr(U[j] - U[i] + n * x[j, i, l] + (n - 2) * x[i, j, l] <= n - 1)
                    else:
                        mdl.addConstr(U[i] >= U[j] + 1 - n * (1 - x[j, i, l]))
                # VI (14): depot start (xd=1) -> U_i = 0 (first job at position 0)
                mdl.addConstr(U[i] + (n - 1) * xd[i, l] <= n - 1)

    # --- optimality cuts (feed the true routing back) ---
    for (h_list, S_list) in opt_cuts:
        for l in range(nMachine):
            if S_list[l]:
                mdl.addConstr(cmax >= h_list[l] * (1 - quicksum(1 - y[i, l] for i in S_list[l])))
    # --- no-good (single aggregate) ---
    for S_list in nogoods:
        sset = [set(S_list[l]) for l in range(nMachine)]
        mdl.addConstr(
            quicksum(
                quicksum(1 - y[i, l] for i in S_list[l]) +
                quicksum(y[i, l] for i in I_l[l] if i not in sset[l])
                for l in range(nMachine)) >= 1)

    mdl.addConstrs(quicksum(y[i, l] for l in L_i[i]) == 1 for i in range(nJob))
    mdl.addConstrs(quicksum(y[i, l] for i in I_l[l]) >= c1[str(l)] for l in range(nMachine))
    mdl.addConstrs(quicksum(y[i, l] for i in I_l[l]) <= c2[str(l)] for l in range(nMachine))

    mdl.Params.TimeLimit = master_tl  # default 10 (baseline); integrated use passes less and iterates more
    mdl.setParam("OutputFlag", 0)
    mdl.setParam("Seed", 1)
    mdl.optimize()
    global LAST_OBJBOUND, LAST_MIPGAP, LAST_STATUS, LAST_S
    LAST_OBJBOUND = mdl.ObjBound if mdl.SolCount > 0 or mdl.Status == GRB.OPTIMAL else None
    LAST_MIPGAP = mdl.MIPGap if mdl.SolCount > 0 else None
    LAST_STATUS = mdl.Status
    try:
        assign = [[i for i in range(nJob) if y[i, l].X > 0.5] for l in range(nMachine)]
        LAST_S = [s[l].X for l in range(nMachine)]   # diagnostic: the master's per-machine routing LB
        return assign, assign, cmax.X
    except AttributeError:
        return None, None, None


def run(nJob, nMachine, c1, c2, readyTime, processTime, setupTime, I_l, L_i,
        total_time_limit=300, time_limit=1, max_iter=400, return_solution=False,
        router="LKH", route_tl=30.0):
    """router="LKH" -> heuristic routing (fast, upper bound/primal).
    router="exact" -> DFJ exact routing (true subproblem optimum; the cuts are valid).
    route_time_total (total time spent in routing) is also reported on screen."""
    clear_environment(); _close_lkh_pool()
    start = time.time()
    best = 1e6; best_time = 0.0; best_assign = None
    opt_cuts = []; nogoods = []; iters = 0; route_time_total = 0.0
    for it in range(max_iter):
        if time.time() - start >= total_time_limit:
            print(f"[arc] sure butcesi ({total_time_limit}s) doldu, iter {it}")
            break
        clear_environment()
        assign, S_list, mcmax = solve_master_arc(nJob, nMachine, c1, c2, processTime,
                                                 setupTime, I_l, L_i, opt_cuts, nogoods)
        if assign is None:
            print(f"[arc] master infeasible, iter {it} -> dur"); break
        rt0 = time.time()
        if router == "exact":
            h_list = route_per_machine_exact(assign, readyTime, processTime, setupTime, route_tl)
        else:
            h_list = route_per_machine(assign, readyTime, processTime, setupTime, time_limit)
        route_time_total += time.time() - rt0
        real = max(h_list); bind = h_list.index(real)
        tag = ""
        if real < best:
            best = real; best_time = time.time() - start; tag = "  >>> iyilesme"
            best_assign = [list(m) for m in assign]        # best assignment, kept for verification
        print(f"{tag}  iter {it}: real={real:.0f} (best={best:.0f}, "
              f"master_tahmin={mcmax:.0f}, darbogaz=makine {bind})", flush=True)
        opt_cuts.append((h_list, S_list)); nogoods.append(S_list); iters = it + 1
    _close_lkh_pool(); clear_environment()
    print(f"\n[arc/{router}] toplam iter={iters}, wall={time.time()-start:.0f}s, "
          f"routing_toplam={route_time_total:.1f}s ({route_time_total/max(iters,1):.3f}s/iter), "
          f"best={best:.0f}, t-best={best_time:.0f}s")
    if return_solution:
        return best, best_time, iters, best_assign
    return best, best_time, iters


def main():
    jf = "new_dataset_ekici/150_15/instance_12.json"
    d = readproblem(jf, consider_compatibility=True, consider_workload=True)
    nJob, nMachine, c1, c2, readyTime, processTime, setupTime, matrix, I_l, L_i, estSetup = d
    print(f"### LBBD + ATSP ATAMA-RELAXATION master (kume-farkinda) | instance_12 ###", flush=True)
    print(f"  hedef: master_tahmin DEGISSIN (plato kirilsin) + best < {ONCEKI_OPTCUT}\n", flush=True)
    best, bt, iters = run(nJob, nMachine, c1, c2, readyTime, processTime, setupTime,
                          I_l, L_i, total_time_limit=300, time_limit=1)
    dt = "DAHA IYI ✅" if best < ONCEKI_OPTCUT else ("AYNI" if best == ONCEKI_OPTCUT else "DAHA KOTU")
    print(f"\nSONUC: arc-relax-best={best:.0f}  (onceki optcut {ONCEKI_OPTCUT} -> {dt})", flush=True)
    print(f"       orijinal HLBB=42870 | referans CP={CP}, GA=35688, SA={SA}", flush=True)
    print(f"       -> master_tahmin yukarida ATAMADAN ATAMAYA DEGISTI mi? Degistiyse "
          f"kume-farkinda relaxation master'i artik yonlendiriyor demektir.", flush=True)


if __name__ == "__main__":
    mp.set_start_method("spawn")
    main()
