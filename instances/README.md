# Instances

Two instance sets back the paper's reported comparisons. Neither is stored
in this Git repository; both are verifiable against
`../instance_manifests/`. Formats: `../INSTANCE_FORMAT.md`.

## Niche set, Track B (`nis_kilit2026/`, ours)

84 locked instances (14 cells × 6), each as JSON and as the compact binary
the Julia baselines read; ~5 GB raw. Two equivalent ways to obtain them:

1. **Download** the data archive (10.5281/zenodo.24198707, CC BY 4.0) and unpack it
   beside the code as `nis_kilit2026/`.
2. **Regenerate** them deterministically:

   ```bash
   python3 kilit_nis_uret.py
   ```

   The generator derives every instance from the string seed
   `kilit2026_{n}x{m}_t{tau}_{i}` (disjoint by construction from every
   development seed), writes `nis_kilit2026/` with a parameter
   `manifest.json`, and emits its own SHA-256 lists.

Either way, verify:

```bash
( cd nis_kilit2026 && sha256sum -c ../instance_manifests/nis_kilit2026_JSON_SHA256.txt \
                   && sha256sum -c ../instance_manifests/nis_kilit2026_NBIN_SHA256.txt )
```

(Both manifests list paths relative to `nis_kilit2026/`; the JSON manifest
as `{n}_{m}_t{tau}/instance_{i}.json`, the NBIN manifest as
`{n}_{m}_t{tau}/instance_{i}.nbin`.)

The DEVELOPMENT niche sets (`new_dataset_niche_v2` for the development
benchmarks and ablation, `new_dataset_sens` for the configuration study,
seeds offset by 100) are reproducible from `niche_generator.py` the same
way but are not part of the reported comparison; the locked test uses only
`nis_kilit2026/`.

## Pure set, Track A (Vallada & Ruiz 2011, not redistributed)

These are **not ours to redistribute**, raw or converted: they are the
published library of

> E. Vallada and R. Ruiz, *A genetic algorithm for the unrelated parallel
> machine scheduling problem with sequence dependent setup times*,
> European Journal of Operational Research 211(3), 2011.

⚠️ The original host `http://soa.iti.es` is no longer reachable. We
obtained the library from the Internet Archive (snapshot dated
2013-07-15; accessed 2026-06-19 for `RSDST.7z` and 2026-07-13 for
`RSDSTSol.7z`):

```
http://web.archive.org/web/20130715180901/http://soa.iti.es/files/RSDST.7z
https://web.archive.org/web/2013id_/http://soa.iti.es/files/RSDSTSol.7z
```

SHA-256 of the archives as downloaded:

```
bf87d6128d1033cdb04ce033e595c5d8a9f89a7df7d67200f7eb0712faf7a7ea  RSDST.7z
502da9dbca75f7f17b038d0bef6fd0f5de1f0d09b923e84bc8471042dc5354b5  RSDSTSol.7z
```

`RSDST.7z` holds the instances (`large/`: 1000 files, `small/`: 640 files,
with their original 2007 timestamps). `RSDSTSol.7z` holds the 2009
best-known-value spreadsheets, used only as context (`ref2009_large.csv`),
not in any reported comparison.

The locked pure test uses 72 of the `large/` files — four configurations
(50×30, 150×30, 100×10, 200×10) × three setup ranges (1-9, 1-49, 1-99) ×
six replicates — unmodified. The full recipe (download → SHA-256 check of
the 72 raw files → `vallada_to_hlbb.py` conversion → SHA-256 check of the
72 converted files) is in the root `README.md` under "Getting the
instances"; the conversion changes no value, and
`kilit_saf_veri_denetimi.py` re-audits that cell by cell.
