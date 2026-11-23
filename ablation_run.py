# -*- coding: utf-8 -*-
"""ABLATION BENCH — for `paper/main.tex` §5.3 (`tab:ablation`, `tab:ablation-scale`).

>>> `hlbb_hm.py` IS NEVER TOUCHED.
    The production loop and its master are COPIED here; two NEW arms (naive opt-cut, RSPA
    perturbation) exist only in this copy. With all of them OFF, the copy must match
    production exactly -> `equiv` proves this.

WHY A COPY (found in PHASE 3): the code of the `plus_optcut` and `plus_perturb` arms does
NOT exist in the production pipeline. `use_optcut`/`_perturb_costs` live only in the OLD
pipeline (`integrated_hlbb.py`, `solve_master_arc`); production's `solve_master_sizered`
does not even have an `opt_cuts` parameter. So the paper's "opt-cut inert" finding came
from the OLD pipeline. The add-back ablation must measure on the FINAL method -> both
levers were ported into this copy.

ARMS (14) — each arm changes ONE component; everything else stays at the BASELINE. The
baseline is NOT WRITTEN OUT AS VALUES here (that would be a second list that could drift):
it is derived from the `hlbb_hm.run_integrated_sr` signature, except for the budget.
To see the effective values: `lockcheck`.

  full            reference = PRODUCTION DEFAULTS (derived, not maintained by hand)
  --- top panel: kept components, removed ONE AT A TIME (leave-one-out) ---
  no_warm         use_warm=False
  no_degree       use_degree=False
  no_bias         use_bias=False
  no_spp          use_spp=False
  no_kmach        kmach=nMachine (no machine-candidate reduction)
  no_pool         pool_mode=None (no master solution-pool harvesting)
  no_master       use_master=False (the main model is NEVER solved: noisy-greedy + LKH +
                  recombination, equal budget — tests the "model-based" attribution, N1/R2.8)
  NOTE: `inside` is NOT AN ARM. inside=False EXCEEDS the budget (the SPP runs outside the
  budget), so it is not a design alternative but a CONTRACT VIOLATION -- it cannot be an
  ablation arm. Its justification is separate: the screen6 gate (it beat the pool-package
  baseline at equal TOTAL time). The loop_s/total_s columns are now written to VERIFY that
  EVERY arm stays within the contract.
  --- bottom panel: dropped components, added back ONE AT A TIME (add-back) ---
  plus_dig        use_dig=True  (DIG was REMOVED from production -> add-back arm; formerly `no_dig`)
  plus_ils        use_ils=True
  plus_setupaware setup_aware=True
  plus_optcut     naive opt-cut     (NEW code, below)
  plus_perturb    RSPA cost perturbation (NEW code, below)
  plus_graded     graded opt-cut    (the form in ab_cut_bneck.py)

MANDATORY LOGGING (ABLATION_PLAN.md §2b): `deg_guard_fired` + `deg_off_iter`. The guard
fires at iter 5 on 640_25 and at iter 1 on 800_30 and is STICKY -> `no_degree` can come out
equal to `full` at large sizes, because degree is already off in `full` too. Without this
log the table is MISREAD.

Usage:
  python3 ablation_run.py lockcheck           # is `full` = production? (~1 s, no Gurobi) RUN FIRST
  python3 ablation_run.py equiv               # is the copy faithful (deterministic regime) ~5 min
  python3 ablation_run.py equiv 50_10 100_15
  python3 ablation_run.py levers              # do the 2 new levers REALLY take effect (sanity)
  python3 ablation_run.py probecuts           # if levers is unclear: cuts ATTACHED / BINDING?
  python3 ablation_run.py cutbind [size] [optcut|graded]   # DEFINITIVE: does the cut raise the master bound
  python3 ablation_run.py regress             # PHASE 3 regression: full == stored HLBB?
  python3 ablation_run.py run  [track] [reps] # main run (resumable)
  python3 ablation_run.py report [track]
  --- SEPARATE EXPERIMENT: re-basing on the DIG-less baseline (does NOT touch ablation.csv) ---
  python3 ablation_run.py rebase [track] [reps]   # results/ablation_rebase.csv (resumable)
  python3 ablation_run.py rebase_report [track]   # new table + interaction check
  --- SEPARATE EXPERIMENT: local branching SCREENING run (does NOT touch the other CSVs) ---
  python3 ablation_run.py screen [reps]           # results/screen_lb.csv (resumable)
  python3 ablation_run.py screen_report
  --- SEPARATE EXPERIMENT: bottleneck-scoped degree SCREENING run ---
  python3 ablation_run.py screen2 [reps]          # results/screen_deg.csv (resumable)
  python3 ablation_run.py screen2_report

  python3 ablation_run.py screen3 [reps]          # results/screen_lazy.csv (resumable)
  python3 ablation_run.py screen3_report          # LAZY OUT-DEGREE screening

  python3 ablation_run.py screen4 [reps]          # results/screen_pool.csv (resumable)
  python3 ablation_run.py screen4_report          # MASTER SOLUTION POOL + SPP budget

  python3 ablation_run.py faz0 [reps]             # STAGNATION TRACING (measure-only, resumable)
  python3 ablation_run.py faz0_report             # is there a trigger, and what should k be?
"""
import collections
import csv
import os
import statistics as stats
import subprocess
import sys
import time
import threading
from collections import Counter, deque

import numpy as np
from gurobipy import GRB, Model, quicksum

from methods import env
from HLBB import clear_environment, _close_lkh_pool, solveSingleLKH, JobsOnMachinesDistMat
from hlbb_hm import arc_candidates, greedy_lpt, _route
from intensify import ils
from spp_recombine import spp_recombine, LAST as _SPP_LAST
from ab_cut_bneck import _load
import feas_hook   # SHARED feasibility checker hook

_HERE = os.path.dirname(os.path.abspath(__file__))
# v3: PRODUCTION package ON + no_pool/no_inside arms; output results/ablation_v3.csv.
CSV_PATH = os.path.join(_HERE, "results", "ablation_v3.csv")
COLS = ["track", "size", "inst", "arm", "rep", "makespan", "pre_spp", "iters", "pool",
        "wall", "deg_guard_fired", "deg_off_iter", "mfail", "collapsed", "loop_s", "total_s", "n_harvest",
        "route_s",
        # did the SPP MIP PROVE optimality (spp_recombine.LAST): 2=OPTIMAL, 9=TIME_LIMIT
        "mip_st", "mip_gap",
        # RESERVE DIAGNOSIS: slack = reserve - (spp_route_s + spp_build_s + spp_mip_s)
        "reserve", "spp_route_s", "spp_build_s", "spp_mip_s", "spp_n_uniq", "spp_n_routed",
        "spp_n_cols"]
# `mfail`/`collapsed`: if the master NEVER returned an incumbent, the loop breaks at mfail>=3
# and the result is the greedy seed. This means "it could propose NOTHING", NOT "it proposed
# a bad assignment" -> the table is misread unless the two are distinguished (measured:
# no_kmach @ 800_30, None even after the guard).

BUDGET = 200

# ============================================================= BASELINE (the `full` arm)
# ⭐ LOCK IS NOT WRITTEN BY HAND; IT IS DERIVED FROM THE PRODUCTION SIGNATURE.
#
# WHY: LOCK used to be a hand-maintained COPY. Whenever production changed (components added
# or removed) someone had to come and update LOCK too; for DIG this WAS NOT DONE and the
# `full` arm described an algorithm that was no longer being shipped. The failure mode is
# invisible: the run does not crash, the table produces plausible numbers, it just accounts
# for the WRONG algorithm. Two hand-synchronized lists diverge sooner or later -- the only
# reliable fix is to ELIMINATE the second list.
#
# The baseline now comes from a single source: the `hlbb_hm.run_integrated_sr` signature.
# If a flag changes in production the baseline changes BY ITSELF; nothing needs writing
# here. For the same reason there are no lines like `use_dig=False` -- DIG has no special
# status any more; whatever production does is the baseline.
# `trace`: when trace entered the production signature it fell into LOCK and COLLIDED with
# the worker's own `trace=tr` pass (duplicate keyword TypeError). The harness owns the
# diagnostic trace.
_HARNESS_OWNED = {"total_time_limit", "seed", "max_iter", "verbose", "return_solution", "diag",
                  "trace"}


def _prod_lock():
    """The `full` arm = production defaults. Keys the harness manages itself are excluded."""
    import inspect
    from hlbb_hm import run_integrated_sr
    prod = inspect.signature(run_integrated_sr).parameters
    copy = inspect.signature(run_abl).parameters
    lock, missing = {}, []
    for k, v in prod.items():
        if k in _HARNESS_OWNED or v.default is inspect._empty:
            continue
        if k not in copy:
            missing.append(k)          # production gained a knob with no counterpart in the copy
            continue
        lock[k] = v.default
    if missing:
        # NO SILENT PASS: the copy lags production; the ablation CANNOT measure that component.
        raise RuntimeError(
            "TEZGAH GERIDE: uretimde olup run_abl'da olmayan parametreler -> " + ", ".join(missing)
            + "\nOnce bunlari run_abl'a tasi, sonra `lockcheck` + `equiv` kos.")
    return lock


# LOCK is assigned AFTER `run_abl` is defined (below: "LOCK = _prod_lock()").

SIZES_B = ["50_10", "100_15", "150_15", "200_20", "250_20", "400_20", "640_25", "800_30"]
SIZES_A = ["50_20", "100_20", "150_15", "200_15", "250_10"]
INSTS = ["1", "2", "3"]

# arm -> run_abl kwargs delta ("__kmach_full__" is filled with nMachine in the worker)
ARMS = {
    "full":            {},
    "no_warm":         {"use_warm": False},
    "no_degree":       {"use_degree": False},
    "no_bias":         {"use_bias": False},
    "no_spp":          {"use_spp": False},
    "no_kmach":        {"kmach": "__kmach_full__"},
    "no_pool":         {"pool_mode": None, "pool_k": 0},   # solution-pool harvesting OFF
    # MASTER-FREE (no_master arm; pre-registration protocol, package 5): greedy(+noise) + LKH
    # + recombination. Direct test of the "model-based advantage" attribution: if this arm
    # gets within <=0.5 RPD of the full method the attribution is narrowed (protocol §8
    # decision table). Equal budget + the same SPP contract.
    "no_master":       {"use_master": False},
    "plus_dig":        {"use_dig": True},                  # DIG was DROPPED -> bottom panel, not top
    "plus_ils":        {"use_ils": True},
    "plus_setupaware": {"setup_aware": True},
    "plus_optcut":     {"cut_mode": "optcut"},
    "plus_perturb":    {"rspa_strength": 0.2},
    "plus_graded":     {"cut_mode": "graded"},
}
ARMS_A = ["full", "no_warm", "no_degree", "no_bias", "no_spp", "no_kmach", "no_pool"]

# ============================================================ REBASE (SEPARATE EXPERIMENT)
# NOT ADDED to ARMS, NOT WRITTEN to ablation.csv. Rationale: this is a DIFFERENT question.
#   ablation.csv (864 runs)  : "which components carry weight around `full`?"
#   ablation_rebase.csv      : "does the answer CHANGE when the shipped design is `no_dig`?"
# Mixing them would alter a finished data set, break the fixed arm lists of the analysis
# scripts, blend two experiments into one table, and falsify the "864 runs" figure.
#
# THE BASELINE IS INSIDE TOO: `no_dig` is re-run in THIS experiment's own session -> the new
# table is fully self-consistent, borrows no numbers from an old session, and the drift
# question never arises.
REBASE_CSV = os.path.join(_HERE, "results", "ablation_rebase.csv")
REBASE_ARMS = {
    "no_dig":          {"use_dig": False},                              # NEW BASELINE (fresh)
    "nodig_no_warm":   {"use_dig": False, "use_warm": False},
    "nodig_no_degree": {"use_dig": False, "use_degree": False},
    "nodig_no_bias":   {"use_dig": False, "use_bias": False},
    "nodig_no_spp":    {"use_dig": False, "use_spp": False},
    "nodig_no_kmach":  {"use_dig": False, "kmach": "__kmach_full__"},
    # --- BOTTOM PANEL: rejected candidates, against the SAME `no_dig` baseline.
    # WHY: the paper's tab:ablation top panel came from this file (baseline no_dig) while the
    # BOTTOM panel still came from ablation.csv (baseline `full` = DIG ON) -> the table
    # carried a footnote that the two panels use different references, the first thing a
    # referee would ask about. Once these 6 arms finish, the ENTIRE table is produced from
    # one file, one baseline, one RPD denominator, and the footnote is REMOVED.
    # CAUTION: adding new arms can LOWER B (the cell denominator = best over all arms) in
    # some cells -> the top panel's published numbers shift a little too. That is CORRECT
    # behavior (one experiment = one denominator) but the table must be regenerated WHOLE,
    # not patched by hand.
    "nodig_plus_dig":        {"use_dig": True},      # = add DIG back (pre-production config)
    "nodig_plus_ils":        {"use_dig": False, "use_ils": True},
    "nodig_plus_setupaware": {"use_dig": False, "setup_aware": True},
    "nodig_plus_optcut":     {"use_dig": False, "cut_mode": "optcut"},
    "nodig_plus_perturb":    {"use_dig": False, "rspa_strength": 0.2},
    "nodig_plus_graded":     {"use_dig": False, "cut_mode": "graded"},
}
REBASE_DROP = [a for a in REBASE_ARMS if a.startswith("nodig_no_")]      # top panel
REBASE_ADD = [a for a in REBASE_ARMS if a.startswith("nodig_plus_")]     # bottom panel
# `_kw` must resolve arms from both tables (the worker is invoked by name).
# `no_dig` has the same kwargs in both -> no clash.

# ========================================= SCREEN: LOCAL BRANCHING (SEPARATE EXPERIMENT)
# Again a SEPARATE CSV. This is a SCREENING run: a go/no-go signal on whether the idea
# works, not a full table. If positive, a full 8-size run is done separately.
#
# LOCAL BRANCHING (Rei, Cordeau, Gendreau & Soriano 2009, INFORMS JoC 21(2):333-345 --
# "Accelerating Benders decomposition by local branching"):
#   ONE constraint on the master: sum_{(i,l) in incumbent} (1 - y[i,l]) <= k
#   = "at most k jobs may change machine". Zero new variables.
#
# WHY THIS IDEA, WHY NOW (from the rebase run's data):
#   - master SIZE is the binding resource: candidates 3->5 = +6.6%, 3->15 = total collapse
#     -> anything that GROWS the master fights a measured penalty. LB SHRINKS the master.
#   - warm start is the largest lever (+6.5) and on 400_20 the warm-less master returns the
#     EXACT greedy seed in 9/9 runs. But warm is a weak tool: it only sets the STARTING
#     point; Gurobi goes wherever it wants for 3 seconds. LB KEEPS it near the incumbent.
#   - HOPE: if the master is limited to a small neighborhood it also solves fast with degree
#     constraints ON -> the deg-guard does not fire -> the +2-5% degree lever lost on
#     640/800 comes back BY ITSELF. That is why the report also prints the guard rate.
SCREEN_CSV = os.path.join(_HERE, "results", "screen_lb.csv")
# `n_lbfail` ONLY in this CSV: in how many iterations was the neighborhood EMPTY and the
# constraint lifted? If high, the arm approaches the baseline -> a negative result then
# means "not tested", NOT "bad idea".
SCREEN_COLS = COLS + ["n_lbfail"]
SCREEN_SIZES = ["100_15", "400_20", "800_30"]   # harm at small size? / cold-start collapse / guard
# k = lb_frac * nJob. PROPORTIONAL, not absolute: "at most X% of n may move" means the SAME
# thing at every scale (no size-dependent rule).
#
# The k values were chosen by MEASUREMENT (probe: Hamming distance between consecutive
# master proposals):
#   100_15: median 19 jobs (19%)   mean  20.1   max  43
#   400_20: median 76 jobs (19%)   mean 152.9   max 379  (= 95% of n! the master sometimes
#           moves everything)
#   800_30: median 60 jobs (7.5%)  mean  68.2   max 331
# So the NATURAL neighborhood is ~8-19%. For any benefit k must be BELOW that (the
# constraint must bind). The bracket deliberately spans "clearly tight" to "natural level"
# -> if the result is negative we can separate "bad idea" from "bad k".
SCREEN_ARMS = {
    "no_dig":   {"use_dig": False},                        # baseline (= the shipped design)
    "lb_tight": {"use_dig": False, "lb_frac": 0.05},       # clearly tighter than natural at all scales
    "lb_mid":   {"use_dig": False, "lb_frac": 0.10},       # near natural at 800, tight at small sizes
    "lb_loose": {"use_dig": False, "lb_frac": 0.20},       # near natural at 100/400 = CONTROL
}


# ================================= SCREEN2: BOTTLENECK-SCOPED DEGREE (SEPARATE EXPERIMENT)
# Again a SEPARATE CSV. Based on the rule that EMERGED from the local-branching screen:
#   "a constraint that TIGHTENS the LP helps; a constraint that merely RESTRICTS the
#    feasible set hurts; adding variables always hurts."
# degree = sparse, VALID inequality, tightens the LP -> the only family PROVEN to work (+2.2).
#
# TARGETED GAP: on 640_25 and 800_30 the deg-guard fires 9/9, i.e. full degree makes the
# master unsolvable in 3 s and the inequality shuts down ENTIRELY. The one lever known to
# work is disabled exactly at the two scales where we are weakest.
# ATTEMPTED FIX: place the inequality not on all machines but on the q machines with the
# largest span. The constraint count drops to ~q/m; since the bottleneck already determines
# the makespan, most of the value sits there. q is PROPORTIONAL (deg_frac * m) -> the same
# rule at every scale.
# The bottleneck set is re-chosen EVERY ITERATION from the most recently routed spans (if
# the bottleneck drifts, the scope drifts with it). The guard stays in place: if the reduced
# form is still unsolvable it shuts down again.
SCREEN2_CSV = os.path.join(_HERE, "results", "screen_deg.csv")
SCREEN2_SIZES = ["100_15", "400_20", "800_30"]   # scales where the guard does not / does fire
SCREEN2_ARMS = {
    "no_dig":    {"use_dig": False},                       # baseline: degree on ALL machines + guard
    "deg_bneck": {"use_dig": False, "deg_frac": 0.001},    # bottleneck only (q=1; ratio forces the floor)
    "deg_q10":   {"use_dig": False, "deg_frac": 0.10},     # top 10% of machines
    "deg_q25":   {"use_dig": False, "deg_frac": 0.25},     # top 25% of machines
}
# NOTE (smoke test 800_30, 60 s): narrowing the scope REALLY stops the guard --
#   no_dig    -> guard fired at iter 1 (degree fully shut down), mk=482
#   deg_bneck -> guard DID NOT fire (degree alive), mk=482
#   deg_q25   -> guard did not fire BUT mk=617 = greedy seed (useless master)
# So 8/30 machines are still too heavy. The interesting region is small q -> the 50% arm was
# DROPPED and 10% added instead. Also the INVERSE DANGER: the guard is not just a safety
# net; it may be a BETTER configuration than partial degree ("shut it all off" yields a
# working master, while "keep it on 8 machines" yields a solvable but useless master and the
# rescue never kicks in).

