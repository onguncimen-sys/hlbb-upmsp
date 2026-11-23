# -*- coding: utf-8 -*-
"""Generates the per-instance appendix longtables (Track A + Track B) ->
paper/per_instance_tables.tex.
B = the TRUE per-instance best solution (min over SA's BEST seed + HLBB + CP; NOT a mean).
SA and HLBB makespan columns = RUN MEAN (multiple repeats); RPD = mean of per-run RPDs.
CP is a single run. The smallest RPD (winner) is bold. (2026-08-10: HLBB moved to 3 repeats;
the old code treated HLBB as single-valued and kept the LAST seed — switched to the general
accumulator.)"""
import csv
from collections import defaultdict
from statistics import mean

OUT = "paper/per_instance_tables.tex"
# 2026-10-22: Track A now comes from the LOCKED PURE run (results/kilitli_saf.csv; the old
# track_a.csv = development data, cannot produce paper tables). Denominators are track-specific:
# Track A B = best per-instance REPEAT-MEAN of the five methods (pre-registered, Appendix C),
# Track B B = best of any single run (previous definition, until the niche lock).
TRACK_A_SIZES = ["50_30", "150_30", "100_10", "200_10"]
TRACK_A_RANGES = ["1-9", "1-49", "1-99"]
TRACK_B_SIZES = ["50x10", "100x15", "150x15", "200x20", "250x20", "400x20", "640x25", "800x30"]
# 2026-10-26: Track B also comes from the LOCKED NICHE run (results/kilitli_nis.csv; App. D).
# The denominator now matches Track A: best per-instance REPEAT-MEAN of the five methods.
KILIT_NIS_HUCRELER = [("50_10","t99"),("100_15","t99"),("150_15","t99"),
    ("200_20","t99"),("250_20","t99"),("400_20","t99"),("640_25","t99"),
    ("800_30","t99"),("800_40","t99"),("400_80","t99"),
    ("400_20","t9"),("400_20","t49"),("800_30","t9"),("800_30","t49")]


def load(csvpath):
    rows = list(csv.DictReader(open(csvpath)))
    for r in rows:
        r["makespan"] = int(r["makespan"]); r["rep"] = int(r["rep"])
    acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        acc[(r["size"], r["rep"])][r["method"]].append(r["makespan"])
    return acc


def fmt(v):
    return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"


def load_kilit(csvpath="results/kilitli_saf.csv"):
    acc = defaultdict(lambda: defaultdict(list))
    for r in csv.DictReader(open(csvpath)):
        acc[(r["size"], r["aralik"], int(r["inst"]))][r["method"]].append(float(r["makespan"]))
    return acc


def rows_kilit(acc, size, aralik, meths):
    """Locked pure: makespan = repeat mean; B = best METHOD MEAN
    (pre-registered Track A denominator); RPD computed on the means."""
    out = []
    for inst in range(1, 7):
        runs = acc[(size, aralik, inst)]
        mu = {m: mean(runs[m]) for m in meths}
        B = min(mu.values())
        rpd = {m: (mu[m] - B) / B * 100 for m in meths}
        rounded = {m: round(v, 1) for m, v in rpd.items()}
        bmin = min(rounded.values())
        rcell = {m: (r"\textbf{" + f"{rpd[m]:.1f}" + "}" if rounded[m] == bmin
                     else f"{rpd[m]:.1f}") for m in meths}
        out.append((inst, {m: fmt(mu[m]) for m in meths}, fmt(B), rcell))
    return out


def rows_for(acc, size, reps, meths=("SA", "HLBB", "CP")):
    out = []
    for rep in reps:
        k = (size, rep)
        if k not in acc or "SA" not in acc[k]:
            continue
        runs = acc[k]                       # {method: [run makespans]}
        B = min(v for vals in runs.values() for v in vals)
        rpd = {m: (mean([(x - B) / B * 100 for x in runs[m]]) if m in runs else None)
               for m in meths}
        mk = {m: (fmt(mean(runs[m])) if m in runs else "--") for m in meths}
        rounded = {m: round(rpd[m], 1) for m in rpd if rpd[m] is not None}
        bmin = min(rounded.values())
        rcell = {}
        for m in meths:
            s = f"{rpd[m]:.1f}" if rpd[m] is not None else "--"
            if rpd[m] is not None and rounded[m] == bmin:
                s = r"\textbf{" + s + "}"
            rcell[m] = s
        out.append((rep, mk, fmt(B), rcell))
    return out


