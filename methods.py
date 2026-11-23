
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

def MIP_Assignment(nJob,nMachine,c1,c2,processTime,I_l,L_i,estSetup,previousS,previousY,iterCount):

    mdl=Model("MIP-A", env=env)
    y_il=mdl.addVars(range(nJob),range(nMachine), vtype=GRB.BINARY, name = "y_il")
    s_l=mdl.addVars(range(nMachine), vtype=GRB.CONTINUOUS, name = "s_l")
    cmax=mdl.addVar(vtype=GRB.CONTINUOUS, name = "cmax")


    mdl.setObjective(cmax,GRB.MINIMIZE)

    #constraints
    mdl.addConstrs(cmax>= s_l[l] for l in range(nMachine))    
    mdl.addConstrs(s_l[l]>= quicksum(processTime[l][i]*y_il[i,l] for i in I_l[l]) + quicksum(estSetup[i][l]*y_il[i,l] for i in I_l[l]) for l in range(nMachine))    
    if iterCount > 0:
        for k in range(len(previousS)):
            for l in range(nMachine):
                mdl.addConstr(
                    quicksum(y_il[i, l] for i in range(nJob)) - quicksum(y_il[i, l] for i in previousY[k][l][1]) + 
                    quicksum(1 - y_il[i, l] for i in previousY[k][l][1]) >= 1)
                
    mdl.addConstrs(quicksum(y_il[i,l] for l in L_i[i])==1 for i in range(nJob))      
    mdl.addConstrs(quicksum(y_il[i,l] for i in I_l[l]) >= c1[str(l)] for l in range(nMachine))
    mdl.addConstrs(quicksum(y_il[i,l] for i in I_l[l]) <= c2[str(l)] for l in range(nMachine))
    

    mdl.Params.TimeLimit = 5
    mdl.setParam("OutputFlag",0)
    mdl.setParam("Seed",1)
    mdl.optimize()
    mdl.write('test.lp')
    Assignments = []
    tempS = [0]
    tempY = []
    try:
        for l in range(nMachine):
            temp = []
            tempS.append(s_l[l].X)
            temp2 = [[],[]]
            for j in range(nJob):
                if y_il[j,l].X>0:
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

    
    #e)
    return(Assignments,previousS,previousY)