# ====================================== SCREEN3: LAZY OUT-DEGREE (SEPARATE EXPERIMENT)
# Again a SEPARATE CSV. The only path left after SCREEN2 (scope narrowing) came out NEGATIVE.
#
# SAME INEQUALITY, DIFFERENT DELIVERY. The mathematics does not change, validity does not
# change, the "all or nothing" discipline is kept (that is what SCREEN2 distorted: WE fixed
# the scope). The only change is WHEN the rows enter the model: all up front -> Gurobi pulls
# them in as they are violated.
#
# WHY (from the rebase data, `no_dig` arm, guard firing time / mean 58 iterations):
#   50_10..250_20  guard 0/9                      -> degree always on,  delta +2.1..+4.9
#   400_20         guard 1/9 @38                  -> +2.12
#   640_25         guard 9/9 @9,13,13,13,22,22,22,23,23  -> on for ~35% of the run -> -1.12 (!)
#   800_30         guard 9/9 @1,1,1,2,5,5,6,7,7   -> practically never on -> +0.52 (noise)
# So the one lever PROVEN to work (+2.2) is disabled exactly at the two scales where we are
# weakest. The guard CANNOT be removed (on 800_30 it fires at iteration 1 = the master
# returns NO incumbent; without the guard the loop would break at mfail>=3 and the result
# would be the greedy seed).
#
# ⭐ THE HARM IS QUALITY, NOT TIME (measured): iteration count 57.6 with degree on / 58.2
# off (1%). So the hypothesis "degree slows the master and eats budget" is WRONG. The extra
# rows change the PATH of Gurobi's 3-second incumbent search. The master is never proven
# optimal at any scale (400_20: 0/29, 800_30: 0/27) -> TIGHT LP != GOOD INCUMBENT under a TL.
#
# LITERATURE: the survey by Rahmaniani et al. flags exactly this pattern as future work:
# "Strategies that tighten the MP usually add inequalities ONLY ONCE, before
# the initial iterations. ... it would be interesting to explore the use of more advanced
# cutting-plane methods to further tighten the MP AT EACH ITERATION." Wu et al. (2024)
# deliver LBBD cuts via lazy constraint callbacks on the same problem family.
# Hooker §4.2 (branch-and-check) is the same architecture.
#
# TRANSPARENT TRADE-OFF: lazy rows are absent from the LP relaxation -> the master's LOWER
# BOUND weakens. Not a problem for us (master = incumbent generator; no certified LB is
# sought). Gurobi Lazy levels 1/2/3 = the "how early should it engage" axis; all three are
# arms so that the DATA decides which balance is right.
#   1 = only if violated at an integer solution     (laziest, smallest model)
#   2 = + at node relaxations                       (middle)
#   3 = + at the root relaxation                    (most eager, closest to current behavior)
#
# ACCEPTANCE THRESHOLD (fixed IN ADVANCE, no after-the-fact rationalization):
#   on 800_30 deg_guard_fired 9/9 -> ~0/9  AND no degradation beyond 2SE at any size.
# If the guard rate does not drop, the mechanism did not work; if it drops but makespan
# degrades, "tight LP != good incumbent" is confirmed. Both negative -> config stays as is.
#
# screen3: arms that deliver out-degree as Gurobi Lazy 1/2/3. The FULL RUN WAS NOT TAKEN;
# the idea was measured directly at the master level (800_30/640_25, single master call):
# lazy rows do not leave the model and slow down the first-feasible search -> NEGATIVE (in
# the paper under 'Rejected mechanisms'). The arms remain as documentation; the measurement
# CSV is not part of the package. For the known limitation of the degree guard see
# KNOWN_LIMITATIONS.md.
SCREEN3_CSV = os.path.join(_HERE, "results", "screen_lazy.csv")
SCREEN3_SIZES = ["100_15", "400_20", "800_30"]   # guard fires never / once / 9 times
SCREEN3_ARMS = {
    "no_dig":     {"use_dig": False},                     # baseline: degree up front, all machines
    "deg_lazy1":  {"use_dig": False, "deg_lazy": 1},
    "deg_lazy2":  {"use_dig": False, "deg_lazy": 2},
    "deg_lazy3":  {"use_dig": False, "deg_lazy": 3},
}

# ==================================== SCREEN4: MASTER SOLUTION POOL (SEPARATE EXPERIMENT)
# Measured finding: on 640/800, after the deg-guard fires the master's NOVELTY collapses
# 0.60 -> 0.06 (confound tested: in the same window the rate is 0.55-0.74 at guard-free
# sizes and 0.19-0.20 at the two guarded ones). So the master is not SLOW, it REPEATS ITSELF.
#
# MEASURED (master_tl=3s, single solution, degree off = the post-guard state):
#   800_30  mode0 (FREE): 6 solutions, pairwise Hamming mean 0.338, columns 30 -> 149  (5.0x)
#   640_25  mode0       : 10 solutions, Hamming 0.222,              columns 25 -> 183  (7.3x)
#   200_20  mode0       : 10 solutions, Hamming 0.187,              columns 20 -> 130  (6.5x)
# For comparison: post-guard CONSECUTIVE iterations have novelty 0.05.
# -> a SINGLE master solve holds more diversity than 60 iterations produce, and right now
#    we THROW AWAY 5 of its 9 solutions. Mode 0 NEEDS NO EXTRA TIME (3.35s vs 3.02s vs
#    3.58s measured).
#
# LITERATURE: the survey by Rahmaniani et al. explicitly marks this direction as OPEN:
# "we are not aware of any study showing how to obtain better cuts via a careful selection
#  from the MULTIPLE OPTIMAL SOLUTIONS of the MP". The actual scheme of Rei et al. (2009)
# was also pool generation -- but for that they add the constraint we measured to be
# harmful to the master; PoolSearchMode delivers the same product FOR FREE.
#
# (!) PRECONDITION — COLUMN-BASED SPP ROUTING (NOT for the budget; for the pool to pay off).
# MEASUREMENT (800_30, budget 200s): with SPP 244s, without SPP 243s
# -> the SPP is 1 SECOND. The whole excess is FIXED start-up cost (process spawn + reading
# the 800x30 instance + LKH pool setup; measured independently of budget: budget 20s->+37,
# 60s->+36, 120s->+39). Also, in the real benchmark (niche_benchmark.py:118) `readproblem`
# runs BEFORE t0, so it never enters the reported wall time. NO FAIRNESS ISSUE.
#
# spp_by_column is STILL REQUIRED, for another reason: the `max_assigns=80` trim. With the
# pool on, the assignment count goes 62 -> ~500; the trim picks 80 and drops the rest =
# most of the gain is wasted. by_column removes the assignment trim and reduces routing to
# a SINGLE pass per column (measured: the old path ran 2400 machine-routes on 800_30 to
# produce ~1050 unique columns = 56% repetition).
# `spp_budget` is no longer a correction but a SEAT BELT: when the pool grows the SPP it
# must not exceed the budget.
# The `spp_fix` arm isolates ONLY the routing change, without the pool (control).
#   spp_by_column: first dedup to (machine, job-set) columns, route each column ONCE.
#     Measured: the old path ran 2400 machine-routes on 800_30 to produce ~1050 unique
#     columns = 56% repetition. It also makes the max_assigns=80 trim unnecessary (with the
#     pool, 80 of 620 assignments would be picked = most of the gain wasted).
#   spp_budget: seconds granted to the SPP ON TOP of the total budget. 0 = fully inside.
#     must_include=incumbent is routed in the first batch -> the SPP stays feasible even if
#     the deadline fills early.
SCREEN4_CSV = os.path.join(_HERE, "results", "screen_pool.csv")
SCREEN4_COLS = COLS + ["tailnov", "n_harvest"]   # THRESHOLD 2 is unmeasurable without these
SCREEN4_SIZES = SIZES_B                   # FULL LADDER (8 sizes)
SCREEN4_INSTS = INSTS                     # 3 inst x 3 reps = 24 cells per arm (x3 runs)
# WHY A DECISION RUN, NOT A SCREEN: the mechanism targets 640/800, but for production it
#   must also be shown harmless at SMALL sizes. 24 cells = the SAME design as the rebase
#   table -> if positive it can enter the config without a second confirmation run.
# READING ORDER: (1) tailnov = did the mechanism work, (2) spp_fix vs pool_free = does the
#   gain come from the trim or from the harvest, (3) makespan. tailnov has far lower
#   variance, so the mechanism question is answered BEFORE the makespan one, and more
#   decisively.
SCREEN4_ARMS = {
    "no_dig":    {"use_dig": False},
    "spp_fix":   {"use_dig": False, "spp_by_column": True, "spp_budget": 0},
    "pool_free": {"use_dig": False, "spp_by_column": True, "spp_budget": 0,
                  "pool_mode": 0},                                       # FREE harvest
    "pool_m1":   {"use_dig": False, "spp_by_column": True, "spp_budget": 0,
                  "pool_mode": 1, "pool_k": 20},
}
# mode 2 (n-best) ARM DROPPED: measured, no information gain. On 640_25 mode0 and mode1
# came out IDENTICAL (10 solutions, same Hamming, same columns); on 800_30 mode1=10 vs
# mode2=11 solutions, pool 500 vs 556 (11%) in the smoke test. An 11% pool difference
# cannot show up in makespan with 8 cells, and mode2 lengthens the solve (3.02s -> 3.58s).
# ACCEPTANCE THRESHOLD (fixed IN ADVANCE; CORRECTED in the dry test, BEFORE the run):
#  (!) MY FIRST THRESHOLD WAS FLAWED: it was "overall dRPD <= -2SE". In a fake-data dry
#  test, injecting a -4 unit effect at 640/800 and nothing elsewhere gave -0.91/-0.73 in
#  the subgroup, but the OVERALL mean stayed at -0.22 and MISSED the threshold -- i.e. it
#  would have REJECTED a real, useful effect. Reason: the mechanism targets 640/800; the 6
#  untargeted sizes dilute the mean. A targeted intervention is tested on the TARGET
#  SUBGROUP; the rest is a do-no-harm check.
#
#  1) MECHANISM (primary, lowest variance): on 640_25 + 800_30 the tail novelty MUST rise
#     clearly above the baseline ~0.05. If it does not, the mechanism did not work; any
#     makespan gain has another cause -> the arm is NOT ACCEPTED.
#  2) QUALITY, TARGET SUBGROUP: in the 640_25+800_30 cells dRPD negative AND |mean| > 2SE
#     (that subgroup's own SE). The overall dRPD is REPORTED but is NOT the gate (dilution).
#  3) DO NO HARM: in the n<=400 subgroup dRPD must NOT exceed +2SE (neutral or better is
#     fine, significantly WORSE is not). This is the condition for production.
#  4) BUDGET: mean run time must not grow across arms.
#  The arm is rejected unless all four hold.

# =========================================================================== SCREEN-5
# MASTER SOLUTION POOL, FAIR MEASUREMENT. The CORRECT design after the screen4 mistake.
#
# WHY A NEW RUN: screen4 COULD NOT measure the pool (spp_budget=0 killed the SPP). spp_probe
# measurements showed the mechanism is REAL (1.2-4.5%) but routing all columns takes
# 76-148 s -> the gain in that measurement also contained the EXTRA TIME; it was not
# separated from the mechanism. This run makes exactly that separation.
#
# WHAT CHANGED (two things, both from measurement):
#   spp_cap=250 : the curve says ALL of the gain arrives within 160-320 unique assignments.
#                 The production cap of 80 drops 75-81% of the columns when the pool is on.
#                 250 is a single number, the same at every size -> NO size-based branching.
#   incumbent   : best_assign is placed at the head of the pool (see the note in run_abl).
#
# ⭐ FAIRNESS ARM (base_plus): the pool arm spends ~25-30 s MORE in the SPP. "Is the gain
# from the mechanism or from the extra time?" can only be separated by giving the baseline
# the SAME time. base_plus = baseline + 30 s EXTRA LOOP budget. If the pool arm cannot beat
# base_plus, we have merely bought time, not a mechanism.
# (Pre-measurement: 62% of the run passes AFTER the last improvement -> base_plus is
#  expected to gain little from the extra 30 s; but an expectation is not a measurement,
#  hence the arm.)
SCREEN5_CSV = os.path.join(_HERE, "results", "screen_pool2.csv")
SCREEN5_SIZES = SIZES_B
SCREEN5_INSTS = INSTS
SCREEN5_ARMS = {
    "base":      {"use_dig": False},
    "pool160":   {"use_dig": False, "pool_mode": 1, "pool_k": 20, "spp_cap": 160},
    "pool250":   {"use_dig": False, "pool_mode": 1, "pool_k": 20, "spp_cap": 250},
    "base_plus": {"use_dig": False, "budget_bonus": 60},
}
# WHY BONUS=60 (MEASURED, spp_probe --rank, cap=250, `even` policy):
#   size       base SPP    pool250 SPP   diff
#   200_20       6.9 s        45.3 s     +38
#   640_25       7.2 s        58.4 s     +51
#   800_30       8.0 s        65.3 s     +57
# My first value of 45 WAS NOT ENOUGH -> on 640/800 pool250 would use MORE time than
# base_plus and the gate would break in its own favor (exactly what we want to avoid). 60
# is DELIBERATELY GENEROUS: an excessive bonus can only produce FALSE NEGATIVES, never a
# false positive. THRESHOLD 3 verifies this empirically.
#
# ⭐ WHY pool160 EXISTS: the curve (spp_probe --curve) showed that on 800_30, 160
# assignments gain as much as 320, in LESS THAN HALF the time. The cheap variant is both
# more defensible (today pool250 spends 28% of the budget in the SPP) and more likely to
# pass the time-equalized gate. base_plus60 is the gate for BOTH -> for pool160 it is
# OVERLY generous, so passing it is an even stronger result.
# A SELECTION POLICY (which 160/250) WAS TRIED and REJECTED: ranking by a master-load proxy
# changed quality NOT AT ALL on 640/800 (475=475=475, 470=470=470) and was 1.7-2.4x MORE
# EXPENSIVE. `even` (the existing evenly spaced sampling) is kept.
# ACCEPTANCE THRESHOLD (fixed BEFORE the run):
#  1) pool250 vs base_plus dRPD < -2SE  -> the mechanism gains INDEPENDENTLY of time
#  2) in the n<=400 subgroup pool250 must NOT harm base by more than +2SE
#  3) pool250's wall clock must NOT exceed base_plus's (else the comparison is again unfair)
# If 1 fails the mechanism is REJECTED (gain = purchased time).

# =========================================================================== SCREEN-6
# INSIDE-200: EVERYONE GETS A REAL 200 SECONDS. screen5 proved the mechanism (pool250 3/3
# thresholds, p=0.0013) but the SPP was OUTSIDE the budget (+31/46s). This run makes the
# same comparison INSIDE the contract:
#   inside=True -> (1) the loop runs until T-reserve; the reserve is derived from the
#   per-assignment routing time measured DURING the run (NO size threshold), (2) the SPP can
#   be cut off at deadline=T-2 (the incumbent is routed first -> feasibility), (3) periodic
#   cleanup inside the SPP (glob load, measured +12%), (4) the loop's route cache is carried
#   into the SPP, (5) last-iteration overshoot protection (it_ema).
# GATE: pool250_inside must beat base_inside at EQUAL TOTAL TIME. base_plus is no longer
# needed -- both arms use the same budget; no "purchased time" difference remains.
# QUICK TEST FIRST (before screen6): 4 runs ~15 min; wall<=~202, SPP alive, mk at the
# screen5 pool250 level. If broken, the long run is NOT started.
SCREEN6_CSV = os.path.join(_HERE, "results", "screen_inside.csv")
SCREEN6_COLS = COLS + ["tailnov", "n_harvest", "loop_s", "total_s", "n_bgroute"]
# THREE ARMS: pool250_bg = the production candidate package (S1 included); pool250_inside =
# pool without S1 -> the ATTRIBUTION split is inside the run:
#   pool250_bg  vs base_inside    = GATE (package, equal contract)
#   pool250_bg  vs pool250_inside = S1's share
#   pool250_inside vs base_inside = the pool's share (without S1)
# S1 smoke (800_30/200_20): bg routed 6014/6299 columns, the SPP dropped to 3.9/8.5 s, loop
# 155->183, iters 47 (NO drop -> the master was not starved), total 186.6/194.1 <= 202.
SCREEN6_ARMS = {
    "base_inside":    {"use_dig": False, "inside": True},
    "pool250_inside": {"use_dig": False, "inside": True,
                       "pool_mode": 1, "pool_k": 20, "spp_cap": 250},
    "pool250_bg":     {"use_dig": False, "inside": True,
                       "pool_mode": 1, "pool_k": 20, "spp_cap": 250, "bg_route": True},
}

ALL_ARMS = {**ARMS, **REBASE_ARMS, **SCREEN_ARMS, **SCREEN2_ARMS, **SCREEN3_ARMS,
            **SCREEN4_ARMS, **SCREEN5_ARMS, **SCREEN6_ARMS}


