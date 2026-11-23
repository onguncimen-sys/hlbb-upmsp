# -*- coding: utf-8 -*-
"""HLBB-HM  --  heuristic master (fix-and-optimize / LNS), plain unified variant.

DESIGN (one loop, one master call, one knob B, no size-dependent branching -- a SINGLE
heuristic master):
  Each iteration the master solves a WINDOWED fix-and-optimize arc MIP (with no-goods). The
  window starts at the bottleneck machine and adds the least-loaded machines until the JOB
  BUDGET B (~150 jobs) is filled. Subproblem = LKH (per-machine ATSP setup sequencing).
  ILS + SPP hybrid intensification.
  The ONLY mechanism is "solve an arc MIP over a machine window". The exact/heuristic
  distinction arises from the WINDOW SIZE, not from separate code (a degenerate LNS property):
    * n <= B (small, ~<=150): all jobs fit the budget -> window = ALL machines -> the call is
                              the full arc formulation over all jobs/machines, i.e. the
                              PROD-exact model (100x15: HM 177 = PROD 177). "Exact is the degenerate case
                              where the window covers everything."
    * n >  B (large):         window = bottleneck subset -> small arc MIP = windowed-LNS
                              heuristic. No full-formulation solve -> the n*m binary blow-up is
                              ruled out structurally.
  So exact is used exactly where it is CHEAP (small) and degrades to a window by itself where
  it is EXPENSIVE (large) -- a single knob B, no explicit switch. (Not "no exact at all";
  only no GLOBAL exact on large instances.)

EMPIRICAL RATIONALE (90s, niche r0, single instance) -- the real competitor is CP (external
baseline), not our exact variant:
  100x15: HM 177  (PROD-exact 177)              -> tie
  250x20: HM 280  vs CP 286 (CP's own optimality gap at the limit: 80%) -> HM BEATS CP (PROD-exact 244 = bonus)
  400x20: HM 372  vs PROD-exact 445 (arcs dead) -> HM dominates
  800x30: HM 393  vs PROD-exact 439 (arcs dead) -> HM dominates; CP not close
  => In this probe HM ties the exact variant on the small instance and beats the external CP
     baseline where CP was run (and CP is not close at 800x30); exact being
     better on small instances (244) is a bonus, not a requirement. NOTE: multi-instance/seed
     and SA/GA robustness not yet verified.

DOES NOT MODIFY EXISTING FILES: route_per_machine, ils, spp_recombine are imported read-only.
lbbd_arc_relax / integrated_hlbb / HLBB stay unchanged. The certified LB (lb_motor) is kept
separate, so provability is preserved. estSetup is never used.

Smoke test: python3 hlbb_hm.py [dataset_dir/inst] [budget=60] [win_budget=150]
"""
import time
import sys
import multiprocessing as mp

import numpy as np
from gurobipy import GRB, Model, quicksum

from methods import env
from readproblem import readproblem
from HLBB import clear_environment, _close_lkh_pool
from lbbd_optcut_try import route_per_machine
from intensify import ils
from spp_recombine import spp_recombine, LAST as _SPP_LAST

WIN_K = 30    # candidate predecessors per (job, machine) in the window (same as arc master)


def greedy_lpt(nJob, nMachine, readyTime, processTime, L_i):
    """LPT-like list scheduling: assign each job (largest processing first) to the
    least-loaded eligible machine. Same rule as the greedy in integrated_hlbb -> initial
    incumbent."""
    load = [float(readyTime[l]) for l in range(nMachine)]
    A = [[] for _ in range(nMachine)]
    order = sorted(range(nJob), key=lambda i: -max((processTime[l][i] for l in L_i[i]), default=0.0))
    for i in order:
        bl = min(L_i[i], key=lambda l: load[l] + processTime[l][i])
        A[bl].append(i)
        load[bl] += processTime[bl][i]
    return A


def pick_window(A, h, nMachine, win_budget, center):
    """Start from the bottleneck 'center'; add the least-loaded machines (low h) until the
    job budget B is filled. If n<=B all machines enter (window=all -> exact). At least 2
    machines."""
    win = [center]
    jobs = len(A[center])
    for l in sorted(range(nMachine), key=lambda m: h[m]):
        if l == center:
            continue
        cnt = len(A[l])
        if jobs + cnt > win_budget and len(win) >= 2:
            break
        win.append(l)
        jobs += cnt
    return win


def solve_master_fixopt(win, A, c1, c2, processTime, setupTime, I_l, L_i,
                        readyTime, bias, nogoods, master_tl, K=WIN_K):
    """Same as the arc master but only over the 'win' machines and the jobs on them; the rest
    stays fixed. No-goods are RESTRICTED to the window jobs (with window=all this matches the
    PROD no-good exactly). The identity assignment is always feasible.
    Returns {l: [jobs...]} or None."""
    winset = set(win)
    J = [i for l in win for i in A[l]]
    if not J:
        return None
    Jset = set(J)
    elig = {i: [l for l in L_i[i] if l in winset] for i in J}

    mdl = Model("fixopt", env=env)
    y = {}
    for i in J:
        for l in elig[i]:
            y[i, l] = mdl.addVar(vtype=GRB.BINARY, name=f"y_{i}_{l}")
    s = {l: mdl.addVar(vtype=GRB.CONTINUOUS, name=f"s_{l}") for l in win}
    cmax = mdl.addVar(vtype=GRB.CONTINUOUS, name="cmax")
    mdl.setObjective(cmax, GRB.MINIMIZE)
    for l in win:
        mdl.addConstr(cmax >= s[l])

    jobs_on = {l: [i for i in J if l in elig[i]] for l in win}
    u = {}
    if readyTime is not None or bias is not None:
        for l in win:
            u[l] = mdl.addVar(vtype=GRB.BINARY, name=f"u_{l}")
            if jobs_on[l]:
                mdl.addConstr(quicksum(y[i, l] for i in jobs_on[l]) <= len(jobs_on[l]) * u[l])

    arcs = {l: {} for l in win}
    x = {}
    xd = {}
    for l in win:
        for i in jobs_on[l]:
            cand = sorted((j for j in jobs_on[l] if j != i), key=lambda j: setupTime[l][j][i])[:K]
            arcs[l][i] = cand
            for j in cand:
                x[j, i, l] = mdl.addVar(lb=0, ub=1, vtype=GRB.CONTINUOUS, name=f"x_{j}_{i}_{l}")
            xd[i, l] = mdl.addVar(lb=0, ub=1, vtype=GRB.CONTINUOUS, name=f"xd_{i}_{l}")

    for l in win:
        for i in jobs_on[l]:
            mdl.addConstr(quicksum(x[j, i, l] for j in arcs[l][i]) + xd[i, l] == y[i, l])
            for j in arcs[l][i]:
                mdl.addConstr(x[j, i, l] <= y[j, l])
        if jobs_on[l]:
            mdl.addConstr(quicksum(xd[i, l] for i in jobs_on[l]) <= 1)

    for l in win:
        ready_term = readyTime[l] * u[l] if readyTime is not None else 0
        bias_term = bias[l] * u[l] if bias is not None else 0
        mdl.addConstr(
            s[l] >= ready_term + bias_term +
                    quicksum(processTime[l][i] * y[i, l] for i in jobs_on[l]) +
                    quicksum(setupTime[l][j][i] * x[j, i, l]
                             for i in jobs_on[l] for j in arcs[l][i]))

    for i in J:
        mdl.addConstr(quicksum(y[i, l] for l in elig[i]) == 1)
    for l in win:
        mdl.addConstr(quicksum(y[i, l] for i in jobs_on[l]) >= c1[str(l)])
        mdl.addConstr(quicksum(y[i, l] for i in jobs_on[l]) <= c2[str(l)])

    # No-goods (restricted to the window): keep the master from repeating a previous window
    # assignment -> exploration. With window=all this is the full PROD no-good; with a
    # partial window it acts only on the window jobs.
    for S_list in nogoods:
        terms = []
        for l in win:
            sset = set(S_list[l]) & Jset
            terms.append(quicksum(1 - y[i, l] for i in sset if l in elig[i]))
            terms.append(quicksum(y[i, l] for i in jobs_on[l] if i not in sset))
        mdl.addConstr(quicksum(terms) >= 1)

    # SECONDARY OBJECTIVE (plateau breaker). The master objective is pure min-max: it CANNOT
    # distinguish machines within the top band (100,100,100,60 and 100,80,70,60 look the
    # same to it). Measured: final solutions also show a top plateau (on 800x30, 31% of the
    # machines are within 1% of the makespan).
    #   sum  : cmax + w * mean(s)            -- also pushes total load down
    #   topk : cmax + w * mean(largest k)    -- targets the top band DIRECTLY
    # topk uses the LP representation of the sum of the k largest (Rockafellar-Uryasev):
    #   sum_{k largest} s = min_t { k*t + sum_l (s_l - t)^+ }
    # The outer min holds automatically because the objective is minimized; no binary
    # variables needed. Dividing by k puts the term on the SAME scale as cmax -> w stays
    # interpretable.
    if sec_obj == "sum":
        mdl.setObjective(cmax + sec_w * quicksum(s[l] for l in range(nMachine)) / nMachine,
                         GRB.MINIMIZE)
    elif sec_obj == "topk":
        _t = mdl.addVar(lb=-GRB.INFINITY, name="owa_t")
        _v = {l: mdl.addVar(lb=0, name=f"owa_v_{l}") for l in range(nMachine)}
        for l in range(nMachine):
            mdl.addConstr(_v[l] >= s[l] - _t)
        _kk = max(1, min(int(sec_k), nMachine))
        mdl.setObjective(cmax + sec_w * (_kk * _t + quicksum(_v[l] for l in range(nMachine))) / _kk,
                         GRB.MINIMIZE)
    mdl.Params.TimeLimit = master_tl
    mdl.setParam("OutputFlag", 0)
    mdl.setParam("Seed", 1)
    mdl.optimize()
    try:
        return {l: [i for i in jobs_on[l] if y[i, l].X > 0.5] for l in win}
    except AttributeError:
        return None


