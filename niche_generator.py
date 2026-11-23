# -*- coding: utf-8 -*-
"""
TRACK C -- OPEN, SEEDED NICHE INSTANCE GENERATOR
Problem:  R | s_ijl, M_j, r_l | C_max
  - unrelated processing times (machine-dependent)
  - sequence- AND machine-dependent setup  s_ijl
  - machine eligibility  M_j
  - machine ready times  r_l   <-- present in NO public benchmark
  - objective: makespan

PURPOSE: produce a PUBLISHABLE community benchmark that exercises the FULL niche (incl. r_l).
Used as a COMPLEMENT to Track A (Vallada, established public) and Track B (Moser, established
public); it does not replace them. The metric is always paired with a certified lower bound,
so the gap is measured OBJECTIVELY even on self-generated instances (not self-referential).

ROLIM-ALIGNMENT PRINCIPLES:
  (1) OPEN + SEEDED + documented -> full reproducibility (Rolim & Nagano's "pristine library"
      call).
  (2) Parameters INHERITED FROM THE LITERATURE, not tuned to us (provenance below).
  (3) Together with Tracks A/B (public) -> the "only on your own data" criticism is closed.

PARAMETER PROVENANCE (every value from a source; not chosen to favor HLBB):
  p_il  ~ U[1,99]                 Vallada & Ruiz (2011) -- standard UPMS processing times
  s_ijl ~ U[1,tau], s_iil=0       Vallada & Ruiz (2011) -- setup severity tau in {9,49,99,124}
                                  (matches valladapure S1-9/S1-49/S1-99/S1-124 exactly)
  eligibility density p=0.5       Moser (2022) ~50% ineligible + Ekici (2019, 1-14 of 15
                                  machines) measurements
  r_l ~ U[0, rho * (n/m) * 50]    machine-availability literature (Lee 1991; Kaabi & Harrath
                                  2014; Shafiee et al. 2025 "non-simultaneous machine start").
                                  rho = ready-time severity = fraction of the expected
                                  per-machine PROCESSING load.
                                  rho=0 -> simultaneous start (classical) = clean ablation.
  sizes n in {50..250}, m in {10..30}      Vallada & Ruiz (2011)
  cardinality: LOOSE (min=0,max=n)         the niche's cardinality relaxation

OUTPUT: HLBB JSON (readproblem schema) -- SAME format as moser_to_hlbb / valladapure.
  Processing times are defined on ALL cells (U[1,99]); eligibility is a SEPARATE mask
  (Compatibility), so a cell stays valid even if compat=False (no Moser-style -1->0 footgun).

USAGE:
  python3 niche_generator.py tek  <n> <m> <tau> <rho> <seed> <out.json> [elig_p=0.5] [elig_mode=rastgele|kumeli]
  python3 niche_generator.py batch [out_root=new_dataset_niche] [reps=5]
      -> default grid: 8 sizes (50..800) x {tau=99} x {rho=0,0.3,0.6} x reps  + manifest.json
      (change the grid via the DEFAULT_* constants in code; parameters go into the manifest)
"""
import os
import sys
import json
import random

# --- provenance-grounded constants ---
P_LOW, P_HIGH = 1, 99                                   # Vallada&Ruiz 2011: p_il ~ U[1,99]
PBAR = (P_LOW + P_HIGH) / 2.0                           # mean processing = 50 (for r_l scale)
TAU_LEVELS = {"1-9": 9, "1-49": 49, "1-99": 99, "1-124": 124}   # Vallada setup severities
ELIG_P = 0.5                                            # Moser/Ekici measurement ~50% eligible
# eligibility ABLATION axis: eoff = constraint OFF (all eligible), e50 = ~50% eligible
# (Moser/Ekici). Controlled on/off like ready -> isolates "does adding eligibility matter".
ELIG_LEVELS = {"eoff": 1.0, "e50": 0.5}                # elig_p=1.0 -> all (machine,job) ok = OFF
# ready ABLATION axis (2 levels, symmetric with elig): r0 = simultaneous (OFF), ron = ready ON.
# ron = 0.2: rho=0.6 made ready DOMINANT (at 800x30, max r_l~782 vs pure makespan~226 = 3.5x,
# drowning the makespan as a shared floor). With 0.2, at large sizes ready ~1x makespan =
# CO-DRIVER (ready and jobs jointly matter), not dominant; ~0.5x at small. r_scale=rho*(n/m)*PBAR.
RHO_LEVELS = {"r0": 0.0, "ron": 0.2, "rlo": 0.3, "rhi": 0.6}   # ron = representative ON level

