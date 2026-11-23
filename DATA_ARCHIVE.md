# Data archive (separate Zenodo record) — content inventory

The code repository stays small; bulk data goes to a SEPARATE Zenodo record
under CC BY 4.0. The two records cross-link each other, and the paper cites
both version DOIs. This file fixes WHAT goes into the data record.

**Packaged on 2026-11-11** (author-run; post-pack verification: unpack,
counts 84+84+3 / 84 / 72, inner SHA lists 168/168 OK, all 156 logs
byte-identical to source; `SHA256SUMS.txt` beside the tars):

```
ddaae41fc87d47852ae89202ece8736bd82c0f1704b10d58800dd233bce84893  locked_niche_2026_v1.tar.gz    (1.41 GiB; 1,517,467,401 bytes)
a705e9d20d37ea4236299c98bdc8a60424b77647af1d655468369ed78fdf4263  locked_niche_cp_logs_v1.tar.gz (131 MiB; 137,178,101 bytes)
284164324726e7a28c8bd090a71cf570635f8a64f7da7d7a7b9ad4972ae969ad  locked_pure_cp_logs_v1.tar.gz  (95 MiB; 100,128,456 bytes)
```

**Renamed on 2026-11-13** (public download names anglicized; the tars were
renamed only — not repacked — so the three content digests above are
unchanged; verified with `sha256sum -c` after the rename). Former names:
`nis_kilit2026_v1.tar.gz`, `kilitli_nis_cp_logs_v1.tar.gz`,
`kilitli_saf_cp_logs_v1.tar.gz`. The copies of the four
`instance_manifests/` files in the data record were likewise renamed
(byte-identical): `locked_niche_2026_{JSON,NBIN}_SHA256.txt`,
`valladapure_locked_{RAW,JSON}_SHA256.txt`. Internal paths, script names
and the `instance_manifests/` originals keep their names for traceability
to the pre-registered commits; the record README's "Naming" section carries
the full mapping and glossary.

The data record additionally ships: a byte-identical copy of the release's
`INSTANCE_FORMAT.md`, renamed byte-identical copies of the four manifests
from `instance_manifests/`, `SHA256SUMS.txt`,
and the record README (draft: `_koken/VERI_KAYDI_README_taslak.md`; the
CP-log tars carry no top directory and unpack INTO
`results/kilitli_{nis,saf}_cozumler/`).

## Record contents

1. **Niche instances (locked niche test set)** — source `nis_kilit2026/`
   (dev repo): 14 cells × 6 instances = 84 instances, each as JSON and as
   the compact binary used by the Julia rivals (84 + 84 files; ~5 GB raw,
   shipped compressed). Their SHA-256 manifests are ALSO shipped in the
   code repo (`instance_manifests/nis_kilit2026_{JSON,NBIN}_SHA256.txt`),
   so the data record and the code record can be checked against each
   other. The seeded producer (`kilit_nis_uret.py` on top of
   `niche_generator.py`, both in the code repo) reproduces all 84
   instances hash-identically.
2. **CP solver logs of the locked niche runs** — source
   `results/kilitli_nis_cozumler/cp_log_*.txt` (dev repo): 84 text logs,
   ~1.01 GB raw; to be shipped compressed. These support the CP arm's
   reported behaviour (optimality status, bounds over time).
3. **CP solver logs of the locked pure runs** — source
   `results/kilitli_saf_cozumler/cp_log_*.txt` (dev repo): 72 text logs,
   ~766 MB raw; to be shipped compressed. (Added in Session 4: the earlier
   inventory covered only the niche logs.)
4. NOT in the data record, because they are small enough for the CODE
   repository: the per-run solution schedules of both locked tests,
   `results/kilitli_nis_cozumler/cozumler.jsonl` (2.4 MB, 1092 records;
   SHA-256 prefix `e291c00bea33e4fc`) and
   `results/kilitli_saf_cozumler/cozumler.jsonl` (608 KB, 936 records;
   SHA-256 prefix `f8db911701110a12`). The README documents the command
   that re-verifies every record against the instance files (tested on all
   2028 records); the local-optimality probe (`_kilit_nis_sonda.py`) reads
   the niche file directly. (Revised from the earlier plan that sent the
   whole 1 GB directory to the data archive: the bulk is the CP logs, not
   the solutions.)

## Not redistributed anywhere

The Vallada & Ruiz (2011) pure-benchmark instances, raw or converted
(decision recorded in `VAAT_TABLOSU.md`): the README's acquisition recipe +
`instance_manifests/valladapure_*` + `vallada_to_hlbb.py` replace
redistribution.

## Licence

Data record: CC BY 4.0 (our generated instances and our run artefacts).
The CP logs contain solver output of IBM CP Optimizer runs on our
instances; no solver binaries or licensed material are included.
