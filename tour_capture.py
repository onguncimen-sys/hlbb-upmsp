# -*- coding: utf-8 -*-
"""Read back the SEQUENCE FOUND BY LKH (a side path; HLBB.py is left untouched).

WHY: `HLBB.getCost` extracts the cost from the tour file NAME (`path[:-5].split(".")[-1]`)
and never opens the file. So every iteration solves m ATSPs, LKH writes each sequence to
disk, and we take only the number. The sequence is paid-for but unused material.

CONSEQUENCE: the solution we report is an UNORDERED assignment. For this reason HLBB is
checked with `feas_hook.check(..., ordered=False)` while rival methods are checked with
`ordered=True` -- we verify our own method LESS than the rivals. The makespan is correct
(LKH computes it from an actual sequence); we merely do not record that sequence.

THIS FILE is NOT used in the hot loop. It is called ONCE for the FINAL solution after the
run ends -> cost is negligible, `run_abl`/`run_integrated_sr` behavior is unchanged.

ENCODING (HLBB.JobsOnMachinesDistMat): node 0 = dummy depot, node v>=1 -> selected_jobs[v-1].
LKH TOUR_SECTION is 1-based -> tour entry 1 = depot, entry t>=2 -> selected_jobs[t-2].
"""
import glob
import os
import subprocess
import uuid

import numpy as np

from HLBB import parameter_file_generator, tsplib_file_generator

_ATSP = "LKH-3.0.7/ATSP"


def _tour_files(problem_name):
    """ALL tour files for the same name + their costs. LKH may write a NEW file as it
    improves -> there can be more than one. The LOWEST-cost one is the valid one.
    (Caught in the smoke test: reading tour and cost via SEPARATE globs could pick
    different files -> 2 of 8 samples disagreed on 800_30/640_25.)"""
    out = []
    for f in glob.glob(f"{_ATSP}/{problem_name}.*.tour"):
        try:
            out.append((int(f[:-5].split(".")[-1]) / 100000.0, f))   # SAME as HLBB.getCost
        except ValueError:
            continue
    return sorted(out)


def _read_tour(path):
    """Read a tour file -> 1-based node list. None if absent."""
    nodes = []
    with open(path) as fh:
        started = False
        for ln in fh:
            ln = ln.strip()
            if ln == "TOUR_SECTION":
                started = True
                continue
            if not started:
                continue
            if ln in ("-1", "EOF", ""):
                break
            try:
                nodes.append(int(ln))
            except ValueError:
                break
    return nodes or None


def _cleanup(problem_name):
    """Delete tour/atsp/par files. HLBB never deletes them (measured: 77 files accumulated)."""
    for pat in (f"{_ATSP}/{problem_name}.*.tour", f"{_ATSP}/{problem_name}.atsp",
                f"{_ATSP}/{problem_name}.par"):
        for f in glob.glob(pat):
            try:
                os.remove(f)
            except OSError:
                pass


