# -*- coding: utf-8 -*-
"""Produces the MAIN TEXT tables and the regime figure of the locked pure test:
  paper/tab_tracka_cells.tex  -- 12 cells (4 sizes x 3 ranges) x 5 methods, mean RPD
  paper/tab_tracka_conf.tex   -- 8 pre-registered comparisons (Delta, 95% CI, Holm p)
  paper/fig_regime.tex        -- two panels (1-49 / 1-99), 5 methods, shared y/legend

Definitions match the Appendix C pre-registration exactly (see paper_stats._kilitlisaf;
the same numbers were verified along three independent code paths).
RPD denominator = the best REPEAT-MEAN of the five methods on the instance.
Run: ./venv/bin/python3 gen_tracka_tables.py
"""
import csv
import os
import statistics as stats
from collections import defaultdict

from scipy.stats import t as _t

_HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(_HERE, "results", "kilitli_saf.csv")
SIZES = [("50_30", "50$\\times$30", 1.7), ("150_30", "150$\\times$30", 5.0),
         ("100_10", "100$\\times$10", 10.0), ("200_10", "200$\\times$10", 20.0)]
RANGES = ["1-9", "1-49", "1-99"]
METH = ["SA", "HGA", "GA", "CP", "HLBB"]          # column order: rivals, then HLBB
RIVALS = ["SA", "HGA", "GA", "CP"]


def _rpdler():
    mk = defaultdict(lambda: defaultdict(list))
    with open(CSV) as fh:
        for r in csv.DictReader(fh):
            mk[(r["size"], r["aralik"], int(r["inst"]))][r["method"]].append(float(r["makespan"]))
    rpd = {}
    for k, runs in mk.items():
        mu = {m: stats.mean(runs[m]) for m in METH}
        B = min(mu.values())
        rpd[k] = {m: 100.0 * (mu[m] - B) / B for m in METH}
    return rpd


def tab_cells(rpd):
    out = [
        "% OTOMATIK URETILDI: gen_tracka_tables.py (kaynak results/kilitli_saf.csv) -- ELLE DUZENLEME YOK",
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Track A, average RPD (\%) on the locked pure test, computed as in",
        r"Section~\ref{sec:fair}: six instances per cell, stochastic methods use the",
        r"three-seed mean per instance, CP is a single run at $1000\,$s against the",
        r"metaheuristics' $200\,$s. Values are the mean $\pm$ the standard deviation",
        r"over the six instances; lower is better and the best of each row is in bold.",
        r"Rows are ordered by increasing job-to-machine ratio $n/m$. The $1$--$9$ rows",
        r"are descriptive; the confirmatory analysis of Section~\ref{sec:trackA}",
        r"covers the $1$--$49$ and $1$--$99$ ranges. Per-instance results are in",
        r"Appendix~\ref{app:per-instance}.}\label{tab:trackA}",
        r"\small",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{tabular}{llccccc}",
        r"\toprule",
        r"Config ($n\times m$) & Setups & SA & HGA & GA & CP & HLBB \\",
        r"\midrule",
    ]
    for sz, lab, oran in SIZES:
        for j, ra in enumerate(RANGES):
            cell = {m: [rpd[(sz, ra, i)][m] for i in range(1, 7)] for m in METH}
            mu = {m: stats.mean(v) for m, v in cell.items()}
            sd = {m: stats.stdev(v) for m, v in cell.items()}
            best = min(round(v, 1) for v in mu.values())
            hucre = []
            for m in METH:
                s = f"{mu[m]:.1f}\\,$\\pm$\\,{sd[m]:.1f}"
                if round(mu[m], 1) == best:
                    s = r"\textbf{" + s + "}"
                hucre.append(s)
            ilk = lab if j == 0 else ""
            out.append(f"{ilk} & ${ra.replace('-', '$--$')}$ & " + " & ".join(hucre) + r" \\")
        if sz != SIZES[-1][0]:
            out.append(r"\midrule")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(out)


