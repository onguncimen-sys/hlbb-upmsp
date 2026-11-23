# -*- coding: utf-8 -*-
"""PARAMETER SENSITIVITY — paper §3.5.

QUESTION: is each of the SIX numbers declared in the paper defensible?
  §3.5 (main.tex:779-782): k=3 (kmach), K=5 (arc_k), master_tl=3s, spp_tl=20s,
  pool of 20 solutions (pool_k), recombination cap of 250 assignments (spp_cap).
  The same paragraph also carries a claim with NO supporting data so far:
     "the makespan is nearly flat across reasonable (K, master_tl) values"
  This run is the data for that sentence.

⚠️ THIS IS NOT A "FIND THE BEST" RUN; IT IS A SENSITIVITY MEASUREMENT. The expected outcome
is a FLAT landscape (past tuning attempts moved within ~0.2-0.5%). If flat, the claim is
measured and the configuration does NOT change; if not flat, we have found a real
improvement and we lock it in. Both outcomes enter the paper -- hence the design is
"single change + threshold", not "pick the winner".

WHY BEFORE THE ABLATION: every number the ablation produces is a difference RELATIVE TO THE
PRODUCTION CONFIGURATION. If the configuration changes here, the entire 936-run ablation
table becomes invalid (~56 h). The converse does not hold: this run does not look at what
the components do and does not wait for the ablation.

⭐ CALLS THE PRODUCTION CODE DIRECTLY (`hlbb_hm.run_integrated_sr`). There is no COPY as in
the ablation harness -> the fidelity question never arises. The base is not hand-written
either: it is derived from the production signature, and each configuration deviates from
it by a SINGLE key.

DATA — DISJOINT TRAINING SET. Track B (`new_dataset_niche_v2`) is the reported test set and
the benchmark uses ALL FIVE of its instances (results/niche_bench_v3.csv, rep 1..5).
Calibrating there would mean "tuned and tested on the same instances". We therefore
generate new instances from the SAME generator, with the SAME distribution (tau=99, e50,
ron) and DIFFERENT seeds (101+): same distribution -> the choice transfers; disjoint
instances -> the objection is closed.

ARMS (15) — each a SINGLE change from production:
  prod                       reference (production signature)
  kmach2/4/5                 machine-candidate count (the number the paper calls "the key
                             to scaling"; so far measured only on/off, never calibrated)
  mtl2/5/8                   master_tl
  k3/8/10                    arc_k
  cap160/400                 spp_cap  (measured: 160 was as good as 250 in LESS THAN HALF
                             the time -> a genuine "less is more" candidate)
  pool10/40                  pool_k
  spptl10                    spp_tl  (ONE level, deliberately: >=~12 is CLIPPED, see below)

⚠️ WHY spp_tl HAS ONE LEVEL: spp_recombine.py:167 `tl = max(1, min(tl, deadline - now))`,
and routing is cut at the `deadline - _MIP_PAY` (=12s) threshold -> the MIP usually keeps
~12 s. So spp_tl=20 and 30 would likely give IDENTICAL runs; the binding number is
_MIP_PAY. Turning 20 and 30 into arms would be waste, not measurement. Instead the
EFFECTIVE tl is logged (tl_req/tl_eff columns): if tl_eff < tl_req, the "spp_tl = 20 s"
statement in paper §3.5 is to be corrected and _MIP_PAY gridded in a separate, SMALL run.
Measure first, grid later.

Usage:
  python3 sensitivity_run.py gen                  # generate the disjoint training set (~1 min, once)
  python3 sensitivity_run.py plan                 # how many runs, how long (no Gurobi)
  python3 sensitivity_run.py run [reps]           # the main run (resumable)
  python3 sensitivity_run.py report
"""
import csv
import glob
import inspect
import json
import os
import statistics as stats
import subprocess
import sys
import time

import feas_hook                      # SHARED feasibility checker
from readproblem import readproblem
from hlbb_hm import run_integrated_sr

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(_HERE, "new_dataset_sens")
CSV_PATH = os.path.join(_HERE, "results", "sensitivity.csv")