# =========================================================================== master (copy)
def solve_master_abl(nJob, nMachine, c1, c2, processTime, setupTime, I_l, L_i,
                     nogoods, master_tl, readyTime=None, bias=None, kmach=5, K=10,
                     hint=None, kcap=None, rank=None, use_degree=True, warm=None,
                     opt_cuts=(), gcuts=(), diag=None, lb_k=None, deg_set=None,
                     deg_lazy=None, pool_mode=None, pool_k=0, pool_sink=None,
                     extra_arcs=None, fix_y=None, gparams=None, arc_rank="cost",
                     tight_s=False, sec_obj="off", sec_k=3, sec_w=0.1,
                     extra=None, arc_keep=False):
    """EXACT copy of hlbb_hm.solve_master_sizered + TWO NEW cut families.
    With opt_cuts/gcuts EMPTY the model is identical to production.
    extra_arcs: {(l, i) -> predecessor set} — S3 ORACLE TEST: incoming arcs harvested from
    LKH tours that are NOT in the K-list are ADDED to the arc set (None = same as production).
    fix_y: [(i, l)] — Q1 ORACLE TEST (FSS consensus fixing): each listed y[i,l] is FIXED
    to 1 (LB=1; skipped and counted if the variable is absent). None = same as production.
    diag["track_inc"]=True — Q4 WASTE ORACLE: incumbent timestamps (RUNTIME, obj) are
    written to diag["inc_log"] + diag["t_build"] = model build time. Off by default."""
    _t_entry = time.time()
    cap = kcap if kcap is not None else (kmach + 2)
    allowed = {}
    allowed0 = {}                      # the set BEFORE machine-side additions (only for arc_keep)
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
            # MACHINE SIDE (3J2M, v6 — block IDENTICAL to hlbb_hm.solve_master_sizered):
            # each machine's fastest jobs are also candidates. NO cap; computed once in run_abl.
            allowed0[i] = list(base)
            for l in extra[i]:
                if l not in base:
                    base.append(l)
        allowed[i] = base
    Ir = {l: [i for i in range(nJob) if l in allowed[i]] for l in range(nMachine)}

    mdl = Model("MIP-A-abl", env=env)
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
    arcs = {l: {} for l in range(nMachine)}
    x = {}; xd = {}
    _IrSet = {l: set(Ir[l]) for l in range(nMachine)} if extra_arcs else None
    _cand_l = {l: arc_candidates(setupTime, l, Ir[l], K, arc_rank, processTime)
               for l in range(nMachine)}
    if arc_keep and extra is not None:
        # ARC-PRESERVING machine side (v6 — block IDENTICAL to production): when Ir[l] grew,
        # the predecessor lists of old jobs were rebuilt and 5-8% of the slots moved to new
        # jobs. Old pairs take their lists UNCHANGED from the old set (Ir0); only new pairs
        # use the enlarged set.
        Ir0 = {l: [i for i in range(nJob) if l in allowed0.get(i, allowed[i])] for l in range(nMachine)}
        for l in range(nMachine):
            a0 = arc_candidates(setupTime, l, Ir0[l], K, arc_rank, processTime)
            old = set(Ir0[l])
            _cand_l[l] = {i: (a0[i] if i in old else _cand_l[l][i]) for i in Ir[l]}
    for l in range(nMachine):
        for i in Ir[l]:
            cand = list(_cand_l[l][i])
            if extra_arcs:
                # ORACLE ARCS: predecessors not in the K-list but used by LKH. Only those
                # inside Ir[l] (no arc can be opened to a pair without a y variable).
                for j in extra_arcs.get((l, i), ()):
                    if j != i and j in _IrSet[l] and j not in cand:
                        cand.append(j)
            arcs[l][i] = cand
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
    if use_degree:
        # If deg_set is given, the inequality is placed ONLY on those machines
        # (bottleneck-scoped degree). Rationale: on 640_25/800_30 full degree makes the
        # master unsolvable in 3 s -> the guard fires 9/9 and shuts the inequality down
        # ENTIRELY, so the +2-5% lever disappears exactly where we are weakest (measured).
        # Narrowing the scope cuts the constraint count to ~|deg_set|/m; since the
        # BOTTLENECK machine already determines the makespan, most of the tightening value
        # sits there. deg_set=None -> old behavior (all machines).
        dset = range(nMachine) if deg_set is None else deg_set
        succ = {l: {} for l in dset}
        for l in dset:
            for i in Ir[l]:
                for j in arcs[l][i]:
                    succ[l].setdefault(j, []).append(i)
        for l in dset:
            for j, succs in succ[l].items():
                con = mdl.addConstr(quicksum(x[j, i, l] for i in succs) <= y[j, l])
                # LAZY DELIVERY: the row is THE SAME; it only enters the model when violated.
                # Goal: prevent the n*kmach up-front rows from making the master unsolvable
                # in 3 s (-> the deg-guard shutting the inequality down ENTIRELY).
                if deg_lazy:
                    con.Lazy = deg_lazy
    for l in range(nMachine):
        ready_term = readyTime[l] * u[l] if readyTime is not None else 0
        bias_term = bias[l] * u[l] if bias is not None else 0
        # SAME AS PRODUCTION (hlbb_hm.solve_master_sizered): with tight_s/sec_obj on, s[l]
        # is SET EQUAL to the load. With both off the constraint stays `>=` = the exact
        # production model.
        if tight_s or sec_obj != "off":
            mdl.addConstr(
                s[l] == ready_term + bias_term +
                        quicksum(processTime[l][i] * y[i, l] for i in Ir[l]) +
                        quicksum(setupTime[l][j][i] * x[j, i, l]
                                 for i in Ir[l] for j in arcs[l][i]))
            continue
        mdl.addConstr(
            s[l] >= ready_term + bias_term +
                    quicksum(processTime[l][i] * y[i, l] for i in Ir[l]) +
                    quicksum(setupTime[l][j][i] * x[j, i, l] for i in Ir[l] for j in arcs[l][i]))
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
    # ---- NEW (A): naive opt-cut. cmax >= h_l * (1 - sum_{i in S_l}(1 - y_il))
    #      once a SINGLE job leaves the assignment the RHS goes <=0 -> the cut dies.
    #      The form in paper §3.2.
    cut_con = []; n_skip = 0
    for (l, S_l, h_l) in opt_cuts:
        # VALIDITY: if a job in S_l is NOT A CANDIDATE for l in this iteration's reduced
        # model (no y[i,l]), that job CANNOT be on l -> S_l can never repeat exactly -> the
        # cut is already satisfied. Skipping the job and building the cut on the remaining
        # subset would be INVALID (it would impose h_l on a machine with fewer jobs). The
        # right move: SKIP the cut entirely.
        if any((i, l) not in y for i in S_l):
            n_skip += 1
            continue
        cut_con.append(mdl.addConstr(cmax >= h_l * (1 - quicksum(1 - y[i, l] for i in S_l))))
    # ---- NEW (B): graded opt-cut (the ab_cut_bneck form). Only Delta_i is subtracted per
    #      departed job -> it stays binding until 4-6 jobs have moved.
    for (b, S_b, h_b, delta) in gcuts:
        # VALIDITY (same flaw, different remedy): for a job absent from the model (1-y)=1 is
        # constant, so delta_i must be subtracted UNCONDITIONALLY. Skipping it raises the
        # RHS = an INVALID cut. Here, instead of dropping the cut, we subtract the constant
        # term correctly -> the cut REMAINS valid.
        present = [i for i in S_b if (i, b) in y]
        absent = sum(delta[i] for i in S_b if (i, b) not in y)
        if not present:
            continue
        cut_con.append(mdl.addConstr(
            cmax >= h_b - absent - quicksum(delta[i] * (1 - y[i, b]) for i in present)))
    # ---- NEW (D): LOCAL BRANCHING (Rei, Cordeau, Gendreau & Soriano 2009, INFORMS JoC 21(2))
    #      ONE constraint: at most k of the (i,l) pairs in the incumbent may be broken
    #        sum_{(i,l) in incumbent} (1 - y[i,l]) <= k     = "at most k jobs change machine"
    #      Zero new variables. It does NOT grow the master; it NARROWS the search space -> a
    #      neighborhood that is actually searchable in 3 s. The answer to warm start's weak
    #      side: warm only sets the STARTING point and Gurobi may go anywhere for 3 seconds;
    #      this constraint KEEPS it near the incumbent.
    #      CAUTION: this is NOT a valid inequality but a search RESTRICTION -- it cuts off
    #      feasible solutions. The master objective is therefore no longer a global lower
    #      bound. Fine here since certified LBs are out of scope; but it must NOT be used
    #      as an LB.
    #      If it returns empty, the caller retries without the constraint (see run_abl).
    if lb_k is not None and warm is not None:
        lbt = [1 - y[i, l] for l in range(nMachine) for i in warm[l] if (i, l) in y]
        if lbt:
            mdl.addConstr(quicksum(lbt) <= lb_k)
    if warm is not None:
        for l in range(nMachine):
            wl = [i for i in warm[l] if (i, l) in y]
            for i in wl:
                y[i, l].Start = 1.0
            if l in u:
                u[l].Start = 1.0 if wl else 0.0
    # Q1 ORACLE: consensus fixing. LB=1 SHRINKS the problem (adds no constraint) -> outside
    # the scope of the local-branching lesson. (i,l) without a variable is skipped; counted
    # in diag.
    n_fix_miss = 0
    if fix_y:
        for _i, _l in fix_y:
            if (_i, _l) in y:
                y[_i, _l].LB = 1.0
            else:
                n_fix_miss += 1
    # SECONDARY OBJECTIVE — SAME as hlbb_hm.solve_master_sizered (see the rationale block
    # there). With sec_obj="off" the objective stays `cmax` = the exact production model.
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
        # 0 = keep incidentally found solutions (NO EXTRA TIME) | 1 = search for more | 2 = n-best
        mdl.Params.PoolSearchMode = pool_mode
        if pool_k:
            mdl.Params.PoolSolutions = pool_k
    if gparams:
        for _k, _v in gparams.items():     # B3 ORACLE: Gurobi knob trials (None = same as production)
            mdl.setParam(_k, _v)
    if diag is not None:
        diag["t_build"] = time.time() - _t_entry     # model build tax (Q4 waste oracle)
    if diag is not None and diag.get("track_inc"):
        _inc_log = []
        def _cb(m, where):
            if where == GRB.Callback.MIPSOL:
                _inc_log.append((m.cbGet(GRB.Callback.RUNTIME),
                                 m.cbGet(GRB.Callback.MIPSOL_OBJ)))
        mdl.optimize(_cb)
        diag["inc_log"] = _inc_log
    else:
        mdl.optimize()
    if diag is not None:                       # DIAGNOSIS: did the cuts enter the model; BINDING?
        diag["ncon"] = diag.get("ncon", 0) + mdl.NumConstrs
        diag["ncut_con"] = diag.get("ncut_con", 0) + len(cut_con)
        diag["skip"] = diag.get("skip", 0) + n_skip
        diag["status"] = mdl.Status                      # 2 = OPTIMAL, 9 = TIME_LIMIT
        diag["solcount"] = mdl.SolCount                  # Q1 oracle: does fixing unlock solcount
        diag["fix_miss"] = n_fix_miss                    # jobs that could not be fixed (outside allowed)
        try:
            diag["gap"] = mdl.MIPGap
        except Exception:
            diag["gap"] = None
        diag["opt"] = diag.get("opt", 0) + (1 if mdl.Status == 2 else 0)
        diag["solves"] = diag.get("solves", 0) + 1
        tight = 0; unread = 0; mins = None
        for c in cut_con:
            try:
                sl = abs(c.Slack)
            except Exception:
                unread += 1                    # HONESTY: unreadable != not binding
                continue
            mins = sl if mins is None else min(mins, sl)
            if sl < 1e-6:
                tight += 1
        diag["tight"] = diag.get("tight", 0) + tight
        diag["unread"] = diag.get("unread", 0) + unread
        if mins is not None:
            diag["minslack"] = min(diag.get("minslack", 1e18), mins)
    try:
        assign = [[i for i in Ir[l] if y[i, l].X > 0.5] for l in range(nMachine)]
        s_vals = [s[l].X for l in range(nMachine)]
    except AttributeError:
        return None, None
    # ---- MASTER SOLUTION POOL: harvest the OTHER assignments Gurobi found in the SAME solve.
    # MEASURED (800_30, master_tl=3s, degree off): mode 0 = 6 solutions (FREE, already
    # found), mean pairwise Hamming 0.338, column yield 30 -> 149 (5.0x). For comparison:
    # post-guard CONSECUTIVE iterations have novelty 0.05 (measured). So a SINGLE master
    # solve holds more diversity than 60 iterations produce, and we were throwing 5 away.
    # Harvested solutions go to the POOL; they are NOT ROUTED in the loop (routing them
    # would cut the iteration count) and produce no NO-GOODS (growing the master row by row
    # is a measured danger).
    if pool_sink is not None:
        try:
            n_extra = min(mdl.SolCount, pool_k if pool_k else mdl.SolCount)
            for si in range(1, n_extra):                 # 0 = the incumbent taken above
                mdl.Params.SolutionNumber = si
                a2 = [[i for i in Ir[l] if y[i, l].Xn > 0.5] for l in range(nMachine)]
                if sum(len(m_) for m_ in a2) == nJob:    # ROBUSTNESS: full-coverage requirement
                    pool_sink.append(a2)
            mdl.Params.SolutionNumber = 0
        except Exception:
            pass                                          # harvesting is optional; never break the run
    return assign, s_vals


def _perturb_costs(processTime, setupTime, strength, rng):
    """RSPA (copy of integrated_hlbb.py:26): give the master PERTURBED costs -> it proposes
    structurally different assignments. Routing ALWAYS uses true costs; this only biases the
    master's proposal."""
    nM = len(processTime)
    pt_p = [[processTime[l][i] * (1.0 + rng.uniform(-strength, strength))
             for i in range(len(processTime[l]))] for l in range(nM)]
    st_p = {l: setupTime[l] * (1.0 + rng.uniform(-strength, strength, size=setupTime[l].shape))
            for l in setupTime}
    return pt_p, st_p


# =========================================================================== S1: dead time
class _BgRouter:
    """S1 — DEAD-TIME ROUTING. While the master solves (Gurobi ~3 s, all cores) the LKH
    workers are IDLE; route harvested pool columns in the background during that window ->
    at the end of the run the SPP columns are already cached -> SPP routing is ~free -> the
    reserve shrinks and the loop grows back.

    WHY A SINGLE THREAD: a parallel LKH pool (m workers) steals cores from Gurobi -> the
    master finds fewer/worse solutions in 3 s (master quality is the real product!). Serial
    routing uses 1 core (~7% of 14), finishes ~5-10 assignments per window, and catches
    most of the harvest over the run. It NEVER touches the parallel pool -> no race with
    the main loop's _route.

    FILE RACE: solveSingleLKH writes under its own uuid + retries once with a new uuid on
    failure (robustness already in HLBB.py) -> the theoretical race with clear_environment
    is harmless; the main loop still waits for `idle` before cleanup (belt and braces).

    COLUMN GRANULARITY: a half-finished assignment is fine; the cache is column-based."""

    def __init__(self, rt, pt, st, cache):
        self.rt, self.pt, self.st, self.cache = rt, pt, st, cache
        self.q = deque(); self.qset = set()
        self.busy = threading.Event()                  # set -> master is solving; routing allowed
        self.idle = threading.Event(); self.idle.set()
        self._stop = threading.Event()
        self.n_done = 0
        self.t = threading.Thread(target=self._work, daemon=True)
        self.t.start()

    def feed(self, A):
        for l, jobs in enumerate(A):
            if jobs:
                k = (l, frozenset(jobs))
                if k not in self.cache and k not in self.qset:
                    self.qset.add(k); self.q.append((k, list(jobs)))

    def frac_pending(self):
        """fraction of harvested columns still unrouted -> multiplier in the reserve formula"""
        return len(self.q) / max(1, len(self.qset))

    def _route_one(self, l, jobs):
        sel = list(set(jobs))                          # same rules as route_per_machine
        if len(sel) == 1:
            return self.rt[l] + self.pt[l][sel[0]]
        if len(sel) == 2:
            a, b = sel
            return self.rt[l] + min(self.pt[l][a] + self.st[l][a][b] + self.pt[l][b],
                                    self.pt[l][b] + self.st[l][b][a] + self.pt[l][a])
        return self.rt[l] + solveSingleLKH((JobsOnMachinesDistMat(self.pt, self.st, sel, l), 1))

    def _work(self):
        while not self._stop.is_set():
            if not self.busy.wait(0.1):
                continue
            if self._stop.is_set():
                break
            if not self.q:
                time.sleep(0.02); continue
            k, jobs = self.q.popleft()
            if k in self.cache:
                continue
            self.idle.clear()
            try:
                self.cache[k] = self._route_one(k[0], jobs)
                self.n_done += 1
            except Exception:
                self.qset.discard(k)                   # could not route -> the SPP routes it itself
            finally:
                self.idle.set()

    def close(self):
        self._stop.set(); self.busy.set()
        self.t.join(timeout=5.0)


# =========================================================================== loop (copy)
def _greedy_perturbed(nJob, nMachine, readyTime, processTime, L_i, rng):
    """Generator step of the MASTER-FREE arm (called only when use_master=False).
    SAME rule as hlbb_hm.greedy_lpt; both selection keys are shaken by multiplicative
    U[0.8, 1.2] noise (GRASP-style): (1) the job-order LPT key, (2) the machine-choice
    load+processing key. The noise affects ONLY the choice; routing and the reported
    makespan use TRUE times. The fixed +-20% range was chosen BEFORE the run
    (pre-registered); since the constructor rule is unchanged, generated assignments are
    always within eligibility (L_i)."""
    noise = rng.uniform(0.8, 1.2, size=nJob)
    load = [float(readyTime[l]) for l in range(nMachine)]
    A = [[] for _ in range(nMachine)]
    order = sorted(range(nJob),
                   key=lambda i: -noise[i] * max((processTime[l][i] for l in L_i[i]), default=0.0))
    for i in order:
        els = list(L_i[i])
        w = rng.uniform(0.8, 1.2, size=len(els))
        q = min(range(len(els)), key=lambda q: w[q] * (load[els[q]] + processTime[els[q]][i]))
        bl = els[q]
        A[bl].append(i)
        load[bl] += processTime[bl][i]
    return A


