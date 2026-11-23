# Instance format

Both benchmarks use the same JSON schema, read by `readproblem.py`. This
document fixes the indexing, the matrix orientations and the timing
conventions, and ends with a small worked example and the binary bridge
format used by the Julia baselines.

## JSON schema

Top-level keys of one instance file:

| key | type | meaning |
|---|---|---|
| `nJob` | int | number of jobs `n`; jobs are indexed `0 … n-1` |
| `nMachine` | int | number of machines `m`; machines are indexed `0 … m-1` |
| `processTime` | dict | `processTime["l"][i]` = processing time of job `i` on machine `l` |
| `setupTime` | dict | `setupTime["l"][i][j]` = setup time on machine `l` when job `j` is processed IMMEDIATELY AFTER job `i` (direction `i -> j`); diagonal entries are 0 and never used |
| `Compatibility` | dict | `Compatibility["l"][i]` ∈ {0,1}; 1 = job `i` is eligible on machine `l` |
| `readyTime` | dict | `readyTime["l"]` = time at which machine `l` becomes available |
| `minimumJobs`, `maximumJobs` | dict | per-machine cardinality bounds; in BOTH benchmarks they are non-binding (0 and `nJob`) — cardinality is not part of the problem |
| `_gen` | dict | generator metadata (niche instances only): `n, m, tau, rho, r_max, elig_p, elig_mode, p_range, seed, generator` |

Conventions that differ from some other formats, stated explicitly:

- **Machine-major dictionaries with STRING keys.** `processTime`,
  `setupTime`, `Compatibility`, `readyTime`, `minimumJobs`, `maximumJobs`
  are dictionaries keyed by the machine index as a string (`"0"`, `"1"`, …),
  each holding a per-job list (or matrix). Job positions inside the lists
  are plain 0-based integers.
- **Setup direction is row -> column.** `setupTime["l"][i][j]` is charged
  when `j` follows `i`. All times are integers in both benchmarks.
- **No initial setup.** The first job on a machine pays NO setup; it starts
  when the machine becomes ready. The completion time of machine `l`
  processing the sequence `j_1, …, j_k` is

  ```
  C_l = readyTime[l] + p[l][j_1] + sum over t=2..k of ( s[l][j_{t-1}][j_t] + p[l][j_t] )
  ```

  and the makespan is `max_l C_l` over all machines (empty machines
  contribute 0). This is exactly `feasibility.sequence_makespan`, which all
  five methods and the independent checker share.

### How the two benchmarks use the flags

`readproblem(path, consider_compatibility, consider_workload)` applies the
`Compatibility` and `minimumJobs`/`maximumJobs` fields only when the flags
are set:

- **Niche instances** (`nis_kilit2026/`, Track B) are read with
  `(True, True)`: eligibility is real (about half the machine-job pairs,
  `elig_p = 0.5`), ready times are positive, the cardinality fields are
  present but equal to the non-binding `0`/`nJob`.
- **Converted Vallada instances** (`valladapure_kilit/`, Track A) are read
  with `(False, False)`: the pure benchmark has no eligibility and no ready
  times, so the converter writes all-ones compatibility, all-zero ready
  times and non-binding cardinality, and the flags are off.

Side effect worth knowing: `readproblem` also writes a scratch file
`dist_mat.npy` (the ATSP distance matrix of the last loaded instance) into
the current working directory.

## Worked example

Three jobs, two machines:

```json
{"nJob": 3, "nMachine": 2,
 "processTime":  {"0": [4, 3, 5], "1": [6, 2, 4]},
 "setupTime":    {"0": [[0,1,2],[1,0,3],[2,2,0]],
                  "1": [[0,2,1],[2,0,2],[1,3,0]]},
 "Compatibility":{"0": [1, 1, 1], "1": [1, 0, 1]},
 "readyTime":    {"0": 2, "1": 0},
 "minimumJobs":  {"0": 0, "1": 0}, "maximumJobs": {"0": 3, "1": 3}}
```

Schedule: machine 0 runs job 1; machine 1 runs job 2 then job 0.

- Machine 0: `C_0 = 2 (ready) + 3 (p of job 1) = 5`.
- Machine 1: `C_1 = 0 (ready) + 4 (p of job 2) + 1 (setup 2->0) + 6 (p of job 0) = 11`.
- Makespan `= max(5, 11) = 11`. Eligibility holds (job 1 is only on
  machine 0; machine 1 runs jobs 0 and 2, both eligible there).

## Niche generator parameters (locked set)

`kilit_nis_uret.py` produced the 84 locked instances with
`niche_generator.write_instance`: 14 cells (8 standard sizes 50×10 … 800×30
at setup range `t99`, two boundary cells 800×40 and 400×80 at `t99`, and
400×20 / 800×30 at `t9` and `t49`), 6 instances per cell, seeds
`"kilit2026_{n}x{m}_t{tau}_{i}"`, `rho = 0.2`, `elig_p = 0.5` (random
mode). Processing times are drawn from `U[1, 99]` (the Vallada & Ruiz
range), setup times from `U[1, tau]`, and machine ready times as
`r_l = round(u_l · rho · (n/m) · 50)` with `u_l ∈ [0, 1)`; the ROUNDED cap
`round(rho · (n/m) · 50)` is recorded per instance as `r_max` in `_gen` and
in the set's `manifest.json` (e.g. 800×30: scale 266.67, recorded
`r_max = 267`). The generation is
deterministic: re-running the script reproduces all 84 JSON and binary
files hash-identically (compare against `instance_manifests/`).

## Raw Vallada text format and the conversion

The Vallada & Ruiz (2011) files (`I_{n}_{m}_S_{range}_{rep}.txt`) are plain
text:

```
line 1:            n  m  <flag>
line 2:            m
next n lines:      "0 p_{i,0}  1 p_{i,1} ..."   (machine index, processing time pairs)
"SSD"
for each machine k: "M{k}" then an n×n setup matrix (row i, column j = setup i->j, diagonal 0)
```

`vallada_to_hlbb.py` maps this to the JSON schema value-for-value (no
rounding, no renumbering): `processTime["k"][i]` = the pair value,
`setupTime["k"]` = the matrix as printed, plus the pure-problem filler
fields (all-ones `Compatibility`, all-zero `readyTime`, non-binding
cardinality). `kilit_saf_veri_denetimi.py` is the cell-by-cell audit of
that claim over the 72 locked files (see MANIFEST for its path caveat).

## Binary bridge format (`.nbin`)

The Julia baselines read a compact little-endian binary written by
`niche_bridge.json_to_bin` instead of parsing JSON:

```
n: Int32, m: Int32
ready: Int32[m]
elig:  Int8 matrix, stored so Julia reads E[machine, job]
proc:  Int32 matrix, stored so Julia reads P[machine, job]
setup: m consecutive Int32 n×n blocks; S[l][i,j] = setup i->j on machine l
```

(NumPy row-major arrays are written transposed so column-major Julia sees
the intended orientation; see the docstring of `niche_bridge.py`.)