# --- SUITE selection ----------------------------------------------------------------
# With `--suite=arc`, the arc-ranking experiment writes to a SEPARATE CSV and runs its OWN
# `prod` base. WHY SEPARATE: after the `arc_candidates` cache was added, a master round got
# a few tens of milliseconds cheaper (~54 ms/call at 800x30). The 360 recorded rows ran
# without the cache; measuring new arms against those rows would hand the new arms a small
# TIME advantage. A base measured in the same run = the question never arises.
SUITE = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--suite=")), None)
sys.argv = [a for a in sys.argv if not a.startswith("--suite=")]   # keep positional parsing intact
if SUITE == "arc":
    CSV_PATH = os.path.join(_HERE, "results", "sensitivity_arc.csv")
if SUITE == "supply":
    CSV_PATH = os.path.join(_HERE, "results", "sensitivity_supply.csv")
if SUITE == "v6":
    # v6 re-run: the old sensitivity.csv was taken with the v4-era algorithm
    # (the base guard would reject it anyway) -> SEPARATE CSV + its own base.
    CSV_PATH = os.path.join(_HERE, "results", "sensitivity_v6.csv")
COLS = ["size", "inst", "cfg", "rep", "makespan", "tbest", "iters", "wall",
        "total_s", "tl_req", "tl_eff", "feas",
        # COLUMN SUPPLY (hlbb_hm.SUPPLY): the loop's product is not an answer but the
        # column supply offered to the terminal SPP. `pool_distinct` measures diversity --
        # a large pool with a small distinct count means the loop repeats itself.
        # `pre_spp`/`post_spp` separates which layer the gain comes from. OLD CSVs LACK
        # these fields: old rows come back empty; comparison requires re-running the arm.
        "pool_n", "pool_distinct", "harvest", "pre_spp", "post_spp", "spp_used",
        # did the SPP MIP PROVE optimality (spp_recombine.LAST): 2=OPTIMAL, 9=TIME_LIMIT
        "mip_st", "mip_gap",
        # RESERVE DIAGNOSIS: `reserve` is what the formula set aside, spp_* what was SPENT.
        # Error margin = reserve - (spp_route_s + spp_build_s + spp_mip_s). `spp_n_routed`
        # compares the formula's assumed 250 with what was actually routed.
        "route_s", "loop_s", "reserve",
        "spp_route_s", "spp_build_s", "spp_mip_s", "spp_n_uniq", "spp_n_routed", "spp_n_cols",
        # Which audit ran: "sirali" (the LKH tour was read back and checked in sequence) /
        # "atama" (assignment level only) / "yok" (none). feas=1 alone does not prove a
        # sequence-level audit.
        "denetim_turu"]
SUPPLY_KEYS = COLS[12:-1]          # supply fields; SAME order in the RESULT line and the CSV

BUDGET = 200
SEED_OFFSET = 100                 # training seeds 101..103; the test set (Track B) uses 1..5
SIZES = [(50, 10), (100, 15), (400, 20), (800, 30)]
# 50_10 SMALL END: the paper's configuration section says "One setting therefore suffices
# for both problem classes", but all our parameter evidence is from medium/large instances.
# There is also a concrete hypothesis: kmach=3 was chosen to keep the master solvable on
# LARGE instances; at small sizes the master is cheap anyway and kmach=4/5 might give
# better assignments for free. That would weaken the "one setting suffices" claim ->
# something to measure.
# ⚠️ DILUTION RISK: at small sizes HLBB is already near-optimal; most arms will likely show
# ~0 difference there and pull the OVERALL mean down. The report therefore also prints the
# per-size breakdown; if the overall row is diluted, read the decision from the breakdown.
# 100_15 / 400_20 / 800_30: deg-guard fires never / once / on every run (regime diversity).
INSTS = ["1", "2", "3"]
REPS = 2                          # HLBB varies ~1.6% run-to-run -> a single run is not enough

# Keys managed by the harness: they are NOT configuration axes.
_HARNESS_OWNED = {"total_time_limit", "seed", "max_iter", "verbose", "return_solution"}


def _prod_base():
    """Base = the production signature. NEVER HAND-WRITTEN -- same principle as the LOCK in
    ablation_run: a hand-synced second list drifts sooner or later (it did so for DIG)."""
    P = inspect.signature(run_integrated_sr).parameters
    return {k: v.default for k, v in P.items()
            if v.default is not inspect._empty and k not in _HARNESS_OWNED}


BASE = _prod_base()

