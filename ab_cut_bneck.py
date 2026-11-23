# -*- coding: utf-8 -*-
"""A/B — BOTTLENECK-SET NO-GOOD (C1): apply the no-good to the bottleneck machine only,
instead of to the WHOLE assignment.

The CURRENT (global) no-good, hlbb_hm.py:333:
    sum_l [ sum_{i in S_l}(1-y_il) + sum_{i notin S_l} y_il ] >= 1
    -> removes EXACTLY 1 point from the assignment space. The master can satisfy the cut by
       moving a single job to another machine; it does NOT guarantee a structurally
       different assignment.

THIS FILE (bneck) applies the no-good, for the bottleneck machine b = argmax(h):
    sum_{i in S_b}(1-y_ib) + sum_{i in Ir_b \\ S_b} y_ib >= 1
    -> eliminates ALL assignments that put S_b on b (a whole slice, not a single point).

RATIONALE (validity): if h_b >= best, every assignment putting S_b on b has
Cmax >= span_b(S_b) = h_b >= best -> it can NEVER improve the incumbent -> eliminating it
loses no solution.
WARNING: h_b comes from LKH (near-optimal, not exact) -> the true span can be slightly
below h_b. A theoretically tiny loss risk exists; acceptable for a primal A/B (NO LB claim).

CONSTRAINT COUNT FIXED (fair A/B): the bneck cut IMPLIES the global cut (its terms are a
subset of the global sum, all >=0). So while h_b >= best ONLY the bneck cut is added,
otherwise (new incumbent) the global cut. 1 constraint per iteration -> same master size
as the baseline. The only difference is the STRENGTH of the cut.

TARGET REGIME: the cuts are strong on SMALL sets. The weak regime of Track A is exactly that:
  50x20 = 2.5 jobs/machine (HLBB RPD 14.6 vs SA 1.6) | 100x20 = 5.0 jobs/machine (7.6 vs 1.7)
No effect expected at large n/m (250x10 = 25 jobs/machine); can serve as a control.

>>> hlbb_hm.py was NOT touched. This file carries its own copy of the master+loop; the
    "global" mode must give EXACTLY the same result as the production function ->
    `--equiv` verifies this. Run it first.

Usage:
  python3 ab_cut_bneck.py equiv                          # is the copy faithful (global == hlbb_hm)? RUN FIRST
  python3 ab_cut_bneck.py ab 50_20 1,2,3,4,5 200         # A/B
  python3 ab_cut_bneck.py ab 100_20 1,2,3,4,5 200
  python3 ab_cut_bneck.py ab 250_10 1,2,3 200            # control (no effect expected)
"""
import os
import sys
import time
from collections import Counter

from gurobipy import GRB, Model, quicksum

from methods import env
from readproblem import readproblem
from HLBB import clear_environment, _close_lkh_pool
from hlbb_hm import greedy_lpt, _route
from intensify import ils
from spp_recombine import spp_recombine

_HERE = os.path.dirname(os.path.abspath(__file__))
JSON_DIR = os.path.join(_HERE, "valladapure")
SEV = "1-99"


