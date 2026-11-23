# HLBB — a heuristic logic-based Benders decomposition for unrelated parallel machine scheduling

Code, data recipes and raw results for

> **A Heuristic Logic-Based Benders Decomposition for Makespan Minimization
> on Constrained Unrelated Parallel Machines**
> Sarp Ongun Cimen. Submitted manuscript, 2026. (The citation will be updated
> here when the paper is published.)

The problem is $R \mid s_{ij\ell}, M_j, r_\ell \mid C_{\max}$: unrelated
parallel machines with sequence- and machine-dependent setup times, machine
eligibility restrictions and machine ready times, minimizing the makespan.
HLBB solves it by decomposition: an arc-relaxation master assigns the jobs,
LKH sequences each machine, and a set-partitioning step recombines the best
machine loads, all inside one wall-clock budget.

**Versions that belong together:** the submitted paper, this repository at
release tag `v1.0.0` (https://github.com/onguncimen-sys/hlbb-upmsp — the
tag is archived on Zenodo at release time and its version DOI is recorded
in the GitHub release notes and the paper), and the data record
(10.5281/zenodo.24198707, instances + CP solver logs; see `DATA_ARCHIVE.md`). The two
Zenodo records cross-link each other.

## Map of the repository

| path | contents |
|---|---|
| `hlbb_hm.py` | the method: Benders loop, `run_integrated_sr` |
| `*.py` (root) | its import closure, the benchmark runners, the analysis scripts, the verification tools |
| `rolim_capsule/` | the baseline library (MIT), three algorithms + the per-run driver extended — `NOTICE.md`, `MODIFICATIONS.md`, documented pre-extension `.orig` snapshots |
| `results/` | the raw per-run files behind every reported table and figure (`DATA_DICTIONARY.md` defines every column) |
| `instance_manifests/` | SHA-256 manifests of the 144 pure-test files and the 168 niche-test files |
| `instances/README.md` | how to obtain or regenerate every instance set |
| `MANIFEST.md` | provenance: which commit produced which results, what was changed for publication, licences |
| `ENVIRONMENT.md`, `requirements.txt` | the measured run environment and pinned Python packages |
| `INSTANCE_FORMAT.md` | the JSON/binary instance formats, with a worked example |
| `ON_KAYIT_PROTOKOLU.md` | the pre-registered analysis plan (in Turkish, included unmodified; its dating is evidenced in `MANIFEST.md`) |
| `KNOWN_LIMITATIONS.md` | known blind spots, stated up front |

**Naming.** Development file names are partly Turkish and are kept
unchanged for traceability to the pre-registered commits (`MANIFEST.md`);
only the data record's public download filenames were anglicized. Glossary:
`nis` = niche, `kilit`/`kilitli` = locked (pre-registered — not
access-restricted), `saf` = pure, `uret` = generate, `cozumler` =
solutions, `duman` = smoke (test), `dogrula` = verify, `HAM` = raw,
`kaynak` = source or resource (context-dependent), `sonda` = probe,
`denetim` = audit. The data record's README maps each download name to the
internal name it corresponds to (e.g. `locked_niche_2026_v1.tar.gz`
extracts into `nis_kilit2026/` — keep that directory name).

## Installation

```bash
pip install -r requirements.txt       # numpy, pandas, scipy, gurobipy, docplex, openpyxl
```

- **Gurobi 13.0** (master problems) and **IBM CP Optimizer 22.2** via
  `docplex` (the CP baseline) are commercial; both need licences for
  solve-time use. What runs WITHOUT them is listed below.
- **LKH-3.0.7** (Helsgaun) is not bundled: download `LKH-3.0.7.tgz` from
  the author's page (http://webhotel4.ruc.dk/~keld/research/LKH-3/), run
  `make`, and place the tree as `./LKH-3.0.7/` next to the Python code.
  LKH is free for research use under the author's own terms; see
  `ENVIRONMENT.md`.
- **Julia 1.7.0** runs the SA/HGA/GA baselines (`rolim_capsule/`), single
  thread. Packages are pinned in `rolim_capsule/code/Project.toml` +
  `Manifest.toml` (`StatsBase v0.34.4`, `Hungarian v0.7.0`,
  `Distributions v0.25.100`); instantiate with
  `julia --project=rolim_capsule/code -e 'using Pkg; Pkg.instantiate()'`.