def _route(assign, readyTime, processTime, setupTime):
    return route_per_machine(assign, readyTime, processTime, setupTime, 1)


def run_integrated_hm(nJob, nMachine, c1, c2, readyTime, processTime, setupTime, I_l, L_i,
                      total_time_limit=300, master_tl=3, seed=0, max_iter=100000,
                      win_budget=150, use_spp=True, spp_tl=20, ils_tl=3, kick=3, ils_margin=0.05,
                      return_solution=False, verbose=False):
    """Plain unified HLBB-HM. Greedy incumbent -> each iteration: pick window (B) ->
    fix-and-optimize (with no-goods) -> route -> selective ILS -> update best/pool/no-goods
    -> SPP. For n<=B this equals PROD; for n>B it is windowed LNS."""
    clear_environment(); _close_lkh_pool()
    start = time.time()
    rng = np.random.default_rng(seed * 7919 + 1)
    nogoods = []; pool = []

    A = greedy_lpt(nJob, nMachine, readyTime, processTime, L_i)
    h = _route(A, readyTime, processTime, setupTime)
    best = max(h); best_assign = [list(m) for m in A]; h_best = list(h); best_time = time.time() - start
    pool.append([list(m) for m in A])
    iters = 0; n_ils = 0; win_stuck = 0

    while time.time() - start < total_time_limit and iters < max_iter:
        iters += 1
        clear_environment()
        # window center: the bottleneck; if stuck, random among the 5 most loaded (diversity)
        if win_stuck == 0:
            center = max(range(nMachine), key=lambda l: h_best[l])
        else:
            topk = sorted(range(nMachine), key=lambda l: -h_best[l])[:min(5, nMachine)]
            center = int(rng.choice(topk))
        win = pick_window(best_assign, h_best, nMachine, win_budget, center)

        newassign = solve_master_fixopt(win, best_assign, c1, c2, processTime, setupTime,
                                        I_l, L_i, readyTime, None, nogoods, master_tl)
        if newassign is None:
            win_stuck += 1
            continue
        cand = [list(m) for m in best_assign]
        for l in win:
            cand[l] = newassign[l]
        nogoods.append([list(m) for m in cand])          # raw proposal as no-good (exploration)
        h_c = _route(cand, readyTime, processTime, setupTime)
        mk_c = max(h_c)
        pool.append([list(m) for m in cand])

        # selective ILS: intensify if the candidate is promising (within margin of best)
        if mk_c <= best * (1 + ils_margin):
            res = ils([list(m) for m in cand], [0.0] * nMachine, readyTime, processTime, setupTime,
                      I_l, c1, c2, budget=ils_tl, kick=kick, seed=seed * 100000 + iters,
                      use_swap=True, pool_k=5, anchor=[list(m) for m in cand])
            n_ils += 1
            pool.extend(res.get("pool_lkh", []))
            if res["lkh_best_mk"] < mk_c - 1e-6:
                cand = res["lkh_best_assign"]
                h_c = _route(cand, readyTime, processTime, setupTime); mk_c = max(h_c)
            pool.append([list(m) for m in cand])

        if mk_c < best - 1e-6:
            best = mk_c; best_assign = [list(m) for m in cand]; h_best = list(h_c)
            best_time = time.time() - start; win_stuck = 0
        else:
            win_stuck += 1
        if verbose:
            print(f"  [hm] iter {iters}: |win|={len(win)} ({sum(len(best_assign[l]) for l in win)} is) "
                  f"-> mk={mk_c:.0f} best={best:.0f}", flush=True)

    ils_best = best
    if use_spp and len(pool) >= 2:
        spp_mk, spp_assign = spp_recombine(pool, nJob, nMachine, readyTime, processTime, setupTime, tl=spp_tl)
        if spp_mk is not None and spp_mk < best - 1e-6:
            best = round(spp_mk, 1); best_time = time.time() - start; best_assign = spp_assign
        print(f"[HM-SPP] havuz={len(pool)} -> pre={ils_best:.0f} -> SPP-best={best:.0f} "
              f"({'iyilesti' if best < ils_best else 'ayni'})", flush=True)
    _close_lkh_pool(); clear_environment()
    print(f"[HM] iter={iters} (ILS {n_ils}x), wall={time.time()-start:.0f}s, best={best:.0f}, "
          f"t-best={best_time:.0f}s, win_budget={win_budget}", flush=True)
    if return_solution:
        return best, best_time, iters, best_assign
    return best, best_time, iters


# ======================================================================================
# SIZE-REDUCED GLOBAL MASTER (size-reduction idea of Fanjul-Peyro & Ruiz 2011/2019)
# Only the k BEST (lowest processing time) eligible machines per job -> the n*m binaries
# shrink to ~n*k -> the GLOBAL exact arc master solves in ~3s even on large instances.
# Alternative to windowed LNS: the master stays GLOBAL (the moat is kept), no size-dependent
# branching (k is uniform). estSetup is never touched.
# ======================================================================================
def _ap_duals(C):
    """OPTIMAL dual potentials (u, v) of the assignment problem -- shortest augmenting path
    (Jonker-Volgenant), vectorized with numpy. C: n x n FINITE cost matrix.
    Guarantees: C - u[:,None] - v[None,:] >= 0 everywhere, equality on the optimal
    assignment, and sum(u)+sum(v) = optimal AP cost (strong duality). All three properties
    were tested. scipy.linear_sum_assignment returns the optimal ASSIGNMENT but not the
    POTENTIALS; the potentials are what we need."""
    n = C.shape[0]
    u = np.zeros(n + 1); v = np.zeros(n + 1)
    p = np.zeros(n + 1, dtype=np.int64); way = np.zeros(n + 1, dtype=np.int64)
    for i in range(1, n + 1):
        p[0] = i; j0 = 0
        minv = np.full(n + 1, np.inf); used = np.zeros(n + 1, dtype=bool)
        while True:
            used[j0] = True
            i0 = p[j0]
            free = ~used; free[0] = False
            cur = C[i0 - 1, :] - u[i0] - v[1:]
            upd = free[1:] & (cur < minv[1:])
            minv[1:][upd] = cur[upd]
            way[1:][upd] = j0
            masked = np.where(free[1:], minv[1:], np.inf)
            j1 = int(np.argmin(masked)) + 1
            delta = masked[j1 - 1]
            u[p[used]] += delta
            v[used] -= delta
            minv[free] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]; p[j0] = p[j1]; j0 = j1
    return u[1:], v[1:]