# ======================================================================
# master — a COPY of hlbb_hm.solve_master_sizered + the mnogoods parameter
# (with mnogoods=[] the behavior is exactly the same)
# ======================================================================
def solve_master_ab(nJob, nMachine, c1, c2, processTime, setupTime, I_l, L_i,
                    nogoods, master_tl, readyTime=None, bias=None, kmach=5, K=10,
                    hint=None, kcap=None, rank=None, use_degree=True, warm=None,
                    mnogoods=(), gcuts=(), dist_d=1):
    cap = kcap if kcap is not None else (kmach + 2)
    allowed = {}
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
        allowed[i] = base
    Ir = {l: [i for i in range(nJob) if l in allowed[i]] for l in range(nMachine)}

    mdl = Model("MIP-A-sizered-ab", env=env)
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
    for l in range(nMachine):
        for i in Ir[l]:
            cand = sorted((j for j in Ir[l] if j != i), key=lambda j: setupTime[l][j][i])[:K]
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
        succ = {l: {} for l in range(nMachine)}
        for l in range(nMachine):
            for i in Ir[l]:
                for j in arcs[l][i]:
                    succ[l].setdefault(j, []).append(i)
        for l in range(nMachine):
            for j, succs in succ[l].items():
                mdl.addConstr(quicksum(x[j, i, l] for i in succs) <= y[j, l])
    for l in range(nMachine):
        ready_term = readyTime[l] * u[l] if readyTime is not None else 0
        bias_term = bias[l] * u[l] if bias is not None else 0
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
    # --- GLOBAL no-good (dist_d=1 -> same as production; dist_d>1 in the C2 "dist" mode) ---
    # Hamming: moving one job a->b raises the sum by 2 -> dist_d = 2*(min jobs to move)
    for S_list in nogoods:
        terms = []
        for l in range(nMachine):
            sset = set(S_list[l])
            terms.append(quicksum(1 - y[i, l] for i in sset if (i, l) in y))
            terms.append(quicksum(y[i, l] for i in Ir[l] if i not in sset))
        mdl.addConstr(quicksum(terms) >= dist_d)
    # --- C1: BOTTLENECK-MACHINE no-good (Hamming >= 1 on a single machine) ---
    for (b, S_b) in mnogoods:
        sset = set(S_b)
        present = [i for i in sset if (i, b) in y]
        if not present:
            continue          # S_b not representable in this master -> cut empty, skip
        mdl.addConstr(quicksum(1 - y[i, b] for i in present) +
                      quicksum(y[i, b] for i in Ir[b] if i not in sset) >= 1)
    # --- C3: GRADED opt-cut (Hooker LBBD 3.4.3): cmax >= h_b - sum Delta_i (1 - y_ib)
    # Delta_i = p_ib + max_j s_jib + max_k s_ikb  (insertion argument: removing one job
    # lowers the span by at most this much). The naive form (cmax >= h*(1-sum(1-y))) dies
    # at a single job's deviation; as measured, this form stays binding up to 4-6 deviations.
    # NOTE: since setups do not satisfy the triangle inequality, the span is NOT monotone in
    # the job set -> this cut is HEURISTIC (no validity claim; the LB was dropped from the paper).
    for (b, S_b, h_b, delta) in gcuts:
        present = [i for i in S_b if (i, b) in y]
        if not present:
            continue
        mdl.addConstr(cmax >= h_b - quicksum(delta[i] * (1 - y[i, b]) for i in present))
    if warm is not None:
        for l in range(nMachine):
            wl = [i for i in warm[l] if (i, l) in y]
            for i in wl:
                y[i, l].Start = 1.0
            if l in u:
                u[l].Start = 1.0 if wl else 0.0
    mdl.Params.TimeLimit = master_tl
    mdl.setParam("OutputFlag", 0)
    mdl.setParam("Seed", 1)
    mdl.optimize()
    try:
        assign = [[i for i in Ir[l] if y[i, l].X > 0.5] for l in range(nMachine)]
        s_vals = [s[l].X for l in range(nMachine)]
        return assign, s_vals
    except AttributeError:
        return None, None