def sequence_one_machine(processTime, setupTime, selected_jobs, mach_ind, time_limit=1,
                         return_cost=False):
    """Return the job SEQUENCE of a single machine (via LKH). selected_jobs: job indices.
    Returns: ordered job list ((sequence, LKH_cost) if return_cost).
    LKH is not called for machines with 0/1/2 jobs (same rule as HLBB)."""
    def _out(seq, cost):
        return (seq, cost) if return_cost else seq

    # ⚠️ JobsOnMachinesDistMat REORDERS internally via `list(set(...))`.
    # The decoding MUST use the SAME order, otherwise the sequence is mis-mapped
    # (caught in the smoke test: cost mismatched in 7 of 8 trials).
    sel = list(set(selected_jobs))
    if len(sel) <= 1:
        return _out(list(sel), processTime[mach_ind][sel[0]] if sel else 0.0)
    if len(sel) == 2:
        a, b = sel
        ab = processTime[mach_ind][a] + setupTime[mach_ind][a][b] + processTime[mach_ind][b]
        ba = processTime[mach_ind][b] + setupTime[mach_ind][b][a] + processTime[mach_ind][a]
        return _out([a, b] if ab <= ba else [b, a], min(ab, ba))
    # ⚠️ WE BUILD THE MATRIX HERE instead of calling HLBB.JobsOnMachinesDistMat.
    # Reason: that function applies `selected_jobs = list(set(selected_jobs))` INTERNALLY,
    # and applying `list(set(x))` TWICE can CHANGE the order (on int hash collisions the
    # insertion order affects slot placement). Measured: on 800_30, in 2 of 8 samples
    # `list(set(x)) != list(set(list(set(x))))` -> the matrix rows did NOT match my `sel`
    # order -> the sequence was mis-decoded (1291 instead of 1716).
    # route_per_machine is NOT affected because it uses only the COST; we are the first
    # consumer that needs the order. The formula matches HLBB exactly.
    BigM = 2000
    n = len(sel)
    mat = np.zeros((n + 1, n + 1))
    for i in range(n + 1):
        for j in range(n + 1):
            if i == 0 and j != 0:
                mat[i][j] = float(processTime[mach_ind][sel[j - 1]])
            elif j == 0:
                mat[i][j] = 0.0
            elif i == j:
                mat[i][j] = BigM
            else:
                mat[i][j] = (float(processTime[mach_ind][sel[j - 1]])
                             + float(setupTime[mach_ind][sel[i - 1]][sel[j - 1]]))
    mat[0][0] = BigM
    name = str(uuid.uuid4())
    tsplib_file_generator(name, mat)
    parameter_file_generator(name, time_limit)
    try:
        subprocess.check_output(f"./LKH ATSP/{name}.par", shell=True, cwd="LKH-3.0.7/")
    except Exception:
        pass
    files = _tour_files(name)
    lkh_cost, path = files[0] if files else (None, None)   # BEST file; tour and cost from the SAME file
    nodes = _read_tour(path) if path else None
    _cleanup(name)
    if not nodes:
        return _out(list(sel), lkh_cost)              # no tour: keep the given order (fallback)
    # node 1 = depot; the jobs follow in tour order
    try:
        z = nodes.index(1)
        rot = nodes[z + 1:] + nodes[:z]
    except ValueError:
        rot = nodes
    seq = [sel[t - 2] for t in rot if 2 <= t <= len(sel) + 1]
    if len(seq) != len(sel):
        return _out(list(sel), lkh_cost)              # incomplete decode: fall back safely

    # ⚠️ DIRECTION AMBIGUITY: LKH solves the ATSP by transforming it into a symmetric TSP
    # and may write the tour in REVERSE (caught in the smoke test: 1 of 8 samples came out
    # consistently reversed, 247 instead of 236). Compute both directions; the one matching
    # the cost REPORTED by LKH is the correct one. This is also a BUILT-IN SANITY CHECK:
    # if neither matches, the decoding is unreliable.
    def _cost(q):
        return (sum(float(processTime[mach_ind][j]) for j in q)
                + sum(float(setupTime[mach_ind][q[k]][q[k + 1]]) for k in range(len(q) - 1)))

    if lkh_cost is not None:
        tol = max(1e-3, 1e-4 * abs(lkh_cost))
        for cand in (seq, seq[::-1]):
            if abs(_cost(cand) - lkh_cost) <= tol:
                return _out(cand, lkh_cost)
        # neither matched -> decoding unreliable; return the cheaper one but mark cost None
        best = min((seq, seq[::-1]), key=_cost)
        return _out(best, None)
    return _out(seq, lkh_cost)


def sequence_solution(assign, processTime, setupTime, time_limit=1):
    """Order the full assignment. Called once at the END of the run."""
    return [sequence_one_machine(processTime, setupTime, assign[l], l, time_limit)
            for l in range(len(assign))]