# Each arm deviates a SINGLE key. The value cannot equal production's (checked below).
CONFIGS = {
    "prod":    {},
    "kmach2":  {"kmach": 2},
    "kmach4":  {"kmach": 4},
    "kmach5":  {"kmach": 5},
    "mtl2":    {"master_tl": 2},
    "mtl5":    {"master_tl": 5},
    "mtl8":    {"master_tl": 8},
    "k3":      {"arc_k": 3},
    "k8":      {"arc_k": 8},
    "k10":     {"arc_k": 10},
    "cap160":  {"spp_cap": 160},
    "cap400":  {"spp_cap": 400},
    "pool10":  {"pool_k": 10},
    "pool40":  {"pool_k": 40},
    "spptl10": {"spp_tl": 10},
    # MACHINE-SIDE (3J2M) sensitivity arm: production uses mach_side=2 (accepted via the
    # gate experiment); a single change turns it off -> measures the choice's marginal
    # contribution on the training data. This is NOT a re-opening (protocol: sensitivity
    # does not change v6); it is a robustness record.
    "mach0":   {"mach_side": 0},
    # T1: the ORDERING of the arc candidate list. Production sorts by raw
    # setup; "rc" sorts by reduced cost. The candidate COUNT (K=5) stays the same -> the
    # model does not grow, no 800x30 collapse risk. Helsgaun 2000 (LKH): with the right
    # measure 5 candidates suffice, with raw cost 20+ are needed.
    "arcrc":   {"arc_rank": "rc"},
    "arcap":   {"arc_rank": "ap"},     # T1b: same idea, with OPTIMAL dual potentials
    # D1: LKH's OWN alpha-nearness set. rc/ap rest on the assignment relaxation and are
    # SUBTOUR-BLIND; alpha rests on the 1-tree, i.e. a CONNECTED relaxation (Helsgaun
    # p.116). A probe was INCONCLUSIVE: alpha-rc coverage +0.83 ± 0.88 (2SE, n=6).
    # The arm is included not because of the probe's positive sign but because the decision
    # is cheap: alpha costs 2 s at 800x30 = 1% of the budget, one-off (Ir fixed, use_dig=False).
    "arcalpha": {"arc_rank": "alpha"},
    # MECHANISM TEST. Measured: at 800x30 the raw-cost K=5 list holds no valid ASSIGNMENT on
    # 46% of the machines -> the master cannot place all jobs on such a machine
    # (`sum_i xd[i,l] <= 1`). `rc` repairs this as a side effect and gains -1.14% (400x20).
    # CLAIM: the gain belongs to the REPAIR, not the measure.
    # `costfix` tests the claim directly: the ordering STAYS the production raw cost,
    # only the matching is repaired (K fixed, model does not grow, ~1-2% of lists change).
    #   close to arcrc -> the claim is CONFIRMED (mechanism = repair)
    #   close to prod  -> the claim is WRONG (the ordering does more than feasibility)
    "costfix": {"arc_rank": "costfix"},
    # The thesis's RECIPE: if diversity pays, filling the pool SYSTEMATICALLY should help.
    # Gurobi PoolSearchMode 1 = keep solutions encountered along the way (production),
    #                        2 = systematically search for the n BEST solutions (expensive).
    # ⚠️ RISK: the master already cannot finish its 3 s cap; mode 2 may lower the iteration
    # count. The instrumentation will show it (pool_n/pool_distinct/iters read together).
    "poolmode2": {"pool_mode": 2},
}

if SUITE == "arc":                     # arc suite: only the base + the ordering arms
    CONFIGS = {k: v for k, v in CONFIGS.items()
               if k in ("prod", "arcrc", "arcap", "arcalpha")}