def emit_longtable(f, label, caption, size_rows, meths=("SA", "HLBB", "CP")):
    k = len(meths)
    hdr = " & ".join(meths)
    f.write(r"\begin{longtable}{l " + "c" * k + " c " + "c" * k + "}\n")
    f.write(r"\caption{" + caption + r"}\label{" + label + r"}\\" + "\n")
    f.write(r"\toprule" + "\n")
    f.write(rf"& \multicolumn{{{k}}}{{c}}{{Makespan}} & & \multicolumn{{{k}}}{{c}}{{RPD (\%)}} \\"
            + "\n")
    f.write(rf"\cmidrule(lr){{2-{k+1}}}\cmidrule(lr){{{k+3}-{2*k+2}}}" + "\n")
    f.write(rf"Instance & {hdr} & $B$ & {hdr} \\" + "\n")
    f.write(r"\midrule\endfirsthead" + "\n")
    f.write(rf"\toprule Instance & {hdr} & $B$ & {hdr} \\\midrule\endhead" + "\n")
    f.write(r"\bottomrule\endfoot" + "\n")
    for szlabel, rr in size_rows:
        for (rep, mk, b, rc) in rr:
            f.write(f"{szlabel}-{rep} & " + " & ".join(mk[m] for m in meths)
                    + f" & {b} & " + " & ".join(rc[m] for m in meths) + r" \\" + "\n")
        f.write(r"\midrule" + "\n")
    f.write(r"\end{longtable}" + "\n\n")


def main():
    accA = load_kilit()
    accB = load_kilit("results/kilitli_nis.csv")
    capA = ("SA, HGA, GA and HLBB report the mean over their three runs; CP is a single "
            "run at $1000\\,$s. $B$ is the best per-instance method mean, the "
            "pre-registered Track A denominator of Section~\\ref{sec:fair}; RPD is "
            "computed on the method means and the lowest of each instance is in bold.")
    cap = ("SA, HGA, GA and HLBB report the mean over their three runs; CP is a single "
           "run at $1000\\,$s. $B$ is the best per-instance method mean, the "
           "pre-registered Track B denominator of Section~\\ref{sec:fair}; RPD is "
           "computed on the method means and the lowest of each instance is in bold. "
           "The last six blocks are the boundary and dose cells "
           "(two boundary, four dose).")
    mA = ("SA", "HGA", "GA", "CP", "HLBB")
    with open(OUT, "w") as f:
        f.write("% OTOMATIK URETILDI: gen_appendix_tables.py -- ELLE DUZENLEME\n\n")
        arows = []
        for sz in TRACK_A_SIZES:
            for ra in TRACK_A_RANGES:
                lab = sz.replace("_", r"$\times$") + ", $" + ra.replace("-", "$--$") + "$"
                arows.append((lab, rows_kilit(accA, sz, ra, mA)))
        emit_longtable(f, "app:trackA-inst",
                       "Track A per-instance results (locked pure test). " + capA, arows, mA)
        brows = []
        for sz, ar in KILIT_NIS_HUCRELER:
            et = {"t9": "1-9", "t49": "1-49", "t99": "1-99"}[ar]
            lab = sz.replace("_", r"$\times$") + ", $" + et.replace("-", "$--$") + "$"
            brows.append((lab, rows_kilit(accB, sz, ar, mA)))
        emit_longtable(f, "app:trackB-inst",
                       "Track B per-instance results (locked niche test). " + cap,
                       brows, mA)
    import os
    print("YAZILDI:", os.path.abspath(OUT), f"({os.path.getsize(OUT)} B)")
    print("Track A:", sum(len(r) for _, r in arows), "| Track B:", sum(len(r) for _, r in brows))


if __name__ == "__main__":
    main()
