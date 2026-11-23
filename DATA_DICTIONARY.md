# Data dictionary (`results/`)

All times are wall-clock seconds unless stated otherwise; all makespans are
in the instances' integer time unit. In the LOCKED files an EMPTY cell
means "not applicable to this method/row" (e.g. CP's bound columns on a
heuristic row), never a failed measurement: failed or rejected attempts of
the locked tests go to `*.denemeler.csv`, not the accepted CSV.
Development-track files do not share that guarantee — e.g.
`rival_tuning.csv` records failed arms as explicit `HATA` rows in place.

## Locked tests (the paper's reported comparison)

### `kilitli_saf.csv` (Track A, 936 rows) and `kilitli_nis.csv` (Track B, 1092 rows)

One row = one accepted run. **Run identity is the composite key
`(aralik, size, inst, method, seed)`**; use it to join any two files of the
same test.

| column | meaning |
|---|---|
| `aralik` | setup-severity cell: `1-9`/`1-49`/`1-99` (Track A), `t9`/`t49`/`t99` (Track B) |
| `size` | `{n}_{m}`, e.g. `800_30` = 800 jobs, 30 machines |
| `inst` | instance replicate within the cell, `1…6` |
| `method` | `HLBB`, `SA`, `HGA`, `GA` or `CP` |
| `seed` | random seed, `0/1/2` for the four stochastic methods; CP has no seed parameter and is run once per instance (recorded as `seed=0`) — its run-to-run behaviour under the wall-clock budget was measured separately (`cp_tekrar.csv`) |
| `makespan` | the method's final makespan, verified by the independent checker before acceptance (see `*_feaslog.csv`) |
| `iters` | iterations: Benders iterations for HLBB, the capsule's iteration count for SA/HGA/GA, empty for CP |
| `evals` | objective evaluations reported by the Julia capsule (SA/HGA/GA only) |
| `tbest` | time at which the final best was first found, as reported by the method; `-1.0` where the method does not report it (GA); empty for CP |
| `wall_real` | measured wall-clock of the run |
| `budget` | wall-clock budget handed to the method (200 s for the stochastic methods; the CP arm's budget is in `*.manifest.json`) |
| `durum` | status note: CP's solver status (`Optimal`/`Feasible`); for stochastic methods empty, or `harness-zaman-asimi` if the harness timed out but a valid, checker-verified partial output was accepted (did not occur in the locked runs) |
| `bound`, `gap_pct` | CP only: best bound and `100·|obj-bound|/obj` |
| `workers`, `solve_s` | CP only: the solver's effective worker count (14 in all recorded runs; CP ran with `Workers=Auto`) and its own reported total time |
| `deneme` | attempt number at which the row was accepted (all locked rows: 1) |
| `sirali` | 1 if the stored solution's machine lists are in processing order (all locked rows: 1) |

### Companion files per locked test

- `*.gorevler.txt` — the pre-registered task list, one `aralik,size,inst,method,seed`
  line per planned run; its SHA-256 prefix is in the manifest, so the run
  set cannot silently change.
- `*.denemeler.csv` — EVERY attempt (`…,deneme,sinif,zaman,detay`):
  `sinif` is `basari` or a failure class, `detay` the reason. In both
  locked tests every run succeeded on attempt 1 (936 and 1092 `basari`
  rows, no failures).
- `*.manifest.json` — run-time snapshot written at launch: timestamp,
  exact dev-repo commit (`git`) plus dirty-file list (`kirli`), runner
  SHA-256 prefix, budgets, seeds, requested environment variables, the
  deliberately-removed niche settings (pure test only), the Julia
  invocation (`-t 1`), task-list SHA-256 prefix, the instance-identity
  verification statement, pending-run count and CPU model.
- `*.KILIT` — advisory lock file (PID of the running process, held via
  `flock`); prevents two runner instances. Not data.
- `*_feaslog.csv` — one line per accepted run from the independent checker
  (`bench,method,inst,seed,claimed,lkh_mk,kapsama,uygunluk,seq_ok,route_ok`):
  the claimed makespan, the checker's LKH re-routed makespan, and the
  coverage / eligibility / sequence-makespan / routing verdicts (`OK`).
- `kilitli_saf_cozumler/cozumler.jsonl` (936 records) and
  `kilitli_nis_cozumler/cozumler.jsonl` (1092 records) — the final
  SCHEDULE of every accepted run:
  `{"key": [aralik,size,inst,method,seed], "claimed": <makespan>,
  "sirali": true, "assign": [[jobs of machine 0 in order], …]}`.
  The README gives a command that re-verifies every record against the
  instance files. The CP solver logs referenced by these runs are in the
  separate data archive (see `DATA_ARCHIVE.md`).

## Ablation and configuration studies

### `ablation_v3.csv` (1008 rows; Tables 5 and 8 via `python3 ablation_run.py report`)

Identity: `(track, size, inst, arm, rep)` (`track` is `niche_v2`, the
development niche set). `arm` is `full` (the locked
configuration), `no_*` (one retained component removed: `no_degree`,
`no_bias`, `no_pool`, `no_kmach`, `no_warm`, `no_spp`, `no_master`) or
`plus_*` (one discarded candidate added back: `plus_perturb`,
`plus_graded`, `plus_dig`, `plus_optcut`, `plus_setupaware`, `plus_ils`).
`makespan`, `wall`, `total_s` as above. The remaining columns are HLBB
internal diagnostics recorded for the ablation analysis: `pre_spp`
(makespan before the final recombination), `iters`, `pool` (solution-pool
size), `deg_guard_fired` (boolean: the out-degree guard fired) with
`deg_off_iter` (the iteration at which the guard dropped the inequality),
`mfail` (COUNTER of master calls that returned no incumbent),
`collapsed` (loop broken after `mfail` reached 3), `loop_s`/`route_s`
(time in the Benders loop / in LKH routing), `n_harvest` (pool harvests),
`mip_st`/`mip_gap` (status and MIP gap of the FINAL SET-PARTITIONING
model, not of the master), `reserve` (seconds reserved for the final
recombination), and the `spp_*` block of that final set-partitioning step:
`spp_route_s`/`spp_build_s`/`spp_mip_s` (routing/model-build/solve time),
`spp_n_uniq` (distinct ASSIGNMENTS after deduplication),
`spp_n_routed` (assignments actually re-routed after clipping),
`spp_n_cols` (distinct machine–jobset COLUMNS entering the model).
Full semantics: `ablation_run.py` and `spp_recombine.py`.

- `ablation_v3.lock.json` — the frozen base configuration (every parameter
  of the locked HLBB configuration the arms depart from).
  `ablation_v3.manifest.txt` — run-time record (commit, dates).

### `sensitivity_v6.csv` (384 rows; Section "configuration" numbers)

Identity: `(size, inst, cfg, rep)` on the DISJOINT training set
(`new_dataset_sens`, generator seeds offset by 100, so it shares no
instance with the reported test set). `cfg` is one of 16 one-factor
variants around the locked configuration (`k3/k8/k10`, `kmach2/…`,
`cap160/cap400`, …; the locked base itself is in
`sensitivity_v6.base.json`). `denetim_turu` names the solution check
applied (all rows: the ordered-sequence check, `sirali`). Columns beyond
the ablation-style diagnostics: `tl_req`/`tl_eff` (requested vs EFFECTIVE
set-partitioning time limit — logged to audit the paper's `spp_tl = 20 s`
statement), `feas` (1/0/-1: checker verdict), `pool_n`/`pool_distinct`
(pool size vs DISTINCT assignments in it, the diversity measure),
`pre_spp`/`post_spp` (makespan before/after the final recombination),
`spp_used` (number of columns the recombination actually examined after
the `spp_cap` clip), `harvest` (pool harvests).

## Supporting result files

| file | what it is | identity / key columns |
|---|---|---|
| `cp_tekrar.csv` (30 rows) | run-to-run variability of CP under its wall-clock budget: 10 pre-selected niche instances × 3 fresh runs with the same model and settings as the comparison, recording the solver detail (`status/bound/gap_pct/workers/solve_s`) | `(size, inst, rep)` |
| `niche_bench_1core.csv` (40 rows) with `niche_bench_multi_v6.csv` (40 rows) | processor-fairness pair: the same HLBB runs pinned to a single core vs multi-core (the Julia rivals are single-threaded by construction, `-t 1`) | `(method, size, elig, rho, rep, seed)`, `method` = HLBB; `elig`/`rho` name the generator axes (`e50`, `ron`) |
| `kaynak_olcumu.csv` (20 rows) | CPU-use measurement behind the processor-fairness note: wall vs CPU seconds and mean cores per method | `(method, size, budget)`; `kapsam` = what was measured |
| `niche_bench_1core_cpu.csv` (40 rows) | per-run CPU accounting of the single-core control runs (`wall_total_s`, `cpu_s`, `ort_cekirdek`) | `(method, inst, seed)` |
| `niche_bench_1core.manifest.json` | run-time record of the single-core campaign: exact command, CPU affinity `[0]`, commit, machine | — |
| `niche_bench_1core_feaslog.csv`, `cp_tekrar_feaslog.csv` | independent-checker verdicts of those runs (same layout as the locked feaslogs) | run key as in their CSVs |
| `cp_tekrar.manifest.txt` | run-time record (commit, dates, settings) of the CP repeat study | — |
| `rival_tuning.csv` | Section 5.3 tuning study of SA/HGA/GA (includes explicit `HATA` rows for arms whose run failed) | `(kol, algo, param, deger, boyut, ornek, tohum)`; `kol` = tuning arm (`{algo}_{param}={value}` or `{algo}_taban` for the published-parameter baseline), `fix` = 1 when the run carried the `DELTAINS_FIX` correction (all HGA/GA runs; SA never) |
| `kilit_nis_sonda.csv` (36 rows) | local-optimality probe on the locked HLBB solutions of the two largest standard cells | `(size, aralik, inst, seed)`; `mk0/mk1` = makespan before/after the oracle polish, `n_deger/n_iyi` = neighbours evaluated/improving, `tukendi` = neighbourhood fully scanned within 300 s |
| `ref2009_large.csv` | the 2009 reference values used for context in Track A | `(size, aralik, inst)` → `ref2009` |
| `fairness_probe.csv` | one-off measurements from the fairness audit; `note` DESCRIBES each measurement's source (documented numbers, not push-button reproducible; see MANIFEST) | `key,value,unit,size,note` |
| `lowratio_k_probe.csv` | complete enumeration probe for the sparse-regime `k` discussion | `(size, rep, rule)` — one row per candidate rule (`free`, `J3`, `M`, `J2M1`, `J3M2`) per instance; `enum_complete`, `optimal`, `checker_ok` are verification flags |

## Development-track files (context, not the reported comparison)

`track_a.csv`, `niche_bench_v4.csv`, `niche_b3.csv`, `capsoft.csv`,
`reserve.csv` are
development-period benchmarks kept for provenance (the paper's reported
numbers come from the locked tests above; see MANIFEST's result-group
table). Their schemas are the simpler
`(method, size, elig, rho, rep, seed) -> makespan, wall_real, tbest, budget`
for the benchmark files, and HLBB-diagnostic layouts (as in the ablation
block) for `capsoft.csv`/`reserve.csv`. `track_a.csv` adds `bks` (the
published best-known value at the time of the development run, looked up
from `vallada_bks.json` in the repository root — our derived JSON of the
2009 published best-known VALUES, 200 entries; values, not instances) and
`sev` (setup severity).