# ======================================================================
# loop — a COPY of hlbb_hm.run_integrated_sr + cut_mode
# cut_mode="global" -> EXACTLY the same as production
# ======================================================================
def run_ab(nJob, nMachine, c1, c2, readyTime, processTime, setupTime, I_l, L_i,
           total_time_limit=300, master_tl=3, kmach=3, arc_k=5, seed=0, max_iter=100000,
           use_spp=True, spp_tl=20, ils_tl=3, kick=3, ils_margin=0.05,
           use_bias=True, bias_alpha=0.3, use_dig=True, hint_k=3, kcap=5,
           setup_aware=False, use_degree=True, use_warm=True, use_ils=False,
           cut_mode="global", dist_jobs=3, verbose=False):
    import numpy as np
    clear_environment(); _close_lkh_pool()
    start = time.time()
    nogoods = []; mnogoods = []; gcuts = []; pool = []
    use_bneck = cut_mode in ("bneck", "bneck+graded")
    use_grad = cut_mode in ("graded", "bneck+graded")
    dist_d = 2 * dist_jobs if cut_mode == "dist" else 1
    # Delta_i coefficients for C3 (static, once per machine): p + largest in + largest out
    delta = None
    if use_grad:
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
    bias = [0.0] * nMachine if use_bias else None
    job_freq = [Counter() for _ in range(nJob)] if use_dig else None
    rank = None
    if setup_aware:
        rank = []
        for i in range(nJob):
            key = {l: processTime[l][i] + float(np.mean(setupTime[l][:, i])) for l in L_i[i]}
            rank.append(sorted(L_i[i], key=lambda l, kk=key: kk[l]))

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
    iters = 0; n_ils = 0; mfail = 0; n_bcut = 0; n_gcut = 0
    deg_on = use_degree
    while time.time() - start < total_time_limit and iters < max_iter:
        iters += 1
        clear_environment()
        hint = ([[l for l, _ in job_freq[i].most_common(hint_k)] for i in range(nJob)]
                if use_dig else None)
        assign, s_vals = solve_master_ab(nJob, nMachine, c1, c2, processTime, setupTime, I_l, L_i,
                                         nogoods, master_tl, readyTime=readyTime, bias=bias,
                                         kmach=kmach, K=arc_k, hint=hint, kcap=kcap, rank=rank,
                                         use_degree=deg_on,
                                         warm=best_assign if use_warm else None,
                                         mnogoods=mnogoods, gcuts=gcuts, dist_d=dist_d)
        if assign is None and deg_on:
            deg_on = False
            assign, s_vals = solve_master_ab(nJob, nMachine, c1, c2, processTime, setupTime, I_l,
                                             L_i, nogoods, master_tl, readyTime=readyTime, bias=bias,
                                             kmach=kmach, K=arc_k, hint=hint, kcap=kcap, rank=rank,
                                             use_degree=False,
                                             warm=best_assign if use_warm else None,
                                             mnogoods=mnogoods, gcuts=gcuts, dist_d=dist_d)
        if assign is None:
            mfail += 1
            if mfail >= 3:
                break
            continue
        h_a = _route(assign, readyTime, processTime, setupTime); mk_a = max(h_a)
        if use_bias and s_vals is not None:
            for l in range(nMachine):
                gap = h_a[l] - s_vals[l]
                bias[l] = (1 - bias_alpha) * bias[l] + bias_alpha * max(0.0, gap)
        if len(pool) < 3000:
            pool.append([list(m) for m in assign])
        # ---------------- CUT CHOICE (the ONLY difference between the arms) ----------------
        b = int(np.argmax(h_a))
        bneck_ok = use_bneck and mk_a >= best - 1e-6 and assign[b]
        if cut_mode == "none":
            pass                       # NO cuts at all: diversity comes only from bias + DIG
        elif bneck_ok:
            mnogoods.append((b, list(assign[b])))     # bneck cut IMPLIES the global one -> skip it
            n_bcut += 1
        else:
            nogoods.append([list(m) for m in assign])
        if use_grad and assign[b]:
            gcuts.append((b, list(assign[b]), float(h_a[b]), delta[b]))
            n_gcut += 1
        # -------------------------------------------------------------------------
        cand, mk_c = assign, mk_a
        if use_ils and mk_a <= best * (1 + ils_margin):
            res = ils([list(m) for m in assign], [0.0] * nMachine, readyTime, processTime, setupTime,
                      I_l, c1, c2, budget=ils_tl, kick=kick, seed=seed * 100000 + iters,
                      use_swap=True, pool_k=5, anchor=[list(m) for m in assign])
            n_ils += 1; pool.extend(res.get("pool_lkh", []))
            if res["lkh_best_mk"] < mk_c - 1e-6:
                cand = res["lkh_best_assign"]; mk_c = res["lkh_best_mk"]
        if len(pool) < 3000:
            pool.append([list(m) for m in cand])
        if use_dig:
            _tally(cand)
        if mk_c < best - 1e-6:
            best = mk_c; best_assign = [list(m) for m in cand]; best_time = time.time() - start
        if verbose:
            print(f"  [{cut_mode}] iter {iters}: master={mk_a:.0f} -> best={best:.0f}", flush=True)
    ils_best = best
    if use_spp and len(pool) >= 2:
        spp_mk, spp_assign = spp_recombine(pool, nJob, nMachine, readyTime, processTime, setupTime,
                                           tl=spp_tl)
        if spp_mk is not None and spp_mk < best - 1e-6:
            best = round(spp_mk, 1); best_time = time.time() - start; best_assign = spp_assign
    _close_lkh_pool(); clear_environment()
    return {"best": float(best), "tbest": float(best_time), "iters": iters,
            "pool": len(pool), "bcut": n_bcut, "gcut": n_gcut, "pre_spp": float(ils_best)}


# ======================================================================
def _load(size, inst, track="pure"):
    """track='pure'  -> valladapure/{n_m}/S1-99/instance_r.json   (no elig, ready=0)
       track='niche' -> new_dataset_niche/{n}_{m}_1-99_e50_ron/instance_r.json (elig 50% + ready)
    In the niche, cardinality is SLACK (same reading as certified_gap_niche)."""
    if track in ("niche", "niche_v2"):
        # niche    = new_dataset_niche      (v1, old generation with DOMINANT ready times)
        # niche_v2 = new_dataset_niche_v2   (development-period Track B set; ready as co-driver)
        root = "new_dataset_niche_v2" if track == "niche_v2" else "new_dataset_niche"
        n, m = size.split("_")
        jf = os.path.join(_HERE, root, f"{n}_{m}_1-99_e50_ron", f"instance_{inst}.json")
        return readproblem(jf, consider_compatibility=True, consider_workload=True)
    jf = os.path.join(JSON_DIR, size, f"S{SEV}", f"instance_{inst}.json")
    return readproblem(jf, consider_compatibility=False, consider_workload=False)   # PURE