# COLUMN SUPPLY MEASUREMENT (same pattern as spp_recombine.LAST: the harness reads it after
# the run). Does NOT change the algorithm, only reports. Fields:
#   pool_n         number of columns offered to the terminal SPP
#   pool_distinct  how many of them are DISTINCT assignments (diversity; a large pool_n with
#                  a small distinct count means the loop is repeating itself)
#   harvest        number of columns harvested from the solution pool
#   pre_spp        best before SPP (the loop's own product)
#   post_spp       best after SPP (the final answer)
#   spp_used       number of columns the SPP actually looked at (clipped by spp_cap)
# mband: number of machines whose s[l] is within 1% of cmax in master proposals (average
# over iterations). MECHANISM MEASURE of the secondary objective -- if it works, this
# number should DROP.
# ⚠️ with tight_s/sec_obj OFF, s[l] is free and all equal cmax -> mband = nM (meaningless).
SUPPLY = {"pool_n": None, "pool_distinct": None, "harvest": None, "mband": None,
          "pre_spp": None, "post_spp": None, "spp_used": None,
          # TIME SHARES (measurement only, not read by the algorithm): route_s = total
          # seconds spent routing during the loop, loop_s = the loop itself. The "routing
          # takes X% of iteration time" claim in paper Sec. 3.3 is computed from these two.
          "route_s": None, "loop_s": None,
          # did the SPP MIP PROVE optimality (spp_recombine.LAST): st=2 OPTIMAL, 9 TIME_LIMIT
          "mip_st": None, "mip_gap": None,
          # RESERVE MEASUREMENT: the formula PREDICTS R as "rt_ema x 250 x 1.2 + 14"; the
          # fields below give the REALIZED values. reserve = last computed R.
          # spp_* fields are copied from spp_recombine.LAST. Formula error =
          # reserve - (spp_route_s + spp_build_s + spp_mip_s).
          "reserve": None, "spp_route_s": None, "spp_build_s": None, "spp_mip_s": None,
          "spp_n_uniq": None, "spp_n_routed": None, "spp_n_cols": None}

_ARC_CACHE = {}          # (id(setup_l), l, K, mode, Ir) -> (REFERENCE to setup_l, cand dict)
ARC_CACHE_ON = True      # False => recompute on every master call = the cache-free behavior.
                         # Candidate lists come out IDENTICAL throughout a run anyway, so the
                         # cache changes only the TIME, not the output (~54 ms/call on
                         # 800x30). The paper's numbers were run cache-free; set this to
                         # False for an exact reproduction.


def _alpha_lists(processTime, setupTime, l, idx, K):
    """LKH's OWN alpha-nearness candidate set (Helsgaun 2000). None = failure.

    WHY ask LKH: alpha is the cost of FORCING the arc into the 1-tree relaxation; since a
    1-tree is CONNECTED, the measure sees "usability within a tour". Our `ap` measure rests
    on the assignment relaxation and is BLIND TO SUBTOURS. Helsgaun makes this distinction
    explicitly (EJOR 126, p.116). LKH already computed this on every call; it is written out
    via `CANDIDATE_FILE` and read back (ReadParameters.c:43-52).

    The matrix is the SAME one the router solves (tour_capture.py:104-118): node 0 is the
    depot, mat[a][b] = pt[b] + st[a][b]. The master's arc term is pure setup, but alpha's
    claim is "a measure on the instance LKH actually solves", so that instance is used.

    Node mapping verified against the SOURCE (LKH-3.0.7/SRC/Distance.c:28-36): in the
    asymmetric case n=DimensionSaved, 1..n are out-copies, n+1..2n in-copies, symmetric edge
    (a, b+n) <-> ATSP arc a->b; (i, i+n) is a fixed edge (FixEdge, ReadProblem.c:1472).
    """
    import os as _os, glob as _glob, uuid as _uuid, subprocess as _sp
    from HLBB import tsplib_file_generator as _gen
    nn = len(idx)
    mat = np.zeros((nn + 1, nn + 1))
    pt_l, st_l = processTime[l], setupTime[l]
    for a in range(nn + 1):
        for b in range(nn + 1):
            if b == 0:
                mat[a][b] = 0.0
            elif a == 0:
                mat[a][b] = float(pt_l[idx[b - 1]])
            elif a == b:
                mat[a][b] = 2000.0                              # same BigM as tour_capture
            else:
                mat[a][b] = float(pt_l[idx[b - 1]]) + float(st_l[idx[a - 1]][idx[b - 1]])
    mat[0][0] = 2000.0

    name = "cand_" + _uuid.uuid4().hex[:12]
    base = "LKH-3.0.7/ATSP"
    try:
        _gen(name, mat)
        with open(f"{base}/{name}.par", "w") as f:
            f.write(f"PROBLEM_FILE = ATSP/{name}.atsp\nMAX_CANDIDATES = {max(K, 5)}\n"
                    f"CANDIDATE_SET_TYPE = ALPHA\nCANDIDATE_FILE = ATSP/{name}.cand\n"
                    "MAX_TRIALS = 1\nRUNS = 1\nSEED = 1\nPRECISION = 1\nTIME_LIMIT = 5\n")
        _sp.check_output(f"./LKH ATSP/{name}.par", shell=True, cwd="LKH-3.0.7/",
                         stderr=_sp.STDOUT, timeout=30)
        out = _parse_cand(f"{base}/{name}.cand", nn, idx)
    except Exception:
        out = None
    finally:
        for fn in _glob.glob(f"{base}/{name}.*"):
            try:
                _os.remove(fn)
            except OSError:
                pass
    return out


def _parse_cand(path, nn, idx):
    """CANDIDATE_FILE parser. Format: first line is the node count; each line is
    `node dad count (end_node alpha)*`; the file ends with "-1"/"EOF".
    Returns None if parsing is DOUBTFUL (never silently produces a wrong list)."""
    import os as _os
    if not _os.path.exists(path):
        return None
    N = nn + 1                                       # ATSP node count (incl. depot)
    lines = [ln.split() for ln in open(path) if ln.strip()]
    if not lines or int(lines[0][0]) != 2 * N:
        return None
    per = {}
    for parts in lines[1:]:
        if not parts[0].lstrip("-").isdigit() or parts[0] == "-1":
            break
        v = list(map(int, parts))
        node, cnt = v[0], v[2]
        if len(v) < 3 + 2 * cnt:
            return None
        per[node] = [(v[3 + 2 * t], v[4 + 2 * t]) for t in range(cnt)]
    if len(per) != 2 * N:
        return None
    for h in range(1, N + 1):                        # DIRECTION CHECK: fixed mate present?
        if h not in [e for e, _ in per.get(h + N, [])]:
            return None
    res = {}
    for h in range(2, N + 1):                        # ATSP node h -> job idx[h-2]
        res[idx[h - 2]] = [idx[e - 2] for e, _a in sorted(per[h + N], key=lambda z: z[1])
                           if e <= N and e != h and e != 1]     # drop same-side/fixed-mate/depot
    return res