# SUPPLY SUITE — testing the "column supply" thesis.
# THESIS: the loop's product is not an answer but the COLUMN SUPPLY offered to the terminal
# SPP; what wins is DIVERSITY, not the master's BOUND TIGHTNESS. (In ~75% of runs the final
# answer comes from the SPP; the pool package won; every bound-tightening intervention --
# opt-cut, local branching, bias calibration -- came out neutral/negative.)
#
# PREDICTION (written BEFORE the run, so it cannot be invented afterwards):
#   K=10's -4.07% at 400x20 should come with a `pool_distinct` INCREASE, NOT with a
#   `pre_spp` improvement. Likewise arcrc's gain (it opens closed machines -> more
#   proposable assignments) should come through the distinct channel.
#   If the opposite holds -- gain in pre_spp, distinct flat -- the THESIS FALLS.
# Second prediction: at 800x30 the distinct/pool_n ratio should be LOW compared to small
# scale (the master repeats itself; the production-record trace of the 0.60->0.06 novelty
# probe).
#
# SEPARATE CSV: sensitivity.csv already HAS prod/k8/k10 rows but NO supply measurement;
# running into the same file would make `_jobs` skip them as "already there". The base is
# also re-measured in this run -> the instrumented/uninstrumented comparison question never
# arises.
#
# THE `poolmode2` ARM WAS DROPPED (smoke test, 400x20, 45 s): it produced the largest pool
# and the WORST result -- mk 451 vs prod 432, with pre_spp=451, i.e. the loss sits directly
# in the master's own solution. The reason is clear: PoolSearchMode=2 searches the n best
# SYSTEMATICALLY while the master already cannot finish its 3 s cap. It shows the limit of
# the thesis's recipe (diversity helps only while master quality is intact), but learning
# this does not require 24 runs (1.3 h). The arm STAYS in CONFIGS and can be invoked
# outside `--suite=`.
if SUITE == "supply":
    CONFIGS = {k: v for k, v in CONFIGS.items()
               if k in ("prod", "k8", "k10", "arcrc", "costfix")}
if SUITE == "v6":
    # only the configuration axes + machine-side. The arc-ranking family is a CLOSED ARM
    # (arcrc; eliminated by measurement) -> not run; costfix belongs to the supply suite.
    CONFIGS = {k: v for k, v in CONFIGS.items() if k in (
        "prod", "kmach2", "kmach4", "kmach5", "mtl2", "mtl5", "mtl8",
        "k3", "k8", "k10", "cap160", "cap400", "pool10", "pool40", "spptl10", "mach0")}
# `costfix` was added to the SAME CSV later: the prod/arcrc rows are already here, produced
# under the SAME conditions (LKH-residue cleanup active) -> only 24 new runs needed, the
# base is not re-measured. `rcfix` is NOT RUN AS AN ARM: on 11 of 12 instances it came out
# IDENTICAL to `rc` (only 2 machines repaired on 800_30 i2), i.e. it would re-run arcrc.


def _check_configs():
    """Does the arm ACTUALLY change something? (The 'nothing to switch off' lesson from
    ablation_run: if a production default drifts, an arm can silently become meaningless.)"""
    bad = []
    for name, kw in CONFIGS.items():
        for k, v in kw.items():
            if k not in BASE:
                bad.append(f"{name}: `{k}` uretim imzasinda YOK")
            elif BASE[k] == v:
                bad.append(f"{name}: `{k}` zaten {v} -> degistirecek bir sey YOK")
        if len(kw) > 1:
            bad.append(f"{name}: TEK degisiklik olmali, {len(kw)} var")
    return bad


def _dirname(n, m):
    return os.path.join(DATA_ROOT, f"{n}_{m}_1-99_e50_ron")


def _load(size, inst):
    n, m = size.split("_")
    jf = os.path.join(_dirname(int(n), int(m)), f"instance_{inst}.json")
    if not os.path.exists(jf):
        raise SystemExit(f"EKSIK: {jf}\nOnce: python3 sensitivity_run.py gen")
    return readproblem(jf, consider_compatibility=True, consider_workload=True)


# =============================================================================== gen
def cmd_gen():
    """Generate the disjoint training set. SAME distribution as Track B, DIFFERENT seeds."""
    from niche_generator import batch
    batch(out_root=DATA_ROOT, reps=len(INSTS), sizes=SIZES, taus=["1-99"],
          eligs=["e50"], rhos=["ron"], seed_offset=SEED_OFFSET)
    man = json.load(open(os.path.join(DATA_ROOT, "manifest.json")))
    print(f"\nseed'ler: {sorted({x['seed'] for x in man})}   (Track B 1..5 kullanir -> AYRIK)")
    print(f"boyutlar: {sorted({(x['nJob'], x['nMachine']) for x in man})}")


