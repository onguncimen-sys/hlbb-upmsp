# -*- coding: utf-8 -*-
"""
Created on Wed Oct 12 13:25:25 2022

@author: Milad
"""
from gurobipy import GRB,Model,LinExpr, quicksum,GurobiError
from methods import MIP_Assignment
from methods_HLBB_Tabu import MIP_Assignment as MIP_Assignment_Tabu

import numpy as np
from copy import deepcopy as dp

import subprocess
# import tsplib95
import numpy as np
import uuid
import random
import glob
import time
from multiprocessing import Pool
import multiprocessing as mp

import sys
import math
import random
from itertools import combinations
import gurobipy as gp
from gurobipy import GRB


####################################LKH#########################################

def row_to_line(row):
    
    ln = ""
    
    row_list = row.tolist()
    
    for i in range(len(row_list)):
        if i!= len(row_list)-1:
            ln = ln + str(int(row_list[i]*100000)) + " "
        else:
            ln = ln + str(int(row_list[i]*100000)) + "\n"
            
    return ln


def tsplib_file_generator(instance_name, dist_mat):
    name = "LKH-3.0.7/" + "ATSP/" + instance_name + ".atsp"
    with open(name, 'w') as the_file:
        the_file.write("NAME : {}.atsp\n".format(instance_name))
        the_file.write("TYPE : ATSP\n")
        the_file.write("DIMENSION : {}\n".format(dist_mat.shape[0]))
        the_file.write("EDGE_WEIGHT_TYPE: EXPLICIT\n")
        the_file.write("EDGE_WEIGHT_FORMAT: FULL_MATRIX\n")
        the_file.write("EDGE_WEIGHT_SECTION: FULL_MATRIX\n")
        for row in dist_mat:
            line = row_to_line(row)
            the_file.write(line)
                
        


def parameter_file_generator(instance_name, time_limit = 0.25):
    name = "LKH-3.0.7/" + "ATSP/"+ instance_name + ".par"
    with open(name, 'w') as the_file:
        the_file.write("PROBLEM_FILE = ATSP/{}.atsp\n".format(instance_name))
        the_file.write("MAX_CANDIDATES = 30\n")
        the_file.write("MAX_TRIALS = 100\n")
        the_file.write("OUTPUT_TOUR_FILE = ATSP/{}.$.tour\n".format(instance_name))
        the_file.write("PRECISION = 1\n")
        the_file.write("RUNS = 1\n")
        the_file.write("SEED = 1\n")
        the_file.write("TIME_LIMIT = {}\n".format(time_limit))
        
    
    
def getCost(problem_name):
    # LKH writes a NEW tour file at every improvement
    # (`$` in OUTPUT_TOUR_FILE -> the current cost; FindTour.c -> WriteTour). Previously
    # glob(...)[0] was taken; directory order is NOT by cost -> an intermediate (worse) tour
    # could be read (~3-6% of routings, avg +1.8 units). The LOWEST-cost file = the best tour
    # found by LKH (SAME rule as tour_capture._tour_files).
    costs = []
    for path in glob.glob("LKH-3.0.7/ATSP/{}.*.tour".format(problem_name)):
        try:
            costs.append(int(path[:-5].split(".")[-1]))
        except ValueError:
            continue
    if not costs:
        raise IndexError("LKH tur dosyasi yok: {}".format(problem_name))   # same exception type as before
    return min(costs)/100000


'''def JobsOnMachinesDistMat(distance_matrix, selected_jobs, mach_ind):

    sel_jobs = [item+1 for item in selected_jobs]


    subset_dist_mat = np.zeros((len(sel_jobs)+1,len(sel_jobs)+1))

    for index,item in enumerate(sel_jobs):
        for indexx,itemm in enumerate(sel_jobs):
            print([index,indexx,"****",item,itemm,"*******",distance_matrix[mach_ind][item,itemm]])
            subset_dist_mat[item,itemm] = distance_matrix[mach_ind][index,indexx]
    

    subset_dist_mat = np.column_stack((np.zeros(len(sel_jobs)), subset_dist_mat))
    subset_dist_mat = np.row_stack((np.zeros(len(sel_jobs)+1), subset_dist_mat))

    print(sel_jobs)
    for index,item in enumerate(sel_jobs):
        subset_dist_mat[0,index] = distance_matrix[mach_ind][0,item]

    
    return subset_dist_mat
'''


