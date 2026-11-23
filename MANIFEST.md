# MANIFEST

Companion package of the paper on HLBB (heuristic logic-based Benders
decomposition) for unrelated parallel machine scheduling with
sequence- and machine-dependent setup times, machine eligibility and
machine ready times, under a makespan objective. The package contains the
code of the method and of every benchmark run, the raw per-run result files
underlying every table and figure, the analysis scripts that turn them into
the paper's tables and figures, and the verification tools. One documented
exception to push-button reproducibility (the one-off fairness diagnostic
probes) is stated under "Producer commands" below. The layout is deliberately FLAT: the
Python files import each other and the analysis scripts expect `results/`
next to them. Environment: `ENVIRONMENT.md` and `requirements.txt`. Known
limitations: `KNOWN_LIMITATIONS.md`.

## Provenance: which commit produced which results

Development happened in a private repository; the commits below identify
the exact code states. The history can be opened to the editor on request.
The algorithm was frozen before the locked tests (commit `11c4b28`,
2026-10-08) and not changed afterwards.

| Result group | Locked/prepared at | Runs completed at | Result files (`results/`) |
|---|---|---|---|
| Locked pure test (936 runs) | `7b2eff4` (2026-10-19; pre-registered plan + runner + SHA manifest of the 144 instance files) | `a747b3a` (2026-10-22) | `kilitli_saf.csv` + `.KILIT`, `.denemeler.csv`, `.gorevler.txt`, `.manifest.json`, `_feaslog.csv`, `kilitli_saf_cozumler/cozumler.jsonl` (CP logs: data archive) |
| Locked niche test (1092 runs) | `091d6de` (2026-10-22; pre-registered plan + runner) | `855c990` (2026-10-26) | `kilitli_nis.csv` + same five companions |
| Ablation v3 (1008 runs) | `a924dea` (2026-10-16) | `cd59e92` (2026-10-18) | `ablation_v3.csv`, `.lock.json`, `.manifest.txt` |
| Sensitivity v6 (384 runs) | `0cd10fb`+`592c620` (2026-10-12) | `218a5eb` (2026-10-13) | `sensitivity_v6.csv`, `.base.json`, `.manifest.txt` |
| Paired side-constraint experiment (B3) | `560b5e9`+`21dd954` (2026-10-14) | `12f5cd3` (2026-10-15) | `niche_b3.csv` |
| Single-core / processor-fairness v6 | `005ea16` (2026-10-18) | `bf2ce28` (2026-10-19) | `niche_bench_1core.csv` + `_feaslog.csv` + `_cpu.csv` + `.manifest.json`, `niche_bench_multi_v6.csv`, `kaynak_olcumu.csv` |
| CP repeats (30 runs) | `005ea16` | `916d86f` (2026-10-19) | `cp_tekrar.csv`, `.manifest.txt`, `_feaslog.csv` |
| Rival tuning (Appendix A) | runner `e39e5d8`→`0ea280c` (2026-10-10), fix `7031196` (2026-10-11) | tuning locked `0c73b93` (2026-10-12) | `rival_tuning.csv` |
| Local-optimality probe | on the locked niche solutions, selection rule fixed in advance | `237d972` (2026-10-26) | `kilit_nis_sonda.csv` (+ `results/kilitli_nis_cozumler/cozumler.jsonl`) |
| Development-track benchmarks | various (development period) | — | `track_a.csv`, `niche_bench_v4.csv`, `capsoft.csv`, `reserve.csv`, `lowratio_k_probe.csv`, `ref2009_large.csv`, `fairness_probe.csv` |

Per-run metadata: the locked runners write `*.manifest.json` carrying the
exact commit hash, dirty-file list, runner SHA-256 prefix (16 hex), budgets, seeds,
environment variables, Julia invocation (`-t 1`), task-list SHA-256 prefix
(16 hex), instance-identity verification and CPU model. Run identity of the locked
tests is the composite key (range, size, instance, method, seed); accepted
rows are in `kilitli_*.csv`, every attempt (including rejected) in
`kilitli_*.denemeler.csv`.

Producer commands worth recording explicitly:

- `lowratio_k_probe.csv`: produced by `_enum_cand.py` (included) as
  `python3 _enum_cand.py 50x20 30 results/lowratio_k_probe.csv`. CAVEAT: the
  script is included as the historical producer; it reads a development-era
  data path and prepends the dev-repo to `sys.path`, so the command is a
  provenance record, not a portable recipe (portable instructions: README).
- `ref2009_large.csv`: produced by `ref2009_cevir.py` (included; lived under
  `lit_gece/araclar/` in the dev repo). Same CAVEAT: it resolves paths
  relative to the dev tree and expects a locally downloaded `.xls` of the
  published 2009 reference values; included as a provenance record.