def _repair_matching(raw, idx, out, K):
    """GUARANTEES that the candidate arc set contains A VALID ASSIGNMENT. K is UNCHANGED.

    WHY. The master's machine-l arc structure (lines 388-406) is an assignment relaxation:
    each job has one predecessor, each job precedes at most one successor, and
    `sum_i xd[i,l] <= 1` allows only ONE route start. If the candidate set contains no
    perfect matching, the master CANNOT place all jobs on that machine -- the machine
    effectively closes. Measured (800x30, K=5): with raw-cost ranking 46% of the machines
    are in this state; `rc` ranking brings this down to 47 out of 48 but does NOT GUARANTEE
    it -- it happens as a side effect of the measure.

    HOW. Solve the assignment-problem optimum pi of the dense matrix (scipy). pi gives
    every job a predecessor and is BY DEFINITION a valid assignment. For each job i whose
    pi(i) is not in the list, REPLACE the LAST (worst-ranked) element with it. Result: pi
    sits inside the set as a WITNESS, so a valid assignment EXISTS; and |list| = K stays
    fixed, the model does NOT GROW.

    CONDITIONAL: the existing list is TESTED first. If it already contains an assignment,
    nothing is changed -- the repair acts only on broken machines. (Unconditional
    pi-insertion was tried: it also dropped the K-th candidate on healthy lists, i.e.
    guarantee+noise instead of a guarantee; it needlessly changed 0.6% of the jobs.)

    SCOPE: the guarantee is for the WHOLE of Ir_l. The master may pick a subset; the same
    guarantee is not given for every subset. The measured defect was at the full-set level
    anyway."""
    from scipy.optimize import linear_sum_assignment
    nn = len(idx)
    pos = {j: p for p, j in enumerate(idx)}
    BIG = float(raw.max()) * nn + 1.0

    # --- TEST: does the current candidate set contain an assignment?
    C = np.full((nn, nn), BIG)
    for i in idx:
        for j in out[i]:
            if j != i:
                C[pos[j], pos[i]] = raw[pos[j], pos[i]]
    np.fill_diagonal(C, BIG)
    r0, c0 = linear_sum_assignment(C)
    if not (C[r0, c0] >= BIG - 1e-9).any():
        _repair_matching.last_fixed = 0
        return out                                     # HEALTHY -> leave untouched

    # --- REPAIR: the dense matrix's assignment optimum pi is a WITNESS; insert missing pi(i)
    D = raw.copy()
    np.fill_diagonal(D, BIG)
    rows, cols = linear_sum_assignment(D)
    tail_of = {idx[c]: idx[r] for r, c in zip(rows, cols)}   # column=successor, row=predecessor
    n_fix = 0
    for i in idx:
        t = tail_of.get(i)
        if t is None or t == i or t in out[i]:
            continue
        lst = out[i]
        if len(lst) >= K:
            lst[-1] = t                                # K FIXED: replace the worst candidate
        else:
            lst.append(t)
        n_fix += 1
    _repair_matching.last_fixed = n_fix                # diagnostic (not read in production)
    return out


def arc_candidates(setupTime, l, Ir_l, K, mode="cost", processTime=None):
    """K predecessor candidates per job on machine l. SINGLE SOURCE: production and ablation
    call the same function (no copies -> no divergence). The returned dict is CACHED; do NOT
    mutate it.

    mode="cost"  : by raw setup time (PRODUCTION DEFAULT, identical to the old behavior).
    mode="rc"    : row+column reduction (first two steps of the Hungarian method). CHEAP
                   proxy.
    mode="rcfix" : "rc" + MATCHING REPAIR (_repair_matching). The candidate set is
                   GUARANTEED to contain a valid assignment; K stays fixed, the model does
                   not grow.
    mode="costfix": "cost" + the same repair. MECHANISM TEST: directly probes the claim
                   "the gain belongs to the REPAIR, not the measure" -- the ranking stays
                   the production raw cost, only the matching is repaired. If it approaches
                   `rc`, the claim is confirmed.
    mode="alpha" : LKH's own alpha-nearness set (see _alpha_lists). processTime REQUIRED.
                   If LKH fails, falls back SILENTLY to "rc" (no crash in production).
    mode="ap"    : OPTIMAL dual potentials of the assignment relaxation (_ap_duals).
                  rc[j][i] = s[j][i] - u[j] - v[i] = "how much EXTRA using this arc costs
                  relative to the best alternatives available to its two endpoints".

    The idea follows Helsgaun's (2000, LKH) alpha-nearness: rank the candidate list not by
    raw cost but by the extra paid relative to a RELAXATION. With the right measure 5
    candidates find the optimum on all test problems, with raw cost 20+ are needed -> the
    ranking measure matters more than the candidate COUNT. Alpha itself is 1-tree based and
    for SYMMETRIC TSP; our machine subproblem is asymmetric, so the counterpart is the
    assignment relaxation. Ties are broken by raw cost (Helsgaun's tie-break).
    """
    key = (id(setupTime[l]), l, K, mode, tuple(Ir_l)) if ARC_CACHE_ON else None
    if key is not None:
        hit = _ARC_CACHE.get(key)
        if hit is not None:
            return hit[1]
    if mode in ("cost", "costfix") or len(Ir_l) <= 2:
        out = {i: sorted((j for j in Ir_l if j != i),
                         key=lambda j: setupTime[l][j][i])[:K] for i in Ir_l}
        if mode == "costfix" and len(Ir_l) > 2:
            idx = list(Ir_l)
            out = _repair_matching(np.asarray(setupTime[l], dtype=float)[np.ix_(idx, idx)],
                                   idx, out, K)
    else:
        idx = list(Ir_l)
        raw = np.asarray(setupTime[l], dtype=float)[np.ix_(idx, idx)]
        if mode == "alpha":
            if processTime is None:
                raise ValueError("arc_rank='alpha' processTime gerektirir")
            al = _alpha_lists(processTime, setupTime, l, idx, K)
            if al is not None:
                # Compute the "rc" base as a FILLER: if the alpha list comes back shorter
                # than K (LKH prunes on its own), COMPLETE it from rc. The aim is to keep K
                # FIXED across arms -- what is tested is the candidate RANKING, not the
                # COUNT. Measured: the short-list rate is 0.0-0.2% on 400x20/800x30, so
                # this path almost never runs.
                S = raw.copy()
                np.fill_diagonal(S, np.inf)
                S = S - S.min(axis=1, keepdims=True)
                S = S - S.min(axis=0, keepdims=True)
                np.fill_diagonal(S, np.inf)
                out = {}
                for p, i in enumerate(idx):
                    got = [j for j in al.get(i, []) if j != i][:K]
                    if len(got) < K:
                        seen = set(got)
                        for q in np.lexsort((raw[:, p], S[:, p])):
                            j = idx[q]
                            if j != i and j not in seen:
                                got.append(j); seen.add(j)
                                if len(got) == K:
                                    break
                    out[i] = got
                if key is not None:
                    _ARC_CACHE[key] = ((setupTime[l], processTime[l]), out)
                return out
            mode = "rc"                        # LKH failed -> fall back to the safe base
        if mode == "ap":
            C = raw.copy()
            np.fill_diagonal(C, raw.max() * len(idx) + 1.0)   # diagonal FORBIDDEN (finite big-M)
            uu, vv = _ap_duals(C)
            S = C - uu[:, None] - vv[None, :]
        else:                                                  # "rc"
            S = raw.copy()
            np.fill_diagonal(S, np.inf)
            S = S - S.min(axis=1, keepdims=True)               # each job's cheapest OUT-arc
            S = S - S.min(axis=0, keepdims=True)               # each job's cheapest IN-arc
        np.fill_diagonal(S, np.inf)
        out = {}
        for p, i in enumerate(idx):
            order = np.lexsort((raw[:, p], S[:, p]))            # primary rc, ties by raw cost
            out[i] = [idx[q] for q in order if idx[q] != i][:K]
        if mode == "rcfix":
            out = _repair_matching(raw, idx, out, K)
    if key is not None:
        _ARC_CACHE[key] = (setupTime[l], out)  # REFERENCE to the array: its id cannot be reused
    return out