def JobsOnMachinesDistMat(processTime, setupTime, selected_jobs, mach_ind):

    BigM = 2000
    matrix = np.zeros((len(selected_jobs)+1,len(selected_jobs)+1))
    selected_jobs = list(set(selected_jobs))
    


    k = mach_ind
    for i in range(1+len(selected_jobs)):
        for j in range(1+len(selected_jobs)):
            if i == 0 and j !=0:
                matrix[i][j] = float(processTime[k][selected_jobs[j-1]])
            elif j==0:
                matrix[i][j] = 0
            elif i==j:
                matrix[i][j] = BigM
            else:
                matrix[i][j] = float(processTime[k][selected_jobs[j-1]]) + float(setupTime[k][selected_jobs[i-1]][selected_jobs[j-1]])
    matrix[0][0] = BigM



    return matrix



def _fallback_tour_cost(mat):
    """If LKH yields no tour: a valid (poor) closed-tour cost: 0->1->...->(N-1)->0.
    mat: (N)x(N) distance matrix (dummy=0). In real units (NOT scaled like getCost) ->
    directly makespan-equivalent, since JobsOnMachinesDistMat returns raw proc+setup."""
    N = mat.shape[0]
    c = sum(float(mat[i][i + 1]) for i in range(N - 1)) + float(mat[N - 1][0])
    return c


def solveSingleLKH(params):
    sample_dst_mat, time_limit = params
    # [ROBUSTNESS] LKH can occasionally exit without producing a tour file (on large
    # instances, 30 concurrent subproblems) -> getCost glob[0] crashed the WHOLE run with an
    # IndexError. Retry once (with a fresh uuid); if still no tour, fall back to a valid
    # identity-tour cost (no crash; unlike a large sentinel it does not poison the makespan).
    for _ in range(2):
        problem_name = str(uuid.uuid4())
        tsplib_file_generator(problem_name, sample_dst_mat)
        parameter_file_generator(problem_name, time_limit)
        try:
            subprocess.check_output('./LKH ATSP/{}.par'.format(problem_name), shell=True, cwd='LKH-3.0.7/')
        except Exception:
            pass
        if glob.glob("LKH-3.0.7/ATSP/{}.*.tour".format(problem_name)):
            return getCost(problem_name)
    return _fallback_tour_cost(sample_dst_mat)


# [FIX] Pool reuse: building 15 workers FROM SCRATCH every iteration under spawn (each one
# re-imports gurobi) cost ~26 s/iteration -> only 12 iterations in 300 s.
# Fix: build the Pool ONCE (persistent) and reuse it every iteration -> the workers load
# gurobi only once. The routing phase drops from ~26 s/iter to ~ms/iter.
_HLBB_LKH_POOL = None
_HLBB_LKH_POOL_N = None

def _get_lkh_pool(n):
    """Return the persistent Pool of size n; rebuilds it if the size changes."""
    global _HLBB_LKH_POOL, _HLBB_LKH_POOL_N
    if _HLBB_LKH_POOL is not None and _HLBB_LKH_POOL_N != n:
        _close_lkh_pool()
    if _HLBB_LKH_POOL is None:
        _HLBB_LKH_POOL = Pool(n)
        _HLBB_LKH_POOL_N = n
    return _HLBB_LKH_POOL

def _close_lkh_pool():
    """Close the persistent Pool. Called at the end of HLBB (normal exit) + at the start of
    the next call (safety) -> on an exception at most 1 Pool leaks; the next call cleans it."""
    global _HLBB_LKH_POOL, _HLBB_LKH_POOL_N
    if _HLBB_LKH_POOL is not None:
        try:
            _HLBB_LKH_POOL.close()
            _HLBB_LKH_POOL.join()
        except Exception:
            pass
        _HLBB_LKH_POOL = None
        _HLBB_LKH_POOL_N = None

def solveParallelLKH(assignment_list, readyTime, processTime, setupTime, time_limit = 0.25):
    to_be_solved = [JobsOnMachinesDistMat(processTime, setupTime, selected_jobs, mach_ind) for mach_ind,selected_jobs in enumerate(assignment_list)]
    time_limits = [time_limit]*len(assignment_list)

    pool = _get_lkh_pool(len(assignment_list))   # [FIX] REUSE instead of a NEW Pool per iteration
    ls1 = pool.map(solveSingleLKH, zip(to_be_solved, time_limits))

    for i in range(len(ls1)):
        ls1[i] = readyTime[i] + ls1[i]

    print("machine objectives:",ls1, "maximum completion time: ", [max(ls1)])
    return max(ls1)