# =============================================================================== worker
def worker(size, inst, cfg, budget):
    d = _load(size, inst)
    nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
    kw = dict(CONFIGS[cfg])
    t0 = time.time()
    best, best_time, iters, assign = run_integrated_sr(
        nJob, nM, c1, c2, rt, pt, st, I_l, L_i,
        total_time_limit=budget, seed=0, return_solution=True, verbose=False, **kw)
    total_s = time.time() - t0
    import spp_recombine as SR                      # effective SPP time-limit measurement
    tl_req, tl_eff = SR.LAST.get("tl_req"), SR.LAST.get("tl_eff")
    # SEQUENCE AUDIT: read back the LKH tour and audit the ordered solution (same rigor as rivals)
    ordered = None
    try:
        from tour_capture import sequence_solution
        if assign:
            ordered = sequence_solution(assign, pt, st)
    except Exception as e:
        print(f"    [tour] sira cikarilamadi: {e}", flush=True)
    ok = feas_hook.check("sensitivity", cfg, f"sens/{size}/i{inst}", 0,
                         ordered or assign, d, float(best), ordered=ordered is not None)
    dt = "sirali" if ordered else ("atama" if assign else "yok")
    import hlbb_hm as HM                             # column supply measurement
    sup = [HM.SUPPLY.get(k) for k in SUPPLY_KEYS]
    print("RESULT " + "|".join(str(x) for x in
                               [best, best_time, iters, round(total_s, 1),
                                tl_req, tl_eff, {True: 1, False: 0, None: -1}[ok]] + sup + [dt]))


def _spawn(size, inst, cfg, budget):
    cmd = [sys.executable, os.path.abspath(__file__), "worker", size, inst, cfg, str(budget)]
    if SUITE:
        cmd.append(f"--suite={SUITE}")      # the worker must see the same arm set
    try:
        p = subprocess.run(cmd, cwd=_HERE, capture_output=True, text=True, timeout=budget + 900)
    except subprocess.TimeoutExpired:
        return None
    for line in p.stdout.splitlines():
        if line.startswith("RESULT "):
            f = line[7:].split("|")
            g = lambda s: None if s in ("None", "") else float(s)
            out = dict(best=float(f[0]), tbest=float(f[1]), iters=int(f[2]),
                       total_s=float(f[3]), tl_req=g(f[4]), tl_eff=g(f[5]), feas=int(f[6]))
            for q, k in enumerate(SUPPLY_KEYS):      # column supply (None if missing)
                out[k] = g(f[7 + q]) if len(f) > 7 + q else None
            q = 7 + len(SUPPLY_KEYS)
            out["denetim_turu"] = f[q] if len(f) > q else ""
            return out
    return None


def _clean_lkh_scratch():
    """Empty the LKH scratch directory. Called BEFORE EVERY RUN, in the main process (no
    worker alive).

    ⛔ WHY MANDATORY — MEASURED BIAS: LKH's .atsp/.par/.tour files accumulate over a run
    (95 files, 6.1 MB after a single 800x30 run). `getCost` calls `glob.glob` on every
    routing call, and glob is O(N) in directory size:
        0 files 0.31 ms | 1000 -> 0.77 | 5000 -> 2.38 | 9000 -> 3.55 ms
    With ~1200 routing calls/run this makes 0.4 s -> 4.3 s, i.e. ~2% of the 200 s budget
    (~1 iteration). Suite arms run in a FIXED order per cell (prod, k8, k10, arcrc) -> with
    a monotonically growing directory, the LAST arm always runs in the slowest environment.
    The arm differences we measure are on the order of 0.5-1%, so this bias is LARGER THAN
    THE SIGNAL WE SEEK.

    ⚠️ If ANOTHER suite runs at the same time, this also deletes its live files. In this
    repo runs are sequential and started by hand; remove this call if you parallelize."""
    n = 0
    for pat in ("*.atsp", "*.par", "*.tour", "*.cand"):
        for f in glob.glob(os.path.join(_HERE, "LKH-3.0.7", "ATSP", pat)):
            try:
                os.remove(f); n += 1
            except OSError:
                pass
    return n