def solve_master_sizered(nJob, nMachine, c1, c2, processTime, setupTime, I_l, L_i,
                         nogoods, master_tl, readyTime=None, bias=None, kmach=5, K=10,
                         hint=None, kcap=None, rank=None, use_degree=True, warm=None,
                         pool_mode=None, pool_k=0, pool_sink=None, arc_rank="cost",
                         tight_s=False, sec_obj="off", sec_k=3, sec_w=0.1, extra=None, arc_keep=False,
                         diag=None):
    # SIZE REDUCTION: the k best eligible machines per job. If rank is given (setup-aware
    # ranking: processing + mean setup) use it; otherwise rank by pure processing time (kJB).
    # DIG-GUIDED (Fanjul-Peyro 3JD): if hint is given (machines the pool placed that job
    # on), it is added to the reduced set (search-informed), capped by kcap.
    cap = kcap if kcap is not None else (kmach + 2)
    allowed = {}
    allowed0 = {}                      # set BEFORE machine-side additions (only for arc_keep)
    for i in range(nJob):
        if rank is not None:
            base = list(rank[i][:max(1, min(kmach, len(rank[i])))])
        else:
            base = sorted(L_i[i], key=lambda l: processTime[l][i])[:max(1, min(kmach, len(L_i[i])))]
        if hint is not None and hint[i]:
            for l in hint[i]:
                if l in L_i[i] and l not in base:
                    base.append(l)
            base = base[:cap]
        if extra is not None:
            # MACHINE SIDE (Fanjul-Peyro & Ruiz 2011 "lMB", 3J2M): the jobs each machine
            # processes fastest are candidates too. No cap (as in the source); precomputed
            # in run_integrated_sr.
            allowed0[i] = list(base)
            for l in extra[i]:
                if l not in base:
                    base.append(l)
        allowed[i] = base
    Ir = {l: [i for i in range(nJob) if l in allowed[i]] for l in range(nMachine)}

    mdl = Model("MIP-A-sizered", env=env)
    y = {}
    for i in range(nJob):
        for l in allowed[i]:
            y[i, l] = mdl.addVar(vtype=GRB.BINARY, name=f"y_{i}_{l}")
    s = {l: mdl.addVar(vtype=GRB.CONTINUOUS, name=f"s_{l}") for l in range(nMachine)}
    cmax = mdl.addVar(vtype=GRB.CONTINUOUS, name="cmax")
    mdl.setObjective(cmax, GRB.MINIMIZE)
    for l in range(nMachine):
        mdl.addConstr(cmax >= s[l])
    u = {}
    if readyTime is not None or bias is not None:
        for l in range(nMachine):
            u[l] = mdl.addVar(vtype=GRB.BINARY, name=f"u_{l}")
            if Ir[l]:
                mdl.addConstr(quicksum(y[i, l] for i in Ir[l]) <= len(Ir[l]) * u[l])
    arcs = {l: arc_candidates(setupTime, l, Ir[l], K, arc_rank, processTime)
            for l in range(nMachine)}
    if arc_keep and extra is not None:
        # ARC-PRESERVING machine side: when Ir[l] grows, OLD jobs' predecessor lists were
        # rebuilt and 5-8% of their slots shifted to new jobs -> good production assignments
        # became impossible for the main model. Old pairs take their lists UNCHANGED from
        # the old set (Ir0); only new pairs use the enlarged set. With the new y's at zero
        # the model matches production exactly (a true superset); K does not grow.
        Ir0 = {l: [i for i in range(nJob) if l in allowed0.get(i, allowed[i])] for l in range(nMachine)}
        for l in range(nMachine):
            a0 = arc_candidates(setupTime, l, Ir0[l], K, arc_rank, processTime)
            old = set(Ir0[l])
            arcs[l] = {i: (a0[i] if i in old else arcs[l][i]) for i in Ir[l]}
    x = {}; xd = {}
    for l in range(nMachine):
        for i in Ir[l]:
            cand = arcs[l][i]
            for j in cand:
                x[j, i, l] = mdl.addVar(lb=0, ub=1, vtype=GRB.CONTINUOUS, name=f"x_{j}_{i}_{l}")
            xd[i, l] = mdl.addVar(lb=0, ub=1, vtype=GRB.CONTINUOUS, name=f"xd_{i}_{l}")
    for l in range(nMachine):
        for i in Ir[l]:
            mdl.addConstr(quicksum(x[j, i, l] for j in arcs[l][i]) + xd[i, l] == y[i, l])
            for j in arcs[l][i]:
                mdl.addConstr(x[j, i, l] <= y[j, l])
        if Ir[l]:
            mdl.addConstr(quicksum(xd[i, l] for i in Ir[l]) <= 1)
    # H1 (Hooker LBBD Sec. 4.6.1): put the subproblem relaxation into the master. The
    # missing half of the ATSP assignment relaxation = OUT-DEGREE. In-degree
    # (sum_j x[j,i]+xd[i]=y[i]) existed but out-degree did not -> the LP made a job j the
    # predecessor of several successors and underestimated setup (makespan plateau).
    # sum_i x[j,i,l] <= y[j,l]: each job precedes at most 1 successor. A valid LB tightening
    # (out-degree<=1 on a real path); it moves the master's s[l] estimate toward reality ->
    # the certified LB rises.
    if use_degree:
        succ = {l: {} for l in range(nMachine)}
        for l in range(nMachine):
            for i in Ir[l]:
                for j in arcs[l][i]:
                    succ[l].setdefault(j, []).append(i)          # j -> [successor i's]
        for l in range(nMachine):
            for j, succs in succ[l].items():
                mdl.addConstr(quicksum(x[j, i, l] for i in succs) <= y[j, l])
    for l in range(nMachine):
        ready_term = readyTime[l] * u[l] if readyTime is not None else 0
        bias_term = bias[l] * u[l] if bias is not None else 0
        _load = (ready_term + bias_term +
                 quicksum(processTime[l][i] * y[i, l] for i in Ir[l]) +
                 quicksum(setupTime[l][j][i] * x[j, i, l] for i in Ir[l] for j in arcs[l][i]))
        # ⚠️ s[l] does NOT appear in the objective and is tied only by `cmax >= s[l]` ->
        # Gurobi leaves it FREE in [LB_l, cmax] (measured: all s_vals = cmax = 202.0). Two
        # consequences: (a) bias is fed from s_vals, so the bias input is BROKEN; (b) the
        # secondary objective cannot be built on s. tight_s makes it an equality -> fixes
        # both. With sec_obj on, equality is MANDATORY (else the secondary term is
        # meaningless).
        if tight_s or sec_obj != "off":
            mdl.addConstr(s[l] == _load)
        else:
            mdl.addConstr(s[l] >= _load)
    for i in range(nJob):
        mdl.addConstr(quicksum(y[i, l] for l in allowed[i]) == 1)
    for l in range(nMachine):
        if c1[str(l)] > 0 and Ir[l]:
            mdl.addConstr(quicksum(y[i, l] for i in Ir[l]) >= c1[str(l)])
        if Ir[l]:
            mdl.addConstr(quicksum(y[i, l] for i in Ir[l]) <= c2[str(l)])
    for S_list in nogoods:
        terms = []
        for l in range(nMachine):
            sset = set(S_list[l])
            terms.append(quicksum(1 - y[i, l] for i in sset if (i, l) in y))
            terms.append(quicksum(y[i, l] for i in Ir[l] if i not in sset))
        mdl.addConstr(quicksum(terms) >= 1)
    # WARM START (partial MIPStart): hand the current best assignment as initial incumbent.
    # Jobs inside `allowed` snap into place; out-of-allowed/cardinality is completed by
    # Gurobi. Aim: with the out-degree cut ON, the master should ALWAYS find an incumbent
    # within master_tl on large instances -> NEVER return None -> the cut stays on at every
    # scale (no guard needed, the LB tightens on large too). If infeasible, Gurobi ignores
    # it (harmless). warm[l] = job list on machine l.
    if warm is not None:
        for l in range(nMachine):
            wl = [i for i in warm[l] if (i, l) in y]
            for i in wl:
                y[i, l].Start = 1.0
            if l in u:
                u[l].Start = 1.0 if wl else 0.0
    # SECONDARY OBJECTIVE (plateau breaker). The master objective is pure min-max: it CANNOT
    # distinguish machines within the top band (100,100,100,60 and 100,80,70,60 look the
    # same to it). Measured: final solutions also show a top plateau (on 800x30, 31% of the
    # machines are within 1% of the makespan).
    #   sum  : cmax + w * mean(s)            -- also pushes total load down
    #   topk : cmax + w * mean(largest k)    -- targets the top band DIRECTLY
    # topk uses the LP representation of the sum of the k largest (Rockafellar-Uryasev):
    #   sum_{k largest} s = min_t { k*t + sum_l (s_l - t)^+ }
    # The outer min holds automatically because the objective is minimized; no binary
    # variables needed. Dividing by k puts the term on the SAME scale as cmax -> w stays
    # interpretable.
    if sec_obj == "sum":
        mdl.setObjective(cmax + sec_w * quicksum(s[l] for l in range(nMachine)) / nMachine,
                         GRB.MINIMIZE)
    elif sec_obj == "topk":
        _t = mdl.addVar(lb=-GRB.INFINITY, name="owa_t")
        _v = {l: mdl.addVar(lb=0, name=f"owa_v_{l}") for l in range(nMachine)}
        for l in range(nMachine):
            mdl.addConstr(_v[l] >= s[l] - _t)
        _kk = max(1, min(int(sec_k), nMachine))
        mdl.setObjective(cmax + sec_w * (_kk * _t + quicksum(_v[l] for l in range(nMachine))) / _kk,
                         GRB.MINIMIZE)
    mdl.Params.TimeLimit = master_tl
    mdl.setParam("OutputFlag", 0)
    mdl.setParam("Seed", 1)
    if pool_mode is not None:
        # 0 = keep incidental solutions (NO EXTRA TIME) | 1 = search for more | 2 = n-best
        mdl.Params.PoolSearchMode = pool_mode
        if pool_k:
            mdl.Params.PoolSolutions = pool_k
    mdl.optimize()
    try:
        assign = [[i for i in Ir[l] if y[i, l].X > 0.5] for l in range(nMachine)]
        s_vals = [s[l].X for l in range(nMachine)]   # master's per-machine routing-LB (for bias)
    except AttributeError:
        if diag is not None:
            diag.clear(); diag.update(status=mdl.Status, solcount=mdl.SolCount, fail=1, runtime=mdl.Runtime)
        return None, None
    if diag is not None:
        # WHY: s[l] is loose -> the load is computed EXPLICITLY from the solution's y, x.
        # q = ready + processing + setup (EXCLUDING BIAS); new = pair added by the machine
        # side (not in the old set).
        _q = []; _new = []
        for l in range(nMachine):
            # u[l]=1 <=> machine used
            ql = float(readyTime[l]) if (readyTime is not None and assign[l]) else 0.0
            ql += sum(processTime[l][i] for i in assign[l])
            ql += sum(setupTime[l][j][i] * x[j, i, l].X for i in Ir[l] for j in arcs[l][i]
                      if x[j, i, l].X > 1e-9)
            _q.append(ql)
            _new.append(sum(1 for i in assign[l] if extra is not None and l not in allowed0.get(i, allowed[i])))
        diag.clear()                                      # pool new-pair count: in the harvest loop
        diag.update(q=_q, new=_new, status=mdl.Status, solcount=mdl.SolCount,
                    gap=(mdl.MIPGap if mdl.SolCount else None), runtime=mdl.Runtime, fail=0,
                    nvar_y=len(y), nvar_x=len(x))
    # MASTER SOLUTION POOL: harvest the OTHER assignments Gurobi found during the same
    # solve; they go to the pool, are not routed in the loop, and produce no no-goods
    # (screen6: -0.85 dRPD% under an equal 200s contract).
    if pool_sink is not None:
        try:
            n_extra = min(mdl.SolCount, pool_k if pool_k else mdl.SolCount)
            for si in range(1, n_extra):                 # 0 = the incumbent taken above
                mdl.Params.SolutionNumber = si
                a2 = [[i for i in Ir[l] if y[i, l].Xn > 0.5] for l in range(nMachine)]
                if sum(len(m_) for m_ in a2) == nJob:    # ROBUSTNESS: full-coverage requirement
                    pool_sink.append(a2)
                    if diag is not None and extra is not None:
                        diag.setdefault("pool_new", []).append(
                            sum(1 for l in range(nMachine) for i in a2[l] if l not in allowed0.get(i, allowed[i])))
            mdl.Params.SolutionNumber = 0
        except Exception:
            pass                                          # harvest is optional; never break the run
    return assign, s_vals


