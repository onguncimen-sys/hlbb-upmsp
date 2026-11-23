# NOTICE — third-party code

This directory contains the reproducible capsule of

> G. A. Rolim and M. S. Nagano, *Designing state-of-the-art metaheuristics:
> What have we learned from the parallel-machine scheduling problem with
> setups?*, Computers & Operations Research 182 (2025) 107110.
> Code Ocean capsule: https://codeocean.com/capsule/3793251/tree/v1

It is redistributed under its own MIT License, reproduced unchanged in
`code/LICENSE` (Copyright (c) 2023 Gustavo Alencar Rolim). All twelve
algorithms of the original capsule are included; the algorithmic content of
the nine we did not extend is untouched, but every algorithm file carries a
one-line mechanical harness adaptation (and four — SA, HGA, FSS, MSA — a
time-to-best stopwatch; GA has none, which is why its runs record
`tbest = -1`) — enumerated as "Layer 1" in `MODIFICATIONS.md`, with the
SHA-256 of the pristine CodeOcean download recorded there.

## What we changed

Three algorithms were extended to machine eligibility and machine ready times
for the niche problem of our paper. The pre-extension baselines (pristine
plus the Layer-1 adaptations) are kept beside them with a `.orig` suffix, so
any reader can diff the two.

| file | original | changed lines |
|---|---|---|
| `code/Algorithms/SA/SA.jl`   | `SA.jl.orig`  | 99 |
| `code/Algorithms/HGA/HGA.jl` | `HGA.jl.orig` | 62 |
| `code/Algorithms/GA/GA.jl`   | `GA.jl.orig`  | 68 |
| `code/run_one.jl`            | `run_one.jl.orig` | 52 (driver: niche mode, binary input via `parse_niche_bin`, solution export) |

Counts are for the production versions that produced the locked runs,
measured as `diff <file>.orig <file> | grep -c '^[<>]'`. Details and the
SHA-256 of the originals: `MODIFICATIONS.md`, `ORIG_SHA256.txt`.

The extensions are structural: operators act inside the legal space and no
penalty terms are used. With the constraints switched off and the extension flags/tuning variables
(`DELTAINS_FIX`, `HGA_DINS`, `GA_PM`) unset, each extended implementation
reproduces its `.orig` baseline bit for bit over the six-seed bench; the tests
that check this are `code/equiv_{sa,hga,ga}_test.jl` (Julia side) and
`validate_algo.py` (driver) in the repository root.

Files added by us: `equiv_*_test.jl`, `feas_*_test.jl`, `bridge_check.jl`,
`*.orig`.