def _migrate_csv():
    """Migrate a CSV written BEFORE the column-supply fields were added to the new header.

    Old rows have 12 columns; new rows 18. Appending to the same file would break the
    alignment. Migration: refresh the header, pad old rows with EMPTY fields. Old rows
    have NO supply measurement and never will -- comparing that arm requires a re-run.
    The files are tracked in git, so the migration is reversible."""
    if not os.path.exists(CSV_PATH):
        return
    rows = list(csv.reader(open(CSV_PATH, newline="")))
    if not rows or rows[0] == COLS:
        return
    if rows[0] != COLS[:len(rows[0])]:
        raise SystemExit(f"\n⛔ CSV basligi taninmadi: {rows[0]}\n"
                         f"Beklenen (eski) : {COLS[:len(rows[0])]}\n"
                         f"Elle bak: {os.path.relpath(CSV_PATH)}\n")
    pad = [""] * (len(COLS) - len(rows[0]))
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for r in rows[1:]:
            w.writerow(r + pad)
    print(f"[goc] {os.path.relpath(CSV_PATH)}: {len(rows)-1} eski satir "
          f"{len(pad)} bos alanla genisletildi (arz olcumu YOK, yeniden kosum gerektirir)")


# =============================================================================== run
def _base_guard():
    """STALE-ROW GUARD (same rationale as ablation_run._lock_guard): since the base is
    DERIVED from the production signature, a change to `hlbb_hm.py` shifts it SILENTLY and
    a half-finished CSV would mix old- and new-base rows."""
    sig_path = os.path.splitext(CSV_PATH)[0] + ".base.json"
    cur = {k: repr(v) for k, v in sorted(BASE.items())}
    if os.path.exists(sig_path):
        old = json.load(open(sig_path))
        if old != cur:
            diff = [f"{k}: {old.get(k, '(yok)')} -> {cur.get(k, '(yok)')}"
                    for k in sorted(set(old) | set(cur)) if old.get(k) != cur.get(k)]
            raise SystemExit("\n⛔ TABAN DEGISMIS — CSV'deki satirlar baska konfigurasyonda "
                             "kosuldu:\n  " + "\n  ".join(diff) +
                             f"\nYeni CSV ac ya da {os.path.relpath(CSV_PATH)} + "
                             f"{os.path.relpath(sig_path)} sil.\n")
    else:
        os.makedirs(os.path.dirname(sig_path), exist_ok=True)
        json.dump(cur, open(sig_path, "w"), indent=1)


def _jobs(reps):
    got = set()
    if os.path.exists(CSV_PATH):
        for r in csv.DictReader(open(CSV_PATH)):
            got.add((r["size"], r["inst"], r["cfg"], r["rep"]))
    sizes = [f"{n}_{m}" for n, m in SIZES]
    return [(s, i, c, r) for s in sizes for i in INSTS for c in CONFIGS
            for r in range(1, reps + 1) if (s, i, c, str(r)) not in got], len(sizes)


def cmd_plan():
    bad = _check_configs()
    print(f"\n{'kol':>9} {'degisen':>12} {'uretim':>8} {'deneme':>8}")
    print("-" * 42)
    for name, kw in CONFIGS.items():
        if not kw:
            print(f"{'prod':>9} {'-':>12} {'-':>8} {'referans':>8}"); continue
        k, v = next(iter(kw.items()))
        print(f"{name:>9} {k:>12} {str(BASE.get(k)):>8} {str(v):>8}")
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else REPS
    jobs, ns = _jobs(reps)
    tot = len(CONFIGS) * ns * len(INSTS) * reps
    print(f"\n{len(CONFIGS)} kol x {ns} boyut x {len(INSTS)} inst x {reps} tekrar = {tot} kosu")
    print(f"butce {BUDGET}s + ~15s surec/okuma -> kabaca {tot * (BUDGET + 15) / 3600:.1f} saat")
    print(f"kalan: {len(jobs)} kosu ({tot - len(jobs)} zaten var)")
    print("\n" + ("== KOLLAR TUTARLI ==" if not bad else "⛔ KOL BOZUK:\n  " + "\n  ".join(bad)))
    return not bad