**Machine paths: set two environment variables before RE-RUNNING
experiments.** No file editing is needed:

- `HLBB_JULIA` — path to your Julia 1.7.0 binary, and `JULIA_DEPOT_PATH` —
  your Julia depot. All seven Julia-driving harnesses honour them; with
  neither set, the defaults are the recorded run machine's paths
  (a documented exception to the byte-faithfulness of the transferred
  sources — see `MANIFEST.md`, "What was changed for publication").
- `CPLEX_STUDIO_DIR` — your IBM CPLEX Studio root (`CP_model.py`); its
  fallback is likewise the run machine's path.
- `_enum_cand.py`, `_enum_probe.py` and `ref2009_cevir.py` read
  development-era paths by design: they are provenance records of three
  supporting CSVs, not portable recipes (see `MANIFEST.md`).

Nothing in the solver-free analysis/verification path below uses any of
these constants.

**Solver-free:** the table/figure generators (`gen_tracka_tables.py`,
`gen_trackb_tables.py`, `gen_appendix_tables.py`, `gen_arc.py`),
`paper_stats.py`, `paper_figs.py`, the instance producer and converters
(`niche_generator.py`, `kilit_nis_uret.py`, `vallada_to_hlbb.py`,
`kilit_saf_veri_denetimi.py`) and the SHA-256 checks need only the Python
packages — no solver is touched at all.

One caveat for everything that imports the method's modules
(`gen_gantt.py`, `ablation_run.py report`, `sensitivity_run.py report`, and
the schedule re-verification command below): importing initializes an empty
Gurobi environment (`methods.py` runs `env.start()` at import), so
`gurobipy` must be able to START an environment, although nothing is
solved. The restricted licence bundled with `pip install gurobipy`
suffices; a present-but-invalid licence file (e.g. a host-ID mismatch)
blocks even these imports. The full dependency table by run mode is in
`MANIFEST.md`.

## Getting the instances

### Niche set (Track B): download or regenerate

The 84 locked niche instances (`nis_kilit2026/`, JSON + binary, ~5 GB raw)
are in the data archive (10.5281/zenodo.24198707). Alternatively regenerate them —
deterministic and hash-identical:

```bash
python3 kilit_nis_uret.py          # writes nis_kilit2026/ next to the code
( cd nis_kilit2026 && sha256sum -c ../instance_manifests/nis_kilit2026_JSON_SHA256.txt )
```

(The generator re-derives every instance from string seeds
`kilit2026_{n}x{m}_t{tau}_{i}`; budget tens of minutes and ~5 GB of disk.)

### Pure set (Track A): obtain Vallada & Ruiz (2011), then convert

These instances are **not ours to redistribute** (raw or converted). The
original host `http://soa.iti.es` is no longer reachable; we obtained the
library from the Internet Archive:

```
http://web.archive.org/web/20130715180901/http://soa.iti.es/files/RSDST.7z
```

1. Unpack so the large set sits at `dataset_vallada/large/` (1000 files).
2. Verify the 72 files the paper uses (the manifest lists exactly those):

   ```bash
   ( cd dataset_vallada/large && sha256sum -c ../../instance_manifests/valladapure_kilit_HAM_SHA256.txt )
   ```
3. Convert the twelve locked cells (value-for-value, see
   `INSTANCE_FORMAT.md`); the severity filter keeps the unused 1-124 range
   out, so this yields exactly the 72 locked files:

   ```bash
   for cfg in "50 30" "150 30" "100 10" "200 10"; do
     for sev in 1-9 1-49 1-99; do
       python3 vallada_to_hlbb.py --batch dataset_vallada/large valladapure_kilit 6 $cfg $sev
     done
   done
   ```

4. Verify the conversion and arm the runner's own identity check — BOTH
   manifests must sit inside `valladapure_kilit/`, because the runner
   re-verifies the raw files AND the converted files at every launch and
   refuses to run on mismatching or missing data:

   ```bash
   cp instance_manifests/valladapure_kilit_HAM_SHA256.txt  valladapure_kilit/HAM_SHA256.txt
   cp instance_manifests/valladapure_kilit_JSON_SHA256.txt valladapure_kilit/JSON_SHA256.txt
   ( cd valladapure_kilit && sha256sum -c JSON_SHA256.txt )
   ```