def run_abl(nJob, nMachine, c1, c2, readyTime, processTime, setupTime, I_l, L_i,
            total_time_limit=200, master_tl=3, kmach=3, arc_k=5, seed=0, max_iter=100000,
            use_spp=True, spp_tl=20, ils_tl=3, kick=3, ils_margin=0.05,
            use_bias=True, bias_alpha=0.3, use_dig=True, hint_k=3, kcap=5,
            setup_aware=False, use_degree=True, use_warm=True, use_ils=False,
            cut_mode="none", rspa_strength=0.0, rspa_every=3, verbose=False, diag=None,
            lb_frac=None, deg_frac=None, deg_lazy=None, trace=None,
            pool_mode=None, pool_k=0, spp_by_column=False, spp_budget=None,
            spp_cap=None, spp_cap_soft=False, inside=False, extra_arcs=None,
                    bg_route=False, arc_rank="cost",
            tight_s=False, sec_obj="off", sec_k=3, sec_w=0.1,
            # v6 production parameters (_prod_lock audits bench-production equality):
            mach_side=2, mach_arc_keep=False, reserve_pool=False, spp_self_cache=True,
            # harness-only lever (NOT in production): the master-free arm (no_master)
            use_master=True):
    """COPY of hlbb_hm.run_integrated_sr + cut_mode + rspa_strength.
    With cut_mode="none" and rspa_strength=0.0 it is IDENTICAL to production (see `equiv`).
    use_master=False: the main model is NEVER solved; each iteration the loop draws an
    assignment from the randomized greedy constructor (see _greedy_perturbed) and the rest
    of the pipeline (LKH routing, pool, EXCEPT bias — there is no master estimate to learn
    from — terminal SPP recombination, the inside-200 contract) stays UNCHANGED. Equal total
    budget; the freed master time goes into more constructor+routing iterations and carries
    a wider pool to the SPP."""
    clear_environment(); _close_lkh_pool()
    start = time.time()
    nogoods = []; pool = []; opt_cuts = []; gcuts = []
    bias = [0.0] * nMachine if use_bias else None
    job_freq = [Counter() for _ in range(nJob)] if use_dig else None
    rng = np.random.default_rng(seed * 7919 + 1)

    rank = None
    if setup_aware:
        rank = []
        for i in range(nJob):
            key = {l: processTime[l][i] + float(np.mean(setupTime[l][:, i])) for l in L_i[i]}
            rank.append(sorted(L_i[i], key=lambda l, kk=key: kk[l]))

    # MACHINE-SIDE CANDIDATES (3J2M, v6 — block IDENTICAL to hlbb_hm.run_integrated_sr):
    # each machine l adds to the candidate list the ceil(mach_side*n/m) eligible jobs it
    # processes FASTEST. Static, once.
    extra = None
    if mach_side and mach_side > 0:
        _a = max(1, int(np.ceil(mach_side * nJob / nMachine)))
        extra = [[] for _ in range(nJob)]
        for l in range(nMachine):
            _jobs = [i for i in range(nJob) if l in L_i[i]]
            for i in sorted(_jobs, key=lambda i: processTime[l][i])[:_a]:
                extra[i].append(l)

    # graded-cut coefficients (static, once): Delta_i = p + largest incoming + largest outgoing setup
    delta = None
    if cut_mode == "graded":
        delta = {}
        for l in range(nMachine):
            js = I_l[l]
            if len(js) < 2:
                delta[l] = {i: float(processTime[l][i]) for i in js}
                continue
            delta[l] = {i: float(processTime[l][i])
                        + max(float(setupTime[l][j][i]) for j in js if j != i)
                        + max(float(setupTime[l][i][k]) for k in js if k != i)
                        for i in js}

    def _tally(sol):
        for l in range(nMachine):
            for i in sol[l]:
                job_freq[i][l] += 1

    A = greedy_lpt(nJob, nMachine, readyTime, processTime, L_i)
    h = _route(A, readyTime, processTime, setupTime)
    best = max(h); best_assign = [list(m) for m in A]
    pool.append([list(m) for m in A])
    if use_dig:
        _tally(A)
    iters = 0; n_ils = 0; mfail = 0; n_perturb = 0; n_lbfail = 0
    _trace_cols = set(); _trace_uniqA = set()   # PHASE 0 counters (inert when trace=None)
    pool_sink = [] if pool_mode is not None else None   # master solution-pool harvest
    n_harvest = 0
    deg_on = use_degree; deg_off_iter = None
    h_ref = list(h)     # reference for BOTTLENECK ORDER: the most recently routed per-machine spans

    # ---- INSIDE-200 state (fully inert when inside=False) ----
    # rt_ema  : EMA of per-assignment routing time (measured DURING the run -> size-free rule)
    # it_ema  : EMA of iteration time (prevents last-iteration overshoot)
    # rcache  : (machine, frozenset) -> route cost already measured in the loop (free for SPP)
    rt_ema = None; it_ema = None
    route_s = 0.0                            # MEASUREMENT: total routing time
    _R = None                                # MEASUREMENT: last computed reserve
    rcache = {} if inside else None
    _cap_eff = (spp_cap or 80)
    # RESERVE POOL (reserve_pool, v6 — SAME as production; default OFF): the base of the
    # reserve formula is tied to an end-of-run DISTINCT-pool estimate instead of a fixed cap
    # (upward-biased, safe).
    _cap_use = _cap_eff
    _psig = set(); _pidx = 0; _p0 = None
    # S1: dead-time router (only with inside+bg_route; nothing changes when off)
    bg = _BgRouter(readyTime, processTime, setupTime, rcache) if (inside and bg_route) else None

    _MIP_PAY = 12.0     # window always left for the SPP MIP (size-free constant)

    def _reserve():
        """Time set aside for the SPP. The formula is the SAME at every size; its inputs are
        in-run measurements. The 1.2 factor + _MIP_PAY: the first version (0.5, +15) FELL
        SHORT in the quick test -- on 800_30 the reserve came out 26 s, the SPP needed ~36,
        routing ate the window, the MIP dropped to ~1 s and the gain was WIPED OUT. The
        0.30*T ceiling: the reserve can never eat more than a third of the loop.
        The S1 factor (frac_pending): if the background harvest cached part of the work, the
        SPP's routing need shrinks by that fraction; without bg the factor is 1 -> the old
        formula EXACTLY."""
        if rt_ema is None:
            # the initial estimate is also CAPPED (SAME fix as production; short-budget protection)
            return min(15.0, 0.30 * total_time_limit)
        frac = bg.frac_pending() if bg else 1.0
        # _cap_use: with reserve_pool OFF = _cap_eff (the old formula EXACTLY); adapted when on.
        return min(max(rt_ema * _cap_use * 1.2 * frac + _MIP_PAY + 2.0, 10.0),
                   0.30 * total_time_limit)

    while iters < max_iter:
        if reserve_pool and inside:
            while _pidx < len(pool):                 # the pool only grows -> incremental distinct count
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
        if bg:
            bg.idle.wait(3.0)          # file-race protection: clean up after bg goes quiet
        clear_environment()
        hint = ([[l for l, _ in job_freq[i].most_common(hint_k)] for i in range(nJob)]
                if use_dig else None)
        # RSPA: solve the master with perturbed costs (routing uses true costs)
        m_pt, m_st = processTime, setupTime
        if rspa_strength > 0 and iters % rspa_every == 0:
            m_pt, m_st = _perturb_costs(processTime, setupTime, rspa_strength, rng)
            n_perturb += 1
        # LOCAL BRANCHING: k = lb_frac * nJob (proportional -> same meaning at every scale)
        if not use_master:
            # MASTER-FREE ARM: the master is not solved; assignments come from the
            # randomized greedy. No s_vals -> bias learning is skipped naturally (there is
            # no master estimate).
            assign = _greedy_perturbed(nJob, nMachine, readyTime, processTime, L_i, rng)
            s_vals = None
            kw = None
        else:
            kw = dict(tight_s=tight_s, sec_obj=sec_obj, sec_k=sec_k, sec_w=sec_w,
                      readyTime=readyTime, bias=bias, kmach=kmach, K=arc_k, hint=hint, kcap=kcap,
                      rank=rank, warm=best_assign if use_warm else None,
                      opt_cuts=opt_cuts, gcuts=gcuts, diag=diag,
                      lb_k=(max(1, int(round(lb_frac * nJob))) if lb_frac else None),
                      # BOTTLENECK-SCOPED DEGREE: the q machines with the largest span
                      # (q = deg_frac * m). Re-chosen EVERY iteration -> if the bottleneck
                      # drifts, the scope drifts with it.
                      deg_set=(set(sorted(range(nMachine), key=lambda l: -h_ref[l])
                                   [:max(1, int(round(deg_frac * nMachine)))])
                               if deg_frac else None),
                      # LAZY OUT-DEGREE (SCREEN3): same inequality, lazy delivery.
                      deg_lazy=deg_lazy,
                      # MASTER SOLUTION POOL: harvest extra assignments from the same solve
                      pool_mode=pool_mode, pool_k=pool_k, pool_sink=pool_sink,
                      extra_arcs=extra_arcs, arc_rank=arc_rank,
                      # v6: machine-side candidates + arc preservation (same pass as production)
                      extra=extra, arc_keep=mach_arc_keep)
            if bg:
                bg.busy.set()              # S1 window OPEN: route while the master solves
            assign, s_vals = solve_master_abl(nJob, nMachine, c1, c2, m_pt, m_st, I_l, L_i,
                                              nogoods, master_tl, use_degree=deg_on, **kw)
            if bg:
                bg.busy.clear()            # window CLOSED (bg finishes its current column, stops)
            if assign is None and kw["lb_k"] is not None:
                # neighborhood EMPTY (the no-goods cut everything within radius k) -> retry
                # without the constraint. Local branching thus produces no FAKE collapse; it
                # is merely disabled for that iteration.
                n_lbfail += 1
                kw["lb_k"] = None
                assign, s_vals = solve_master_abl(nJob, nMachine, c1, c2, m_pt, m_st, I_l, L_i,
                                                  nogoods, master_tl, use_degree=deg_on, **kw)
            if assign is None and deg_on:
                deg_on = False; deg_off_iter = iters          # MANDATORY LOG (§2b)
                assign, s_vals = solve_master_abl(nJob, nMachine, c1, c2, m_pt, m_st, I_l, L_i,
                                                  nogoods, master_tl, use_degree=False, **kw)
        if assign is None:
            mfail += 1
            if mfail >= 3:
                break
            continue
        # MASTER SOLUTION POOL harvest -> STRAIGHT into the pool. Not routed (we do not want
        # the iteration count to drop) and produces no no-goods; its value lies in enriching
        # the SPP's column set. It injects diversity exactly where novelty collapses, on
        # 640/800 (measured).
        if pool_sink:
            n_harvest += len(pool_sink)
            if bg:
                for _A in pool_sink:   # S1: harvest to the background queue (column-based, deduped)
                    bg.feed(_A)
            pool.extend(pool_sink)
            pool_sink = []
            kw["pool_sink"] = pool_sink
        _t_r0 = time.time()
        h_a = _route(assign, readyTime, processTime, setupTime); mk_a = max(h_a)
        route_s += time.time() - _t_r0       # MEASUREMENT; no effect on the flow
        if inside:
            _dt_r = time.time() - _t_r0
            rt_ema = _dt_r if rt_ema is None else 0.7 * rt_ema + 0.3 * _dt_r
            for _l in range(nMachine):
                if assign[_l]:
                    # [v6, SAME as production] if the same (machine, job set) is routed
                    # again, the best KNOWN value is kept.
                    _rk = (_l, frozenset(assign[_l])); _ro = rcache.get(_rk)
                    rcache[_rk] = h_a[_l] if _ro is None else min(_ro, h_a[_l])
        h_ref = list(h_a)                      # refresh the bottleneck order
        if diag is not None:
            diag.setdefault("traj", []).append(tuple(frozenset(m) for m in assign))
            diag.setdefault("mk", []).append(mk_a)
        if use_bias and s_vals is not None:
            for l in range(nMachine):
                bias[l] = (1 - bias_alpha) * bias[l] + bias_alpha * max(0.0, h_a[l] - s_vals[l])
        pool.append([list(m) for m in assign]); nogoods.append([list(m) for m in assign])
        # ---- NEW: generate cuts (from the RAW assign, at the same point as production's no-good)
        if cut_mode == "optcut":
            for l in range(nMachine):
                if assign[l]:
                    opt_cuts.append((l, list(assign[l]), float(h_a[l])))
        elif cut_mode == "graded":
            b = max(range(nMachine), key=lambda l: h_a[l])
            if assign[b]:
                gcuts.append((b, list(assign[b]), float(h_a[b]), delta[b]))
        cand, mk_c = assign, mk_a
        if use_ils and mk_a <= best * (1 + ils_margin):
            res = ils([list(m) for m in assign], [0.0] * nMachine, readyTime, processTime, setupTime,
                      I_l, c1, c2, budget=ils_tl, kick=kick, seed=seed * 100000 + iters,
                      use_swap=True, pool_k=5, anchor=[list(m) for m in assign])
            n_ils += 1; pool.extend(res.get("pool_lkh", []))
            if res["lkh_best_mk"] < mk_c - 1e-6:
                cand = res["lkh_best_assign"]; mk_c = res["lkh_best_mk"]
        # ---- PHASE 0 TRACING (only if trace is given; algorithm behavior is UNCHANGED) ----
        # Goal: is the "stuck" state visible FROM INSIDE? Two candidate signals are logged:
        #   (a) best_age  = iterations since the best last improved (the literature standard:
        #       Lin I_non-improving, Ying N/G_non-improving, Arnaout BestIter, FSS Stag)
        #   (b) novelty   = Hamming distance (job fraction) of this proposal to its NEAREST
        #       pool member. (b) is NECESSARY because our loop is partly a POOL GENERATOR:
        #       in 62% of runs the terminal SPP produces the final best -> "best not
        #       improving" can be a FALSE signal while the pool is still refreshing.
        if trace is not None:
            _loc = {i: l for l in range(nMachine) for i in cand[l]}
            nov = 1.0
            # CAUTION: the pool's LAST element is this iteration's own `assign` (added above)
            # -> exclude it, or novelty always comes out 0 (caught in the smoke test).
            for prev in pool[-41:-1]:                    # the last 40 members suffice (fixed cost)
                pl = {i: l for l in range(nMachine) for i in prev[l]}
                diff = sum(1 for i in range(nJob) if _loc.get(i) != pl.get(i))
                nov = min(nov, diff / max(1, nJob))
            # ⭐ THE REAL CURRENCY: the SPP works on (machine, job-set) COLUMNS, not on
            # assignments. 62 master proposals -> far more UNIQUE COLUMNS. "62 samples" is
            # therefore misleading; these two counters measure the true search space.
            # Also spp_recombine TRIMS the pool with max_assigns=80 (pool 122-125) -> once
            # `uniqA` passes 80 the produced diversity NEVER REACHES the SPP.
            for _P in (assign, cand):
                _trace_uniqA.add(tuple(frozenset(m) for m in _P))
                for _l in range(nMachine):
                    if _P[_l]:
                        _trace_cols.add((_l, frozenset(_P[_l])))
            trace.append({"uniqA": len(_trace_uniqA), "cols": len(_trace_cols),
                          "iter": iters, "master_mk": round(mk_a, 1),
                          "cand_mk": round(mk_c, 1), "best": round(best, 1),
                          "improved": int(mk_c < best - 1e-6), "novelty": round(nov, 4),
                          "pool": len(pool), "deg_on": int(deg_on),
                          "t": round(time.time() - start, 1)})
        pool.append([list(m) for m in cand])
        if use_dig:
            _tally(cand)
        if mk_c < best - 1e-6:
            best = mk_c; best_assign = [list(m) for m in cand]
        if inside:
            _dt_it = time.time() - _t_iter0
            it_ema = _dt_it if it_ema is None else 0.7 * it_ema + 0.3 * _dt_it
        if verbose:
            print(f"  [abl] iter {iters}: master={mk_a:.0f} -> best={best:.0f}", flush=True)

    loop_s = time.time() - start
    if bg:
        bg.close()                     # always stop BEFORE the SPP and the pool shutdown
    pre_spp = best
    if use_spp and len(pool) >= 2:
        # spp_budget: bring the SPP INSIDE the total budget. Measured: it currently stays
        # OUTSIDE (800_30: loop 201.5s + SPP 45.5s = 247s; rivals get 200s while we take 247s).
        _dl = (start + total_time_limit + spp_budget) if spp_budget is not None else None
        # ⭐ spp_cap: the UNIQUE-ASSIGNMENT ceiling given to the SPP (default None ->
        # spp_recombine's own 80, i.e. EXACTLY AS IN PRODUCTION). Measured (spp_probe curve):
        # with the pool on, ALL of the gain arrives within 160-320 unique assignments; the
        # remaining ~400 assignments and ~100 s are WASTED.
        # INCUMBENT GUARANTEE: `must_include` is applied in spp_recombine ONLY on the
        # by_column branch; on the capped path the incumbent CAN DROP OUT during sampling
        # (measured: 14/25 columns lost on 640_25). Fix WITHOUT touching the production
        # file: put best_assign at the HEAD of the pool -- sampling is `uniq[int(i*step)]`,
        # i=0 -> uniq[0], so index 0 is ALWAYS selected. Dedup keeps the first-seen record,
        # so it stays at the head.
        _pool_in = ([best_assign] + pool) if ((spp_cap or inside) and best_assign) else pool
        # INSIDE-200: the SPP is INSIDE the contract too. deadline = T - 2 (final-route +
        # extraction margin); the incumbent is routed as the first assignment -> feasible
        # even if cut off. clean_every=20: glob load (+12%, measured). route_cache: columns
        # the loop already measured are free.
        if inside:
            _dl = start + total_time_limit - 2.0
        spp_mk, spp_assign = spp_recombine(_pool_in, nJob, nMachine, readyTime, processTime,
                                           setupTime, tl=spp_tl, by_column=spp_by_column,
                                           max_assigns=(spp_cap or 80),
                                           cap_soft=spp_cap_soft,
                                           deadline=_dl, must_include=best_assign,
                                           route_cache=rcache,
                                           clean_every=(20 if inside else None),
                                           mip_pay=(_MIP_PAY if inside else None), c1=c1,
                                           self_cache=spp_self_cache)
        if spp_mk is not None and spp_mk < best - 1e-6:
            best = round(spp_mk, 1); best_assign = spp_assign
    _close_lkh_pool(); clear_environment()
    return {"best": best, "pre_spp": pre_spp, "iters": iters, "pool": len(pool),
            "assign": best_assign,
            "mfail": mfail, "n_ils": n_ils, "n_perturb": n_perturb, "n_lbfail": n_lbfail,
            "n_harvest": n_harvest, "loop_s": round(loop_s, 1), "route_s": round(route_s, 2),
            "mip_st": _SPP_LAST.get("status"), "mip_gap": _SPP_LAST.get("gap"),
            "reserve": (round(_R, 2) if _R is not None else None),
            "spp_route_s": _SPP_LAST.get("route_s"), "spp_build_s": _SPP_LAST.get("build_s"),
            "spp_mip_s": _SPP_LAST.get("mip_s"), "spp_n_uniq": _SPP_LAST.get("n_uniq"),
            "spp_n_routed": _SPP_LAST.get("n_routed"),
            "spp_n_cols": _SPP_LAST.get("n_cols"),
            "total_s": round(time.time() - start, 1),
            "n_bgroute": (bg.n_done if bg else 0),
            "n_cuts": len(opt_cuts) + len(gcuts),
            "deg_guard_fired": deg_off_iter is not None, "deg_off_iter": deg_off_iter}


# =========================================================================== commands
LOCK = _prod_lock()   # `full` arm = production signature. See file header; audit: `lockcheck`.


def _kw(arm, nMachine, base=None):
    """Arm kwargs. If `base` is given, they are MERGED and the arm wins.
    CAUTION: LOCK and the arm may carry the same key (kmach) -> a double splat raises
    TypeError, hence the merge here (caught in the smoke test)."""
    kw = dict(base or {})
    kw.update(ALL_ARMS[arm])
    if kw.get("kmach") == "__kmach_full__":
        kw["kmach"] = nMachine
    return kw


def cmd_lockcheck():
    """BASELINE AUDIT (~1 second, no Gurobi): is the `full` arm REALLY the algorithm that
    production ships?

    Since LOCK is now DERIVED from the production signature (see `_prod_lock`), parameter
    drift is structurally IMPOSSIBLE. This command audits the three remaining things:
      1. is the copy BEHIND production (a knob present in production but absent from
         run_abl; _prod_lock already raises, here it is reported readably),
      2. are the arms still MEANINGFUL: `no_*` may only turn off something that is ON,
         `plus_*` may only turn on something that is OFF. When DIG left production,
         `no_dig` became meaningless; this rule catches a recurrence,
      3. no arm touches the harness-owned keys (budget/seed)."""
    import inspect
    from hlbb_hm import run_integrated_sr
    P = inspect.signature(run_integrated_sr).parameters
    bad = []
    print(f"\n{'param':>18} {'URETIM = FULL KOLU':>20}   degistiren kol(lar)")
    print("-" * 68)
    for k, v in sorted(LOCK.items()):
        touched = [a for a, kw in ARMS.items() if k in kw]
        print(f"{k:>18} {str(v):>20}   {', '.join(touched) if touched else '-'}")
    # arm direction: no_* must turn off something ON, plus_* must turn on something OFF
    print()
    for arm, kw in ARMS.items():
        for k, val in kw.items():
            if k in _HARNESS_OWNED:
                bad.append(f"kol {arm}: {k} harness'in kontrolunde, kol degistiremez")
            if k not in P or val == "__kmach_full__":
                continue                      # harness-only lever (cut_mode, rspa_strength...)
            cur = LOCK.get(k)
            if arm.startswith("no_") and val == cur:
                bad.append(f"kol {arm}: {k} zaten {cur} -> kapatacak bir sey YOK")
            if arm.startswith("plus_") and val == cur:
                bad.append(f"kol {arm}: {k} zaten {cur} -> acacak bir sey YOK")
    if bad:
        print("== TABAN BOZUK, KOSMA ==")
        for b in bad:
            print("  ⛔ " + b)
    else:
        print(f"== TABAN SAGLAM: `full` kolu uretim imzasiyla ozdes, {len(ARMS)} kol tutarli ==")
    return not bad


def cmd_equiv():
    """Is cut_mode='none' + rspa=0 EXACTLY equal to production? (A BEHAVIOR test -- lockcheck
    audits parameters, this audits the BODIES: a logic change not ported into the copy is
    only caught here.)

    DETERMINISM: at production settings (master_tl=3s, wall clock) HLBB varies run to run
    -> for equiv, master_tl is LARGE + max_iter is FIXED.

    (!) TWO PASSES: `use_spp=False` compares only loop+master and SKIPS the recombination
    stage -- the pool/spp_cap/inside package stays inert there, so its fidelity is NOT
    MEASURED. The second pass runs with the SPP ON (spp_tl LARGE: the 20 s wall-clock limit
    alone breaks determinism). Together the two passes cover both stages."""
    from hlbb_hm import run_integrated_sr
    sizes = sys.argv[2:] or ["50_10"]
    ok = True
    # The baseline comes from LOCK (= the production signature). NO hand-written flag list:
    # the old hand-written list here skipped use_dig and equiv compared two DIFFERENT
    # algorithms.
    det = dict(total_time_limit=10 ** 6, master_tl=300, max_iter=6)
    PASSES = [("dongu+master", dict(LOCK, **det, use_spp=False)),
              ("+ SPP/havuz",  dict(LOCK, **det, use_spp=True, spp_tl=600))]
    for size in sizes:
        nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = _load(size, "1", "niche_v2")
        for tag, kw in PASSES:
            print(f"\n### EQUIV — {size} | {tag} | kapak = {6*300}s ###", flush=True)
            t0 = time.time()
            ra = run_abl(nJob, nM, c1, c2, rt, pt, st, I_l, L_i, verbose=True, **kw)
            a, Aa = ra["best"], ra["assign"]
            wa = time.time() - t0
            t0 = time.time()
            rb = run_integrated_sr(nJob, nM, c1, c2, rt, pt, st, I_l, L_i, verbose=True,
                                   return_solution=True, **kw)
            b, Ab = rb[0], rb[3]
            wb = time.time() - t0
            # STRUCTURAL COMPARISON: makespan alone is weak -- the two sides can reach the
            # same number by DIFFERENT paths (plausible on small instances). We also compare
            # the assignment; within-machine order is meaningless under the SPP, so SETS are
            # compared per machine.
            def _sig(A):
                return None if A is None else tuple(frozenset(m) for m in A)
            same_mk = abs(a - b) < 1e-6
            same_as = _sig(Aa) == _sig(Ab)
            same = same_mk and same_as
            ok &= same
            note = "" if same_as else "   ⚠️ makespan ayni ama ATAMA FARKLI"
            print(f"==> {size} [{tag}]: kopya={a:.1f} ({wa:.0f}s)  uretim={b:.1f} ({wb:.0f}s)"
                  f"  -> {'AYNI' if same else '*** FARKLI ***'}{note}", flush=True)
            if max(wa, wb) > 0.9 * 6 * 300:
                print("    UYARI: master kapaga takildi -> rejim deterministik degil, "
                      "sonuc gecersiz.", flush=True)
    print(f"\n{'== KOPYA SADIK ==' if ok else '== SADAKAT BOZUK, KOSMA =='}", flush=True)


