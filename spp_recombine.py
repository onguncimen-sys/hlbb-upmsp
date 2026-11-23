# -*- coding: utf-8 -*-
"""SET-PARTITIONING RECOMBINATION (Ekici TSBM adapted to makespan / Maniezzo solution merging).
Extracts per-machine schedule COLUMNS from the pooled assignments; a set-partitioning MIP MIXES
the machine parts of different solutions and selects the best combination. The SPP optimum is
never worse than the best pooled solution: every individual solution can be rebuilt column by
column, so the optimal makespan is at most the pool best (under a time limit the solver returns
its best incumbent), and mixing may improve on it.

Formulation (makespan):
  variables: z_g in {0,1} (column g selected), Cmax
  min Cmax
  s.t. Cmax >= sum_{g in machine l} w_g z_g          (selected completion of each machine)
       sum_{g: i in I_g} z_g = 1  for each job i      (exact cover)
       sum_{g in machine l} z_g <= 1  for each machine l    (at most 1 schedule per machine)
  w_g = the column's LKH completion time.
"""
import time

from gurobipy import GRB, Model, quicksum

from methods import env
from HLBB import clear_environment
from lbbd_optcut_try import route_per_machine


# MEASUREMENTS OF THE LAST CALL (read-only diagnostics; does not affect the algorithm). The
# caller reads it right after spp_recombine. Single-threaded use is assumed.
LAST = {"tl_req": None, "tl_eff": None, "status": None, "gap": None,
        # PHASE TIMES: to MEASURE how far off the reserve formula is.
        # route_s = column routing, build_s = MIP model build (this eats from INSIDE the
        # "12 s reserved for the MIP" window), mip_s = what the solver actually spent.
        # n_uniq = distinct assignments after dedup, n_routed = assignments actually routed
        # after TRIMMING. The formula always assumes `cap` (250); the difference shows here.
        "route_s": None, "build_s": None, "mip_s": None,
        "n_uniq": None, "n_routed": None,
        # n_cols: number of distinct (machine, job-set) COLUMNS ENTERING THE MODEL.
        # The capsoft run showed the gain is NOT proportional to the assignment COUNT: at
        # 50x10, 100% of the pool was priced with ZERO gain; at 150x15, 44% was priced and
        # won 9/0/0. Hypothesis: harvested assignments neighbor the incumbent -> many
        # assignments, FEW distinct columns. `n_uniq` is at assignment level; SPP works at
        # COLUMN level. This counter closes that gap.
        "n_cols": None}
# status/gap: the paper says "we solve this model exactly"; a time-limited MIP can finish
# WITHOUT proving optimality and this was recorded nowhere. The share of status=2 (OPTIMAL)
# and the MIPGap are the measurable counterpart of that claim.


