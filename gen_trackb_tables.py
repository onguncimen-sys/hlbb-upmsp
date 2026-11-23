#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Track B (locked niche) table/figure generator — source results/kilitli_nis.csv.

Output: paper/tab_trackb_cells.tex  (main table: 10 cells t99, 5 methods)
        paper/tab_trackb_conf.tex   (Appendix D confirmatory m=8: paired t + Holm)
        paper/tab_trackb_doz.tex    (descriptive dose: 2 sizes x 3 ranges)
        paper/fig_scale.tex         (8 standard sizes t99, 5 methods)
Appendix D definitions verbatim: unit = instance, repeat mean; denominator = the best
per-instance repeat-mean of the five methods. NO NUMBERS ENTERED BY HAND."""
import csv, math, os, statistics as st
from collections import defaultdict
from scipy import stats as sps

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "results", "kilitli_nis.csv")

ANA = ["50_10", "100_15", "150_15", "200_20", "250_20", "400_20", "640_25", "800_30"]
SINIR = ["800_40", "400_80"]
DOZ = ["400_20", "800_30"]
METS = ["SA", "HGA", "GA", "CP", "HLBB"]
RAKIP = ["SA", "HGA", "GA", "CP"]
CONF = [("400_20", "t99"), ("800_30", "t99")]


def _lab(sz):
    n, m = sz.split("_")
    return f"{n}$\\times${m}"


def _oku():
    r = list(csv.DictReader(open(CSV)))
    assert len(r) == 1092, len(r)
    g = defaultdict(list)
    for x in r:
        g[(x["size"], x["aralik"], int(x["inst"]), x["method"])].append(float(x["makespan"]))
    mo = {k: st.mean(v) for k, v in g.items()}
    rpd = {}
    for (sz, ar, i, m) in list(mo):
        b = min(mo[(sz, ar, i, mm)] for mm in METS)
        rpd[(sz, ar, i, m)] = 100.0 * (mo[(sz, ar, i, m)] - b) / b
    return mo, rpd


def _cellstats(rpd, sz, ar):
    out = {}
    for m in METS:
        v = [rpd[(sz, ar, i, m)] for i in range(1, 7)]
        out[m] = (st.mean(v), st.stdev(v))
    return out


def _fmt(mu, sd, bold):
    s = f"{mu:.1f}\\,$\\pm$\\,{sd:.1f}"
    return f"\\textbf{{{s}}}" if bold else s


def tab_cells(rpd):
    out = [
        "% OTOMATIK URETILDI: gen_trackb_tables.py (kaynak results/kilitli_nis.csv) -- ELLE DUZENLEME YOK",
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Track~B, average RPD (\%) on the locked niche test at setup",
        r"range $1$--$99$: eight standard sizes and the two boundary cells, six",
        r"instances per cell. Stochastic methods use the three-seed mean per",
        r"instance; CP is a single run at $1000\,$s against the metaheuristics'",
        r"$200\,$s. $B$ is the best of the five methods' per-instance means, the",
        r"pre-registered Track~B denominator of Section~\ref{sec:fair}. Values are",
        r"the mean $\pm$ the standard deviation over the six instances; the best",
        r"of each row is in bold. The dose cells are in",
        r"Table~\ref{tab:trackB-doz}; per-instance results are in",
        r"Appendix~\ref{app:per-instance}.}\label{tab:trackB-hh}",
        r"\small",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{tabular}{lccccc}",
        r"\toprule",
        r"Size ($n\times m$) & SA & HGA & GA & CP & HLBB \\",
        r"\midrule",
    ]
    for sz in ANA + SINIR:
        if sz == SINIR[0]:
            out.append(r"\midrule")
        cs = _cellstats(rpd, sz, "t99")
        best = min(METS, key=lambda m: cs[m][0])
        hucre = " & ".join(_fmt(*cs[m], bold=(m == best)) for m in ("SA", "HGA", "GA", "CP", "HLBB"))
        out.append(f"{_lab(sz)} & {hucre} \\\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(out)


def conf_rows(mo, rpd):
    rows = []
    for sz, ar in CONF:
        for rv in RAKIP:
            d = [rpd[(sz, ar, i, rv)] - rpd[(sz, ar, i, "HLBB")] for i in range(1, 7)]
            ham = [mo[(sz, ar, i, rv)] - mo[(sz, ar, i, "HLBB")] for i in range(1, 7)]
            n = len(d)
            mu, sd = st.mean(d), st.stdev(d)
            t = mu / (sd / math.sqrt(n))
            p = 2 * sps.t.sf(abs(t), n - 1)
            h = sps.t.ppf(0.975, n - 1) * sd / math.sqrt(n)
            rows.append(dict(sz=sz, rv=rv, mu=mu, lo=mu - h, hi=mu + h, p=p,
                             ham=st.mean(ham),
                             w=sum(1 for x in d if x > 0), l=sum(1 for x in d if x < 0)))
    sira = sorted(range(8), key=lambda k: rows[k]["p"])
    enb = 0.0
    for j, k in enumerate(sira):
        enb = max(enb, (8 - j) * rows[k]["p"])
        rows[k]["ph"] = min(1.0, enb)
    return rows


def _texp(p):
    if p >= 0.001:
        return f"{p:.4f}".rstrip("0")
    e = int(math.floor(math.log10(p)))
    return f"{p / 10 ** e:.1f}\\times 10^{{{e}}}"


def tab_conf(rows):
    out = [
        "% OTOMATIK URETILDI: gen_trackb_tables.py (kaynak results/kilitli_nis.csv) -- ELLE DUZENLEME YOK",
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Track~B, the eight pre-registered comparisons: the two largest",
        r"standard cells at setup range $1$--$99$, each against the four rivals.",
        r"$\hat\Delta$ is the mean over the six instances of the per-instance RPD",
        r"difference (rival minus HLBB, in RPD points), so positive values favour",
        r"HLBB; the interval is the per-comparison $95\%$ paired $t$-interval",
        r"(five degrees of freedom), without multiplicity adjustment. $p$-values",
        r"are two-sided and Holm-adjusted over the single family of all eight",
        r"comparisons. The last column is the same difference in raw makespan",
        r"units.}\label{tab:trackB-conf}",
        r"\small",
        r"\setlength{\tabcolsep}{6pt}",
        r"\begin{tabular}{llcccc}",
        r"\toprule",
        r"Cell & HLBB vs & $\hat\Delta$ (RPD points) & $95\%$ CI & Holm $p$ & Makespan \\",
        r"\midrule",
    ]
    for k, r in enumerate(rows):
        c = _lab(r["sz"]) if k % 4 == 0 else ""
        if k == 4:
            out.append(r"\midrule")
        out.append(
            f"{c} & {r['rv']} & ${r['mu']:+.2f}$ & $[{r['lo']:+.2f},\\,{r['hi']:+.2f}]$"
            f" & ${_texp(r['ph'])}$ & ${r['ham']:+.1f}$ \\\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(out)


def tab_doz(rpd):
    out = [
        "% OTOMATIK URETILDI: gen_trackb_tables.py (kaynak results/kilitli_nis.csv) -- ELLE DUZENLEME YOK",
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Descriptive dose check at two selected sizes: average RPD (\%)",
        r"as the setup range varies, computed exactly as in",
        r"Table~\ref{tab:trackB-hh}; the $1$--$99$ rows repeat that table's cells",
        r"for reference. Instances are drawn independently per cell, so rows are",
        r"not paired across ranges, and the check does not measure the effect of",
        r"raising severity on a fixed instance. It lies outside the confirmatory",
        r"family.}\label{tab:trackB-doz}",
        r"\small",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{tabular}{llccccc}",
        r"\toprule",
        r"Size & Setups & SA & HGA & GA & CP & HLBB \\",
        r"\midrule",
    ]
    for sz in DOZ:
        if sz == DOZ[1]:
            out.append(r"\midrule")
        for ar, et in (("t9", "$1$--$9$"), ("t49", "$1$--$49$"), ("t99", "$1$--$99$")):
            cs = _cellstats(rpd, sz, ar)
            best = min(METS, key=lambda m: cs[m][0])
            hucre = " & ".join(_fmt(*cs[m], bold=(m == best)) for m in ("SA", "HGA", "GA", "CP", "HLBB"))
            c = _lab(sz) if ar == "t9" else ""
            out.append(f"{c} & {et} & {hucre} \\\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(out)


STIL = {
    "HLBB": "mark=*,thick,black",
    "SA": "mark=square*,thick,black,dashed",
    "CP": "mark=triangle*,thick,black,dotted",
    "HGA": "mark=diamond*,thick,black!60,dashdotted",
    "GA": "mark=o,thick,black!60,densely dotted",
}


def fig_scale(rpd):
    ymax = 0.0
    seri = {}
    for m in ("HLBB", "SA", "CP", "HGA", "GA"):
        v = []
        for x, sz in enumerate(ANA, 1):
            mu = st.mean([rpd[(sz, "t99", i, m)] for i in range(1, 7)])
            v.append((x, mu))
            ymax = max(ymax, mu)
        seri[m] = v
    ymax = (int(ymax / 5) + 1) * 5
    xt = ",".join(f"${sz.split('_')[0]}{{\\times}}{sz.split('_')[1]}$" for sz in ANA)
    out = [
        "% OTOMATIK URETILDI: gen_trackb_tables.py (kaynak results/kilitli_nis.csv) -- ELLE DUZENLEME YOK",
        r"\begin{figure}[H]\centering",
        r"\begin{tikzpicture}",
        r"\begin{axis}[width=0.86\linewidth,height=6.2cm,",
        r"  xlabel={Instance size ($n\times m$)}, ylabel={Average RPD (\%)},",
        f"  xtick={{1,...,{len(ANA)}}}, xticklabels={{{xt}}},",
        r"  xticklabel style={font=\scriptsize,rotate=28,anchor=north east},",
        f"  ymin=0, ymax={ymax}, legend pos=north west, legend cell align=left,",
        r"  grid=major, grid style={gray!25},",
        r"  tick label style={font=\small}, label style={font=\small},",
        r"  legend style={font=\small}]",
    ]
    for m in ("HLBB", "SA", "CP", "HGA", "GA"):
        pts = " ".join(f"({x},{y:.2f})" for x, y in seri[m])
        out.append(rf"\addplot[{STIL[m]}] coordinates {{{pts}}};")
        out.append(rf"\addlegendentry{{{m}}}")
    out += [
        r"\end{axis}",
        r"\end{tikzpicture}",
        r"\caption{Track~B, average RPD by instance size on the eight standard",
        r"cells at setup range $1$--$99$. Values are the cell means of",
        r"Table~\ref{tab:trackB-hh}; the boundary and dose cells are reported",
        r"there and in Table~\ref{tab:trackB-doz}.}\label{fig:scale}",
        r"\end{figure}",
        "",
    ]
    return "\n".join(out)


def main():
    mo, rpd = _oku()
    rows = conf_rows(mo, rpd)
    for ad, icerik in [("tab_trackb_cells.tex", tab_cells(rpd)),
                       ("tab_trackb_conf.tex", tab_conf(rows)),
                       ("tab_trackb_doz.tex", tab_doz(rpd)),
                       ("fig_scale.tex", fig_scale(rpd))]:
        yol = os.path.join(HERE, "paper", ad)
        with open(yol, "w") as f:
            f.write(icerik)
        print("YAZILDI:", yol, f"({os.path.getsize(yol)} B)")
    # cross-check: do the numbers match the analysis script (print to console)
    for r in rows:
        print(f"KONTROL {r['sz']} vs {r['rv']}: {r['mu']:+.2f} [{r['lo']:+.2f},{r['hi']:+.2f}] "
              f"Holm={r['ph']:.2e} ham={r['ham']:+.1f}")


if __name__ == "__main__":
    main()