def cmd_equiv():
    """Is the global mode EXACTLY identical to the production function?

    CAUTION — DETERMINISM: under production settings (master_tl=3s, wall-clock budget) HLBB
    is NOT repeatable run to run: a MIP that hits the time limit can return a different
    solution depending on machine load, and the iteration count varies too. The equality
    test is therefore run in a DETERMINISTIC REGIME:
      max_iter=6 (fixed work)  + master_tl=30 (master solved to optimality, no limit hit)
      + use_spp=False (SPP was NOT copied, it is imported from the module -> no drift risk)
    In this regime both sides do the same operations in the same order -> the makespans
    must be EXACTLY equal.
    """
    from hlbb_hm import run_integrated_sr
    print("### EQUIVALENCE (deterministik rejim: max_iter=6, master_tl=30, SPP kapali) ###", flush=True)
    DET = dict(total_time_limit=600, max_iter=6, master_tl=30, kmach=3, arc_k=5, seed=0, use_spp=False)
    ok = True
    for size, inst in [("50_20", "1"), ("100_20", "1")]:
        nJob, nMachine, c1, c2, rt, pt, st, mx, I_l, L_i, es = _load(size, inst)
        r = run_ab(nJob, nMachine, c1, c2, rt, pt, st, I_l, L_i, cut_mode="global", **DET)
        b, _, itp = run_integrated_sr(nJob, nMachine, c1, c2, rt, pt, st, I_l, L_i, **DET)
        same = abs(r["best"] - float(b)) < 1e-6 and r["iters"] == itp
        ok &= same
        print(f"  {size} i{inst}: kopya={r['best']:.1f} ({r['iters']} iter) | "
              f"uretim={float(b):.1f} ({itp} iter) -> "
              f"{'AYNI' if same else '!!! FARKLI — A/B GECERSIZ, once bunu duzelt'}", flush=True)
    print(f"\nSONUC: {'kopya sadik, A/B kosulabilir' if ok else 'KOPYA SAPMIS — A/B kosma'}", flush=True)
    return ok


def cmd_ab(size, insts, budget, reps=3):
    """A/B with `reps` REPEATS per arm.

    HLBB is NOT repeatable run to run in the production regime (see cmd_repro): master_tl
    wall-clock limit + wall-clock budget -> ~1.5-2.5% noise. With a SINGLE run per arm this
    noise exceeds the effect being sought and the A/B wrongly reports 'no difference'. So
    each arm is run `reps` times and the MEANS are compared; the noise floor (within-arm
    std) is also printed so that significance is read against the noise, not judged by eye.
    """
    import statistics as stats
    print(f"### A/B DARBOGAZ-KUME NO-GOOD | valladapure/{size}/S{SEV} | insts={insts} "
          f"| budget={budget}s | kol basina {reps} tekrar ###", flush=True)
    print(f"{'inst':>5} {'global(ort±std)':>18} {'bneck(ort±std)':>18} {'delta':>8} | "
          f"{'it_g':>5} {'it_b':>5} {'bcut':>5}", flush=True)
    diffs = []; sds = []; t0 = time.time()
    for inst in insts:
        nJob, nMachine, c1, c2, rt, pt, st, mx, I_l, L_i, es = _load(size, inst)
        vals = {}; info = {}
        for mode in ("global", "bneck"):
            rs = [run_ab(nJob, nMachine, c1, c2, rt, pt, st, I_l, L_i,
                         total_time_limit=budget, kmach=3, arc_k=5, seed=0, cut_mode=mode)
                  for _ in range(reps)]
            vals[mode] = [r["best"] for r in rs]
            info[mode] = rs[-1]
        mg, mb = stats.mean(vals["global"]), stats.mean(vals["bneck"])
        sg = stats.stdev(vals["global"]) if reps > 1 else 0.0
        sb = stats.stdev(vals["bneck"]) if reps > 1 else 0.0
        d = mb - mg                                  # negative = bneck BETTER
        diffs.append(d); sds += [sg, sb]
        print(f"{inst:>5} {mg:>11.1f}±{sg:>5.2f} {mb:>11.1f}±{sb:>5.2f} {d:>+8.2f} | "
              f"{info['global']['iters']:>5} {info['bneck']['iters']:>5} {info['bneck']['bcut']:>5}",
              flush=True)
    n = len(diffs)
    md = stats.mean(diffs)
    se = (stats.stdev(diffs) / (n ** 0.5)) if n > 1 else float("nan")
    noise = stats.mean(sds)
    print(f"\nORT DELTA = {md:+.2f}  (SE={se:.2f}, kol-ici gurultu std={noise:.2f})", flush=True)
    if n > 1 and abs(md) < 2 * se:
        print("  -> GURULTUDE: |delta| < 2*SE. Etki varsa bu tasarimin cozunurlugunun altinda; "
              "reps'i artirmadan 'fark yok' SONUCU CIKARMA.", flush=True)
    elif md < 0:
        print(f"  -> bneck KAZANDI (delta {md:+.2f}, 2*SE={2*se:.2f} esiginin otesinde)", flush=True)
    else:
        print(f"  -> bneck KAYBETTI (delta {md:+.2f}, 2*SE={2*se:.2f} esiginin otesinde)", flush=True)
    print(f"  kazandigi inst={sum(1 for d in diffs if d < -1e-6)}/{n}, "
          f"kaybettigi={sum(1 for d in diffs if d > 1e-6)}/{n} | "
          f"wall={(time.time()-t0)/60:.1f}dk", flush=True)