def clear_environment():
    
    import os

    dir_name = os.getcwd() + "/LKH-3.0.7/ATSP/"
    test = os.listdir(dir_name) 

    for item in test:
        if item.endswith(".tour") or item.endswith(".par") or item.endswith(".atsp"):
            os.remove(os.path.join(dir_name, item))





def gurobi_tsp_solver(params):
    
    dist_matrix,time_limit = params
    n = int(dist_matrix.shape[0])

    # Create a new model
    m = gp.Model("atsp")

    # Create variables
    x = m.addVars(n, n, vtype=GRB.BINARY, name="x")
    u = m.addVars(n, vtype=GRB.CONTINUOUS, name="u")

    # Set objective
    m.setObjective(gp.quicksum(dist_matrix[i][j] * x[i, j] for i in range(n) for j in range(n)), GRB.MINIMIZE)

    # Add constraints
    m.addConstrs(gp.quicksum(x[i, j] for j in range(n) if j != i) == 1 for i in range(n))  # Each city is left once
    m.addConstrs(gp.quicksum(x[j, i] for j in range(n) if j != i) == 1 for i in range(n))  # Each city is entered once

    # Subtour elimination constraints
    m.addConstrs((u[i] - u[j] + n * x[i, j] <= n - 1) for i in range(1, n) for j in range(1, n) if i != j)

    # Optimize model
    
    m.Params.OutputFlag = 0
    m.params.Threads = 1
    m.Params.TimeLimit = time_limit
    
    m.optimize()
        
    print("Final MIP gap value: %f" % m.MIPGap)
    print("Objective function value: %f" % obj1)
    print("Tour: ", tour)


    if m.status == GRB.OPTIMAL:
        return m.objVal
    else:
        return 1e6


def solveParallelGurobi(assignment_list, readyTime, processTime, setupTime, time_limit):
    to_be_solved = [JobsOnMachinesDistMat(processTime, setupTime, selected_jobs, mach_ind) for mach_ind,selected_jobs in enumerate(assignment_list)]
    
    n_cores = len(assignment_list)
    
    time_limits = [time_limit]*len(assignment_list)

    with Pool(n_cores) as p:
        
        ls1 = p.map(gurobi_tsp_solver, zip(to_be_solved, time_limits))
        
        p.close()
        
        for i in range(len(ls1)):
            ls1[i] = readyTime[i]+ ls1[i]


    print("machine objectives:",ls1, "maximum completion time: ", [max(ls1)])
        
    return max(ls1)

####################################LKH#########################################


