# Modifications to the Rolim et al. capsule

Source: the public CodeOcean capsule of Rolim and Nagano (2025),
"Designing state-of-the-art metaheuristics: What have we learned from the
parallel-machine scheduling problem with setups?" (C&OR 182, 107110),
https://codeocean.com/capsule/3793251 — MIT licence (see NOTICE.md). The
capsule was added to our development repository on 2026-08-14; the original
`environment/` and `metadata/` directories are kept unchanged as provenance
(they describe the ORIGINAL capsule, including its Julia 1.7.0 image, not
our modifications).

## Change layers

Differences from the pristine capsule fall into THREE layers, each fully
enumerable. SHA-256 of the pristine CodeOcean download
(`capsule-3793251.zip`):
`8461ae3614ca8602cc45ed43cee58d5ea07b143974f2d7ec31e8626a04b77f0f`.
`Main.jl` and `Input.jl` are byte-identical to that download.

### Layer 1 — mechanical harness adaptations (2026-08-14, at capsule import)

Applied so OUR harness could drive the capsule; no algorithmic content was
changed:

- **Budget-type widening, all twelve algorithm files** (one line each): the
  budget parameter was declared `t::Int8` in the original. Its unit is the
  capsule's own scale (real seconds ≈ `n·m·t/2000`; our driver inverts
  this at `run_one.jl`: `t = round(Int, wall·2000/(n·m))`), so a 200 s
  wall-clock implies `t` values above the Int8 limit of 127 on the smaller
  sizes (e.g. 50×30 → `t = 267`), and the driver passes an `Int` in any
  case, which the original `t::Int8` signature would not accept. The
  signature was therefore widened to `t::Int`.
- **Time-to-best instrumentation** in FOUR files — `SA.jl`, `HGA.jl`,
  `FSS.jl` and `MSA/MultiStart.jl`: a `tbest` stopwatch and a fourth return
  value (read by the driver's RESULT line). `GA.jl` carries NO stopwatch at
  this layer; its extended version returns a constant `-1.0` placeholder as
  the fourth value (a Layer-2 driver-interface addition), which is why the
  result files record `tbest = -1` for GA.
- **`Modules.jl` include paths**: the original uses CodeOcean container
  paths (`/code/Algorithms/...`), which cannot resolve outside that
  container; the development copy used machine-absolute paths, and THIS
  RELEASE uses file-relative paths (`Algorithms/...`). What this makes
  portable is OUR `run_one.jl` driver chain
  (`run_one.jl → Modules.jl → Algorithms/...`), which runs wherever the
  capsule is unpacked; the capsule's own demo path (`run → Main.jl`) is NOT
  made portable — `Input.jl` keeps its original container default and
  `Main.jl` still constructs an `Int8` budget. Pristine copy:
  `Modules.jl.orig`.

Behavioural scope of this layer, stated precisely: the search operators and
every RNG call are untouched; what changed is the driver interface
(signature, return arity) and time measurement. The added `time()` reads do
not consume random numbers, but under a WALL-CLOCK budget they can shift
how many iterations fit; no fixed-time result equality with the pristine
capsule is claimed (the equivalence benches below run under FIXED ITERATION
COUNTS for exactly this reason).

The `*.jl.orig` files of SA/HGA/GA are snapshots of THIS layer, NOT the
pristine files — they are the exact baselines the equivalence benches
compare against. The pristine state of every file is recoverable from the
zip hash above; the remaining nine algorithms (ALNS-TS, FACL, GALA, HABC,
SSAFA, VNS-AiNet, WOAFA — and FSS and MSA beyond their stopwatch) differ
from pristine ONLY by Layer 1. `run`, `Readme.md`, `LICENSE`, `Example/`,
`environment/` and `metadata/` are byte-identical to the pristine capsule;
the root-level `metadata.yml` is our byte-identical convenience copy of
`metadata/metadata.yml`.

### Layer 2 — our niche extensions (the four substantively modified files)

Counts measured as `diff <file>.orig <file> | grep -c '^[<>]'` on the
production versions that produced the locked runs.

| File | Changed lines (vs the Layer-1 `.orig`) | What was added |
|---|---|---|
| `code/Algorithms/SA/SA.jl`   | 99 | machine-eligibility and machine-ready-time handling |
| `code/Algorithms/HGA/HGA.jl` | 62 | same two side constraints; `DELTAINS_FIX`-guarded delta-insertion correction |
| `code/Algorithms/GA/GA.jl`   | 68 | same two side constraints; `DELTAINS_FIX`-guarded delta-insertion correction |
| `code/run_one.jl`            | 52 | per-run driver: niche mode, binary instance input (`parse_niche_bin`), solution export |

Design rule of the extension: with the side constraints switched OFF and the
extension flags/tuning variables (`DELTAINS_FIX`, `HGA_DINS`, `GA_PM`) unset,
each extended file reproduces its Layer-1 baseline bit for bit over the
six-seed equivalence bench below (a bench result, not a universal proof over
all inputs); with the constraints ON, every reported solution passes the
independent feasibility checker. Parameters that the niche setting overrides
(`HGA_DINS`, `GA_PM`) and the `DELTAINS_FIX` flag are set through environment
variables by the Python runners, never by editing further capsule files.

### Layer 3 — our additions beside the capsule

The test benches below and `run_one.jl` itself (the per-run driver; its
`.orig` is our pre-extension version of that driver).

## Added test benches (ours, not part of the original capsule)

- `code/equiv_{sa,hga,ga}_test.jl` — fixed-iteration equivalence harness:
  runs original vs extended implementation with constraints off and compares
  outputs bit for bit (6 seeds).
- `code/feas_{sa,hga,ga}_test.jl` — feasibility smoke benches with the
  constraints on.
- `code/gate_deltains_test.jl` — acceptance bench for the `DELTAINS_FIX`
  correction.
- `code/bridge_check.jl` — instance-bridge consistency check.

Correction record (2026-11-11, release-validation sweep): an earlier
version of this file stated that the nine non-extended algorithms and
`Modules.jl` were "unmodified" — that was inaccurate; their exact
differences from pristine are the Layer-1 adaptations enumerated above,
found by a full diff against the pristine zip.