def cmd_repro(size, inst, budget, reps):
    """Run the PRODUCTION function N times with the SAME arguments: is it self-repeatable?

    This test has NOTHING to do with the copy — it only calls hlbb_hm.run_integrated_sr.
    Purpose: measure whether HLBB VARIES run to run because of the master_tl wall-clock
    limit + wall-clock budget. If it varies: (a) exact equality cannot be expected in equiv,
    (b) the paper's "HLBB deterministic, run once" statement must be revisited (what was
    measured was SEED variance; re-run variance under the same seed is a different thing).
    """
    from hlbb_hm import run_integrated_sr
    nJob, nMachine, c1, c2, rt, pt, st, mx, I_l, L_i, es = _load(size, inst)
    print(f"### REPRO | valladapure/{size}/S{SEV}/instance_{inst} | budget={budget}s | "
          f"{reps} tekrar, AYNI seed=0, AYNI arguman ###", flush=True)
    vals = []
    for r in range(reps):
        b, bt, it = run_integrated_sr(nJob, nMachine, c1, c2, rt, pt, st, I_l, L_i,
                                      total_time_limit=budget, kmach=3, arc_k=5, seed=0)
        vals.append(float(b))
        print(f"  tekrar {r+1}: best={float(b):.1f}  (iter={it}, t-best={float(bt):.0f}s)", flush=True)
    lo, hi = min(vals), max(vals)
    spread = (hi - lo) / lo * 100 if lo else 0.0
    print(f"\n  min={lo:.1f} max={hi:.1f} yayilim={hi-lo:.1f} ({spread:.2f}%)", flush=True)
    if hi - lo < 1e-6:
        print("  -> TEKRARLANABILIR: equiv'de tam esitlik beklenebilir; paper'in 'deterministic' "
              "ifadesi bu boyutta dogru.", flush=True)
    else:
        print("  -> TEKRARLANABILIR DEGIL: ayni seed, ayni arguman, farkli sonuc. equiv'de tam "
              "esitlik BEKLENEMEZ (kopya sadik olsa bile). Paper'da 'deterministic single run' "
              "ifadesi + tek-kosu raporlama gozden gecirilmeli.", flush=True)
    return vals


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "equiv"
    if cmd == "equiv":
        cmd_equiv(); return
    if cmd == "repro":
        cmd_repro(sys.argv[2] if len(sys.argv) > 2 else "100_20",
                  sys.argv[3] if len(sys.argv) > 3 else "1",
                  int(sys.argv[4]) if len(sys.argv) > 4 else 60,
                  int(sys.argv[5]) if len(sys.argv) > 5 else 3); return
    size = sys.argv[2] if len(sys.argv) > 2 else "50_20"
    insts = (sys.argv[3] if len(sys.argv) > 3 else "1,2,3,4,5").split(",")
    budget = int(sys.argv[4]) if len(sys.argv) > 4 else 200
    reps = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    cmd_ab(size, insts, budget, reps)


if __name__ == "__main__":
    main()