def cmd_levers():
    """SANITY: do the two new levers REALLY enter the model? (an EFFECT test, not quality)
    Same deterministic regime: full vs plus_optcut vs plus_graded vs plus_perturb.
    Expectation: at least one trajectory differs -> the lever is not dead. If all come out
    the SAME, the code is not attached."""
    size = sys.argv[2] if len(sys.argv) > 2 else "100_15"
    nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = _load(size, "1", "niche_v2")
    kw = dict(total_time_limit=10 ** 6, master_tl=60, kmach=3, arc_k=5, max_iter=8, use_spp=False)
    print(f"\n### LEVER TESTI — {size} (deterministik, 8 iter) ###", flush=True)
    base = None
    for arm in ("full", "plus_optcut", "plus_graded", "plus_perturb"):
        r = run_abl(nJob, nM, c1, c2, rt, pt, st, I_l, L_i, **_kw(arm, nM, kw))
        if base is None:
            base = r["best"]
        tag = "= full" if abs(r["best"] - base) < 1e-6 else "FARKLI"
        print(f"  {arm:>15}: best={r['best']:7.1f} iter={r['iters']:3d}  {tag}", flush=True)
    print("  NOT: 'FARKLI' = lever modele giriyor. Hepsi '= full' ise kesitler baglanmamis.",
          flush=True)


def cmd_probecuts():
    """If `levers` stays INCONCLUSIVE: did the cuts ENTER the model, and are they BINDING?
    `= full` can mean two things: (a) the code is not attached, (b) attached but truly inert.
    This command separates them -> counts of generated cuts / constraints in the model /
    BINDING ones (slack~0). Also for plus_perturb: how often the perturbation fired +
    whether the trajectory diverged from full."""
    size = sys.argv[2] if len(sys.argv) > 2 else "100_15"
    nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = _load(size, "1", "niche_v2")
    kw = dict(total_time_limit=10 ** 6, master_tl=60, kmach=3, arc_k=5, max_iter=8, use_spp=False)
    print(f"\n### KESIT TESHISI — {size} (deterministik, 8 iter) ###", flush=True)
    print(f"{'kol':>14} {'uretilen':>9} {'kisit':>7} {'BAGLAYICI':>10} {'perturb':>8}  yorunge", flush=True)
    ref = None
    for arm in ("full", "plus_optcut", "plus_graded", "plus_perturb"):
        d = {}
        r = run_abl(nJob, nM, c1, c2, rt, pt, st, I_l, L_i, diag=d, **_kw(arm, nM, kw))
        if ref is None:
            ref = d.get("traj", [])
            div = "-"
        else:
            tr = d.get("traj", [])
            k = next((i + 1 for i in range(min(len(tr), len(ref))) if tr[i] != ref[i]), None)
            div = f"iter {k}'de ayristi" if k else "full ile AYNI"
        print(f"{arm:>14} {r['n_cuts']:>9} {d.get('ncut_con',0):>7} {d.get('tight',0):>10} "
              f"{r['n_perturb']:>8}  {div}", flush=True)
    print("\n  uretilen>0 + kisit>0  => kod BAGLI (modele giriyor)", flush=True)
    print("  BAGLAYICI=0           => kesit ATIL (mekanizma kaniti, tam da bekledigimiz)", flush=True)
    print("  uretilen>0 + kisit=0  => KOD BOZUK (kesitler modele hic girmiyor)", flush=True)


def cmd_cutbind():
    """DEFINITIVE VACUITY TEST. In `probecuts`, "0 BINDING" meant either (a) the cut is
    truly inert or (b) the slack read failed silently — it did not distinguish them.

    Here a SINGLE trajectory (production = cut-free) runs; at every iteration the master is
    solved TWICE in the SAME state (same no-goods, same bias, same hints, same warm):
    without cuts and with cuts. The master's objective is min cmax and at the optimum
    cmax = max_l s[l], hence:

        d = max(s_with_cuts) - max(s_without)   >= 0

    d = 0 at every iteration  ->  the cut NEVER raises the master's estimate = PROVEN INERT.
    d > 0                     ->  the cut tightens the lower bound (NOT inert)."""
    size = sys.argv[2] if len(sys.argv) > 2 else "100_15"
    mode = sys.argv[3] if len(sys.argv) > 3 else "optcut"
    iters = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    TL = int(sys.argv[5]) if len(sys.argv) > 5 else 300   # LARGE so it reaches the optimum
    nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = _load(size, "1", "niche_v2")
    clear_environment(); _close_lkh_pool()
    nogoods = []; opt_cuts = []; gcuts = []; bias = [0.0] * nM
    jf = [Counter() for _ in range(nJob)]
    delta = None
    if mode == "graded":
        delta = {}
        for l in range(nM):
            js = I_l[l]
            delta[l] = ({i: float(pt[l][i]) for i in js} if len(js) < 2 else
                        {i: float(pt[l][i]) + max(float(st[l][j][i]) for j in js if j != i)
                         + max(float(st[l][i][k]) for k in js if k != i) for i in js})
    A = greedy_lpt(nJob, nM, rt, pt, L_i)
    h = _route(A, rt, pt, st); best = max(h); ba = [list(m) for m in A]
    for l in range(nM):
        for i in A[l]:
            jf[i][l] += 1
    print(f"\n### VACUITY TESTI — {size} | {mode} | {iters} iter ###", flush=True)
    print(f"{'iter':>5} {'kesit':>6} {'atlan':>6} {'kesitsiz':>12} {'kesitli':>12} {'FARK':>8}", flush=True)
    print("  (atlan = gecerlilik geregi eklenmeyen kesit; kapaga takilan cozumler kiyasa KATILMAZ)",
          flush=True)
    diffs = []
    for it in range(1, iters + 1):
        clear_environment()
        hint = [[l for l, _ in jf[i].most_common(3)] for i in range(nJob)]
        kw = dict(readyTime=rt, bias=bias, kmach=3, K=5, hint=hint, kcap=5, warm=ba)
        d0 = {}
        a0, s0 = solve_master_abl(nJob, nM, c1, c2, pt, st, I_l, L_i, nogoods, TL,
                                  diag=d0, **kw)
        if a0 is None:
            break
        nc = len(opt_cuts) + len(gcuts)
        if nc:
            d1 = {}
            a1, s1 = solve_master_abl(nJob, nM, c1, c2, pt, st, I_l, L_i, nogoods, TL,
                                      opt_cuts=opt_cuts, gcuts=gcuts, diag=d1, **kw)
            d = (max(s1) - max(s0)) if s1 is not None else float("nan")
            both_opt = (d0.get("status") == 2 and d1.get("status") == 2)
            if both_opt:
                diffs.append(d)
            flag = "" if both_opt else "  <-- KAPAKTA, gecersiz kiyas"
            print(f"{it:>5} {nc:>6} {d1.get('skip',0):>6} {max(s0):>12.2f} {max(s1):>12.2f} "
                  f"{d:>+8.3f}{flag}", flush=True)
        else:
            print(f"{it:>5} {nc:>6} {0:>6} {max(s0):>12.2f} {'-':>12} {'-':>8}", flush=True)
        # the trajectory advances WITHOUT cuts (production behavior)
        h_a = _route(a0, rt, pt, st)
        for l in range(nM):
            bias[l] = 0.7 * bias[l] + 0.3 * max(0.0, h_a[l] - s0[l])
        nogoods.append([list(m) for m in a0])
        for l in range(nM):
            for i in a0[l]:
                jf[i][l] += 1
        if max(h_a) < best:
            best = max(h_a); ba = [list(m) for m in a0]
        if mode == "optcut":
            for l in range(nM):
                if a0[l]:
                    opt_cuts.append((l, list(a0[l]), float(h_a[l])))
        elif mode == "graded":
            b = max(range(nM), key=lambda l: h_a[l])
            if a0[b]:
                gcuts.append((b, list(a0[b]), float(h_a[b]), delta[b]))
    _close_lkh_pool()
    if diffs:
        mx_ = max(diffs)
        print(f"\n  gecerli kiyas sayisi = {len(diffs)}", flush=True)
        print(f"  en buyuk fark = {mx_:+.4f}  ->  "
              f"{'KANITLI ATIL (master tahminini hic yukseltmiyor)' if mx_ < 1e-6 else 'ATIL DEGIL: alt siniri sikistiriyor'}",
              flush=True)


def cmd_regress():
    """PHASE 3 REGRESSION: is the `full` arm in the same range as the stored HLBB results?
    Exact equality is NOT expected (HLBB varies run to run); |delta| must stay within the
    repeat spread (~2.5 units). A large deviation means the copy is broken."""
    # SCHEMA (verified): method,size,elig,rho,rep,seed,n,m,makespan,...
    #   size = "50x10" ('x', NOT underscore) | instance number in the `rep` column |
    #   the method filter is REQUIRED
    ref = {}
    p = os.path.join(_HERE, "results", "niche_bench_v2.csv")
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            if r.get("method") != "HLBB":
                continue
            try:
                ref[(r["size"].replace("x", "_"), r["rep"])] = float(r["makespan"])
            except (KeyError, ValueError):
                pass
    print(f"\n### REGRESYON — full vs depolanan HLBB ({len(ref)} referans) ###", flush=True)
    if not ref:
        print("  depolanan HLBB satiri okunamadi; basliklar:", flush=True)
        print("   ", open(p).readline().strip() if os.path.exists(p) else "(dosya yok)", flush=True)
        return
    ds = []
    plan = [(sz, i) for sz in ("100_15", "250_20", "640_25") for i in ("1", "2")]
    missing = [k for k in plan if k not in ref]
    if missing:
        print(f"  UYARI: referansta yok -> {missing}", flush=True)
    for size, inst in plan:
            if (size, inst) not in ref:
                continue
            nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = _load(size, inst, "niche_v2")
            r = run_abl(nJob, nM, c1, c2, rt, pt, st, I_l, L_i,
                        total_time_limit=BUDGET, seed=0, **LOCK)
            d = r["best"] - ref[(size, inst)]
            ds.append(d)
            print(f"  {size:>8} i{inst}: full={r['best']:7.1f}  depolanan={ref[(size,inst)]:7.1f}"
                  f"  delta={d:+6.1f}", flush=True)
    if ds:
        print(f"\n  ort delta={stats.mean(ds):+.2f}  max|delta|={max(abs(d) for d in ds):.1f}"
              f"  -> {'TAMAM (yayilim icinde)' if max(abs(d) for d in ds) <= 8 else 'DIKKAT: sapma buyuk'}",
              flush=True)


def worker(track, size, inst, arm, budget, want_trace=False):
    d = _load(size, inst, track)
    nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
    # TRACING (novelty/column counters) ONLY ON REQUEST. It used to be on for EVERY run: the
    # cost is small (~O(40n)/iter) and cancels in Delta since it is the same across arms,
    # BUT it is work production does not do -> under a wall-clock budget it nudges the copy
    # away from production. The only places needing tailnov are screen4/screen6; the main
    # ablation (`run`) does not write that column anyway.
    tr = [] if want_trace else None
    kwa = _kw(arm, nM, LOCK)
    # budget_bonus: NOT a run_abl parameter but a harness parameter -> stripped here.
    # Only the FAIRNESS arm (base_plus) uses it; it gives the baseline, as LOOP time, the
    # extra time the pool arm spends in the SPP, separating "mechanism or time".
    bonus = kwa.pop("budget_bonus", 0)
    r = run_abl(nJob, nM, c1, c2, rt, pt, st, I_l, L_i,
                total_time_limit=budget + bonus, seed=0, trace=tr, **kwa)
    # TAIL NOVELTY: mean of the last 10 iterations. The phase-0 novelty measurement: the
    # baseline collapses to 0.05 on 640/800 after the guard. If the pool is to raise it,
    # THRESHOLD 2 is measured exactly here.
    r["tailnov"] = round(stats.mean([x["novelty"] for x in tr[-10:]]), 4) if tr else -1.0
    # SHARED feasibility checker -- AFTER the run ends; steals nothing from the budget.
    # ⭐ ORDERED CHECK: we read back the sequence LKH found (tour_capture) and verify the
    # solution IN ORDER. Previously HLBB was checked with `ordered=False` and the rival
    # methods with `ordered=True` -> we verified our own method LESS than the rivals.
    # Cost measured: 0.5 s on 800_30 (AFTER the run; steals nothing from the budget).
    # Sequence extraction verified 8/8 across 5 scales.
    ordered_assign = None
    try:
        from tour_capture import sequence_solution
        if r.get("assign"):
            ordered_assign = sequence_solution(r["assign"], pt, st)
    except Exception as e:
        print(f"    [tour] sira cikarilamadi: {e}", flush=True)
    feas_hook.check("ablation", arm, f"{track}/{size}/i{inst}", 0,
                    ordered_assign or r.get("assign"), d, float(r["best"]),
                    ordered=ordered_assign is not None)
    print("RESULT " + "|".join(str(r[k]) for k in
                               ("best", "pre_spp", "iters", "pool", "deg_guard_fired",
                                "deg_off_iter", "mfail", "n_lbfail", "tailnov", "n_harvest",
                                "loop_s", "total_s", "n_bgroute", "route_s", "mip_st", "mip_gap",
                                "reserve", "spp_route_s", "spp_build_s", "spp_mip_s",
                                "spp_n_uniq", "spp_n_routed", "spp_n_cols")))


def _spawn(track, size, inst, arm, budget, want_trace=False):
    cmd = [sys.executable, os.path.abspath(__file__), "worker", track, size, inst, arm,
           str(budget), "1" if want_trace else "0"]
    try:
        p = subprocess.run(cmd, cwd=_HERE, capture_output=True, text=True, timeout=budget + 900)
    except subprocess.TimeoutExpired:
        return None
    for line in p.stdout.splitlines():
        if line.startswith("RESULT "):
            f = line[7:].split("|")
            mf = int(f[6])
            return dict(best=float(f[0]), pre_spp=float(f[1]), iters=int(f[2]), pool=int(f[3]),
                        deg_guard_fired=(f[4] == "True"), deg_off_iter=(f[5] if f[5] != "None" else ""),
                        mfail=mf, collapsed=(mf >= 3),
                        n_lbfail=int(f[7]) if len(f) > 7 else 0,
                        tailnov=float(f[8]) if len(f) > 8 else -1.0,
                        n_harvest=int(f[9]) if len(f) > 9 else 0,
                        loop_s=float(f[10]) if len(f) > 10 else -1.0,
                        total_s=float(f[11]) if len(f) > 11 else -1.0,
                        n_bgroute=int(f[12]) if len(f) > 12 else 0,
                        route_s=float(f[13]) if len(f) > 13 else -1.0,
                        mip_st=(int(f[14]) if len(f) > 14 and f[14] not in ("None", "") else None),
                        mip_gap=(float(f[15]) if len(f) > 15 and f[15] not in ("None", "") else None),
                        **{k: (float(f[16 + q]) if len(f) > 16 + q
                               and f[16 + q] not in ("None", "") else None)
                           for q, k in enumerate(["reserve", "spp_route_s", "spp_build_s",
                                                  "spp_mip_s", "spp_n_uniq", "spp_n_routed",
                                                  "spp_n_cols"])})
    return None


def _done(path=None):
    got = set()
    p = path or CSV_PATH
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            got.add((r["track"], r["size"], r["inst"], r["arm"], r["rep"]))
    # FAILURE RULE (pre-registration protocol §9): (instance, arm) pairs that crashed in
    # both attempts are read from the exclusion file -> resume never retries forever; the
    # report lists them explicitly.
    xp = p + ".dislanan.csv"
    if os.path.exists(xp):
        for r in csv.DictReader(open(xp)):
            got.add((r["track"], r["size"], r["inst"], r["arm"], r["rep"]))
    return got


def _exclude(path, key, neden):
    """Record of an excluded (track,size,inst,arm,rep) — NO error row is written to the CSV
    (the report expects floats); the separate side file is both an audit trail and the
    resume filter (see _done)."""
    xp = path + ".dislanan.csv"
    new = not os.path.exists(xp)
    with open(xp, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["track", "size", "inst", "arm", "rep", "neden", "zaman"])
        w.writerow(list(key) + [neden, time.strftime("%F %T")])


def _lock_guard(csv_path):
    """STALE-ROW PROTECTION. Runs are resumable: rows already in the CSV are accepted as is.
    But LOCK is now DERIVED from the production signature -- if a default changes in
    `hlbb_hm.py` the baseline changes SILENTLY and a half-finished CSV MIXES old-baseline
    and new-baseline rows. The resulting table describes no algorithm at all.

    Remedy: the baseline signature is written next to the CSV and compared on every run.
    If it differs, the run does NOT START -- the decision (new CSV, or drop the old rows)
    belongs to a human."""
    import json
    sig_path = os.path.splitext(csv_path)[0] + ".lock.json"
    cur = {k: repr(v) for k, v in sorted(LOCK.items())}
    if os.path.exists(sig_path):
        old = json.load(open(sig_path))
        if old != cur:
            diff = [f"{k}: {old.get(k, '(yok)')} -> {cur.get(k, '(yok)')}"
                    for k in sorted(set(old) | set(cur)) if old.get(k) != cur.get(k)]
            raise SystemExit(
                "\n⛔ TABAN DEGISMIS — bu CSV'deki satirlar BASKA bir konfigurasyonda kosuldu:\n  "
                + "\n  ".join(diff)
                + f"\n\nKarisik veri = anlamsiz tablo. Ya yeni bir CSV_PATH ac (v4), ya da\n"
                  f"{os.path.relpath(csv_path)} + {os.path.relpath(sig_path)} dosyalarini sil.\n")
    else:
        os.makedirs(os.path.dirname(sig_path), exist_ok=True)
        json.dump(cur, open(sig_path, "w"), indent=1)


