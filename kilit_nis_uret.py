# -*- coding: utf-8 -*-
"""LOCKED NICHE TEST — instance generation (EK-B extended matrix).

14 cells × 6 instances = 84 fresh-seed instances -> nis_kilit2026/{n}_{m}_t{tau}/instance_{i}.json
+ .nbin (bridge for the Julia capsule) + manifest.json + JSON_SHA256.txt + NBIN_SHA256.txt.

Seeds: "kilit2026_{n}x{m}_t{tau}_{i}" — they collide with no seed used during development
(development inventory: integers 1-6, 101-103, "tarama2026_*" strings; the script VERIFIES this).
Regime: elig_p=0.5 (random), rho=0.2 (ron) — same distribution as the development niche,
only the seeds are new.
Run: ./venv/bin/python3 lit_gece/araclar/kilit_nis_uret.py
"""
import glob
import hashlib
import json
import os
import sys

# RELEASE ADAPTATION (one line): in the dev repository this file lived under lit_gece/araclar/
# and ROOT was two directories up; in the package it sits at the root, so ROOT = script dir.
ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, ROOT)
from niche_generator import write_instance, RHO_LEVELS, ELIG_P  # noqa: E402
from niche_bridge import json_to_bin  # noqa: E402

OUT = os.path.join(ROOT, "nis_kilit2026")
RHO = RHO_LEVELS["ron"]          # 0.2
INSTS = range(1, 7)

# 14 cells: 8 standard (t99) + 2 boundary (t99) + 4 dose (400x20/800x30 × t9/t49)
HUCRELER = ([(n, m, 99) for (n, m) in [(50, 10), (100, 15), (150, 15), (200, 20),
                                       (250, 20), (400, 20), (640, 25), (800, 30),
                                       (800, 40), (400, 80)]] +
            [(n, m, t) for (n, m) in [(400, 20), (800, 30)] for t in (9, 49)])


def dev_tohumlari():
    """Inventory of all (generator) seeds used during development."""
    tohum = set()
    for man in ["new_dataset_niche/manifest.json", "new_dataset_niche_v2/manifest.json",
                "new_dataset_niche_b3/manifest.json", "new_dataset_sens/manifest.json"]:
        p = os.path.join(ROOT, man)
        if os.path.exists(p):
            tohum |= {x["seed"] for x in json.load(open(p))}
    for f in glob.glob(os.path.join(ROOT, "new_dataset_devscan", "**", "*.json"), recursive=True) + \
             glob.glob(os.path.join(ROOT, "new_dataset_niche_v2_holdout", "**", "*.json"), recursive=True):
        try:
            g = json.load(open(f)).get("_gen", {})
            if "seed" in g:
                tohum.add(g["seed"])
        except Exception:
            pass
    return tohum


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    dev = dev_tohumlari()
    manifest, j_sha, b_sha = [], [], []
    for (n, m, t) in HUCRELER:
        ddir = os.path.join(OUT, f"{n}_{m}_t{t}")
        os.makedirs(ddir, exist_ok=True)
        for i in INSTS:
            seed = f"kilit2026_{n}x{m}_t{t}_{i}"
            assert seed not in dev, f"TOHUM CAKISMASI: {seed}"
            jp = os.path.join(ddir, f"instance_{i}.json")
            bp = os.path.join(ddir, f"instance_{i}.nbin")
            d = write_instance(n, m, t, RHO, seed, jp, ELIG_P)
            json_to_bin(jp, bp)
            rel = os.path.relpath(jp, OUT)
            relb = os.path.relpath(bp, OUT)
            j_sha.append(f"{sha(jp)}  {rel}")
            b_sha.append(f"{sha(bp)}  {relb}")
            manifest.append({"hucre": f"{n}_{m}_t{t}", "inst": i, "nJob": n, "nMachine": m,
                             "tau": t, "rho": RHO, "elig_p": ELIG_P, "seed": seed,
                             "r_max": d["_gen"]["r_max"], "json": rel, "nbin": relb})
    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)
    open(os.path.join(OUT, "JSON_SHA256.txt"), "w").write("\n".join(j_sha) + "\n")
    open(os.path.join(OUT, "NBIN_SHA256.txt"), "w").write("\n".join(b_sha) + "\n")
    print(f"URETILDI: {len(manifest)} ornek ({len(HUCRELER)} hucre x 6) -> {OUT}")
    print(f"gelistirme tohumu envanteri: {len(dev)} tohum tarandi, cakisma yok")


if __name__ == "__main__":
    main()