# batch default grid: Vallada sizes (50-250) + LARGE end (400-800) to showcase "HLBB wins at
# scale". Large sizes are literature-based: Adan (2022) uses 800 jobs/60 machines, Moser (2022)
# up to 1000 jobs. n/m ~ 5-27 jobs/machine (Vallada regime preserved).
DEFAULT_SIZES = [(50, 10), (100, 15), (150, 15), (200, 20), (250, 20),
                 (400, 20), (640, 25), (800, 30)]
DEFAULT_TAUS = ["1-99"]        # one representative setup severity (Track A already sweeps all 4)
# 2x2 CONTROLLED FACTORIAL: elig{off,on} x ready{off,on} -> isolated marginal effect per feature.
DEFAULT_ELIGS = ["eoff", "e50"]       # eligibility on/off
DEFAULT_RHOS = ["r0", "ron"]          # ready on/off (ron=0.2; see RHO_LEVELS)


def gen_instance(n, m, tau, rho, seed, elig_p=ELIG_P, elig_mode="rastgele"):
    """(n,m,tau,rho,seed,elig_p) -> HLBB JSON dict. tau = setup upper bound, rho = ready-time
    severity fraction, elig_p = eligibility threshold (1.0 -> constraint OFF). String seeds =>
    reproducible across processes.

    CLEAN 2x2 ABLATION: the base (processing/setup/eligibility THRESHOLDS/ready PATTERN) is
    generated INDEPENDENTLY of rho AND elig_p -> for the same (n,m,tau,seed) the base stays
    identical even when both rho and elig_p change.
      - eligibility: per (machine,job) a threshold u_jl in [0,1) (n*m FIXED draws).
        Eligible <=> u_jl < elig_p. elig_p=1.0 -> all eligible (OFF); 0.5 -> ~50%. Levels are
        NESTED (e50 subset of eoff). The fallback is DETERMINISTIC (consumes no rng) ->
        changing elig_p leaves the rng state seen by ready FIXED.
      - ready: per machine a pattern u_l in [0,1); r_l = round(u_l * rho * (n/m) * 50).
        rho=0 -> all 0.
    """
    rng = random.Random(f"niche|{n}|{m}|{tau}|{seed}")   # no rho/elig_p -> base independent of both

    # processing times: EVERY (machine,job) cell U[1,99] (eligibility is a separate mask)
    processTime = {str(l): [rng.randint(P_LOW, P_HIGH) for _ in range(n)] for l in range(m)}

    # eligibility THRESHOLDS: n*m FIXED draws (elig_p-independent); filter + deterministic feasibility.
    elig_u = [[rng.random() for _ in range(m)] for _ in range(n)]
    # elig_mode="kumeli" (clustered):
    # jobs form 4 families (i mod 4), machines 2 groups (first half / second half); families
    # {0,1} -> group 0, {2,3} -> group 1. Threshold p_in inside the own group, p_out outside;
    # 0.5*p_in + 0.5*p_out = elig_p (mean density preserved). The SAME elig_u thresholds are
    # used, with NO extra rng draws -> base and ready pattern unchanged; the default
    # ("rastgele") path reproduces the old behavior exactly.
    if elig_mode == "kumeli":
        p_in = min(1.0, 1.75 * elig_p)
        p_out = max(0.0, 2.0 * elig_p - p_in)
    Compatibility = {str(l): [0] * n for l in range(m)}
    for i in range(n):
        if elig_mode == "kumeli":
            own = range(0, m // 2) if (i % 4) < 2 else range(m // 2, m)
            elig = [l for l in range(m) if elig_u[i][l] < (p_in if l in own else p_out)]
        else:
            elig = [l for l in range(m) if elig_u[i][l] < elig_p]
        if not elig:                                        # every job GUARANTEED >=1 machine
            elig = [min(range(m), key=lambda l: elig_u[i][l])]   # lowest threshold wins (no rng)
        for l in elig:
            Compatibility[str(l)][i] = 1

    # setup s_ijl ~ U[1,tau], diagonal (same job) 0 -- Vallada&Ruiz
    setupTime = {}
    for l in range(m):
        mat = [[0 if i == j else rng.randint(1, tau) for j in range(n)] for i in range(n)]
        setupTime[str(l)] = mat

    # machine ready-time PATTERN u_l in [0,1) from the base (rho-independent) -> SCALE by rho
    r_scale = rho * (n / m) * PBAR
    r_max = int(round(r_scale))
    readyTime = {str(l): int(round(rng.random() * r_scale)) for l in range(m)}

    return {
        "nJob": n,
        "nMachine": m,
        "processTime": processTime,
        "setupTime": setupTime,
        "Compatibility": Compatibility,
        "readyTime": readyTime,
        "minimumJobs": {str(l): 0 for l in range(m)},   # loose cardinality (niche)
        "maximumJobs": {str(l): n for l in range(m)},
        # provenance/generation parameters (also embedded in the instance for reproducibility)
        "_gen": {"n": n, "m": m, "tau": tau, "rho": rho, "r_max": r_max,
                 "elig_p": elig_p, "elig_mode": elig_mode, "p_range": [P_LOW, P_HIGH], "seed": seed,
                 "generator": "niche_generator.py"},
    }


def _feasible(d):
    """Does every job have >=1 eligible machine (so the master cannot be infeasible)."""
    n, m, C = d["nJob"], d["nMachine"], d["Compatibility"]
    return all(any(C[str(l)][i] == 1 for l in range(m)) for i in range(n))


def write_instance(n, m, tau, rho, seed, path, elig_p=ELIG_P, elig_mode="rastgele"):
    d = gen_instance(n, m, tau, rho, seed, elig_p, elig_mode)
    assert _feasible(d), f"infeasible instance ({n}x{m})"
    with open(path, "w") as f:
        json.dump(d, f)
    return d


def batch(out_root="new_dataset_niche", reps=5, sizes=DEFAULT_SIZES, taus=DEFAULT_TAUS,
          eligs=DEFAULT_ELIGS, rhos=DEFAULT_RHOS, seed_offset=0):
    """2x2 factorial grid: sizes x taus x eligs x rhos x reps.
    Dir: {out}/{n}_{m}_{tau}_{elig}_{rho}/instance_{rep}.json. manifest.json = publication-ready
    record. Same (n,m,tau,seed) -> all (elig,rho) cells share the SAME base (clean ablation).

    seed_offset: seed = seed_offset + rep. DEFAULT 0 -> existing datasets reproduced EXACTLY
    (new_dataset_niche_v2 was generated with seeds 1..5). A nonzero value yields a DISJOINT
    instance family, so that parameter calibration is not performed on the reported instances
    (train/test split; counters the "tuned and tested on the same instances" objection)."""
    os.makedirs(out_root, exist_ok=True)
    manifest = []
    count = 0
    for (n, m) in sizes:
        for tau in taus:
            for elig in eligs:
                for rho in rhos:
                    ddir = os.path.join(out_root, f"{n}_{m}_{tau}_{elig}_{rho}")
                    os.makedirs(ddir, exist_ok=True)
                    tau_val = TAU_LEVELS[tau]
                    rho_val = RHO_LEVELS[rho]
                    elig_val = ELIG_LEVELS[elig]
                    for rep in range(1, reps + 1):
                        seed = seed_offset + rep     # rep = seed (offset=0 -> 1..reps)
                        path = os.path.join(ddir, f"instance_{rep}.json")
                        d = write_instance(n, m, tau_val, rho_val, seed, path, elig_val)
                        manifest.append({"dataset": ddir, "inst": str(rep), "nJob": n, "nMachine": m,
                                         "tau": tau, "tau_val": tau_val, "elig": elig,
                                         "elig_p": elig_val, "rho": rho, "rho_val": rho_val,
                                         "seed": seed, "r_max": d["_gen"]["r_max"]})
                        count += 1
    json.dump(manifest, open(os.path.join(out_root, "manifest.json"), "w"), indent=1)
    print(f"Uretildi: {count} instance -> {out_root}/  (manifest.json yazildi)")
    from collections import Counter
    by_cell = Counter((x["elig"], x["rho"]) for x in manifest)
    print(f"  boyutlar: {sizes}")
    print(f"  tau: {taus} | elig: {eligs} | rho: {rhos} | reps: {reps}")
    print(f"  2x2 hucre dagilimi (elig,rho): {dict(by_cell)}")
    return manifest


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "tek":
        n, m = int(sys.argv[2]), int(sys.argv[3])
        tau = int(sys.argv[4]); rho = float(sys.argv[5]); seed = sys.argv[6]; out = sys.argv[7]
        seed = int(seed) if seed.lstrip("-").isdigit() else seed   # string seeds accepted (kilit2026_...)
        ep = float(sys.argv[8]) if len(sys.argv) > 8 else ELIG_P
        em = sys.argv[9] if len(sys.argv) > 9 else "rastgele"
        d = write_instance(n, m, tau, rho, seed, out, ep, em)
        print(f"{out}  ({n}x{m}, tau={tau}, rho={rho}, r_max={d['_gen']['r_max']}, seed={seed})")
    elif mode == "batch":
        out_root = sys.argv[2] if len(sys.argv) > 2 else "new_dataset_niche"
        reps = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        # optional regime filter: argv[4]=eligs, argv[5]=rhos (comma-separated), e.g. batch dir 3 e50 ron
        kw = {}
        if len(sys.argv) > 4:
            kw["eligs"] = sys.argv[4].split(",")
        if len(sys.argv) > 5:
            kw["rhos"] = sys.argv[5].split(",")
        batch(out_root, reps, **kw)
    else:
        print(__doc__)
        sys.exit(1)