- `fairness_probe.csv`: one-off diagnostic probes from the fairness audit;
  the CSV's `note` column DESCRIBES each measurement's source (it does not
  contain runnable commands). The probe scripts themselves were
  session-local and are not part of this package, and some cited sources
  are development artefacts likewise not shipped (e.g. a development-set
  solution file under the excluded `results/solutions/`); these numbers are
  documented measurements, not push-button reproducible ones.
- `kilit_nis_uret.py` (lived under `lit_gece/araclar/` in the dev repo,
  relocated to the root like `ref2009_cevir.py`): the producer of the
  locked niche instance set. It carries the ONE-LINE `ROOT` adaptation
  described below, after which it writes `nis_kilit2026/` next to the code;
  in a clean checkout its development-seed-collision scan finds no
  development datasets and passes trivially, and regeneration is
  hash-identical to `instance_manifests/`.
- `kilit_saf_veri_denetimi.py` (same dev location, same relocation): the
  cell-by-cell raw-vs-converted audit of the 72 locked pure instances;
  same one-line `ROOT` adaptation, after which it runs from the package
  root with `dataset_vallada/` and `valladapure_kilit/` beside it
  (verified: `TAM DOGRULANAN: 72/72`).

  **Documented exception to the comments-only rule, exactly two files:**
  these two relocated scripts resolved the dev-repo root as
  `dirname(__file__)/../..`, which is wrong at the package root (the niche
  producer would try to write OUTSIDE the checkout). In each, that one
  `ROOT` line was changed to `dirname(__file__)`, marked in place with a
  `YAYIN UYARLAMASI` comment; nothing else differs, and the dev originals
  are unchanged in the dev repository. Every OTHER transferred source
  remains AST-identical to production with comments-only differences.
- `gen_gantt.py`, `gen_arc.py`: the producers of Figures 1 and 3
  (illustrative panels); both verify their own output exhaustively at
  generation time and reproduce the paper's fragments byte-for-byte.

## Pre-registration dating

`ON_KAYIT_PROTOKOLU.md` is included unmodified. Its lock-in dates are
evidenced by the development repository's history: the pure-test plan was
committed at `7b2eff4` (2026-10-19) and the niche plan at `091d6de`
(2026-10-22), both BEFORE the corresponding runs completed (2026-10-22 and
2026-10-26). The SHA-256 manifests of the locked instance files are in
`instance_manifests/` (pure: 72 raw + 72 converted = 144 files; niche:
84 JSON + 84 binary).

## What was changed for publication

The TRANSFERRED PYTHON SOURCES differ from their production counterparts in
COMMENTS AND DOCSTRINGS ONLY (translated to English for publication; see
below) — with TWO documented exceptions, each marked in place with a
`YAYIN UYARLAMASI` (publication adaptation) comment:

1. The two scripts relocated from `lit_gece/araclar/`
   (`kilit_nis_uret.py`, `kilit_saf_veri_denetimi.py`) each carry a single
   changed `ROOT` line so they resolve the package root instead of the
   dev-repo root; see "Producer commands" above.
2. In the seven Julia-driving harnesses (`kilitli_saf_run.py`,
   `kilitli_nis_run.py`, `niche_benchmark.py`, `track_a_benchmark.py`,
   `validate_algo.py`, `rival_tuning_benchmark.py`, `verify_all.py`) the
   hard-coded Julia paths became environment-variable fallbacks:
   `HLBB_JULIA` selects the Julia binary and `JULIA_DEPOT_PATH` is now
   honoured instead of overwritten; WITH NEITHER VARIABLE SET, every
   default equals the recorded run machine's path, so the behaviour that
   produced the results is unchanged. (This generalizes the pattern
   `CP_model.py` already used via `CPLEX_STUDIO_DIR`.) Verified both ways:
   defaults byte-identical without the variables; both variables take
   precedence in all seven files when set.

The package as a whole also selects files, relocates
producer scripts and adds documentation. Comment and docstring language:
development happened in Turkish; for publication, every `#` comment and
docstring across the Python sources was translated to English (42 of the
47 `.py` files carried Turkish text and changed; the other five were
already English and are byte-identical to their pre-translation state).
Commented-out code and selected development-only notes (internal memory
links, session and tour references) were removed in the same pass;
measured numbers, design rationales, acceptance thresholds and literature
pointers were kept. Structural-equivalence check, stage one
(pre-translation release copy vs final release copy): for every changed
`.py` file, `ast.dump(ast.parse(src), include_attributes=False)` differs
only in docstring string literals (`#` comments never enter the AST),
verified mechanically file by file. Stage two (production vs
pre-translation release copy) is the transfer check recorded above, with
the two documented adaptations. Apart from docstrings — which are string
literals, are runtime-visible via `help()`, and feed the usage banners
some scripts print (`print(__doc__)`), so those banners now show the
translated text — and the two documented adaptations, string literals,
printed messages, CLI subcommand names and all identifiers are unchanged.
The Turkish comment lines in the Julia files carrying our niche extensions
were translated the same way (comment lines only; every changed file
re-parsed with the pinned Julia 1.7.0; the pristine `.orig` snapshots and
their SHA-256 list are untouched). The pre-registration document
`ON_KAYIT_PROTOKOLU.md` remains in Turkish, included unmodified. The
release-validation battery (isolated imports, seeded instance regeneration
against the SHA manifests, the Vallada conversion chain, byte-identical
regeneration of the paper's table and figure fragments, re-verification of
all 2028 published schedules, and a leak sweep) is re-run from a fresh
extraction on every archive cut; the accepted archive's SHA-256 is
recorded in the release commit message.

