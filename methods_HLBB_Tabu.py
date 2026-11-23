
import pandas as pd
import numpy as np
from gurobipy import GRB,Model,LinExpr, quicksum,GurobiError
import gurobipy as gp
import time
rnd = np.random
rnd.seed(320)

env = gp.Env(empty=True)
env.setParam("OutputFlag",0)
env.start()


# Initialize the tabu list
tabu_list = {}

def update_tabu_list(new_tabu_assignments, tabu_tenure=2):
    global tabu_list
    for key in list(tabu_list.keys()):
        tabu_list[key] -= 1
        if tabu_list[key] <= 0:
            del tabu_list[key]
    for job, machine in new_tabu_assignments:
        tabu_list[(job, machine)] = tabu_tenure

def find_highest_process_setup_job(Assignments, processTime, setupTime):
    max_value = -1
    max_job = -1
    max_machine = -1
    for mach_ind, jobs in enumerate(Assignments):
        for j in range(len(jobs)):
            current_job = jobs[j]
            prev_job = jobs[j-1] if j > 0 else -1
            next_job = jobs[j+1] if j < len(jobs) - 1 else -1

            prev_setup_time = setupTime[mach_ind][prev_job][current_job] if prev_job != -1 else 0
            next_setup_time = setupTime[mach_ind][current_job][next_job] if next_job != -1 else 0

            total_time = processTime[mach_ind][current_job] + prev_setup_time + next_setup_time

            if total_time > max_value:
                max_value = total_time
                max_job = current_job
                max_machine = mach_ind

    return max_job, max_machine

def MIP_Assignment(nJob, nMachine, c1, c2, processTime, I_l, L_i, estSetup, previousS, previousY, iterCount, setupTime):
    global tabu_list

    mdl = Model("MIP-A", env=env)
    y_il = mdl.addVars(range(nJob), range(nMachine), vtype=GRB.BINARY, name="y_il")
    s_l = mdl.addVars(range(nMachine), vtype=GRB.CONTINUOUS, name="s_l")
    cmax = mdl.addVar(vtype=GRB.CONTINUOUS, name="cmax")

    mdl.setObjective(cmax, GRB.MINIMIZE)

    # constraints
    mdl.addConstrs(cmax >= s_l[l] for l in range(nMachine))
    mdl.addConstrs(s_l[l] >= quicksum(processTime[l][i] * y_il[i, l] for i in I_l[l]) + quicksum(estSetup[i][l] * y_il[i, l] for i in I_l[l]) for l in range(nMachine))

    if iterCount > 0:
        for k in range(len(previousS)):
            for l in range(nMachine):
                mdl.addConstr(
                    quicksum(y_il[i, l] for i in range(nJob)) - quicksum(y_il[i, l] for i in previousY[k][l][1]) +
                    quicksum(1 - y_il[i, l] for i in previousY[k][l][1]) >= 1)

    mdl.addConstrs(quicksum(y_il[i, l] for l in L_i[i]) == 1 for i in range(nJob))
    mdl.addConstrs(quicksum(y_il[i, l] for i in I_l[l]) >= c1[str(l)] for l in range(nMachine))
    mdl.addConstrs(quicksum(y_il[i, l] for i in I_l[l]) <= c2[str(l)] for l in range(nMachine))

    # Add constraints for tabu list
    if len(tabu_list) > 0:
        for job in tabu_list.keys():
            flag = 0
            for _ in L_i[job[0]]:
                if _ != job[1]:
                    flag = 1
                    break
            if flag == 1:        
                mdl.addConstr(y_il[job[0], job[1]]== 0)

    mdl.Params.TimeLimit = 5
    mdl.setParam("OutputFlag", 0)
    mdl.setParam("Seed", 1)
    mdl.optimize()
    # mdl.write('test.lp')
    Assignments = []
    tempS = [0]
    tempY = []
    try:
        for l in range(nMachine):
            temp = []
            tempS.append(s_l[l].X)
            temp2 = [[], []]
            for j in range(nJob):
                if y_il[j, l].X > 0:
                    temp.append(j)
                    temp2[1].append(j)
                else:
                    temp2[0].append(j)
            tempY.append(temp2)
            Assignments.append(temp)
        previousS.append(tempS)
        previousY.append(tempY)
    except AttributeError:
        Assignments = []

    # Find the job with the highest processTime + setup time and update tabu list
    if Assignments:
        highest_job = find_highest_process_setup_job(Assignments, processTime, setupTime)
        update_tabu_list([highest_job])

    return Assignments, previousS, previousY

