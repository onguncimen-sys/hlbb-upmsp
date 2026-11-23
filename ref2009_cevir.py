# -*- coding: utf-8 -*-
"""Converts the reference file published in 2009 (BoundsP_SDST_Large.xls) to
results/ref2009_large.csv for the 72 instances of the locked pure test.
Columns: size,aralik,inst,ref2009. For the DESCRIPTIVE column only; never given
to the algorithms (Appendix C item 4).
Run: ./venv/bin/python3 lit_gece/araclar/ref2009_cevir.py"""
import csv
import os

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
XLS = "/home/sarp/İndirilenler/RSDSTSol/BoundsP_SDST_Large.xls"
OUT = os.path.join(ROOT, "results", "ref2009_large.csv")
SIZES = ["50_30", "150_30", "100_10", "200_10"]
RANGES = ["1-9", "1-49", "1-99"]

df = pd.read_excel(XLS, header=0)
df.columns = ["Instance", "n", "m", "ref2009"]
ref = {str(r["Instance"]).strip(): float(r["ref2009"]) for _, r in df.iterrows()}

with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["size", "aralik", "inst", "ref2009"])
    say = 0
    for s in SIZES:
        n, m = s.split("_")
        for r in RANGES:
            for i in range(1, 7):
                w.writerow([s, r, i, ref[f"I_{n}_{m}_S_{r}_{i}"]])
                say += 1
print(f"YAZILDI: {OUT} ({say} satir)")