def run_integrated_sr(nJob, nMachine, c1, c2, readyTime, processTime, setupTime, I_l, L_i,
                      total_time_limit=300, master_tl=3, kmach=3, arc_k=5, seed=0, max_iter=100000,
                      use_spp=True, spp_tl=20, ils_tl=3, kick=3, ils_margin=0.05,
                      use_bias=True, bias_alpha=0.3, use_dig=False, hint_k=3, kcap=5,
                      setup_aware=False, use_degree=True, use_warm=True, use_ils=False,
                      return_solution=False, verbose=False,
                      pool_mode=1, pool_k=20, spp_cap=250, spp_cap_soft=True,
                      inside=True, arc_rank="cost",
                      # mach_side=2: machine-side candidate addition (3J2M), production
                      # default; acceptance measured with a 540-run gate experiment.
                      tight_s=False, sec_obj="off", sec_k=3, sec_w=0.1, mach_side=2,
                      mach_arc_keep=False, trace=None, reserve_pool=False, spp_self_cache=True):
    """The PROD loop but master = size-reduced GLOBAL arc master (n*k binaries). Greedy seed
    -> each iter: size-reduced master (no-goods, PRIMAL bias) -> LKH route -> selective ILS
    -> best/pool/no-good -> SPP. bias learns the master's per-machine true-routing excess.
    DIG (Fanjul-Peyro 3JD): reduced set = k-best UNION machines-the-pool-placed-that-job-on
    (capped by kcap). setup_aware: rank the k-best by processing + mean setup (instead of
    processing alone; precomputed a single time).

    POOL+INSIDE PACKAGE (validated with 216 screen6 runs, DEFAULT ON):
      pool_mode/pool_k : Gurobi solution-pool harvest -> SPP column material (free
                         diversity).
      spp_cap          : cap on distinct assignments given to the SPP (old 80 -> 250).
      inside           : the SPP runs INSIDE the total budget. The loop stops at T-reserve;
                         the reserve is computed from the routing EMA measured in-run (no
                         size branching), SPP deadline=T-2, routing is cut at
                         deadline-MIP_PAY, loop cache + periodic cleanup.
      Measurement: vs the old base under an equal 200s contract, dRPD -0.845% (21w/3t/0l),
      0 contract violations. Old behavior: pool_mode=None, spp_cap=None, inside=False."""
    from collections import Counter
    clear_environment(); _close_lkh_pool()
    start = time.time()
    nogoods = []; pool = []
    bias = [0.0] * nMachine if use_bias else None
    job_freq = [Counter() for _ in range(nJob)] if use_dig else None
    # SETUP-AWARE RANKING (static, computed at startup): key(l) = proc[l][i] + mean_j setup[l][j->i]
    rank = None
    if setup_aware:
        rank = []
        for i in range(nJob):
            key = {l: processTime[l][i] + float(np.mean(setupTime[l][:, i])) for l in L_i[i]}
            rank.append(sorted(L_i[i], key=lambda l, kk=key: kk[l]))

    # MACHINE-SIDE CANDIDATES (mach_side>0): each machine l adds the ceil(mach_side*n/m)
    # jobs it processes FASTEST among its eligible jobs (Fanjul-Peyro & Ruiz 2011, lMB;
    # mach_side=2 -> 3J2M). Static, computed at startup. In the sparse regime the "fastest
    # 3" rule was measured to exclude machines that receive almost no jobs.
    extra = None
    if mach_side and mach_side > 0:
        _a = max(1, int(np.ceil(mach_side * nJob / nMachine)))
        extra = [[] for _ in range(nJob)]
        for l in range(nMachine):
            _jobs = [i for i in range(nJob) if l in L_i[i]]
            for i in sorted(_jobs, key=lambda i: processTime[l][i])[:_a]:
                extra[i].append(l)

    def _tally(sol):
        for l in range(nMachine):
            for i in sol[l]:
                job_freq[i][l] += 1

    A = greedy_lpt(nJob, nMachine, readyTime, processTime, L_i)
    h = _route(A, readyTime, processTime, setupTime)
    best = max(h); best_assign = [list(m) for m in A]; best_time = time.time() - start
    pool.append([list(m) for m in A])
    if use_dig:
        _tally(A)
    iters = 0; n_ils = 0; mfail = 0
    deg_on = use_degree                      # H1 guard: off for good if the master returns None
    pool_sink = [] if pool_mode is not None else None   # master solution-pool harvest
    n_harvest = 0
    for _k in SUPPLY:                        # RESET the measurement fields: on an early exit
        SUPPLY[_k] = None                    # a previous run's value must not be read
    _band = []                               # see SUPPLY["mband"]
    # ---- INSIDE-200 state (entirely idle when inside=False) ----
    # rt_ema : EMA of per-assignment routing time (measured IN-RUN -> size-free rule)
    # it_ema : EMA of iteration time (prevents last-iteration overrun)
    # rcache : (machine, frozenset) -> route cost already measured in the loop (free for SPP)
    rt_ema = None; it_ema = None
    route_s = 0.0                            # MEASUREMENT: total routing time (SUPPLY)
    _R = None                                # MEASUREMENT: last computed reserve (SUPPLY)
    rcache = {} if inside else None
    # ⚠️ _cap_eff is the BASE of the reserve formula. `spp_cap_soft` does NOT change it: the
    # soft cap only widens how many assignments routing may LOOK AT, not the time set aside.
    # So the loop does not shorten (that was the cap400 arm's defect: a larger cap grew R
    # and stole from the loop). See spp_recombine(..., cap_soft=...).
    _cap_eff = (spp_cap or 80)
    _MIP_PAY = 12.0     # window always left for the SPP MIP (size-free constant)

    def _reserve():
        """Time to set aside for the SPP. The formula is the same at EVERY size; its inputs
        are in-run measurements. The 1.2 factor and _MIP_PAY were calibrated by measurement
        (too little starves the MIP and kills the gain, extra is harmless). Cap 0.30*T: the
        reserve cannot eat more than a third of the loop."""
        if rt_ema is None:
            # the initial guess is ALSO capped: on short budgets (e.g. an 8s smoke test) a
            # fixed 15 exceeded the budget and the loop never started (caught in the track A
            # pre-check)
            return min(15.0, 0.30 * total_time_limit)
        return min(max(rt_ema * _cap_use * 1.2 + _MIP_PAY + 2.0, 10.0),
                   0.30 * total_time_limit)

    # SPP_SELF_CACHE (spp_self_cache): the same (machine, job-set) is not re-routed; no
    # quality difference in measurement (-0.24 +- 0.26), 1.2-2x more assignments routed; on
    # a fixed pool the result is bit-identical.
    # RESERVE-POOL (reserve_pool, default OFF): the formula assumes the SPP will route 250
    # assignments; on runs whose pool stays smaller (400x20: 184-207 distinct) ~10-20 s of
    # the contract was wasted (results/ab_degree.csv: prod 400x20 finishes in 180 s). When
    # on, the base = min(250, an UPWARD-biased estimate of the DISTINCT pool at run end) ->
    # if the pool exceeds 250 the behavior is bit-identical. Estimate: current distinct
    # count + mean growth per iteration x remaining iterations (remaining time / iteration
    # time; reserve NOT subtracted -> overestimate, the safe direction).
    _cap_use = _cap_eff
    _psig = set(); _pidx = 0; _p0 = None

    while iters < max_iter:
        if reserve_pool and inside:
            while _pidx < len(pool):                 # the pool only grows -> incremental count
                _psig.add(tuple(frozenset(m) for m in pool[_pidx])); _pidx += 1
            if _p0 is None:
                _p0 = len(_psig)
            if it_ema is not None and iters > 0:
                _rate = (len(_psig) - _p0) / iters
                _rem = max(0.0, (total_time_limit - (time.time() - start)) / it_ema)
                _cap_use = min(_cap_eff, len(_psig) + 1 + _rate * _rem)
        _R = _reserve() if inside else None          # MEASUREMENT: same number of _reserve() calls
        _tlim = (total_time_limit - _R) if inside else total_time_limit
        _el = time.time() - start
        if _el >= _tlim or (inside and it_ema is not None and _el + it_ema > _tlim):
            break
        _t_iter0 = time.time()
        iters += 1
        clear_environment()
        hint = ([[l for l, _ in job_freq[i].most_common(hint_k)] for i in range(nJob)]
                if use_dig else None)
        _dg = {} if trace is not None else None          # DIAGNOSTIC trace (default OFF; no effect)
        assign, s_vals = solve_master_sizered(nJob, nMachine, c1, c2, processTime, setupTime, I_l, L_i,
                                              nogoods, master_tl, readyTime=readyTime, bias=bias,
                                              kmach=kmach, K=arc_k, hint=hint, kcap=kcap, rank=rank,
                                              use_degree=deg_on,
                                              warm=best_assign if use_warm else None,
                                              pool_mode=pool_mode, pool_k=pool_k, pool_sink=pool_sink,
                                              arc_rank=arc_rank, tight_s=tight_s, sec_obj=sec_obj,
                                              sec_k=sec_k, sec_w=sec_w, extra=extra,
                                              arc_keep=mach_arc_keep, diag=_dg)
        # H1 GUARD: on large instances the out-degree constraints can make the master
        # unsolvable within master_tl and return None (the 800x30 mfail collapse). On the
        # first failure turn degree off PERMANENTLY (sticky) and re-solve that iteration
        # without it -> keeps the small/medium gain, drops to OFF speed on large, NEVER
        # collapses to greedy, and pays the failed-solve cost a single time, not per
        # iteration.
        if assign is None and deg_on:
            if trace is not None:                    # DIAG: failed attempt that tripped the guard
                trace.append(dict(kind="deg_off", it=iters, t=round(time.time() - start, 2),
                                  status=_dg.get("status"), solcount=_dg.get("solcount"),
                                  runtime=_dg.get("runtime")))
            deg_on = False
            assign, s_vals = solve_master_sizered(nJob, nMachine, c1, c2, processTime, setupTime, I_l,
                                                  L_i, nogoods, master_tl, readyTime=readyTime, bias=bias,
                                                  kmach=kmach, K=arc_k, hint=hint, kcap=kcap, rank=rank,
                                                  use_degree=False,
                                                  warm=best_assign if use_warm else None,
                                                  pool_mode=pool_mode, pool_k=pool_k, pool_sink=pool_sink,
                                                  arc_rank=arc_rank, tight_s=tight_s, sec_obj=sec_obj,
                                                  sec_k=sec_k, sec_w=sec_w, extra=extra,
                                              arc_keep=mach_arc_keep, diag=_dg)
        if s_vals:
            _mx = max(s_vals)
            _band.append(sum(1 for _v in s_vals if _v >= _mx * 0.99 - 1e-9))
        if assign is None and trace is not None:
            trace.append(dict(kind="iter", it=iters, t=round(time.time() - start, 2), deg_on=int(deg_on),
                              fail=1, status=_dg.get("status"), solcount=_dg.get("solcount")))
        if assign is None:
            mfail += 1
            if mfail >= 3:
                break
            continue
        # Pool harvest -> goes STRAIGHT to the pool. Not routed (we do not want the
        # iteration count to drop) and produces no no-goods; its value lies in enriching
        # the SPP column set.
        if pool_sink:
            n_harvest += len(pool_sink)
            pool.extend(pool_sink)
            pool_sink = []
        _t_r0 = time.time()
        h_a = _route(assign, readyTime, processTime, setupTime); mk_a = max(h_a)
        route_s += time.time() - _t_r0       # MEASUREMENT (SUPPLY); no effect on flow
        if inside:
            _dt_r = time.time() - _t_r0
            rt_ema = _dt_r if rt_ema is None else 0.7 * rt_ema + 0.3 * _dt_r
            for _l in range(nMachine):
                if assign[_l]:
                    # If the same (machine, job set) is routed again, the best KNOWN value
                    # is kept (previously the last reading was written; a worse reading
                    # could make a good column look expensive in the SPP). Every value
                    # rests on a real LKH tour.
                    _rk = (_l, frozenset(assign[_l])); _ro = rcache.get(_rk)
                    rcache[_rk] = h_a[_l] if _ro is None else min(_ro, h_a[_l])
        if trace is not None:
            _pn = _dg.get("pool_new") or []
            trace.append(dict(kind="iter", it=iters, t=round(time.time() - start, 2), deg_on=int(deg_on), fail=0,
                              status=_dg.get("status"), gap=_dg.get("gap"), solcount=_dg.get("solcount"),
                              runtime=_dg.get("runtime"), q=list(_dg.get("q", [])),
                              b=(list(bias) if bias is not None else [0.0] * nMachine), h=list(h_a),
                              new=list(_dg.get("new", [])), nj=[len(m) for m in assign],
                              pool_new_mean=(sum(_pn) / len(_pn) if _pn else None), pool_n=len(_pn),
                              mk_a=mk_a, best_before=best))
        # Learn the PRIMAL bias: excess of true routing (h_a) over the master estimate (s_vals)
        if use_bias and s_vals is not None:
            for l in range(nMachine):
                gap = h_a[l] - s_vals[l]
                bias[l] = (1 - bias_alpha) * bias[l] + bias_alpha * max(0.0, gap)
        pool.append([list(m) for m in assign]); nogoods.append([list(m) for m in assign])
        cand, mk_c = assign, mk_a
        # ILS LOCKED OFF (ablation: pure -1.25 + niche -2.50, load-bearing on no instance;
        # subsumed by throughput->SPP + a strong master). Also safe on rlo/ready-time
        # (-9,-1). Re-enabled with use_ils=True.
        # DIG (use_dig) is out of production, default False. Three independent pieces of
        # evidence:
        #  (1) LOO ablation: -0.02 +- 0.69 -> noise (864 runs).
        #  (2) The mechanism is DEAD: `hint` comes only from job_freq, job_freq is fed by
        #      the solutions the master PROPOSES, and the master already picks from
        #      `allowed` -> the suggested machines are almost always ALREADY in the base
        #      set. Measured (800_30): DIG adds 0.09 machines per job (3.00 -> 3.09), and
        #      this number does NOT change from the first iteration to the last.
        #  (3) Re-basing (432 runs): dropping it does not change the other components'
        #      contributions.
        # The flag is NOT deleted: it is needed to reproduce the paper's ablation row and
        # because 10 helper scripts pass use_dig. use_dig=True restores the old behavior.
        if use_ils and mk_a <= best * (1 + ils_margin):
            res = ils([list(m) for m in assign], [0.0] * nMachine, readyTime, processTime, setupTime,
                      I_l, c1, c2, budget=ils_tl, kick=kick, seed=seed * 100000 + iters,
                      use_swap=True, pool_k=5, anchor=[list(m) for m in assign])
            n_ils += 1; pool.extend(res.get("pool_lkh", []))
            if res["lkh_best_mk"] < mk_c - 1e-6:
                cand = res["lkh_best_assign"]; mk_c = res["lkh_best_mk"]
        pool.append([list(m) for m in cand])
        if use_dig:
            _tally(cand)                    # DIG: tally the accepted candidate's machine choices
        if mk_c < best - 1e-6:
            best = mk_c; best_assign = [list(m) for m in cand]; best_time = time.time() - start
        if inside:
            _dt_it = time.time() - _t_iter0
            it_ema = _dt_it if it_ema is None else 0.7 * it_ema + 0.3 * _dt_it
        if verbose:
            print(f"  [sr] iter {iters}: master={mk_a:.0f} -> best={best:.0f}", flush=True)
    ils_best = best
    if trace is not None:                    # new-pair count: diag script; assignment from here
        trace.append(dict(kind="pre_spp", best=best, assign=[list(m) for m in best_assign]))
    loop_s = time.time() - start
    # ------------------------------------------------------- COLUMN SUPPLY MEASUREMENT
    # WHY: in ~75% of runs the final answer comes from the terminal SPP (t-best ~
    # T-reserve), so the loop's product is not an ANSWER but a COLUMN SUPPLY. Without this
    # measurement, the question "does diversity or bound tightness bring the gain" cannot
    # be tested on data. The DISTINCT column count is the critical field: a large pool of
    # the SAME assignment is actually a narrow supply.
    _canon = {tuple(tuple(sorted(m)) for m in a) for a in pool}
    SUPPLY["mband"] = round(sum(_band) / len(_band), 2) if _band else None
    SUPPLY.update(pool_n=len(pool), pool_distinct=len(_canon), harvest=n_harvest,
                  pre_spp=round(float(ils_best), 1), post_spp=None, spp_used=None,
                  route_s=round(route_s, 2), loop_s=round(loop_s, 2),
                  reserve=(round(_R, 2) if _R is not None else None))
    if use_spp and len(pool) >= 2:
        # INCUMBENT GUARANTEE: best_assign goes to the FRONT of the pool -> sampling always
        # takes index 0, so even if the deadline cuts in, the first routed assignment is
        # the incumbent (feasibility preserved).
        _pool_in = ([best_assign] + pool) if ((spp_cap or inside) and best_assign) else pool
        # INSIDE-200: the SPP is INSIDE the contract too. deadline=T-2 (final route +
        # extraction slack); clean_every=20 cuts the glob load (+12% measured); route_cache
        # hands the loop's columns for free.
        _dl = (start + total_time_limit - 2.0) if inside else None
        spp_mk, spp_assign = spp_recombine(_pool_in, nJob, nMachine, readyTime, processTime, setupTime,
                                           tl=spp_tl, max_assigns=(spp_cap or 80),
                                           cap_soft=spp_cap_soft,
                                           deadline=_dl, must_include=best_assign,
                                           route_cache=rcache,
                                           clean_every=(20 if inside else None),
                                           mip_pay=(_MIP_PAY if inside else None), c1=c1,
                                           self_cache=spp_self_cache)
        if spp_mk is not None and spp_mk < best - 1e-6:
            best = round(spp_mk, 1); best_time = time.time() - start; best_assign = spp_assign
        SUPPLY["post_spp"] = round(float(best), 1)
        if trace is not None:
            trace.append(dict(kind="post_spp", best=best, assign=[list(m) for m in best_assign]))
        SUPPLY["mip_st"] = _SPP_LAST.get("status"); SUPPLY["mip_gap"] = _SPP_LAST.get("gap")
        for _a, _b in (("spp_route_s", "route_s"), ("spp_build_s", "build_s"),
                       ("spp_mip_s", "mip_s"), ("spp_n_uniq", "n_uniq"),
                       ("spp_n_routed", "n_routed"), ("spp_n_cols", "n_cols"),
                       ("spp_final_gap", "final_minus_obj")):
            SUPPLY[_a] = _SPP_LAST.get(_b)
        SUPPLY["spp_used"] = min(len(_pool_in), spp_cap or 80)   # columns the SPP LOOKED AT
        print(f"[SR-SPP] havuz={len(pool)} (ayrik {SUPPLY['pool_distinct']}, hasat {n_harvest}) "
              f"-> pre={ils_best:.0f} -> SPP-best={best:.0f}", flush=True)
    _close_lkh_pool(); clear_environment()
    # The ILS counter is printed ONLY when enabled: use_ils is OFF in production and an
    # "ILS 0x" line read as if the component were part of the method. The flag stays for
    # the ablation's `plus_ils` arm; behavior unchanged -- a disabled component is just no
    # longer logged.
    _ils_txt = f"ILS {n_ils}x, " if use_ils else ""
    print(f"[SR] iter={iters} ({_ils_txt}mfail={mfail}), dongu={loop_s:.0f}s, "
          f"wall={time.time()-start:.0f}s, best={best:.0f}, t-best={best_time:.0f}s, kmach={kmach}",
          flush=True)
    if return_solution:
        return best, best_time, iters, best_assign
    return best, best_time, iters