def tab_conf(rpd):
    kay = []
    pler = []
    for ra in ("1-49", "1-99"):
        for v in RIVALS:
            dbars, s2n = [], []
            for sz, _, _ in SIZES:
                d = [rpd[(sz, ra, i)][v] - rpd[(sz, ra, i)]["HLBB"] for i in range(1, 7)]
                dbars.append(stats.mean(d))
                s2n.append(stats.variance(d) / 6)
            D = sum(dbars) / 4
            se = 0.25 * sum(s2n) ** 0.5
            nu = sum(s2n) ** 2 / sum(x * x / 5 for x in s2n)
            p = 2.0 * _t.sf(abs(D / se), nu)
            ci = _t.ppf(0.975, nu) * se
            kay.append([ra, v, D, D - ci, D + ci, p])
            pler.append(p)
    # Holm (m=8) — aligned with the row order of kay
    sirali = sorted(range(len(pler)), key=lambda j: pler[j])
    kmax = 0.0
    holm = [0.0] * len(pler)
    for r_, j in enumerate(sirali):
        kmax = max(kmax, (len(pler) - r_) * pler[j])
        holm[j] = min(1.0, kmax)

    def texp(p):
        if p >= 1e-3:
            return f"{p:.2g}"
        m_, e_ = f"{p:.1e}".split("e")
        return f"{m_}\\times 10^{{{int(e_)}}}"

    out = [
        "% OTOMATIK URETILDI: gen_tracka_tables.py (kaynak results/kilitli_saf.csv) -- ELLE DUZENLEME YOK",
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Track A, the eight pre-registered comparisons. $\hat\Delta$ is the",
        r"equal-weight mean over the four configurations of the per-instance RPD",
        r"difference (rival minus HLBB, in RPD points), so positive values favour",
        r"HLBB. Standard errors are stratified by configuration with",
        r"Welch--Satterthwaite degrees of freedom; $p$-values are two-sided and",
        r"Holm-adjusted over the single family of all eight comparisons. The $95\%$",
        r"confidence intervals are per-comparison, without multiplicity adjustment.}",
        r"\label{tab:trackA-conf}",
        r"\small",
        r"\setlength{\tabcolsep}{6pt}",
        r"\begin{tabular}{llccc}",
        r"\toprule",
        r"Setups & HLBB vs & $\hat\Delta$ (RPD points) & $95\%$ CI & Holm $p$ \\",
        r"\midrule",
    ]
    onceki = None
    for (ra, v, D, lo, hi, p), ph in zip(kay, holm):
        rlab = f"${ra.replace('-', '$--$')}$" if ra != onceki else ""
        onceki = ra
        if rlab and ra == "1-99":
            out.append(r"\midrule")
        out.append(f"{rlab} & {v} & ${D:+.2f}$ & $[{lo:+.2f},\\,{hi:+.2f}]$ & ${texp(ph)}$ \\\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(out)


def fig_regime(rpd):
    stil = {
        "HLBB": "mark=*,thick,black",
        "SA": "mark=square*,thick,black,dashed",
        "CP": "mark=triangle*,thick,black,dotted",
        "HGA": "mark=diamond*,thick,black!60,dashdotted",
        "GA": "mark=o,thick,black!60,densely dotted",
    }
    sira = ["HLBB", "SA", "CP", "HGA", "GA"]
    ymax = 0.0
    seri = {}
    for ra in ("1-9", "1-49", "1-99"):
        for m in sira:
            v = []
            for x, (sz, _, _) in enumerate(SIZES, 1):
                mu = stats.mean([rpd[(sz, ra, i)][m] for i in range(1, 7)])
                v.append((x, mu))
                ymax = max(ymax, mu)
            seri[(ra, m)] = v
    ymax = (int(ymax / 5) + 1) * 5
    xt = ",".join(f"{{{lab} ({o:g})}}" for _, lab, o in SIZES)
    out = [
        "% OTOMATIK URETILDI: gen_tracka_tables.py (kaynak results/kilitli_saf.csv) -- ELLE DUZENLEME YOK",
        r"\begin{figure}[H]\centering",
        r"\begin{tikzpicture}",
        r"\begin{groupplot}[group style={group size=3 by 1, horizontal sep=0.9cm,",
        r"    ylabels at=edge left},",
        r"  width=0.36\linewidth,height=6.4cm,",
        r"  ylabel={Average RPD (\%)},",
        f"  ymin=0, ymax={ymax},",
        r"  xtick={1,2,3,4},",
        f"  xticklabels={{{xt}}},",
        r"  xticklabel style={font=\scriptsize,rotate=28,anchor=north east},",
        r"  grid=major, grid style={gray!25},",
        r"  tick label style={font=\small}, label style={font=\small}]",
    ]
    for pi, ra in enumerate(("1-9", "1-49", "1-99")):
        baslik = "$" + ra.replace("-", "$--$") + "$"
        if ra == "1-9":
            baslik += " (descriptive)"
        ek = (r", legend to name=regimelegend, legend columns=-1,"
              r" legend style={font=\small,"
              r" /tikz/every even column/.append style={column sep=8pt}}") if pi == 0 else ""
        out.append(rf"\nextgroupplot[title={{Setups {baslik}}}, title style={{font=\small}}{ek}]")
        for m in sira:
            pts = " ".join(f"({x},{y:.2f})" for x, y in seri[(ra, m)])
            out.append(rf"\addplot[{stil[m]}] coordinates {{{pts}}};")
            if pi == 0:
                out.append(rf"\addlegendentry{{{m}}}")
    out += [
        r"\end{groupplot}",
        r"\node[below=2mm] at (current bounding box.south)",
        r"  {\pgfplotslegendfromname{regimelegend}};",
        r"\end{tikzpicture}",
        r"\caption{Average RPD by configuration on the locked pure test, ordered by",
        r"increasing job-to-machine ratio (in parentheses), for the three setup",
        r"ranges. The $1$--$9$ panel is descriptive and lies outside the",
        r"confirmatory family (Section~\ref{sec:fair}). Size and ratio change",
        r"together along the axis, so the axis orders the configurations and does",
        r"not isolate the ratio. Values are the cell means of",
        r"Table~\ref{tab:trackA}.}\label{fig:regime}",
        r"\end{figure}",
        "",
    ]
    return "\n".join(out)


def main():
    rpd = _rpdler()
    assert len(rpd) == 72
    for ad, icerik in [("tab_tracka_cells.tex", tab_cells(rpd)),
                       ("tab_tracka_conf.tex", tab_conf(rpd)),
                       ("fig_regime.tex", fig_regime(rpd))]:
        yol = os.path.join(_HERE, "paper", ad)
        with open(yol, "w") as f:
            f.write(icerik)
        print("YAZILDI:", yol, f"({os.path.getsize(yol)} B)")


if __name__ == "__main__":
    main()
