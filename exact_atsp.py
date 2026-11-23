# -*- coding: utf-8 -*-
"""EXACT ATSP solver = a CORRECTED version of HLBB.py:gurobi_tsp_solver (separate file;
the original HLBB.py is untouched). Only difference: the undefined `obj1`/`tour` print
lines (the crash cause) were removed. Formulation: Gurobi + MTZ subtour elimination
(fast enough for n<=~18; an alternative to the paper's eq (44) DFJ-lazy with the same
EXACT result).

Matrix = output of HLBB.JobsOnMachinesDistMat (0=depot). The return value matches LKH:
the total tour cost (EXCLUDING readyTime; the caller adds it). So it is directly
comparable with LKH.

In Phase 2: used instead of (or alongside) LKH for the C_l entering a cut and/or routing.
"""
import gurobipy as gp
from gurobipy import GRB, quicksum


def exact_atsp(dist_matrix, time_limit=10.0):
    """EXACT minimum tour cost for the given (n x n) ATSP cost matrix.
    n<=1 -> 0. Returns ObjVal if a solution is found, 1e6 otherwise."""
    n = int(dist_matrix.shape[0])
    if n <= 1:
        return 0.0

    m = gp.Model("atsp_exact")
    x = m.addVars(n, n, vtype=GRB.BINARY, name="x")
    u = m.addVars(n, vtype=GRB.CONTINUOUS, name="u")

    m.setObjective(
        quicksum(float(dist_matrix[i][j]) * x[i, j]
                 for i in range(n) for j in range(n) if i != j),
        GRB.MINIMIZE)

    # each node: exactly 1 in-arc / 1 out-arc
    m.addConstrs(quicksum(x[i, j] for j in range(n) if j != i) == 1 for i in range(n))
    m.addConstrs(quicksum(x[j, i] for j in range(n) if j != i) == 1 for i in range(n))
    # MTZ subtour elimination (excluding depot=0)
    m.addConstrs((u[i] - u[j] + n * x[i, j] <= n - 1)
                 for i in range(1, n) for j in range(1, n) if i != j)

    m.Params.OutputFlag = 0
    m.Params.Threads = 1
    m.Params.TimeLimit = time_limit
    m.optimize()

    # [FIX] the old code had `print(... obj1)` / `print(tour)` here -> obj1/tour
    # undefined -> NameError -> crash. Removed.
    val = m.ObjVal if m.SolCount > 0 else 1e6
    m.dispose()                        # [10h robustness] release the model explicitly
    return val


# ============================================================
#  DFJ lazy subtour elimination (the paper's eq 44) — STRONGER than MTZ
# ============================================================
def _shortest_subtour(n, edges):
    """In an integer solution every node has out-degree=1 -> it splits into disjoint
    cycles. Returns the shortest cycle (subtour)."""
    succ = {i: j for (i, j) in edges}
    unvisited = set(range(n))
    cycles = []
    while unvisited:
        node = next(iter(unvisited))
        cyc = []
        while node in unvisited:
            unvisited.remove(node)
            cyc.append(node)
            node = succ.get(node)
            if node is None:
                break
        cycles.append(cyc)
    return min(cycles, key=len) if cycles else None


def _subtour_cb(model, where):
    if where != GRB.Callback.MIPSOL:
        return
    x = model._x; n = model._n
    vals = model.cbGetSolution(x)
    edges = [(i, j) for (i, j) in x.keys() if vals[i, j] > 0.5]
    tour = _shortest_subtour(n, edges)
    if tour is not None and len(tour) < n:                 # subtour found -> eq (44)
        S = set(tour)
        model.cbLazy(quicksum(x[i, j] for i in S for j in S if i != j) <= len(S) - 1)


def exact_atsp_dfj(dist_matrix, time_limit=10.0, return_proven=False):
    """EXACT ATSP, DFJ lazy subtour (paper eq 44). A much stronger relaxation than MTZ
    -> PROVEN optimal in ms for n<=~18 (no occasional TL-hitting issue as with MTZ).
    return_proven=True -> returns (obj, proven) (proven = was optimality proven)."""
    n = int(dist_matrix.shape[0])
    if n <= 1:
        return (0.0, True) if return_proven else 0.0
    if n == 2:
        val = float(dist_matrix[0][1] + dist_matrix[1][0])
        return (val, True) if return_proven else val

    m = gp.Model("atsp_dfj")
    x = m.addVars([(i, j) for i in range(n) for j in range(n) if i != j],
                  vtype=GRB.BINARY, name="x")
    m.setObjective(quicksum(float(dist_matrix[i][j]) * x[i, j]
                            for i in range(n) for j in range(n) if i != j), GRB.MINIMIZE)
    m.addConstrs(quicksum(x[i, j] for j in range(n) if j != i) == 1 for i in range(n))
    m.addConstrs(quicksum(x[j, i] for j in range(n) if j != i) == 1 for i in range(n))

    m._x = x; m._n = n
    m.Params.OutputFlag = 0
    m.Params.Threads = 1
    m.Params.LazyConstraints = 1
    m.Params.TimeLimit = time_limit
    m.optimize(_subtour_cb)

    obj = m.ObjVal if m.SolCount > 0 else 1e6
    proven = (m.Status == GRB.OPTIMAL)
    m.dispose()                        # [10h robustness] release after every exact solve
    return (obj, proven) if return_proven else obj