`RSDSTSol.7z` (same Archive host, snapshot `2013id_`) holds the 2009
best-known-value spreadsheets; they are context only (`ref2009_large.csv`),
not part of any reported comparison.

## Quick start: solve one instance

```bash
python3 - <<'PY'
from readproblem import readproblem
from hlbb_hm import run_integrated_sr
d = readproblem("nis_kilit2026/100_15_t99/instance_1.json",
                consider_compatibility=True, consider_workload=True)
nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
best, t_best, iters = run_integrated_sr(nJob, nM, c1, c2, rt, pt, st, I_l, L_i,
                                        total_time_limit=200)[:3]
print(f"makespan {best}  found at {t_best:.1f}s  after {iters} iterations")
PY
```

The shipped configuration is the default of `run_integrated_sr`; no tuning
arguments are needed to reproduce the paper. (For bit-faithful reproduction
set `ARC_CACHE_ON = False` in `hlbb_hm.py`; see `KNOWN_LIMITATIONS.md`.
Loading an instance writes a scratch `dist_mat.npy` in the working
directory.)

## Reproducing the paper

### From the shipped results (seconds, solver-free)

Every reported table and figure is derived from a file in `results/`:

| paper item | source file(s) in `results/` | command |
|---|---|---|
| Table 1 (literature comparison) | — (bibliographic, no data) | — |
| Figure 1 (Gantt anatomy) | — (illustrative instance, self-verifying by exhaustive enumeration) | `python3 gen_gantt.py` |
| Figure 2 (flow diagram) | — (hand-drawn TikZ) | — |
| Figure 3 (arc-relaxation panels) | — (four-job example, self-verifying by brute force) | `python3 gen_arc.py` |
| Table 2, Figure 4 (Track A cells + regime) | `kilitli_saf.csv` | `python3 gen_tracka_tables.py` |
| Tables 3–4, Figure 5 (Track B cells, dose, scale) | `kilitli_nis.csv` | `python3 gen_trackb_tables.py` |
| Table 5, Table 8 (ablation, discarded candidates) | `ablation_v3.csv` | `python3 ablation_run.py report` (prints the Δ values; the LaTeX bodies in the paper are maintained by hand from this output) |
| Tables 6–7 (per-instance appendix) | `kilitli_saf.csv`, `kilitli_nis.csv` | `python3 gen_appendix_tables.py` |
| statistics quoted in the prose (`\stat…` macros) | `kilitli_saf.csv`, `kilitli_nis.csv`, `ref2009_large.csv`, `fairness_probe.csv`, `lowratio_k_probe.csv`, `niche_bench_1core.csv`, `niche_bench_multi_v6.csv`, `kaynak_olcumu.csv` (plus development-track files for development-period statements) | `python3 paper_stats.py` (writes `paper/stats_snippets.tex`) |
| configuration-study numbers (Section 4.5) | `sensitivity_v6.csv` | `python3 sensitivity_run.py report`; quoted in the text |
| CP repeat statement (Section 5.2, fairness item v) | `cp_tekrar.csv` | produced by `cp_tekrar_run.py`; quoted in the text |
| local-optimality probe (Section 6.4) | `kilit_nis_sonda.csv` | produced by `_kilit_nis_sonda.py`; quoted in the text |
| tuning protocol numbers (Section 5.3) | `rival_tuning.csv` | produced by `rival_tuning_benchmark.py`; quoted in the text |

The `gen_*` scripts write LaTeX fragments into `paper/` (create it first:
`mkdir -p paper`). They regenerate the paper's fragments byte-for-byte from
the shipped CSVs. Two of the generated fragments
(`tab_tracka_conf.tex`, `tab_trackb_conf.tex` — the confirmatory test
tables) are produced but not included in the final manuscript; their
numbers are quoted in the prose via `paper_stats.py`.

One caution: `paper_figs.py` is the DEVELOPMENT-era figure script (it reads
the development benchmarks and can overwrite `fig_scale.tex`/
`fig_regime.tex` with development-data versions). The published figures
come from `gen_tracka_tables.py` and `gen_trackb_tables.py`; `paper_figs.py`
is kept for provenance of the development-period figures only.

### Re-running the experiments (hours to days, all solvers required)