# ====================================================== screen: local branching (separate)
def _generic_run(csv_path, arms, sizes, title, reps, cols=None, insts=None):
    """SAME body as cmd_rebase; separate CSV + separate arm/size lists. Resumable."""
    track = "niche_v2"
    _lock_guard(csv_path)
    got = _done(csv_path)
    insts = insts or INSTS
    jobs = [(s, i, a, r) for s in sizes for i in insts for a in arms
            for r in range(1, reps + 1) if (track, s, i, a, str(r)) not in got]
    tot = len(sizes) * len(insts) * len(arms) * reps
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    new = not os.path.exists(csv_path)
    fh = open(csv_path, "a", newline="")
    w = csv.writer(fh)
    cols = cols or COLS
    if new:
        w.writerow(cols)
    print(f"\n### {title} | {len(arms)} kol x {len(sizes)} boyut x {len(insts)} inst x {reps} "
          f"tekrar = {tot} kosu ({tot-len(jobs)} var, {len(jobs)} kalan), {BUDGET}s ###")
    print(f"### -> {os.path.relpath(csv_path)}   (diger CSV'lere DOKUNULMUYOR) ###\n", flush=True)
    t0 = time.time()
    want_tr = "tailnov" in cols          # tracing only in experiments that write that column
    for k, (s, i, a, r) in enumerate(jobs, 1):
        res = _spawn(track, s, i, a, BUDGET, want_trace=want_tr)
        if res is None:
            print(f"[{k}/{len(jobs)}] {s} i{i} r{r} {a:>10}  *** BASARISIZ ***", flush=True)
            continue
        row = [track, s, i, a, r, res["best"], res["pre_spp"], res["iters"], res["pool"],
               round(time.time() - t0, 1), res["deg_guard_fired"], res["deg_off_iter"],
               res["mfail"], res["collapsed"]]
        if "n_lbfail" in cols:
            row.append(res.get("n_lbfail", 0))
        if "tailnov" in cols:
            row.append(res.get("tailnov", -1.0)); row.append(res.get("n_harvest", 0))
        if "loop_s" in cols:
            row.append(res.get("loop_s", -1.0)); row.append(res.get("total_s", -1.0))
        if "n_bgroute" in cols:
            row.append(res.get("n_bgroute", 0))
        if "route_s" in cols:
            row.append(res.get("route_s", -1.0))
        if "mip_st" in cols:
            row.append(res.get("mip_st")); row.append(res.get("mip_gap"))
        if "reserve" in cols:
            row += [res.get(k) for k in ("reserve", "spp_route_s", "spp_build_s",
                                         "spp_mip_s", "spp_n_uniq", "spp_n_routed", "spp_n_cols")]
        # ROBUSTNESS: if row/header alignment breaks, fail BEFORE the run starts (a 12-hour
        # run's data must not shift silently)
        assert len(row) == len(cols), f"CSV hizasi bozuk: {len(row)} != {len(cols)}"
        w.writerow(row)
        fh.flush()
        g = "  guard@" + str(res["deg_off_iter"]) if res["deg_guard_fired"] else ""
        if res.get("n_lbfail"):
            g += f"  lb-bos@{res['n_lbfail']}"
        if res["collapsed"]:
            g += "  *** COKTU ***"
        el = time.time() - t0
        print(f"[{k}/{len(jobs)}] {s:>8} i{i} r{r} {a:>10}  mk={res['best']:7.1f} "
              f"iter={res['iters']:3d} pool={res['pool']:4d}{g}"
              f"  [{el/3600:.1f}sa gecti, ~{el/k*(len(jobs)-k)/3600:.1f}sa kaldi]", flush=True)
    fh.close()
    print("kosu bitti", flush=True)


def cmd_screen():
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    _generic_run(SCREEN_CSV, list(SCREEN_ARMS), SCREEN_SIZES,
                 "ELEME KOSUSU — LOCAL BRANCHING", reps, cols=SCREEN_COLS)


def cmd_screen2():
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    _generic_run(SCREEN2_CSV, list(SCREEN2_ARMS), SCREEN2_SIZES,
                 "ELEME KOSUSU — DARBOGAZ-KAPSAMLI DEGREE", reps)


def cmd_screen2_report():
    """THE REAL QUESTION: does narrowing the scope STOP the guard from firing (= does degree
    survive), and does that SHOW UP in makespan?"""
    if not os.path.exists(SCREEN2_CSV):
        print("eleme-2 sonucu yok"); return
    R = [r for r in csv.DictReader(open(SCREEN2_CSV))]
    if not R:
        print("satir yok"); return
    B, base, D = _cell_deltas(R, "no_dig")
    arms = [a for a in SCREEN2_ARMS if a != "no_dig"]
    print(f"\n{'='*98}\nELEME-2 — DARBOGAZ-KAPSAMLI DEGREE   taban = no_dig (degree TUM makinelerde)\n"
          f"Delta = RPD(kol) - RPD(taban)   ( - = daraltma IYILESTIRDI )\n{'='*98}")
    print(f"{'kol':>11} {'kapsam':>9} {'dRPD%':>8} {'SE':>6} {'2SE':>6} {'w/t/l':>9}  karar")
    for a in arms:
        v = list(D.get(a, {}).values())
        if len(v) < 2:
            continue
        m = stats.mean(v); se = stats.stdev(v) / len(v) ** 0.5
        w = sum(1 for x in v if x < -1e-9); l = sum(1 for x in v if x > 1e-9)
        verdict = ("IYILESTIRIYOR -> tam kosuya aday" if m < -2 * se else
                   "ZARARLI" if m > 2 * se else "gurultude (fayda yok)")
        q = SCREEN2_ARMS[a]["deg_frac"]
        print(f"{a:>11} {('darbogaz' if q < 0.01 else f'%{int(q*100)}'):>9} {m:+8.3f} "
              f"{se:6.3f} {2*se:6.3f} {w:>3}/{len(v)-w-l}/{l:<3}  {verdict}")
    sizes = [s for s in SCREEN2_SIZES if any(r["size"] == s for r in R)]
    print(f"\n--- olcek kirilimi (dRPD%) ---\n{'kol':>11}" + "".join(f"{s:>10}" for s in sizes))
    for a in arms:
        row = ""
        for s in sizes:
            v = [x for (ss, i), x in D.get(a, {}).items() if ss == s]
            row += f"{stats.mean(v):+10.2f}" if v else f"{'--':>10}"
        print(f"{a:>11}" + row)
    print(f"\n--- ⭐ ASIL OLCUM: deg-guard tetiklenme (9 kosu/hucre) — DUSMESI gereken ---")
    print(f"{'kol':>11}" + "".join(f"{s:>12}" for s in sizes))
    for a in ["no_dig"] + arms:
        row = ""
        for s in sizes:
            v = [r for r in R if r["arm"] == a and r["size"] == s]
            row += f"{sum(1 for r in v if r['deg_guard_fired']=='True')}/{len(v)}".rjust(12) if v else f"{'--':>12}"
        print(f"{a:>11}" + row)
    print("  taban 800_30'da 9/9 tetikliyor = degree TAMAMEN kapali. Daraltilmis kollarda 0/9")
    print("  cikarsa esitsizlik HAYATTA KALMIS demektir -> asil kazanc orada aranmali.")
    print(f"\n--- iterasyon / havuz / cokus ---")
    for a in ["no_dig"] + arms:
        v = [r for r in R if r["arm"] == a]
        if v:
            print(f"  {a:>11}: ort iter={stats.mean([int(r['iters']) for r in v]):5.1f}  "
                  f"ort havuz={stats.mean([int(r['pool']) for r in v]):6.1f}  "
                  f"coken={sum(1 for r in v if r['collapsed']=='True')}")


# ============================================ PHASE 0: STAGNATION TRACING (measure-only)
# DOES NOT CHANGE THE ALGORITHM. One question: is the "stuck" state visible FROM WITHIN a
# SINGLE RUN?
#
# WHY NEEDED: in 5 of 24 cells the baseline returns the SAME result in all 3 repeats and
# `perturb` gains -0.91 there (+0.13 elsewhere). So the failure looks TRIGGERABLE, but we
# must be able to see the trigger FROM INSIDE -- not by comparing repeats.
#
# OUR ITERATION ECONOMY (measured, baseline arm, 72 runs): 62 iterations, 2.90 s/iter, and
# that time IS master_tl=3s itself -> iteration count = (200 - spp_tl) / master_tl. So the
# iteration count is a DIAL, not a constant.
# LITERATURE RATIO: stagnation thresholds are 13-25% of the outer loop (Ying RSA 28/214;
# ABC 150/600 and 210/1200; FSS Stag=100). Our equivalent is k ~ 9-15 iterations ->
# proportionally we are not abnormal. The difference: their inner loops make millions of
# cheap evaluations, ours solves a single MIP -> we work with 62 SAMPLES.
#
# (!) TWO CANDIDATE SIGNALS, because our loop is partly a POOL GENERATOR:
#   in 62% of runs the TERMINAL SPP produces the final best (50_10 0%, 200_20 100%).
#   So "best not improving" alone can mislead; the pool may still be fresh.
#   (a) best_age  = iterations since best improved        [the literature's standard signal]
#   (b) novelty   = Hamming distance of the proposal to the pool    [pool freshness]
# Decision rule: if stuck and healthy cells DO NOT SEPARATE on these signals there is NO
# trigger -> no mechanism is built, and that is learned in 1.5 hours (not 9).
FAZ0_CSV = os.path.join(_HERE, "results", "faz0_trace.csv")
FAZ0_COLS = ["track", "size", "inst", "rep", "iter", "master_mk", "cand_mk", "best",
             "improved", "novelty", "pool", "uniqA", "cols", "deg_on", "t"]
# cells where the baseline returned the SAME result in all 3 repeats of
# ablation_rebase.csv (measured):
FAZ0_STUCK = {("50_10", "1"), ("50_10", "2"), ("200_20", "2"),
              ("800_30", "1"), ("800_30", "3")}


def cmd_faz0():
    """Runs the baseline configuration over 8 sizes x 3 inst x reps and writes the
    ITERATION TRACE. No arms, no comparison -- measurement only. Resumable."""
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    track = "niche_v2"
    got = set()
    if os.path.exists(FAZ0_CSV):
        for r in csv.DictReader(open(FAZ0_CSV)):
            got.add((r["track"], r["size"], r["inst"], r["rep"]))
    jobs = [(s, i, r) for s in SIZES_B for i in INSTS for r in range(1, reps + 1)
            if (track, s, i, str(r)) not in got]
    os.makedirs(os.path.dirname(FAZ0_CSV), exist_ok=True)
    new = not os.path.exists(FAZ0_CSV)
    fh = open(FAZ0_CSV, "a", newline="")
    w = csv.writer(fh)
    if new:
        w.writerow(FAZ0_COLS)
    tot = len(SIZES_B) * len(INSTS) * reps
    print(f"\n### FAZ 0 — DURGUNLUK IZLEME (olcum-only, algoritma DEGISMIYOR) ###")
    print(f"### {tot} kosu ({tot-len(jobs)} var, {len(jobs)} kalan) x {BUDGET}s "
          f"-> {os.path.relpath(FAZ0_CSV)} ###\n", flush=True)
    t0 = time.time()
    for k, (s, i, r) in enumerate(jobs, 1):
        p = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "faz0worker", track, s, i, str(BUDGET)],
            cwd=_HERE, capture_output=True, text=True, timeout=BUDGET + 900)
        rows = [ln for ln in p.stdout.splitlines() if ln.startswith("TRACE ")]
        if not rows:
            print(f"[{k}/{len(jobs)}] {s} i{i} r{r}  *** BASARISIZ ***", flush=True)
            continue
        for ln in rows:
            w.writerow([track, s, i, r] + ln[6:].split("|"))
        fh.flush()
        last = rows[-1][6:].split("|")
        el = time.time() - t0
        print(f"[{k}/{len(jobs)}] {s:>8} i{i} r{r}  iter={last[0]:>3} best={last[3]:>7} "
              f"[{el/3600:.1f}sa gecti, ~{el/k*(len(jobs)-k)/3600:.1f}sa kaldi]", flush=True)
    fh.close()
    print("faz0 bitti", flush=True)


def faz0worker(track, size, inst, budget):
    nJob, nM, c1, c2, rt, pt, st_, mx, I_l, L_i, es = _load(size, inst, track)
    tr = []
    run_abl(nJob, nM, c1, c2, rt, pt, st_, I_l, L_i,
            total_time_limit=budget, seed=0, trace=tr, **_kw("no_dig", nM, LOCK))
    for d in tr:
        print("TRACE " + "|".join(str(d[c]) for c in FAZ0_COLS[4:]))


def cmd_faz0_report():
    """DECISION: do stuck cells SEPARATE from healthy ones, and what should k be?"""
    if not os.path.exists(FAZ0_CSV):
        print("faz0 izi yok"); return
    R = [r for r in csv.DictReader(open(FAZ0_CSV))]
    if not R:
        print("satir yok"); return
    runs = collections.defaultdict(list)
    for r in R:
        runs[(r["size"], r["inst"], r["rep"])].append(r)
    for v in runs.values():
        v.sort(key=lambda r: int(r["iter"]))

    def prof(rows):
        """Stagnation profile of one run."""
        best = [float(r["best"]) for r in rows]
        n = len(best)
        # best_age series + longest stagnation block + the iteration where the best was found
        age = 0; ages = []; last_imp = 0
        for j in range(n):
            if j and best[j] < best[j - 1] - 1e-9:
                age = 0; last_imp = j
            else:
                age += 1
            ages.append(age)
        nov = [float(r["novelty"]) for r in rows]
        return dict(n=n, maxage=max(ages), tail=n - 1 - last_imp,
                    tbest_frac=last_imp / max(1, n - 1),
                    nov_mean=stats.mean(nov), nov_tail=stats.mean(nov[last_imp:]) if last_imp < n else 0.0)

    print(f"\n{'='*104}\nFAZ 0 — DURGUNLUK PROFILI (taban konfigurasyonu, olcum-only)\n{'='*104}")
    print(f"{'hucre':>12} {'durum':>9} {'iter':>5} {'en uzun durgunluk':>18} "
          f"{'son iyilesmeden sonra':>22} {'best@%':>7} {'novelty':>8} {'kuyrukta nov':>13}")
    agg = collections.defaultdict(list)
    for (s, i, r), rows in sorted(runs.items(), key=lambda kv: (int(kv[0][0].split("_")[0]), kv[0][1])):
        p = prof(rows)
        lab = "TAKILI" if (s, i) in FAZ0_STUCK else "saglikli"
        agg[lab].append(p)
        print(f"{s+' i'+i:>12} {lab:>9} {p['n']:5d} {p['maxage']:18d} {p['tail']:22d} "
              f"{100*p['tbest_frac']:6.0f}% {p['nov_mean']:8.3f} {p['nov_tail']:13.3f}")
    print(f"\n{'-'*104}\n{'ORTALAMA':>12}")
    for lab in ("TAKILI", "saglikli"):
        v = agg.get(lab)
        if not v:
            continue
        print(f"{lab:>21} {stats.mean([x['n'] for x in v]):5.1f} "
              f"{stats.mean([x['maxage'] for x in v]):18.1f} "
              f"{stats.mean([x['tail'] for x in v]):22.1f} "
              f"{100*stats.mean([x['tbest_frac'] for x in v]):6.0f}% "
              f"{stats.mean([x['nov_mean'] for x in v]):8.3f} "
              f"{stats.mean([x['nov_tail'] for x in v]):13.3f}")
    print("\nOKUMA:")
    print("  'en uzun durgunluk' = k icin ust sinir. TAKILI'da belirgin BUYUKSE sinyal VAR.")
    print("  'son iyilesmeden sonra' = bosa giden kuyruk uzunlugu = kazanilabilecek iterasyon.")
    print("  'novelty' dusuk + durgunluk uzun = master ayni bolgede donuyor (gercek tikanma).")
    print("  'novelty' YUKSEK ama durgunluk uzun = havuz taze, dongu HAVUZ URETECI olarak")
    print("     calisiyor; o zaman best-tabanli tetikleyici YANLIS sinyal olur.")
    print("  IKI GRUP AYRISMIYORSA: tetikleyici yok -> mekanizma insa EDILMEZ.")


def cmd_screen4():
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    _generic_run(SCREEN4_CSV, list(SCREEN4_ARMS), SCREEN4_SIZES,
                 "ELEME KOSUSU — MASTER COZUM HAVUZU", reps,
                 cols=SCREEN4_COLS, insts=SCREEN4_INSTS)


def cmd_screen5():
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    _generic_run(SCREEN5_CSV, list(SCREEN5_ARMS), SCREEN5_SIZES,
                 "ELEME-5 — MASTER COZUM HAVUZU, ADIL OLCUM", reps,
                 cols=SCREEN4_COLS, insts=SCREEN5_INSTS)


def cmd_screen5_report():
    """THE REAL QUESTION: is the pool250 gain from the MECHANISM or from extra TIME?
    The gate is `base_plus` (the baseline given the same extra time as LOOP time) --
    not `base`."""
    if not os.path.exists(SCREEN5_CSV):
        print("eleme-5 sonucu yok"); return
    R = [r for r in csv.DictReader(open(SCREEN5_CSV))]
    if not R:
        print("satir yok"); return
    sizes = [s for s in SCREEN5_SIZES if any(r["size"] == s for r in R)]
    print("=" * 100)
    print("ELEME-5 — MASTER COZUM HAVUZU, ADIL OLCUM")
    print("=" * 100)

    def _panel(base_arm, arms, baslik):
        _B, _b, D = _cell_deltas(R, base_arm)
        print(f"\n--- {baslik}  (taban = {base_arm}) ---")
        print(f"{'kol':>11} {'dRPD%':>8} {'SE':>6} {'2SE':>6} {'w/t/l':>10} {'medyan':>7}  karar")
        for a in arms:
            v = list(D.get(a, {}).values())
            if len(v) < 2:
                print(f"{a:>11}   {'veri yok':>8}"); continue
            m = stats.mean(v); se = stats.stdev(v) / len(v) ** 0.5
            w = sum(1 for x in v if x < -1e-9); l = sum(1 for x in v if x > 1e-9)
            k = "IYILESTIRIYOR" if m < -2 * se else ("ZARARLI" if m > 2 * se else "gurultude")
            print(f"{a:>11} {m:+8.3f} {se:6.3f} {2*se:6.3f} {w:>3}/{len(v)-w-l}/{l:<3} "
                  f"{stats.median(v):+7.2f}  {k}")
        return D

    pool_arms = [a for a in SCREEN5_ARMS if a.startswith("pool")]
    # ⭐ THRESHOLD 1 (GATE): time-equalized comparison
    _panel("base_plus", pool_arms, "⭐ ESIK 1 — KAPI: mekanizma mi, satin alinmis zaman mi")
    # informational: the raw baseline
    _panel("base", pool_arms + ["base_plus"], "bilgi — ham tabana gore (KAPI DEGIL)")

    # THRESHOLD 2: do no harm (vs the raw baseline, small sizes)
    _, _, Db = _cell_deltas(R, "base")
    print("\n--- ESIK 2 — ZARAR VERMEME (vs base, n<=400) ---")
    for a in pool_arms:
        keys = [k for k in Db.get(a, {}) if k[0] not in ("640_25", "800_30")]
        v = [Db[a][k] for k in keys]
        if len(v) >= 2:
            m = stats.mean(v); se = stats.stdev(v) / len(v) ** 0.5
            print(f"  {a:>9}  dRPD {m:+.3f} +-{se:.3f}   "
                  f"{'!! ZARAR VERIYOR' if m > 2 * se else 'zarar yok'}")

    # THRESHOLD 3: wall clock
    dur = {}; prev = None
    for r in R:
        w = float(r["wall"])
        if prev is not None and 0 < w - prev < 3000:
            dur.setdefault((r["arm"], r["size"]), []).append(w - prev)
        prev = w
    print("\n--- ESIK 3 — DUVAR SAATI (ort kosu suresi, sn): pool250 <= base_plus OLMALI ---")
    print(f"{'kol':>11}" + "".join(f"{s:>10}" for s in sizes))
    for a in SCREEN5_ARMS:
        row = ""
        for s in sizes:
            x = dur.get((a, s))
            row += f"{stats.mean(x):10.1f}" if x else f"{'--':>10}"
        print(f"{a:>11}" + row)

    print("\n  KABUL, her havuz kolu icin AYRI (ucu birden): (1) base_plus'a gore dRPD < -2SE,")
    print("  (2) n<=400'de base'e gore +2SE'yi asan zarar YOK, (3) duvar saati base_plus'i asmiyor.")
    print("  (1) saglanmazsa o kolun kazanci MEKANIZMA DEGIL, satin alinmis zamandir -> REDDEDILIR.")
    print("  Ikisi de gecerse UCUZ OLANI (pool160) tercih edilir: ayni sonuc, daha az butce.")


def cmd_screen6():
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    _generic_run(SCREEN6_CSV, list(SCREEN6_ARMS), SCREEN5_SIZES,
                 "ELEME-6 — INSIDE-200: HERKES GERCEK 200 SANIYE", reps,
                 cols=SCREEN6_COLS, insts=SCREEN5_INSTS)