def cmd_run():
    if not cmd_plan():
        return
    _base_guard()
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else REPS
    jobs, _ = _jobs(reps)
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    # Run record: code version + budget + seed policy into a side file.
    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True, cwd=_HERE).stdout.strip()
    with open(os.path.splitext(CSV_PATH)[0] + ".manifest.txt", "a") as mf:
        mf.write(f"{time.strftime('%F %T')} suite={SUITE} git={git} budget={BUDGET}s "
                 f"reps={reps} tohum=sabit0(uretim-varsayilani; tekrarlar ayni tohum "
                 f"altindaki kosudan-kosuya oynakligi olcer) veri={os.path.basename(DATA_ROOT)} "
                 f"bekleyen={len(jobs)}\n")
    _migrate_csv()
    new = not os.path.exists(CSV_PATH)
    fh = open(CSV_PATH, "a", newline="")
    w = csv.writer(fh)
    if new:
        w.writerow(COLS)
    t0 = time.time()
    for k, (s, i, c, r) in enumerate(jobs, 1):
        _clean_lkh_scratch()            # every run starts in the SAME environment (see note)
        res = _spawn(s, i, c, BUDGET)
        # Failure rule (pre-registered): retry once; if it fails again, EXCLUDE
        # and record it — do not allow "retry until it succeeds" selection.
        if res is None:
            print(f"[{k}/{len(jobs)}] {s} i{i} r{r} {c:>8}  HATA, tekrar deneniyor", flush=True)
            _clean_lkh_scratch()
            res = _spawn(s, i, c, BUDGET)
        if res is None:
            print(f"[{k}/{len(jobs)}] {s} i{i} r{r} {c:>8}  *** IKINCI HATA -> DISLANDI ***",
                  flush=True)
            w.writerow([s, i, c, r, "HATA"] + [""] * (len(COLS) - 5)); fh.flush()
            continue
        row = ([s, i, c, r, res["best"], round(res["tbest"], 1), res["iters"],
                round(time.time() - t0, 1), res["total_s"],
                res["tl_req"], res["tl_eff"], res["feas"]]
               + [res.get(k) for k in SUPPLY_KEYS] + [res.get("denetim_turu", "")])
        assert len(row) == len(COLS), f"CSV hizasi bozuk: {len(row)} != {len(COLS)}"
        w.writerow(row); fh.flush()
        flag = "" if res["feas"] == 1 else ("  *** IHLAL ***" if res["feas"] == 0
                                            else "  (denetlenemedi)")
        el = time.time() - t0
        print(f"[{k}/{len(jobs)}] {s:>7} i{i} r{r} {c:>8}  mk={res['best']:7.1f} "
              f"iter={res['iters']:3d} tl={res['tl_eff']}/{res['tl_req']} "
              f"tot={res['total_s']:.0f}s{flag}"
              f"  [{el/3600:.1f}sa gecti, ~{el/k*(len(jobs)-k)/3600:.1f}sa kaldi]", flush=True)
    fh.close()
    print("kosu bitti", flush=True)