| experiment | command | scale |
|---|---|---|
| Locked pure test (Track A) | `python3 kilitli_saf_run.py` (first `… duman` for a smoke run, `… dogrula` to re-check) | 936 runs: 864 × 200 s + 72 CP × 1000 s ≈ 68 h of budget; completed 2026-10-19 → 10-22 on one machine |
| Locked niche test (Track B) | `python3 kilitli_nis_run.py` (same subcommands) | 1092 runs: 1008 × 200 s + 84 CP × 1000 s ≈ 79 h; completed 2026-10-22 → 10-26 |
| Ablation (Tables 5, 8) | `python3 ablation_run.py run` | 1008 runs on the development niche set |
| Configuration study | `python3 sensitivity_run.py run` (then `report`) | 384 runs on the disjoint training set |
| CP variability repeats | `python3 cp_tekrar_run.py` | 30 × 1000 s |
| Processor-fairness pair | `taskset -c 0 python3 onecore_run.py --csv results/niche_bench_1core.csv` (the runner refuses to start without single-core affinity; see its docstring for the remaining arguments) | 40 single-core runs; the multi-core counterpart is `niche_bench_multi_v6.csv` |
| CPU-use measurement | `python3 kaynak_olcumu.py` | 20 measurements (wall vs CPU seconds per method/size) |
| Rival tuning (frozen before the locked tests) | `python3 rival_tuning_benchmark.py` | protocol in Section 5.3 of the paper |

Both locked runners are resumable (accepted runs are skipped on restart),
verify the instance hashes at launch, run every task of the pre-registered
`*.gorevler.txt` list, pass every result through the independent
feasibility checker before accepting it, and append the evidence to
`results/` — which is why re-runs need the isolation step below.

### ⚠️ Isolating re-runs from the shipped evidence

The locked runners APPEND to the shipped evidence files
(`results/kilitli_*.csv`, `…denemeler.csv`, `…_feaslog.csv`,
`…cozumler/cozumler.jsonl`), and they are RESUMABLE: accepted runs present
in the CSV are skipped on restart. Two consequences:

1. **To re-check the shipped evidence**, work on a plain copy — this is
   what `kilitli_saf_run.py dogrula` / `kilitli_nis_run.py dogrula` do, and
   they only read.
2. **To actually re-RUN the experiments**, the copy must not contain the
   accepted rows, or the runner will skip all 936/1092 tasks as done:

   ```bash
   git clone <this repo> rerun && cd rerun          # or: cp -r the unpacked archive
   mkdir results/referans_yedek
   mv results/kilitli_saf.csv results/kilitli_saf.denemeler.csv \
      results/kilitli_saf_feaslog.csv results/kilitli_saf_cozumler \
      results/referans_yedek/        # same for kilitli_nis.* on the niche side
   python3 kilitli_saf_run.py       # starts from the pre-registered task list
   ```

   The runner rebuilds its evidence files from scratch in the copy; compare
   them against `results/referans_yedek/` afterwards.

Never edit the shipped `results/` in place — its reference state is frozen
by the release tag and the Zenodo archive. (The `*.KILIT` lock prevents two
runners in the SAME directory, not across copies.)

## Verifying the claims

**1. Every reported run was checker-verified at acceptance time** — the
verdicts are shipped: `results/kilitli_*_feaslog.csv` (coverage,
eligibility, sequence makespan, LKH re-route) with one `OK` line per run.

**2. Re-verify every reported schedule yourself (no solve; see the
gurobipy-initialization caveat under Installation).** The final
schedule of each of the 936 + 1092 locked runs is in
`results/kilitli_{saf,nis}_cozumler/cozumler.jsonl`. With the instance sets
in place (previous section), this re-checks coverage, eligibility and the
claimed makespan of every record against the instance files (the completion
formula is also three lines in `INSTANCE_FORMAT.md`, if you prefer a
dependency-free reimplementation):