def spp_recombine(pool_assignments, nJob, nMachine, readyTime, processTime, setupTime, tl=20,
                  max_assigns=80, by_column=False, deadline=None, must_include=None,
                  route_cache=None, clean_every=None, mip_pay=None, c1=None, cap_soft=False, self_cache=False):
    """pool_assignments: list of assignments (each a per-machine job list). Returns (mk, assign)
    or (None, None).

    TWO ROUTING MODES:
      by_column=False (DEFAULT, production): route per assignment, at most max_assigns of them.
      by_column=True  : first dedup into (machine, job-set) COLUMNS, route each column ONCE,
                        no assignment trimming.
    WHY (measured, 800_30): the old path runs 80 assignments x 30 machines = 2400 machine
    routings but yields only ~1050 UNIQUE columns -> 56% of the routing is REPEATED. The
    column-based path produces the same column set ~2.3x cheaper. Once the master solution
    pool opens, the assignment count grows 5-10x and the max_assigns=80 trim would discard
    most of the gain; by_column makes it unnecessary.

    deadline: wall clock (time.time() scale). Routing STOPS once this moment passes.
    MEASURED: SPP time fell OUTSIDE the 200 s budget (800_30: loop 201.5 s + SPP 45.5 s =
    247 s). With a deadline, SPP is brought INSIDE the budget.
    must_include: the incumbent assignment. Its columns are ALWAYS routed first -> even if
    the deadline expires early, SPP has a full-cover (feasible) solution.

    route_cache: {(machine, frozenset(jobs)) -> cost}. The loop already routed every
    assignment and discarded the per-machine costs; if provided, those columns skip LKH.
    None = old behavior.
    clean_every: clear_environment every N assignment routings. WHY: getCost globs the ATSP/
    directory on every call; within one long SPP call thousands of files pile up and create
    O(n^2) load (measured: +4.7 s at 800_30, noise floor 0.57). The loop already cleans every
    iteration; SPP did not. None = old behavior.
    (deadline now also cuts ROUTING on the False path: the incumbent is routed as the FIRST
    assignment, so feasibility is preserved. With deadline=None behavior is unchanged.)
    mip_pay: the routing stop threshold becomes deadline - mip_pay -> the MIP keeps at least
    this many seconds in all cases. WHY (caught in a quick test, 800_30): when routing eats
    the whole window the MIP drops to ~1 s and finds NOTHING with 3000+ columns -> the gain
    vanishes (starving the merge step). None = 0.
    c1: per-machine MINIMUM job-count dict (c1[str(l)]); a SAFEGUARD. The master obeys c1 but
    the SPP model says 'at MOST 1 column per machine', not 'at least' -> on data with c1>0,
    SPP could silently leave a machine empty (feas_hook does not check cardinality). If c1 is
    given: columns with |S|<c1 are dropped + column selection becomes MANDATORY for those
    machines. On current data c1=0 -> the constraint never fires, behavior is identical.
    None = old behavior.
    self_cache (default OFF): on the per-assignment path, the columns routed by THIS call
    (cols) also count as cache -> the same (machine, job set) never goes to LKH twice
    (measured: 44-52% of calls are repeats). Per-assignment parallel routing and assignment
    order are PRESERVED (unlike the closed by_column path). An assignment whose machines are
    all cached skips LKH entirely."""
    _t_fn = time.time()                      # MEASUREMENT: phase times (LAST); no effect on flow
    LAST["final_minus_obj"] = None           # MEASUREMENT: do not carry over from a previous call
    # 0) DEDUP (identical assignment signature)
    seen = set(); uniq = []
    for A in pool_assignments:
        sig = tuple(frozenset(m) for m in A)
        if sig in seen:
            continue
        seen.add(sig); uniq.append(A)
    LAST["n_uniq"] = len(uniq)               # MEASUREMENT: distinct assignments BEFORE trimming
    if not by_column and len(uniq) > max_assigns:
        step = len(uniq) / max_assigns   # evenly spaced sample across the run (keeps diversity)
        idx = [int(i * step) for i in range(max_assigns)]
        if cap_soft:
            # SOFT CAP: the cap becomes an ORDERING, not a TRIM. The first `max_assigns`
            # elements are EXACTLY the old set (evenly spaced sample); the rest are APPENDED.
            # Routing already stops at `deadline - mip_pay` -> with time left the extra
            # columns get priced, otherwise the cut lands exactly where today's set ends. So
            # the worst case equals today's behavior; the reserve (`_cap_eff`) is UNCHANGED
            # and no time is stolen from the loop.
            # WHY: measured (results/reserve.csv, 120 runs) -> 22-54% of the pool gets routed
            # while ~14.7 s of the contract sits IDLE. Two wastes, one root cause.
            _in = set(idx)
            uniq = ([uniq[k] for k in idx]
                    + [uniq[k] for k in range(len(uniq)) if k not in _in])
        else:
            uniq = [uniq[k] for k in idx]
    pool_assignments = uniq

    cols = {}
    if by_column:
        # 1a) extract UNIQUE COLUMNS; group per machine. must_include goes FIRST.
        per_m = {l: [] for l in range(nMachine)}
        put = set()
        ordered = ([must_include] if must_include else []) + pool_assignments
        for A in ordered:
            for l in range(nMachine):
                if not A[l]:
                    continue
                key = (l, frozenset(A[l]))
                if key not in put:
                    put.add(key); per_m[l].append(key)
        # 1b) BATCHES: 1 column per machine per batch -> LKH pool parallelism is preserved.
        nb = max((len(v) for v in per_m.values()), default=0)
        for b in range(nb):
            batch = [[] for _ in range(nMachine)]
            keys = []
            for l in range(nMachine):
                if b < len(per_m[l]):
                    batch[l] = list(per_m[l][b][1]); keys.append((l, per_m[l][b]))
            if not keys:
                continue
            h = route_per_machine(batch, readyTime, processTime, setupTime, 1)
            for l, key in keys:
                if key not in cols or h[l] < cols[key]:
                    cols[key] = h[l]
            # first batch covers must_include -> feasibility guaranteed; check the clock after
            if deadline is not None and b >= 1 and time.time() >= deadline - (mip_pay or 0):
                break
    else:
        # 1) OLD PATH: COLUMNS via per-assignment routing. No empty-machine columns.
        nR = 0
        for A in pool_assignments:
            # deadline: may cut after the first assignment (the incumbent, placed first by
            # the caller) is routed (mip_pay: the MIP window is NOT consumed by routing)
            if deadline is not None and nR >= 1 and time.time() >= deadline - (mip_pay or 0):
                break
            if clean_every and nR and nR % clean_every == 0:
                clear_environment()                     # avoid glob-load buildup (see docstring)
            if route_cache is not None:
                red = []; hit = {}
                for l in range(nMachine):
                    c = route_cache.get((l, frozenset(A[l]))) if A[l] else None
                    if c is None and self_cache and A[l]:
                        c = cols.get((l, frozenset(A[l])))
                    if c is not None:
                        red.append([]); hit[l] = c      # cached -> do not send to LKH
                    else:
                        red.append(A[l])
                if self_cache and not any(red):
                    h = [0.0] * nMachine                # all cached -> no LKH call
                else:
                    h = route_per_machine(red, readyTime, processTime, setupTime, 1)
                for l, c in hit.items():
                    h[l] = c
            else:
                h = route_per_machine(A, readyTime, processTime, setupTime, 1)
            nR += 1
            for l in range(nMachine):
                if not A[l]:
                    continue
                key = (l, frozenset(A[l]))
                if key not in cols or h[l] < cols[key]:
                    cols[key] = h[l]
    LAST["route_s"] = round(time.time() - _t_fn, 2)
    LAST["n_routed"] = (nR if not by_column else None)
    if not cols:
        return None, None
    # c1 SAFEGUARD: below-minimum columns are invalid parts -> keep them out of the model
    if c1 is not None:
        cols = {g: w for g, w in cols.items() if len(g[1]) >= int(c1[str(g[0])])}
        if not cols:
            return None, None
    columns = list(cols.keys())
    LAST["n_cols"] = len(columns)            # MEASUREMENT: distinct columns entering the model

    # 2) SPP MIP
    mdl = Model("SPP", env=env)
    z = {g: mdl.addVar(vtype=GRB.BINARY, name=f"z{gi}") for gi, g in enumerate(columns)}
    Cmax = mdl.addVar(vtype=GRB.CONTINUOUS, name="Cmax")
    mdl.setObjective(Cmax, GRB.MINIMIZE)
    by_mach = {l: [g for g in columns if g[0] == l] for l in range(nMachine)}
    for l in range(nMachine):
        if by_mach[l]:
            mdl.addConstr(Cmax >= quicksum(cols[g] * z[g] for g in by_mach[l]))
            mdl.addConstr(quicksum(z[g] for g in by_mach[l]) <= 1)      # <=1 schedule per machine
        if c1 is not None and int(c1[str(l)]) > 0:
            if by_mach[l]:
                mdl.addConstr(quicksum(z[g] for g in by_mach[l]) >= 1)  # c1>0 -> machine not empty
            else:
                return None, None       # no column for a c1>0 machine -> no SPP (incumbent stays)
    for i in range(nJob):
        gi = [g for g in columns if i in g[1]]
        if gi:
            mdl.addConstr(quicksum(z[g] for g in gi) == 1)             # exact cover
    tl_req = tl
    if deadline is not None:
        tl = max(1.0, min(tl, deadline - time.time()))   # the MIP is also INSIDE the budget
    # MEASUREMENT (does NOT change behavior): does the requested spp_tl equal the tl ACTUALLY
    # used? Routing is cut at deadline-mip_pay, so the MIP usually keeps ~mip_pay seconds,
    # i.e. spp_tl >= mip_pay may be IDLE. The paper (§3.5) states "spp_tl = 20 s"; whether
    # the binding number is really 20 or mip_pay -- the sensitivity run reads it from here.
    LAST["tl_req"], LAST["tl_eff"] = tl_req, tl
    mdl.Params.TimeLimit = tl
    mdl.Params.OutputFlag = 0
    mdl.Params.Seed = 1
    _t_opt = time.time()
    LAST["build_s"] = round(_t_opt - _t_fn - (LAST["route_s"] or 0.0), 2)
    mdl.optimize()
    LAST["mip_s"] = round(time.time() - _t_opt, 2)
    try:                                   # MEASUREMENT: optimality proven? (2=OPTIMAL, 9=TIME_LIMIT)
        LAST["status"] = int(mdl.Status)
        LAST["gap"] = round(float(mdl.MIPGap), 4) if mdl.SolCount else None
    except Exception:
        LAST["status"] = LAST["gap"] = None

    # 3) EXTRACT THE SOLUTION
    try:
        assign = [[] for _ in range(nMachine)]
        for g in columns:
            if z[g].X > 0.5:
                assign[g[0]] = list(g[1])
        mk = max(route_per_machine(assign, readyTime, processTime, setupTime, 1))
        # MEASUREMENT (does NOT change behavior): is the final re-routing worse than the known
        # cost of the selected columns (MIP objective)? The returned value is the re-routing
        # (an auditable sequence).
        try:
            LAST["final_minus_obj"] = round(float(mk) - float(Cmax.X), 3)
        except Exception:
            LAST["final_minus_obj"] = None
        return mk, assign
    except (AttributeError, Exception):
        return None, None