## Third-party components and licences

- **Our code**: MIT (`LICENSE`). This repository grants no rights over the
  external solvers below.
- **Rolim et al. capsule** (`rolim_capsule/`): MIT, original notice kept
  (`NOTICE.md`); added to the dev repository on 2026-08-14 from
  https://codeocean.com/capsule/3793251 (pristine download SHA-256 recorded
  in `MODIFICATIONS.md`). Changes are enumerated there in three layers:
  mechanical harness adaptations across the algorithm files (budget-type
  widening; time-to-best stopwatch; include-path portability in
  `Modules.jl`), our niche extensions in four files (three algorithms + the
  per-run driver) with their `.orig` baselines and SHA-256 alongside
  (`ORIG_SHA256.txt`), and our added test benches. `environment/` and
  `metadata/` describe the ORIGINAL capsule.
- **LKH-3.0.7** (Helsgaun): not bundled; build recipe and terms note in
  `ENVIRONMENT.md`. SHA-256 of the official source archive could not be
  recorded yet: the distribution host (webhotel4.ruc.dk) was unreachable
  from our environment on 2026-11-10 (two attempts, http and https) and
  again on 2026-11-11. The
  checksum will be recorded here at release time after a successful
  download; until then, readers should obtain `LKH-3.0.7.tgz` from the
  author's page and can compare their build against the behaviour reported
  in the paper. Our local source tree identifies itself as LKH-3.0.7.
- **Gurobi 13.0** and **IBM CP Optimizer 22.2**: commercial; licences
  required for solve-time use. `ENVIRONMENT.md` lists which scripts need
  which solver.
- **Vallada & Ruiz (2011) instances**: used unmodified and NOT
  redistributed here (neither raw nor converted). The acquisition recipe
  (original URL, Internet Archive snapshot, expected SHA-256 of the raw
  files) is in the README; `instance_manifests/` lets the reader verify a
  local copy, and `vallada_to_hlbb.py` converts it.
- **Niche instances and bulk run artefacts**: separate data archive
  (CC BY 4.0), see `DATA_ARCHIVE.md`; the code record and the data record
  cross-link each other.

## Command → solver dependency

Dependencies are per RUN MODE, not just per file:

| Needs | Commands / modes |
|---|---|
| Gurobi + LKH + Julia | the benchmark runners: `kilitli_saf_run.py`, `kilitli_nis_run.py`, `niche_benchmark.py`, `track_a_benchmark.py`, `ablation_run.py`, `sensitivity_run.py`, `onecore_run.py`, `kaynak_olcumu.py`, `rival_tuning_benchmark.py`, `_capsoft_probe.py`, `_reserve_probe.py` |
| Gurobi + LKH | `hlbb_hm.py` (the method itself) |
| Gurobi only | `_enum_cand.py`; `feasibility.py` WHEN its exact-ATSP re-routing is used (`exact_atsp.py` builds and solves a Gurobi model) |
| LKH only | `_kilit_nis_sonda.py` |
| CP Optimizer | `CP_model.py`, `cp_tekrar_run.py`, and the CP arm of the locked runners |
| Julia | `validate_algo.py` (drives the capsule via subprocess), the capsule test benches |
| None at solve time, but importing initializes a Gurobi environment (`methods.py` runs `env.start()` at import; the restricted pip-bundled licence suffices, a present-but-invalid licence file blocks the import) | `feasibility.py` in its assignment/sequence-checking modes (`sequence_makespan` etc.), `gen_gantt.py`, the schedule re-verification command in the README, and the `report` subcommands of `ablation_run.py`/`sensitivity_run.py` |
| None (pandas/numpy only) | `paper_stats.py`, `paper_figs.py`, `gen_tracka_tables.py`, `gen_trackb_tables.py`, `gen_appendix_tables.py`, `gen_arc.py`, `niche_generator.py`, `kilit_nis_uret.py`, `vallada_to_hlbb.py`, `kilit_saf_veri_denetimi.py`, `ref2009_cevir.py` |

`verify_all.py` re-runs the methods and then checks them, so the full chain
needs everything above (Gurobi, CP Optimizer, LKH, Julia).

The publication commit/tag of THIS repository is recorded in the release
metadata (GitHub release + Zenodo), not inside this file.