def main():
    spec = sys.argv[1] if len(sys.argv) > 1 else "new_dataset_niche/100_15_1-99_r0/instance_1"
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    mode = sys.argv[3] if len(sys.argv) > 3 else "sr"         # "sr" recommended | "win" windowed
    param = int(sys.argv[4]) if len(sys.argv) > 4 else (150 if mode == "win" else 3)
    arc_k = int(sys.argv[5]) if len(sys.argv) > 5 else 5        # sr: arc cands (k=3, arc_k=5 won)
    jf = spec if spec.endswith(".json") else spec + ".json"
    d = readproblem(jf, consider_compatibility=True, consider_workload=True)
    nJob, nMachine, c1, c2, readyTime, processTime, setupTime, matrix, I_l, L_i, estSetup = d
    if mode == "sr":
        print(f"### HLBB-SR (size-reduced global master, k={param}, arc_k={arc_k}) | {jf} | "
              f"{nJob}x{nMachine} | budget={budget}s ###", flush=True)
        best, bt, it = run_integrated_sr(nJob, nMachine, c1, c2, readyTime, processTime, setupTime,
                                         I_l, L_i, total_time_limit=budget, master_tl=3,
                                         kmach=param, arc_k=arc_k, verbose=True)
        print(f"\nSONUC: SR-best={best:.0f} (t-best={bt:.0f}s, iter={it})", flush=True)
    else:
        print(f"### HLBB-HM yalin (pencereli fix-optimize, B={param}) | {jf} | {nJob}x{nMachine} | "
              f"budget={budget}s ###", flush=True)
        best, bt, it = run_integrated_hm(nJob, nMachine, c1, c2, readyTime, processTime, setupTime,
                                         I_l, L_i, total_time_limit=budget, master_tl=3,
                                         win_budget=param, verbose=True)
        print(f"\nSONUC: HM-best={best:.0f} (t-best={bt:.0f}s, iter={it})", flush=True)


if __name__ == "__main__":
    mp.set_start_method("spawn")
    main()