def cmd_screen6_report():
    """GATE: pool250_inside vs base_inside at EQUAL total time. Additionally a CONTRACT
    AUDIT: each run's total_s must not exceed the budget (in-algorithm time; harness
    overhead excluded)."""
    if not os.path.exists(SCREEN6_CSV):
        print("eleme-6 sonucu yok"); return
    R = [r for r in csv.DictReader(open(SCREEN6_CSV))]
    if not R:
        print("satir yok"); return
    sizes = [s for s in SCREEN5_SIZES if any(r["size"] == s for r in R)]
    print("=" * 100)
    print("ELEME-6 — INSIDE-200, UC KOL   (herkes ayni 200s kontrati)")
    print("=" * 100)

    def _panel(base_arm, arms, baslik):
        _B0, _b0, D0 = _cell_deltas(R, base_arm)
        print(f"\n--- {baslik}  (taban = {base_arm}) ---")
        print(f"{'kol':>15} {'dRPD%':>8} {'SE':>6} {'2SE':>6} {'w/t/l':>10} {'medyan':>7}  karar")
        for a in arms:
            v = list(D0.get(a, {}).values())
            if len(v) < 2:
                print(f"{a:>15}   veri yok"); continue
            m = stats.mean(v); se = stats.stdev(v) / len(v) ** 0.5
            w = sum(1 for x in v if x < -1e-9); l = sum(1 for x in v if x > 1e-9)
            k = "IYILESTIRIYOR" if m < -2 * se else ("ZARARLI" if m > 2 * se else "gurultude")
            print(f"{a:>15} {m:+8.3f} {se:6.3f} {2*se:6.3f} {w:>3}/{len(v)-w-l}/{l:<3} "
                  f"{stats.median(v):+7.2f}  {k}")
        # size breakdown (for the first arm)
        per = {}
        for kk, x in D0.get(arms[0], {}).items():
            per.setdefault(kk[0], []).append(x)
        print("   boyut: " + "".join(f"{s:>9}" for s in sizes))
        print(f"   {arms[0][:5]:>5}: " + "".join(
            f"{stats.mean(per[s]):9.2f}" if s in per else f"{'--':>9}" for s in sizes))

    _panel("base_inside", ["pool250_bg", "pool250_inside"],
           "⭐ KAPI: uretim paketi (ve S1'siz havuz) esit kontratta kazaniyor mu")
    _panel("pool250_inside", ["pool250_bg"], "S1'in payi (ayni malzeme, ucuz SPP + buyuk dongu)")
    # CONTRACT AUDIT
    print("\n--- KONTRAT: algoritma-ici toplam sure (total_s; butce 200) ---")
    print(f"{'kol':>15}" + "".join(f"{s:>9}" for s in sizes) + f"{'MAX':>8}{'ihlal':>7}")
    for a in SCREEN6_ARMS:
        row = ""; mx = 0.0; nv = 0
        for s in sizes:
            ts = [float(r["total_s"]) for r in R if r["arm"] == a and r["size"] == s
                  and float(r.get("total_s", -1)) > 0]
            if ts:
                row += f"{stats.mean(ts):9.1f}"; mx = max(mx, max(ts))
                nv += sum(1 for t in ts if t > 202.0)
            else:
                row += f"{'--':>9}"
        print(f"{a:>15}" + row + f"{mx:8.1f}{nv:7d}")
    print("\n--- dongu / SPP paylasimi (ort loop_s -> total_s) + SPP kazanci% ---")
    for a in SCREEN6_ARMS:
        row = ""
        for s in sizes:
            rs = [r for r in R if r["arm"] == a and r["size"] == s]
            if rs:
                lp = stats.mean(float(r["loop_s"]) for r in rs)
                tt = stats.mean(float(r["total_s"]) for r in rs)
                g = stats.mean(100 * (float(r["pre_spp"]) - float(r["makespan"])) /
                               float(r["pre_spp"]) for r in rs)
                row += f" {lp:4.0f}>{tt:4.0f}/{g:4.1f}"
            else:
                row += f"{'--':>15}"
        print(f"{a:>15}" + row)
    # bg routing volume (mechanism liveness)
    bgv = [int(r.get("n_bgroute", 0) or 0) for r in R if r["arm"] == "pool250_bg"]
    if bgv:
        print(f"\n  pool250_bg ort bg-rotalama: {stats.mean(bgv):.0f} sutun/kosu "
              f"(0'a yakinsa S1 calismamis demektir)")
    print("\n  KABUL: (1) pool250_bg vs base_inside dRPD < -2SE, (2) total_s hicbir kosuda")
    print("  202'yi asmamis, (3) base_inside'in SPP'si CANLI (kazanc% > 0 olan boyutlar var).")
    print("  S1 paneli BILGI: bg, inside'i yenmese de paket ucuzsa tercih edilebilir.")


def cmd_screen4_report():
    """THREE QUESTIONS together: (1) makespan, (2) mechanism (novelty), (3) budget (wall clock)."""
    if not os.path.exists(SCREEN4_CSV):
        print("eleme-4 sonucu yok"); return
    R = [r for r in csv.DictReader(open(SCREEN4_CSV))]
    if not R:
        print("satir yok"); return
    B, base, D = _cell_deltas(R, "no_dig")
    arms = [a for a in SCREEN4_ARMS if a != "no_dig"]
    print(f"\n{'='*100}\nELEME-4 — MASTER COZUM HAVUZU   taban = no_dig\n"
          f"Delta = RPD(kol) - RPD(taban)   ( - = havuz IYILESTIRDI )\n{'='*100}")
    print(f"{'kol':>11} {'dRPD%':>8} {'SE':>6} {'2SE':>6} {'w/t/l':>9} {'medyan':>7}  karar")
    for a in arms:
        v = list(D.get(a, {}).values())
        if len(v) < 2:
            continue
        m = stats.mean(v); se = stats.stdev(v) / len(v) ** 0.5
        w = sum(1 for x in v if x < -1e-9); l = sum(1 for x in v if x > 1e-9)
        verdict = ("IYILESTIRIYOR -> tam kosuya aday" if m < -2 * se else
                   "ZARARLI" if m > 2 * se else "gurultude (fayda yok)")
        print(f"{a:>11} {m:+8.3f} {se:6.3f} {2*se:6.3f} {w:>3}/{len(v)-w-l}/{l:<3} "
              f"{stats.median(v):+7.2f}  {verdict}")
    sizes = [s for s in SCREEN4_SIZES if any(r["size"] == s for r in R)]
    print(f"\n--- olcek kirilimi (dRPD%) — ASIL BEKLENTI 640/800 ---\n{'kol':>11}"
          + "".join(f"{s:>10}" for s in sizes))
    for a in arms:
        row = ""
        for s in sizes:
            v = [x for (ss, i), x in D.get(a, {}).items() if ss == s]
            row += f"{stats.mean(v):+10.2f}" if v else f"{'--':>10}"
        print(f"{a:>11}" + row)
    # ---- ⭐ THRESHOLD 2 (THE REAL SIGNAL): MECHANISM. Baseline tailnov ~0.05 on 640/800
    # (phase-0 novelty). If the pool arms raise it clearly, the mechanism worked. If not,
    # anything visible in makespan has another cause -> the arm is NOT ACCEPTED.
    print(f"\n--- ⭐ ESIK 2 — MEKANIZMA: kuyruk novelty (son 10 iter) + hasat sayisi ---")
    print(f"{'kol':>11}" + "".join(f"{s:>12}" for s in sizes) + f"{'ort hasat':>11}")
    for a in ["no_dig"] + arms:
        row = ""
        for s in sizes:
            v = [float(r["tailnov"]) for r in R
                 if r["arm"] == a and r["size"] == s and float(r.get("tailnov", -1)) >= 0]
            row += f"{stats.mean(v):12.3f}" if v else f"{'--':>12}"
        hv = [int(r.get("n_harvest", 0) or 0) for r in R if r["arm"] == a]
        print(f"{a:>11}" + row + f"{stats.mean(hv) if hv else 0:11.0f}")
    print("  Taban ~0.05 bekleniyor. Havuz kolu bunu yukseltmiyorsa MEKANIZMA CALISMAMISTIR.")

    # ---- THRESHOLD 3: BUDGET. wall is CUMULATIVE -> run time = difference from the
    # previous row in FILE ORDER (differencing within an arm would count interleaved runs of
    # other arms; the first version had this bug, caught in the smoke test).
    print(f"\n--- ESIK 3: BUTCE (ort kosu suresi, sn) — kollar arasi BUYUMEMELI ---")
    dur = {}
    prev = None
    for r in R:
        w = float(r["wall"])
        if prev is not None and 0 < w - prev < 3000:
            dur.setdefault((r["arm"], r["size"]), []).append(w - prev)
        prev = w
    print(f"{'kol':>11}" + "".join(f"{s:>12}" for s in sizes))
    for a in ["no_dig"] + arms:
        row = ""
        for s in sizes:
            v = dur.get((a, s))
            row += f"{stats.mean(v):12.1f}" if v else f"{'--':>12}"
        print(f"{a:>11}" + row)
    print("  NOT: SPP suresi olculdu = 1 saniye (244s vs 243s, 800_30). Buyume beklenmiyor;")
    print("  buyurse havuz SPP'yi sisirmis demektir -> spp_budget devreye girmeli.")
    print(f"\n--- iterasyon / havuz / cokus ---")
    for a in ["no_dig"] + arms:
        v = [r for r in R if r["arm"] == a]
        if v:
            print(f"  {a:>11}: ort iter={stats.mean([int(r['iters']) for r in v]):5.1f}  "
                  f"ort havuz={stats.mean([int(r['pool']) for r in v]):7.1f}  "
                  f"coken={sum(1 for r in v if r['collapsed']=='True')}")
    # ---- ⭐ THRESHOLD 2: QUALITY, SUBGROUP SPLIT. The overall mean DILUTES a targeted
    # intervention (measured in the dry test: -0.9 in the subgroup vs -0.22 overall) ->
    # the gate is the SUBGROUP.
    print(f"\n--- ⭐ ALT GRUP AYRIMI (kapi: HEDEF; n<=400 zarar-vermeme kontrolu) ---")
    print(f"{'kol':>11} {'HEDEF 640+800':>26} {'n<=400 (zarar vermemeli)':>30}")
    for a in arms:
        out = ""
        for lab, keys in (("hedef", [k for k in D.get(a, {}) if k[0] in ("640_25", "800_30")]),
                          ("kucuk", [k for k in D.get(a, {}) if k[0] not in ("640_25", "800_30")])):
            v = [D[a][k] for k in keys]
            if len(v) < 2:
                out += f"{'--':>28}"; continue
            m = stats.mean(v); se = stats.stdev(v) / len(v) ** 0.5
            if lab == "hedef":
                tag = "IYILESTIRIYOR" if m < -2 * se else ("ZARARLI" if m > 2 * se else "gurultude")
            else:
                tag = "!! ZARAR VERIYOR" if m > 2 * se else "zarar yok"
            out += f"{m:+8.3f}+-{se:5.3f} {tag:<13}"
        print(f"{a:>11} {out}")
    print("\n  KABUL (dordu birden): (1) 640/800'de tailnov 0.05'ten belirgin yukselmis,")
    print("  (2) HEDEF alt grupta dRPD < -2SE, (3) n<=400'de +2SE'yi asan zarar YOK,")
    print("  (4) kosu suresi buyumemis.  Genel dRPD raporlanir ama KAPI DEGILDIR.")


def cmd_screen3():
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    _generic_run(SCREEN3_CSV, list(SCREEN3_ARMS), SCREEN3_SIZES,
                 "ELEME KOSUSU — LAZY OUT-DEGREE", reps)


def cmd_screen3_report():
    """THE REAL QUESTION: with LAZY delivery of the inequality, does the guard stop firing
    (= does degree SURVIVE on 640/800), and does that SHOW UP in makespan?
    Acceptance threshold (fixed in advance): 800_30 guard 9/9 -> ~0/9 AND no degradation
    beyond 2SE at any size."""
    if not os.path.exists(SCREEN3_CSV):
        print("eleme-3 sonucu yok"); return
    R = [r for r in csv.DictReader(open(SCREEN3_CSV))]
    if not R:
        print("satir yok"); return
    B, base, D = _cell_deltas(R, "no_dig")
    arms = [a for a in SCREEN3_ARMS if a != "no_dig"]
    lvl = {"deg_lazy1": "1 (tam-sayi)", "deg_lazy2": "2 (+dugum)", "deg_lazy3": "3 (+kok)"}
    print(f"\n{'='*98}\nELEME-3 — LAZY OUT-DEGREE   taban = no_dig (esitsizlik ONDEN, tum makineler)\n"
          f"Delta = RPD(kol) - RPD(taban)   ( - = TEMBEL TESLIM IYILESTIRDI )\n{'='*98}")
    print(f"{'kol':>11} {'seviye':>13} {'dRPD%':>8} {'SE':>6} {'2SE':>6} {'w/t/l':>9}  karar")
    for a in arms:
        v = list(D.get(a, {}).values())
        if len(v) < 2:
            continue
        m = stats.mean(v); se = stats.stdev(v) / len(v) ** 0.5
        w = sum(1 for x in v if x < -1e-9); l = sum(1 for x in v if x > 1e-9)
        verdict = ("IYILESTIRIYOR -> tam kosuya aday" if m < -2 * se else
                   "ZARARLI" if m > 2 * se else "gurultude (fayda yok)")
        print(f"{a:>11} {lvl.get(a,'?'):>13} {m:+8.3f} "
              f"{se:6.3f} {2*se:6.3f} {w:>3}/{len(v)-w-l}/{l:<3}  {verdict}")
    sizes = [s for s in SCREEN3_SIZES if any(r["size"] == s for r in R)]
    print(f"\n--- olcek kirilimi (dRPD%) — ASIL BEKLENTI 640/800 tarafinda ---\n{'kol':>11}"
          + "".join(f"{s:>10}" for s in sizes))
    for a in arms:
        row = ""
        for s in sizes:
            v = [x for (ss, i), x in D.get(a, {}).items() if ss == s]
            row += f"{stats.mean(v):+10.2f}" if v else f"{'--':>10}"
        print(f"{a:>11}" + row)
    print(f"\n--- ⭐ MEKANIZMA OLCUMU: deg-guard tetiklenme — DUSMESI gereken ---")
    print(f"{'kol':>11}" + "".join(f"{s:>12}" for s in sizes))
    for a in ["no_dig"] + arms:
        row = ""
        for s in sizes:
            v = [r for r in R if r["arm"] == a and r["size"] == s]
            row += f"{sum(1 for r in v if r['deg_guard_fired']=='True')}/{len(v)}".rjust(12) if v else f"{'--':>12}"
        print(f"{a:>11}" + row)
    print("  Taban 800_30'da 9/9 tetikliyor = degree TAMAMEN kapali (master incumbent DONDURMUYOR).")
    print("  Lazy kollarda 0/9 -> model kucuk kaldi, esitsizlik hayatta = MEKANIZMA CALISTI.")
    print("  Guard DUSMUYORSA mekanizma calismamistir (satir sayisi darbogaz degilmis).")
    print("  Guard DUSUP makespan BOZULUYORSA 'siki LP != TL altinda iyi incumbent' teyit edilir.")
    print(f"\n--- iterasyon / havuz / cokus (zarar hizdan mi kaliteden mi) ---")
    for a in ["no_dig"] + arms:
        v = [r for r in R if r["arm"] == a]
        if v:
            print(f"  {a:>11}: ort iter={stats.mean([int(r['iters']) for r in v]):5.1f}  "
                  f"ort havuz={stats.mean([int(r['pool']) for r in v]):6.1f}  "
                  f"coken={sum(1 for r in v if r['collapsed']=='True')}")


def cmd_screen_report():
    if not os.path.exists(SCREEN_CSV):
        print("eleme sonucu yok"); return
    R = [r for r in csv.DictReader(open(SCREEN_CSV))]
    if not R:
        print("satir yok"); return
    B, base, D = _cell_deltas(R, "no_dig")
    arms = [a for a in SCREEN_ARMS if a != "no_dig"]
    ks = {a: SCREEN_ARMS[a].get("lb_frac") for a in arms}
    print(f"\n{'='*96}\nELEME — LOCAL BRANCHING   taban = no_dig (gonderilen yapi)\n"
          f"Delta = RPD(kol) - RPD(taban)   ( - = local branching IYILESTIRDI )\n{'='*96}")
    print(f"{'kol':>10} {'k (n orani)':>12} {'dRPD%':>8} {'SE':>6} {'2SE':>6} {'w/t/l':>9}  karar")
    for a in arms:
        v = list(D.get(a, {}).values())
        if len(v) < 2:
            continue
        m = stats.mean(v); se = stats.stdev(v) / len(v) ** 0.5
        w = sum(1 for x in v if x < -1e-9); l = sum(1 for x in v if x > 1e-9)
        verdict = ("IYILESTIRIYOR -> tam kosuya aday" if m < -2 * se else
                   "ZARARLI" if m > 2 * se else "gurultude (fayda yok)")
        print(f"{a:>10} {str(ks[a]):>12} {m:+8.3f} {se:6.3f} {2*se:6.3f} "
              f"{w:>3}/{len(v)-w-l}/{l:<3}  {verdict}")
    sizes = [s for s in SCREEN_SIZES if any(r["size"] == s for r in R)]
    print(f"\n--- olcek kirilimi (dRPD%) ---\n{'kol':>10}" + "".join(f"{s:>10}" for s in sizes))
    for a in arms:
        row = ""
        for s in sizes:
            v = [x for (ss, i), x in D.get(a, {}).items() if ss == s]
            row += f"{stats.mean(v):+10.2f}" if v else f"{'--':>10}"
        print(f"{a:>10}" + row)
    # THE REAL HOPE: does LB shrink the master and keep degree alive?
    print(f"\n--- deg-guard tetiklenme orani (9 kosu/hucre) — DUSMESI beklenen ---")
    print(f"{'kol':>10}" + "".join(f"{s:>10}" for s in sizes))
    for a in ["no_dig"] + arms:
        row = ""
        for s in sizes:
            v = [r for r in R if r["arm"] == a and r["size"] == s]
            row += f"{sum(1 for r in v if r['deg_guard_fired']=='True')}/{len(v):<8}" if v else f"{'--':>10}"
        print(f"{a:>10}" + row)
    print("  (guard tetiklenmezse degree kisitlari ACIK kalir = +%2-5'lik kaldirac geri gelir)")
    print(f"\n--- iterasyon / havuz / BOS-KOMSULUK ---")
    for a in ["no_dig"] + arms:
        v = [r for r in R if r["arm"] == a]
        if v:
            lbf = [int(r.get("n_lbfail") or 0) for r in v]
            it = stats.mean([int(r["iters"]) for r in v])
            print(f"  {a:>10}: ort iter={it:5.1f}  "
                  f"ort havuz={stats.mean([int(r['pool']) for r in v]):6.1f}  "
                  f"coken={sum(1 for r in v if r['collapsed']=='True')}  "
                  f"lb-bos={stats.mean(lbf):5.1f}/iter ({100*stats.mean(lbf)/max(it,1):.0f}%)")
    print("  lb-bos% YUKSEKSE (>%50) kisit cogu iterasyonda KALKIYOR -> kol tabana yaklasir;")
    print("  o durumda negatif sonuc 'fikir kotu' DEGIL 'fikir test edilmedi' demektir.")


