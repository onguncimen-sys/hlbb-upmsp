# -*- coding: utf-8 -*-
"""
Created on Thu Sep 15 08:46:37 2022

@author: Milad
"""
import numpy as np
import pandas as pd
rnd = np.random
rnd.seed(32)
import json

#%% Read the problems
def readproblem(JSON_file, consider_compatibility=False, consider_workload=False):
    """
    Reads according to the experimental setup of the paper (Heuristic Logic-Based
    Benders, Vestel).

    Paper, Section 5 "Data set and parameter generation":
      "For small, medium, and large-sized instances, machine-job compatibility
       and workload balancing are not considered, meaning there are no limits on
       the minimum and maximum number of jobs assigned to each machine. However,
       in Vestel (real-life) instances, the minimum and maximum number of jobs
       assigned to a machine are set to 5 and 15, respectively."

    Therefore compatibility and workload constraints are NOT applied on the
    synthetic (small/medium/large) instances. The Compatibility matrix in the
    JSON files is broken (some jobs have no compatible machine at all, e.g. in
    15j_2m) and max=nJob (i.e. not binding anyway), so enforcing them makes the
    model artificially infeasible. To stay faithful to the paper, both are off
    by default.

    consider_compatibility=True  -> the Compatibility matrix in the JSON is applied
                                    (only for the real-life / Vestel instance).
    consider_workload=True       -> minimumJobs/maximumJobs in the JSON are applied.
    """
    BigM=200000
    # Read the JSON file
    with open(JSON_file, 'r') as f:
        data = json.load(f)
    nJob = data["nJob"]
    nMachine = data["nMachine"]
    processTime = data["processTime"]
    setupTime = data["setupTime"]
    compatibility = data["Compatibility"]
    readyTime = data["readyTime"]

    # --- Workload (min/max job count) constraints ---
    # Paper: no min/max on synthetic instances. When off, c1=0, c2=nJob
    # (so the model constraints are not binding).
    if consider_workload:
        c1 = data["minimumJobs"]
        c2 = data["maximumJobs"]
    else:
        c1 = {str(l): 0 for l in range(nMachine)}
        c2 = {str(l): nJob for l in range(nMachine)}

    # Convert the data to the necessary formats
    processTime = [[float(processTime[str(k)][i]) for i in range(nJob)] for k in range(nMachine)]
    setupTime = {int(k): np.array(v) for k, v in setupTime.items()}
    compatibility = {int(k): v for k, v in compatibility.items()}
    readyTime = [readyTime[str(k)] for k in range(nMachine)]
    I_l = [[] for _ in range(nMachine)]  # Set of jobs that Machine l can process
    L_i = [[] for _ in range(nJob)]  # Set of Machines that job i can be processed on
    for i in range(nJob):
        for l in range(nMachine):
            # Paper: no compatibility on synthetic instances -> every job on every machine.
            if (not consider_compatibility) or compatibility[l][i] == 1:
                I_l[l].append(i)
                L_i[i].append(l)


    estSetup = np.zeros((nJob,nMachine))
    for l in range(nMachine):
        for i in range(nJob):
            estSetup[i][l] = 0
            for j in range(nJob):
                if i!=j:
                    estSetup[i][l] += (setupTime[l][i][j] + setupTime[l][j][i])
            estSetup[i][l] = estSetup[i][l]/(2*nJob)   # paper eq (18): denominator 2|I| (was |I|)


    matrix = np.zeros((nMachine,nJob+1,nJob+1))
    for k in range(nMachine):
        for i in range(1+nJob):
            for j in range(1+nJob):
                if i == 0 and j !=0:
                    matrix[k][i][j] = float(processTime[k][j-1])
                elif i==j:
                    matrix[k][i][j] = BigM
                else:
                    matrix[k][i][j] = float(processTime[k][j-1]) + setupTime[k][i-1][j-1]
        matrix[k][0][0] = BigM
    np.save("dist_mat.npy",matrix)

    return(nJob,nMachine,c1,c2,readyTime,processTime,setupTime,matrix,I_l,L_i,estSetup)

