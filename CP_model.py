"""
CP Optimizer counterpart of the MIP.py model.

Models exactly the same problem as the MIP:
  - Parallel (eligible) machines, sequence-dependent setup times
  - Each job is processed on exactly one eligible machine
  - Minimum (c1) / maximum (c2) number of jobs per machine
  - Machine ready time (rDate[l]): the first job on a machine cannot start before rDate[l]
  - Objective: minimize makespan (Cmax = maximum completion time)

Called with the same signature/parameters as MIP(...), so the two are directly comparable.
"""
import os

# IBM CPLEX Studio Linux installation path (default: /opt/ibm/ILOG/CPLEX_Studio2211)
_CPLEX_ROOT = os.environ.get(
    "CPLEX_STUDIO_DIR",
    "/home/sarp/CPLEX_Studio2220"
)
CP_BIN_DIR = os.path.join(_CPLEX_ROOT, "cpoptimizer", "bin", "x86-64_linux")
CPLEX_BIN_DIR = os.path.join(_CPLEX_ROOT, "cplex", "bin", "x86-64_linux")
os.environ["PATH"] = CP_BIN_DIR + os.pathsep + CPLEX_BIN_DIR + os.pathsep + os.environ.get("PATH", "")

from docplex.cp.model import CpoModel

CP_OPTIMIZER_EXEC = os.path.join(CP_BIN_DIR, "cpoptimizer")


def CP(nJob, nMachine, c1, c2, rDate, processTime, setupTime, I_l, L_i, time_limit=60, log=False,
       return_solution=False):
    """
    Takes the same arguments as MIP(...). Returns (obj, gap).
    obj  : best Cmax found (1e6 if no solution)
    gap  : % optimality gap (~0 if proven optimal). -100 if unknown.
    """
    mdl = CpoModel()

    # --- Decision variables: an optional interval for each (job, eligible machine) pair ---
    tasks = {}
    for i in range(nJob):
        for l in L_i[i]:
            tasks[i, l] = mdl.interval_var(
                name=f"t_{i}_m{l}",
                optional=True,
                size=int(processTime[l][i]),
            )

    # --- Each job runs on exactly one machine (MIP constraint 1) ---
    # UPDATE: guard added to avoid an infeasible model when the eligible set is empty.
    for i in range(nJob):
        if L_i[i]:
            mdl.add(mdl.sum(mdl.presence_of(tasks[i, l]) for l in L_i[i]) == 1)
        else:
            if log:
                print(f"-> [UYARI] İş {i} için uyumlu makine listesi (L_i) boş! Kısıt dışı bırakıldı.")

    # --- Sequencing + setup times on each machine (MIP constraints 4 & 8) ---
    # no_overlap + transition matrix: gap between consecutive jobs i->j >= setupTime[l][i][j]
    sequences = {}
    for l in range(nMachine):
        jobs_l = I_l[l]
        if not jobs_l:
            continue
        machine_tasks = [tasks[i, l] for i in jobs_l]
        types = list(range(len(jobs_l)))
        transition = [
            [int(setupTime[l][jobs_l[a]][jobs_l[b]]) for b in range(len(jobs_l))]
            for a in range(len(jobs_l))
        ]
        sequences[l] = mdl.sequence_var(machine_tasks, types=types, name=f"seq_m{l}")
        # [FIX] is_direct=True: setup applies ONLY between immediate (consecutive) job pairs.
        # The default (False) also applied setups to indirect successors and inflated the
        # makespan (inst 12: phantom +82 -> 35893 vs true 35688; caught by feasibility.py).
        mdl.add(mdl.no_overlap(sequences[l], transition, True))

    # --- Machine cardinality: c1[l] <= number of jobs <= c2[l] (MIP constraints 5 & 6) ---
    for l in range(nMachine):
        if not I_l[l]:
            continue
        cnt = mdl.sum(mdl.presence_of(tasks[i, l]) for i in I_l[l])
        mdl.add(cnt >= int(c1[str(l)]))
        mdl.add(cnt <= int(c2[str(l)]))

    # --- Machine ready time (MIP constraint 7) ---
    # The MIP imposes it only on the first job; with no_overlap, imposing it on all jobs
    # is equivalent.
    for i in range(nJob):
        for l in L_i[i]:
            if rDate[l] > 0:
                mdl.add(mdl.if_then(
                    mdl.presence_of(tasks[i, l]),
                    mdl.start_of(tasks[i, l]) >= int(rDate[l]),
                ))

    # --- Objective: makespan ---
    mk_expr = mdl.max([mdl.end_of(tasks[i, l]) for i in range(nJob) for l in L_i[i] if L_i[i]])
    mdl.add(mdl.minimize(mk_expr))

    sol = mdl.solve(
        execfile=CP_OPTIMIZER_EXEC,
        TimeLimit=time_limit,
        LogVerbosity="Normal" if log else "Quiet",
        # Workers not specified -> default "Auto" = all CPU cores (fair/standard setup)
    )

    if sol and sol.get_objective_value() is not None:
        obj = sol.get_objective_value()
        bound = sol.get_objective_bound()
        if bound is not None and obj > 0:
            gap = abs(obj - bound) / obj * 100
        else:
            gap = -100
        if return_solution:
            # each machine: job list ordered by start time (for verification)
            tmp = [[] for _ in range(nMachine)]
            for i in range(nJob):
                for l in L_i[i]:
                    vs = sol.get_var_solution(tasks[i, l])
                    if vs is not None and vs.is_present():
                        tmp[l].append((vs.get_start(), i))
            assignment = [[i for (_, i) in sorted(tmp[l])] for l in range(nMachine)]
            return obj, gap, assignment
        return obj, gap

    if return_solution:
        return 1e6, -100, None
    return 1e6, -100