# ============================================================ rebase (separate experiment)
def cmd_rebase():
    """LOO ablation against the DIG-less baseline. SEPARATE CSV
    (`results/ablation_rebase.csv`); does NOT touch `ablation.csv`. Resumable: if
    interrupted, the same command continues where it left off."""
    track = sys.argv[2] if len(sys.argv) > 2 else "niche_v2"
    reps = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    sizes = SIZES_B if track == "niche_v2" else SIZES_A
    arms = list(REBASE_ARMS)
    got = _done(REBASE_CSV)
    jobs = [(s, i, a, r) for s in sizes for i in INSTS for a in arms
            for r in range(1, reps + 1) if (track, s, i, a, str(r)) not in got]
    tot = len(sizes) * len(INSTS) * len(arms) * reps
    os.makedirs(os.path.dirname(REBASE_CSV), exist_ok=True)
    new = not os.path.exists(REBASE_CSV)
    fh = open(REBASE_CSV, "a", newline="")
    w = csv.writer(fh)
    if new:
        w.writerow(COLS)
    print(f"\n### REBASE ABLASYON (DIG'siz taban) — {track} | {len(arms)} kol x {len(sizes)} boyut "
          f"x {len(INSTS)} inst x {reps} tekrar = {tot} kosu "
          f"({tot-len(jobs)} var, {len(jobs)} kalan), {BUDGET}s ###")
    print(f"### -> {os.path.relpath(REBASE_CSV)}   (ablation.csv'ye DOKUNULMUYOR) ###\n", flush=True)
    t0 = time.time()
    for k, (s, i, a, r) in enumerate(jobs, 1):
        res = _spawn(track, s, i, a, BUDGET)
        if res is None:
            print(f"[{k}/{len(jobs)}] {s} i{i} r{r} {a:>16}  *** BASARISIZ ***", flush=True)
            continue
        w.writerow([track, s, i, a, r, res["best"], res["pre_spp"], res["iters"], res["pool"],
                    round(time.time() - t0, 1), res["deg_guard_fired"], res["deg_off_iter"],
                    res["mfail"], res["collapsed"],
                    res["loop_s"], res["total_s"], res["n_harvest"],
                    res.get("route_s", -1.0), res.get("mip_st"), res.get("mip_gap")]
                   + [res.get(k) for k in ("reserve", "spp_route_s", "spp_build_s",
                                           "spp_mip_s", "spp_n_uniq", "spp_n_routed",
                                           "spp_n_cols")])
        fh.flush()
        g = "  guard@" + str(res["deg_off_iter"]) if res["deg_guard_fired"] else ""
        if res["collapsed"]:
            g += "  *** COKTU (master incumbent vermedi -> greedy) ***"
        el = time.time() - t0
        eta = el / k * (len(jobs) - k)
        print(f"[{k}/{len(jobs)}] {s:>8} i{i} r{r} {a:>16}  mk={res['best']:7.1f} "
              f"iter={res['iters']:3d} pool={res['pool']:4d}{g}"
              f"  [{el/3600:.1f}sa gecti, ~{eta/3600:.1f}sa kaldi]", flush=True)
    fh.close()
    print("rebase kosusu bitti", flush=True)


def _cell_deltas(rows, base_arm):
    """Per (size,inst): B = best over all arms/repeats (the eq:rpd denominator),
    delta_arm = 100*(mean(arm) - mean(base))/B.
    Returns: (B, base_mean, {arm: {(s,i): delta}})."""
    cell = {}
    for r in rows:
        cell.setdefault((r["size"], r["inst"], r["arm"]), []).append(float(r["makespan"]))
    B = {}
    for (s, i, a), v in cell.items():
        B[(s, i)] = min(B.get((s, i), 1e18), min(v))
    base = {k[:2]: stats.mean(v) for k, v in cell.items() if k[2] == base_arm}
    d = {}
    for (s, i, a), v in cell.items():
        if a == base_arm or (s, i) not in base:
            continue
        d.setdefault(a, {})[(s, i)] = 100.0 * (stats.mean(v) - base[(s, i)]) / B[(s, i)]
    return B, base, d


def cmd_rebase_report():
    """The new table (based on `no_dig`) + SIDE-BY-SIDE comparison with the OLD table.
    The side-by-side part answers the real question: are the LOO results robust to the
    choice of baseline?"""
    track = sys.argv[2] if len(sys.argv) > 2 else "niche_v2"
    if not os.path.exists(REBASE_CSV):
        print("rebase sonucu yok"); return
    R = [r for r in csv.DictReader(open(REBASE_CSV)) if r["track"] == track]
    if not R:
        print(f"{track} icin satir yok"); return
    B, base, D = _cell_deltas(R, "no_dig")
    sizes = sorted({r["size"] for r in R}, key=lambda s: int(s.split("_")[0]))

    print(f"\n{'='*100}\nREBASE ABLASYON — {track}   taban = no_dig (TAZE, ayni oturum)\n"
          f"Delta = RPD(kol) - RPD(no_dig)   (+ = bileseni cikarmak BOZDU = bilesen gerekli)\n{'='*100}")
    def _panel(title, arm_list, drop):
        """drop=True  -> the arm REMOVES a component; + = removal hurt = component needed.
           drop=False -> the arm ADDS a component;   + = adding hurt = candidate rejected."""
        rows = [a for a in arm_list if a in D and len(D[a]) >= 2]
        if not rows:
            return
        print(f"\n--- {title} ---")
        print(f"{'kol':>22} {'dRPD%':>8} {'SE':>6} {'2SE':>6} {'w/t/l':>9}  {'medyan':>7}  karar")
        for a in rows:
            v = list(D[a].values())
            m = stats.mean(v); se = stats.stdev(v) / len(v) ** 0.5
            w = sum(1 for x in v if x < -1e-9); l = sum(1 for x in v if x > 1e-9)
            if drop:
                verdict = ("YUK TASIYOR" if m > 2 * se else
                           "!! CIKARMAK IYILESTIRIYOR -> bilesen zararli" if m < -2 * se else
                           "gurultude (yuk tasimiyor)")
            else:
                verdict = ("!! EKLEMEK IYILESTIRIYOR -> konfige alinmali" if m < -2 * se else
                           "ZARARLI -> reddedildi" if m > 2 * se else
                           "gurultude -> reddedildi")
            # median: does the mean come from outlier cells? (bias: mean +1.29 / median +0.29)
            print(f"{a:>22} {m:+8.3f} {se:6.3f} {2*se:6.3f} {w:>3}/{len(v)-w-l}/{l:<3}  "
                  f"{stats.median(v):+7.2f}  {verdict}")

    _panel("UST PANEL: korunan bilesenler, TEK TEK CIKARILDI", REBASE_DROP, True)
    _panel("ALT PANEL: iptal edilen adaylar, TEK TEK GERI EKLENDI", REBASE_ADD, False)

    # ---- THE REAL QUESTION: same as the old table? (baseline full -> baseline no_dig)
    if os.path.exists(CSV_PATH):
        R0 = [r for r in csv.DictReader(open(CSV_PATH)) if r["track"] == track]
        _, _, D0 = _cell_deltas(R0, "full")
        print(f"\n{'='*100}\nETKILESIM KONTROLU — ayni bilesen, IKI farkli tabanda\n"
              f"  D1 = arm - full     (ablation.csv, DIG'li taban)\n"
              f"  D2 = arm - no_dig   (ablation_rebase.csv, DIG'siz taban)\n"
              f"  |D1-D2| kendi 2SE'sinin altindaysa ETKILESIM YOK -> LOO sonuclari tabana saglam\n{'='*100}")
        print(f"{'bilesen':>12} {'D1(full)':>10} {'D2(nodig)':>11} {'fark':>8} {'2SE(fark)':>10}  karar")
        for suffix in ("no_warm", "no_degree", "no_bias", "no_spp", "no_kmach",
                       "plus_ils", "plus_setupaware", "plus_optcut",
                       "plus_perturb", "plus_graded"):
            a2 = "nodig_" + suffix
            if suffix not in D0 or a2 not in D:
                continue
            keys = sorted(set(D0[suffix]) & set(D[a2]))
            if len(keys) < 2:
                continue
            d1 = [D0[suffix][k] for k in keys]; d2 = [D[a2][k] for k in keys]
            diff = [b - a for a, b in zip(d1, d2)]          # matched-cell difference
            md = stats.mean(diff); sed = stats.stdev(diff) / len(diff) ** 0.5
            ok = abs(md) <= 2 * sed
            print(f"{suffix:>12} {stats.mean(d1):+10.2f} {stats.mean(d2):+11.2f} "
                  f"{md:+8.2f} {2*sed:10.2f}  "
                  f"{'etkilesim YOK (saglam)' if ok else '!! ETKILESIM VAR -> tablo yeniden tabanlanmali'}")

    print(f"\n--- olcek kirilimi (dRPD%, taban no_dig) ---\n{'kol':>18}"
          + "".join(f"{s:>10}" for s in sizes))
    for a in REBASE_ARMS:
        if a == "no_dig" or a not in D:
            continue
        row = ""
        for s in sizes:
            v = [x for (ss, i), x in D[a].items() if ss == s]
            row += f"{stats.mean(v):+10.2f}" if v else f"{'--':>10}"
        print(f"{a:>18}" + row)
    coll = [r for r in R if r.get("collapsed") == "True"]
    if coll:
        by = {}
        for r in coll:
            by.setdefault(r["arm"], set()).add(r["size"])
        print("\n--- ⚠️ COKEN KOSULAR (master incumbent vermedi -> sonuc = greedy tohum) ---")
        for a, ss in sorted(by.items()):
            print(f"  {a:>18}: boyutlar = {sorted(ss, key=lambda s: int(s.split('_')[0]))}")


def cmd_run():
    track = sys.argv[2] if len(sys.argv) > 2 else "niche_v2"
    reps = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    sizes = SIZES_B if track == "niche_v2" else SIZES_A
    arms = list(ARMS) if track == "niche_v2" else ARMS_A
    _lock_guard(CSV_PATH)          # stale-row protection (do not start if the baseline changed)
    got = _done()
    jobs = [(s, i, a, r) for s in sizes for i in INSTS for a in arms
            for r in range(1, reps + 1) if (track, s, i, a, str(r)) not in got]
    tot = len(sizes) * len(INSTS) * len(arms) * reps
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    # RUN RECORD (package 1-4 convention): version + budget + seed policy to a side file.
    try:
        git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_HERE,
                             capture_output=True, text=True).stdout.strip()
    except Exception:
        git = "?"
    with open(os.path.splitext(CSV_PATH)[0] + ".manifest.txt", "a") as mf:
        mf.write(f"{time.strftime('%F %T')} track={track} git={git} budget={BUDGET}s "
                 f"reps={reps} kol={len(arms)} tohum=sabit0(tekrarlar ayni tohum altindaki "
                 f"kosudan-kosuya oynakligi olcer) bekleyen={len(jobs)}\n")
    new = not os.path.exists(CSV_PATH)
    fh = open(CSV_PATH, "a", newline="")
    w = csv.writer(fh)
    if new:
        w.writerow(COLS)
    # ARM ORDER SHUFFLE: fixed-seed deterministic shuffle so arms spread over time
    # (thermal/load drift must not pile onto one arm). Resume-safe: each job is independent;
    # finished ones were already filtered out.
    import random as _rnd
    _rnd.Random("ablasyon2026").shuffle(jobs)
    print(f"\n### ABLASYON — {track} | {len(arms)} kol x {len(sizes)} boyut x {len(INSTS)} inst "
          f"x {reps} tekrar = {tot} kosu ({tot-len(jobs)} var, {len(jobs)} kalan), {BUDGET}s ###",
          flush=True)
    t0 = time.time()
    for k, (s, i, a, r) in enumerate(jobs, 1):
        # FAILURE RULE (protocol §9): crash/no-output exit -> 1 retry with the SAME settings;
        # if it recurs, (instance, arm, rep) is excluded + recorded. NO instance/cell SWAPS.
        res = None
        for _deneme in (1, 2):
            try:
                res = _spawn(track, s, i, a, BUDGET)
            except Exception as e:
                print(f"    [ariza] deneme {_deneme}: {type(e).__name__}: {e}", flush=True)
                res = None
            if res is not None:
                break
            if _deneme == 1:
                print(f"[{k}/{len(jobs)}] {s} i{i} r{r} {a:>15}  *** 1. deneme BASARISIZ, "
                      f"tekrar ***", flush=True)
        if res is None:
            _exclude(CSV_PATH, (track, s, i, a, str(r)), "iki deneme basarisiz")
            print(f"[{k}/{len(jobs)}] {s} i{i} r{r} {a:>15}  *** DISLANDI (iki deneme) ***",
                  flush=True)
            continue
        row = [track, s, i, a, r, res["best"], res["pre_spp"], res["iters"], res["pool"],
               round(time.time() - t0, 1), res["deg_guard_fired"], res["deg_off_iter"],
               res["mfail"], res["collapsed"],
               res["loop_s"], res["total_s"], res["n_harvest"], res.get("route_s", -1.0),
               res.get("mip_st"), res.get("mip_gap")] \
              + [res.get(k) for k in ("reserve", "spp_route_s", "spp_build_s",
                                      "spp_mip_s", "spp_n_uniq", "spp_n_routed", "spp_n_cols")]
        # When COLS is extended this check must be updated too; an old version lagged behind
        # = new columns would be written EMPTY. The assert fails on the run's first row,
        # not 50 hours later.
        assert len(row) == len(COLS), f"CSV hizasi bozuk: {len(row)} != {len(COLS)}"
        w.writerow(row)
        fh.flush()
        g = "  guard@" + str(res["deg_off_iter"]) if res["deg_guard_fired"] else ""
        if res["collapsed"]:
            g += "  *** COKTU (master incumbent vermedi -> greedy) ***"
        el = time.time() - t0
        eta = el / k * (len(jobs) - k)                      # remaining-time estimate
        print(f"[{k}/{len(jobs)}] {s:>8} i{i} r{r} {a:>15}  mk={res['best']:7.1f} "
              f"iter={res['iters']:3d} pool={res['pool']:4d}{g}"
              f"  [{el/3600:.1f}sa gecti, ~{eta/3600:.1f}sa kaldi]", flush=True)
    fh.close()
    print("kosu bitti", flush=True)


def cmd_report():
    track = sys.argv[2] if len(sys.argv) > 2 else "niche_v2"
    if not os.path.exists(CSV_PATH):
        print("sonuc yok"); return
    R = [r for r in csv.DictReader(open(CSV_PATH)) if r["track"] == track]
    if not R:
        print(f"{track} icin satir yok"); return
    cell = {}
    for r in R:
        cell.setdefault((r["size"], r["inst"], r["arm"]), []).append(float(r["makespan"]))
    sizes = sorted({k[0] for k in cell}, key=lambda s: int(s.split("_")[0]))
    arms = [a for a in ARMS if any(k[2] == a for k in cell)]
    # B = per-instance best over ALL arms/repeats (the eq:rpd denominator)
    B = {}
    for (s, i, a), v in cell.items():
        B[(s, i)] = min(B.get((s, i), 1e18), min(v))
    print(f"\n{'='*92}\nABLASYON — {track}   Delta = RPD(kol) - RPD(full)   (+ = full daha iyi)\n{'='*92}")
    print(f"{'kol':>16} {'dRPD%':>8} {'SE':>6} {'2SE':>6} {'w/t/l':>9}  karar")
    full = {k[:2]: stats.mean(v) for k, v in cell.items() if k[2] == "full"}
    for a in arms:
        if a == "full":
            continue
        d = []
        for (s, i) in full:
            if (s, i, a) not in cell:
                continue
            b = B[(s, i)]
            d.append(100 * (stats.mean(cell[(s, i, a)]) - full[(s, i)]) / b)
        if len(d) < 2:
            continue
        se = stats.stdev(d) / len(d) ** 0.5
        w = sum(1 for x in d if x < -1e-9); l = sum(1 for x in d if x > 1e-9)
        m = stats.mean(d)
        # CAUTION: the same sign means DIFFERENT things in the two panels.
        #  top panel (no_X):      +Delta = removal HURT     -> the component carries weight
        #  bottom panel (plus_X): +Delta = adding back HURT -> the drop decision is confirmed
        if a.startswith("plus_"):
            verdict = ("geri ekleme ZARARLI (atma dogrulandi)" if m > 2 * se else
                       "!! GERI EKLEME IYILESTIRIYOR -> atma karari yanlis" if m < -2 * se else
                       "gurultude (atma dogrulandi)")
        else:
            verdict = ("YUK TASIYOR" if m > 2 * se else
                       "!! CIKARMAK IYILESTIRIYOR -> bilesen zararli" if m < -2 * se else
                       "gurultude (yuk tasimiyor)")
        print(f"{a:>16} {m:+8.3f} {se:6.3f} {2*se:6.3f} {w:>3}/{len(d)-w-l}/{l:<3}  {verdict}")
    print(f"\n--- olcek kirilimi (dRPD%) ---\n{'kol':>16}" + "".join(f"{s:>10}" for s in sizes))
    for a in arms:
        if a == "full":
            continue
        row = ""
        for s in sizes:
            d = [100 * (stats.mean(cell[(s, i, a)]) - full[(s, i)]) / B[(s, i)]
                 for (ss, i) in full if ss == s and (s, i, a) in cell]
            row += f"{stats.mean(d):+10.2f}" if d else f"{'--':>10}"
        print(f"{a:>16}" + row)
    coll = [r for r in R if r.get("collapsed") == "True"]
    if coll:
        by_arm = {}
        for r in coll:
            by_arm.setdefault(r["arm"], set()).add(r["size"])
        print("\n--- ⚠️ COKEN KOSULAR (master incumbent vermedi -> sonuc = greedy tohum) ---")
        print("    Bu satirlar 'kotu atama onerdi' DEGIL 'hicbir sey oneremedi' demektir;")
        print("    Delta buyuk cikar ama sebebi kalite degil YAPISAL COKUS.")
        for a, ss in sorted(by_arm.items()):
            print(f"  {a:>16}: {len(coll)} kosu, boyutlar = {sorted(ss, key=lambda s: int(s.split('_')[0]))}")
    fired = [r for r in R if r["deg_guard_fired"] == "True"]
    print(f"\n--- deg guard: {len(fired)}/{len(R)} kosuda tetiklendi ---")
    by = {}
    for r in fired:
        by.setdefault(r["size"], []).append(int(r["deg_off_iter"]) if r["deg_off_iter"] else 0)
    for s in sizes:
        v = by.get(s, [])
        print(f"  {s:>8}: {len(v):3d} kosu" + (f"  ort iter={stats.mean(v):.1f}" if v else ""))
    # FAILURE RULE trail (protocol §9): exclusions are listed EXPLICITLY; no silent drops.
    xp = CSV_PATH + ".dislanan.csv"
    if os.path.exists(xp):
        X = [r for r in csv.DictReader(open(xp)) if r["track"] == track]
        if X:
            print(f"\n--- ⚠️ DISLANAN KOSULAR ({len(X)}) — iki denemede de basarisiz ---")
            for r in X:
                print(f"  {r['size']:>8} i{r['inst']} r{r['rep']} {r['arm']:>15}  "
                      f"{r['neden']}  ({r['zaman']})")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "equiv"
    if cmd == "worker":
        worker(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6]),
               want_trace=(len(sys.argv) > 7 and sys.argv[7] == "1"))
    elif cmd == "faz0worker":
        faz0worker(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]))
    elif cmd == "faz0":
        cmd_faz0()
    elif cmd == "faz0_report":
        cmd_faz0_report()
    elif cmd == "lockcheck":
        cmd_lockcheck()
    elif cmd == "equiv":
        if cmd_lockcheck():        # equiv is unreadable on a broken baseline -> audit first
            cmd_equiv()
    elif cmd == "levers":
        cmd_levers()
    elif cmd == "probecuts":
        cmd_probecuts()
    elif cmd == "cutbind":
        cmd_cutbind()
    elif cmd == "regress":
        cmd_regress()
    elif cmd == "run":
        cmd_run()
    elif cmd == "report":
        cmd_report()
    elif cmd == "rebase":
        cmd_rebase()
    elif cmd == "screen":
        cmd_screen()
    elif cmd == "screen_report":
        cmd_screen_report()
    elif cmd == "screen2":
        cmd_screen2()
    elif cmd == "screen2_report":
        cmd_screen2_report()
    elif cmd == "screen3":
        cmd_screen3()
    elif cmd == "screen3_report":
        cmd_screen3_report()
    elif cmd == "screen4":
        cmd_screen4()
    elif cmd == "screen4_report":
        cmd_screen4_report()
    elif cmd == "screen5":
        cmd_screen5()
    elif cmd == "screen5_report":
        cmd_screen5_report()
    elif cmd == "screen6":
        cmd_screen6()
    elif cmd == "screen6_report":
        cmd_screen6_report()
    elif cmd == "rebase_report":
        cmd_rebase_report()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