# =============================================================================== report
def cmd_report():
    if not os.path.exists(CSV_PATH):
        print("sonuc yok"); return
    R_all = list(csv.DictReader(open(CSV_PATH)))
    # AUDIT GATE: only feas=1 rows enter the quality computation. An invalid low makespan
    # would corrupt both the arm and the B denominator. "HATA" = an excluded run.
    hata = [r for r in R_all if r["makespan"] == "HATA"]
    R = [r for r in R_all if r["makespan"] != "HATA"]
    kalite = [r for r in R if r["feas"] == "1"]
    disi = [r for r in R if r["feas"] != "1"]
    cell = {}
    for r in kalite:
        cell.setdefault((r["size"], r["inst"], r["cfg"]), []).append(float(r["makespan"]))
    sizes = sorted({k[0] for k in cell}, key=lambda s: int(s.split("_")[0]))
    prod = {k[:2]: stats.mean(v) for k, v in cell.items() if k[2] == "prod"}
    B = {}
    for (s, i, c), v in cell.items():
        B[(s, i)] = min(B.get((s, i), 1e18), min(v))
    print(f"\n{'='*88}\nPARAMETRE DUYARLILIGI   Delta = RPD(kol) - RPD(prod)   "
          f"(+ = uretim daha iyi)\n{'='*88}")
    print(f"{'kol':>9} {'n':>3} {'dRPD%':>8} {'SE':>6} {'2SE':>6} {'w/t/l':>9}  karar")
    for c in CONFIGS:
        if c == "prod":
            continue
        d = [100 * (stats.mean(cell[(s, i, c)]) - prod[(s, i)]) / B[(s, i)]
             for (s, i) in prod if (s, i, c) in cell]
        if len(d) < 2:
            continue
        m = stats.mean(d); se = stats.stdev(d) / len(d) ** 0.5
        w = sum(1 for x in d if x < -1e-9); l = sum(1 for x in d if x > 1e-9)
        # |Delta| <= 2SE only means "no difference SHOWN" — it is NOT proof of flatness
        # (little data / high noise yields the same outcome). If a difference favors the
        # arm, v6 does NOT change (pre-registered): reported as a post-freeze finding.
        verdict = ("uretim lehine fark" if m > 2 * se else
                   "kol lehine fark — dondurma sonrasi bulgu, v6 DEGISMEZ" if m < -2 * se else
                   "fark gosterilemedi")
        print(f"{c:>9} {len(d):>3} {m:+8.3f} {se:6.3f} {2*se:6.3f} {w:>3}/{len(d)-w-l}/{l:<3}  {verdict}")
    print(f"\n--- olcek kirilimi (dRPD%) ---\n{'kol':>9}" + "".join(f"{s:>10}" for s in sizes))
    for c in CONFIGS:
        if c == "prod":
            continue
        row = ""
        for s in sizes:
            d = [100 * (stats.mean(cell[(s, i, c)]) - prod[(s, i)]) / B[(s, i)]
                 for (ss, i) in prod if ss == s and (s, i, c) in cell]
            row += f"{stats.mean(d):+10.2f}" if d else f"{'--':>10}"
        print(f"{c:>9}" + row)
    # does spp_tl actually bind?
    print("\n--- SPP time limit: ISTENEN -> ETKIN (paper §3.5 'spp_tl = 20 s' denetimi) ---")
    for c in ("prod", "spptl10"):
        rs = [r for r in R if r["cfg"] == c and r["tl_eff"] not in ("", "None")]
        if not rs:
            continue
        req = stats.mean(float(r["tl_req"]) for r in rs)
        eff = stats.mean(float(r["tl_eff"]) for r in rs)
        clip = sum(1 for r in rs if float(r["tl_eff"]) < float(r["tl_req"]) - 0.5)
        print(f"  {c:>9}: istenen {req:5.1f}s -> etkin {eff:5.1f}s   "
              f"kirpilan kosu: {clip}/{len(rs)}")
    print("  (etkin < istenen ise §3.5'teki beyan duzeltilmeli; baglayan sayinin _MIP_PAY olup"
          " olmadigi ayri dogrulama ister)")
    # Completeness + uniqueness + audit summary
    from collections import Counter
    anahtar = Counter((r["size"], r["inst"], r["cfg"], r["rep"]) for r in R_all)
    cift = [k for k, v in anahtar.items() if v > 1]
    kol_n = Counter(r["cfg"] for r in kalite)
    beklenen = len(SIZES) * len(INSTS) * REPS
    eksikli = {c: n for c, n in kol_n.items() if n != beklenen}
    sirasiz = [r for r in kalite if r.get("denetim_turu", "") not in ("sirali", "")]
    print(f"\n--- butunluk: {len(R_all)} satir = kalite {len(kalite)} + denetim-disi {len(disi)}"
          f" + dislanmis {len(hata)} | tekrarlanan anahtar: {len(cift)} ---")
    if eksikli:
        print(f"    ⚠️ beklenen {beklenen}/kol'dan sapan kollar: {eksikli}")
    if sirasiz:
        print(f"    not: {len(sirasiz)} satirda denetim sirali degil ({Counter(r.get('denetim_turu') for r in sirasiz)})")
    bad = [r for r in R if r["feas"] == "0"]
    print(f"--- feasibility: {len(bad)} ihlal / {len(R)} kosu ---")
    if bad:
        for r in bad[:10]:
            print(f"    IHLAL: {r['size']} i{r['inst']} {r['cfg']} r{r['rep']}")
    nd = [r for r in R if r["feas"] == "-1"]
    if nd:
        print(f"    ⚠️ {len(nd)} kosu DENETLENEMEDI (kalite hesabina ALINMADI)")
    if hata:
        for r in hata:
            print(f"    DISLANDI: {r['size']} i{r['inst']} {r['cfg']} r{r['rep']}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "worker":
        worker(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]))
    elif cmd == "gen":
        cmd_gen()
    elif cmd == "plan":
        cmd_plan()
    elif cmd == "run":
        cmd_run()
    elif cmd == "report":
        cmd_report()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