def HLBB(nJob,nMachine,c1,c2,rDate,processTime,setupTime,I_l,L_i,estSetup,JSON_file,routingSolver, tabu, time_limit, total_time_limit=None, return_time=False, iter_count=200, no_improve_limit=None, return_solution=False):
    # total_time_limit: total wall-clock budget for HLBB (seconds). None -> old behavior
    # (fixed iter_count iterations). Used for a fair comparison against CP/MIP.
    # return_time=True -> returns (bestObjective, best_time); best_time = wall-clock time at
    # which the best solution was found (time-to-best, as reported in the literature).
    # iter_count: total number of iterations. iter_count=1 -> construction only
    # (initial solution build), no search. Used in ablation experiments.
    # no_improve_limit: stop after this many consecutive iterations without improvement
    # (early stopping). None -> disabled. Cuts idle search after convergence.
    clear_environment()
    start = time.time()
    bestObjective = 1e6
    bestAssignment = None      # [return_solution] best assignment for verification
    best_iter = 0
    best_time = 0.0
    no_improve = 0
    iters_done = 0
    previousS = []
    previousY = []
    
    assignment_time_spent = 0
    routing_time_spent = 0
    
    q=open("Logs/LOG_{}j_{}m.txt".format(nJob,nMachine), "a")
    q.write("***************************************************")
    q.write('\n')
    if tabu == "Yes":
        q.write(JSON_file + '   ' + "Parameters:"+ '    ' + routingSolver + '    '  + "Tabu ON" + '    ' + str(time_limit) + '    ' + "Seconds")
    else:
        q.write(JSON_file + '   ' + "Parameters:"+ '    ' + routingSolver + '    '  + "Tabu OFF" + '    ' + str(time_limit) + '    ' + "Seconds")
    q.write('\n')
    q.close()

    _close_lkh_pool()   # [FIX] clean a stale Pool if the previous call ended in an exception

    for iter in range(iter_count):
        # break the loop once the total time budget is spent (fair comparison with CP/MIP)
        if total_time_limit is not None and time.time() - start >= total_time_limit:
            print("HLBB wall-clock butcesi ({}s) doldu, iterasyon {} de durduruldu".format(total_time_limit, iter))
            break
        clear_environment()
        s1 = time.time()
        if tabu == "Yes":
            Assignments,previousS,previousY = MIP_Assignment_Tabu(nJob,nMachine,c1,c2,processTime,I_l,L_i,estSetup,previousS,previousY,iter,setupTime)
        else:
            Assignments,previousS,previousY = MIP_Assignment(nJob,nMachine,c1,c2,processTime,I_l,L_i,estSetup,previousS,previousY,iter)
        assignment_time_spent += time.time()-s1
        
        if routingSolver == "LKH":
            s2 = time.time()
            if len(Assignments)>0:
                currentObjective = solveParallelLKH(Assignments, rDate, processTime, setupTime, time_limit = time_limit)
            else:
                currentObjective = 1e6
            routing_time_spent += time.time()-s2
            
        if routingSolver == "Gurobi":
            s2 = time.time()
            if len(Assignments)>0:
                currentObjective = solveParallelGurobi(Assignments, rDate, processTime, setupTime, time_limit = time_limit)
            else:
                currentObjective = 1e6
            routing_time_spent += time.time()-s2
            
            

        q=open("Logs/LOG_{}j_{}m.txt".format(nJob,nMachine), "a")
        cpu = time.time() - start
        q.write(JSON_file + '   ' + str(currentObjective)+ '    ' + str(iter) + '    ' + str(cpu))
        q.write('\n')
        q.close()

        if currentObjective < bestObjective:
            best_iter = iter
            best_time = time.time() - start   # best found at this moment (time-to-best)
            print("new improvement found  >>>>>>>>>>>>>>>>>>>>>>> " + str(currentObjective) + " at iteration ", best_iter)
            print("new assignment found  >>>>>>>>>>>>>>>>>>>>>>> " + str(Assignments) + " at iteration ", best_iter)
            bestObjective = currentObjective
            bestAssignment = [list(m) for m in Assignments]   # [return_solution]
            no_improve = 0                     # improvement -> reset the counter
        else:
            no_improve += 1                    # no improvement -> increment the counter
        iters_done = iter + 1
        # Early stopping: halt after no_improve_limit consecutive non-improving iterations
        if no_improve_limit is not None and no_improve >= no_improve_limit:
            print("HLBB early stop: {} iterasyon iyilesme yok, iterasyon {} de durduruldu".format(no_improve_limit, iter))
            break

    _close_lkh_pool()   # [FIX] loop finished -> close the persistent Pool (normal exit)
    print("HLBB Runtime is >>>>>>>>>>>>>>>>", time.time()-start, "seconds ")
    print("HLBB Best Objective is >>>>>>>>>>>>>>>>", bestObjective)
    print("HLBB Best Iteration is >>>>>>>>>>>>>>>>", best_iter)
    print("HLBB Time-to-Best is >>>>>>>>>>>>>>>>", best_time, "seconds ")
    print("HLBB Total Iteration Count >>>>>>>>>>>>>>>>", iters_done)

    q=open("Logs/LOG_{}j_{}m.txt".format(nJob,nMachine), "a")
    q.write("Final:" + '    ' + "instance_" + JSON_file  + '   ' + str(bestObjective) + '   ' + str(best_iter) + '   ' + str(time.time()-start))
    q.write('\n')
    q.write("Assignment Time: " + str(assignment_time_spent) + '   ' +  "Routing Time: " + str(routing_time_spent))
    q.write('\n')
    q.close()

    clear_environment()

    if return_solution:
        return bestObjective, best_time, bestAssignment
    if return_time:
        return bestObjective, best_time
    return bestObjective