```bash
python3 - <<'PY'
import collections, json
from feasibility import sequence_makespan
from readproblem import readproblem

for jsonl, root, flags in [
        ("results/kilitli_nis_cozumler/cozumler.jsonl", "nis_kilit2026/{sz}_{ar}/instance_{i}.json", (True, True)),
        ("results/kilitli_saf_cozumler/cozumler.jsonl", "valladapure_kilit/{sz}/S{ar}/instance_{i}.json", (False, False))]:
    recs = collections.defaultdict(list)
    for line in open(jsonl):
        d = json.loads(line)
        ar, sz, i, m, s = d["key"]
        recs[(sz, ar, int(i))].append(d)
    n = 0
    for (sz, ar, i), ds in sorted(recs.items()):
        nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = readproblem(
            root.format(sz=sz, ar=ar, i=i), *flags)
        for d in ds:
            A = d["assign"]
            assert sorted(j for mach in A for j in mach) == list(range(nJob)), d["key"]
            assert all(l in L_i[j] for l in range(nM) for j in A[l]), d["key"]
            mk = max(sequence_makespan(A[l], l, rt, pt, st) for l in range(nM))
            assert abs(mk - d["claimed"]) < 1e-6, (d["key"], mk, d["claimed"])
            n += 1
    print(f"{jsonl}: {n} records verified")
PY
```

Expected output: `… 1092 records verified` and `… 936 records verified`
(takes tens of minutes; the large instances dominate the load time). A
stronger per-solution check — exact ATSP re-routing of each machine — is
`feasibility.check_assignment` (needs Gurobi).

**3. Baseline equivalence.** The extended Julia baselines reproduce the
untouched originals bit for bit on the pure problem class:

```bash
python3 validate_algo.py SA     # also HGA, GA; needs Julia
```

**4. Full chain.** `python3 verify_all.py` re-runs methods and checks them
end to end (needs Gurobi, CP Optimizer, LKH and Julia).

**5. Data identity.** `sha256sum -c` against `instance_manifests/*` (see
"Getting the instances"); with `dataset_vallada/` and `valladapure_kilit/`
in place, `python3 kilit_saf_veri_denetimi.py` additionally re-compares
every processing-time and setup cell of the 72 converted pure instances
against the raw Vallada files (expected output: `TAM DOGRULANAN: 72/72`).

### What reproduction means here

- Instance regeneration/conversion must match the SHA-256 manifests exactly.
- Analysis scripts must reproduce the paper's tables and figures from the
  shipped `results/` to the printed precision.
- Re-RUNNING the experiments reproduces the paper's conclusions, not the
  identical numbers: the methods are stochastic and wall-clock-budgeted,
  and even a fixed seed does not pin HLBB down, because its master runs
  under per-iteration time limits (the paper's Section 5.2, fairness
  item v, quantifies the three-run spread). No bit-for-bit promise is made
  for time-limited solver runs.

## Resources

All reported runs: one machine, Intel Core Ultra 7 155U (12 cores), 30 GB
RAM, Linux x86_64 (details and the measured-vs-recorded distinction in
`ENVIRONMENT.md`). Budgets: 200 s wall-clock per stochastic run, 1000 s per
CP run. Threading: the Julia baselines run single-threaded (`-t 1`); HLBB
is wall-clock-budgeted but NOT single-threaded — its Gurobi master and
parallel LKH routing used a measured mean of 3.96–12.81 cores depending on
size (`results/kaynak_olcumu.csv`), and the paper's fairness section
reports the single-core control run addressing exactly this asymmetry; CP
used `Workers=Auto` (14 effective workers).
Disk: ~5 GB for the regenerated niche set, ~1.5 GB for the Vallada library,
~2.5 GB for the unpacked CP-log archive. Memory: the 800-job instances
need a few GB per process.

## Licence and attribution

Our code is MIT (`LICENSE`). This repository grants no rights over Gurobi,
CP Optimizer or LKH-3.

`rolim_capsule/` is the reproducible capsule of Rolim & Nagano (2025),
redistributed under its MIT licence; three of its algorithms (SA, HGA, GA)
and its per-run driver carry our eligibility and ready-time extensions,
documented line-for-line in `rolim_capsule/MODIFICATIONS.md`, with the
documented pre-extension snapshots (`.orig`) and their SHA-256 beside them
(the pristine capsule is identified by its download hash there).

The pure-benchmark instances are those of Vallada & Ruiz (2011), used
unmodified and not redistributed here. LKH-3 is by Keld Helsgaun.

## Citation

See `CITATION.cff`, or:

```bibtex
@misc{cimen_hlbb,
  author       = {Cimen, Sarp Ongun},
  title        = {A Heuristic Logic-Based Benders Decomposition for Makespan
                  Minimization on Constrained Unrelated Parallel Machines},
  year         = {2026},
  howpublished = {Submitted manuscript; code at
                  \url{https://github.com/onguncimen-sys/hlbb-upmsp}},
}
```

(The journal citation will replace this entry upon publication.)
