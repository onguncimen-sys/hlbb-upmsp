# -*- coding: utf-8 -*-
"""B5 — paper figures, from EXISTING data (NO new runs).

No matplotlib; we produce pgfplots -> vector output, same font as the paper, compiles
in Overleaf.
Output: paper/fig_scale.tex, paper/fig_regime.tex, paper/fig_tbest.tex
main.tex needs \\usepackage{pgfplots} in the preamble.
"""
import csv
import os
import statistics as st
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.join(_HERE, "paper")


def _load(path):
    d = defaultdict(lambda: defaultdict(list))
    for r in csv.DictReader(open(os.path.join(_HERE, path))):
        d[(r["size"], r["rep"])][r["method"]].append(float(r["makespan"]))
    return d


def _rpd_by_size(data):
    """-> {size: {method: mean RPD}}, denominator = the best of all runs per instance."""
    acc = defaultdict(lambda: defaultdict(list))
    for (sz, _), md in data.items():
        B = min(v for vals in md.values() for v in vals)
        for m, vals in md.items():
            acc[sz][m].append(100.0 * (st.mean(vals) - B) / B)
    return {sz: {m: st.mean(v) for m, v in md.items()} for sz, md in acc.items()}


def _tbest_by_size(path):
    acc = defaultdict(lambda: defaultdict(list))
    for r in csv.DictReader(open(os.path.join(_HERE, path))):
        if float(r["tbest"]) >= 0:
            acc[r["size"]][r["method"]].append(float(r["tbest"]))
    return acc


_STYLE = {"HLBB": "mark=*,thick,black",
          "SA":   "mark=square*,thick,black,dashed",
          "CP":   "mark=triangle*,thick,black,dotted",
          "HGA":  "mark=diamond*,gray,dashed,mark options={solid}",
          "GA":   "mark=pentagon*,gray,dashdotted,mark options={solid}"}


def _coords(pairs):
    return " ".join(f"({x},{y:.2f})" for x, y in pairs)


def fig_scale():
    """Figure 1: Track B, RPD as size grows — the paper's central claim."""
    rpd = _rpd_by_size(_load("results/niche_bench_v4.csv"))
    sizes = sorted(rpd, key=lambda s: int(s.split("x")[0]))
    body = []
    for m in ["HLBB", "SA", "HGA", "GA", "CP"]:
        pts = [(i + 1, rpd[s][m]) for i, s in enumerate(sizes) if m in rpd[s]]
        if not pts:
            continue
        body.append(f"\\addplot[{_STYLE[m]}] coordinates {{{_coords(pts)}}};\n"
                    f"\\addlegendentry{{{m}}}")
    ticks = ",".join(str(i + 1) for i in range(len(sizes)))
    labels = ",".join("$" + s.replace("x", r"{\times}") + "$" for s in sizes)
    tex = rf"""% OTOMATIK URETILDI — paper_figs.py
% [!htbp]: Tablo 3 ile birlikte §5.2 metninin SONUNA bildiriliyor; [t] iken ikisi
% ayri sayfalara dusuyordu (kullanici 2026-08-22). Sira: metin -> Tablo 3 -> Sekil 3
% -> \FloatBarrier -> §5.3. Bariyer olmadan ikisi §5.3'un ICINE kayiyordu.
\begin{{figure}}[!htbp]\centering
\begin{{tikzpicture}}
\begin{{axis}}[width=0.86\linewidth,height=6.2cm,
  xlabel={{Instance size ($n\times m$)}}, ylabel={{Average RPD (\%)}},
  xtick={{{ticks}}}, xticklabels={{{labels}}}, xticklabel style={{rotate=35,anchor=east,font=\scriptsize}},
  ymin=0, legend pos=north west, legend cell align=left,
  grid=major, grid style={{gray!25}}, tick label style={{font=\small}}, label style={{font=\small}}]
{chr(10).join(body)}
\end{{axis}}
\end{{tikzpicture}}
\caption{{Track~B, average RPD by instance size. HLBB stays at or near the
per-instance best across the whole range, while HGA and GA degrade
monotonically with scale and SA does so apart from one dip at
$200\times 20$. This is the scale interaction discussed in
Section~\ref{{sec:disc}}.}}\label{{fig:scale}}
\end{{figure}}
"""
    open(os.path.join(PAPER, "fig_scale.tex"), "w").write(tex)
    return "fig_scale.tex", sizes


def fig_regime():
    """Figure 2: Track A, regime transition along the n/m ratio — the paper's honesty
    anchor.

    2026-08-22 (user decision): two changes.
    (1) CP ADDED. Previously only HLBB+SA were drawn, but the sentence right before
        the figure says "each method owns one regime: CP the smallest, SA the
        transition, HLBB the scale" -> only two of the three regimes were visible.
        Figure 3 (Track B) already draws all five methods; this keeps them consistent.
    (2) X AXIS EQUALLY SPACED. Previously the true n/m values (2.5, 5, 10, 13.3, 25)
        were placed on a number line; with 25 far away, the critical transition region
        was squeezed into the left third. Now the configurations are equally spaced,
        in increasing n/m order (the scheme of Figure 3).
    NOTE: adding CP pushes the y axis from 15 to 27; the price is that the CP (1.0)
    vs SA (1.6) difference at 50x20 is no longer readable visually. That number
    remains in Table 2.
    """
    rpd = _rpd_by_size(_load("results/track_a.csv"))
    order = sorted(rpd, key=lambda s: int(s.split("x")[0]) / int(s.split("x")[1]))
    body = []
    for m in ["HLBB", "SA", "CP"]:
        pts = [(i + 1, rpd[s][m]) for i, s in enumerate(order) if m in rpd[s]]
        body.append(f"\\addplot[{_STYLE[m]}] coordinates {{{_coords(pts)}}};\n"
                    f"\\addlegendentry{{{m}}}")
    ticks = ",".join(str(i + 1) for i in range(len(order)))
    labels = ",".join("$" + s.replace("x", r"{\times}") + "$" for s in order)
    tex = rf"""% OTOMATIK URETILDI — paper_figs.py
% [!htbp]: [t] iken Tablo 2 ile birlikte sayfa tepesine cikiyordu ve §5.1'in son
% iki satiri sekil basliginin ALTINDA kaliyordu (kullanici 2026-08-22). !htbp ile
% sekil metnin arkasina yerlesiyor: tablo -> paragrafin kuyrugu -> sekil -> §5.2.
% Olculdu: [b] +2 sayfa, floatlari sona tasimak degisiklik yok, [!htbp] 32 sayfa.
\begin{{figure}}[!htbp]\centering
\begin{{tikzpicture}}
\begin{{axis}}[width=0.86\linewidth,height=6.2cm,
  xlabel={{Configuration ($n\times m$), ordered by increasing $n/m$}},
  ylabel={{Average RPD (\%)}},
  xtick={{{ticks}}}, xticklabels={{{labels}}}, xticklabel style={{font=\scriptsize}},
  ymin=0, legend pos=north west, legend cell align=left,
  grid=major, grid style={{gray!25}}, tick label style={{font=\small}}, label style={{font=\small}}]
{chr(10).join(body)}
\end{{axis}}
\end{{tikzpicture}}
\caption{{Track~A, average RPD by configuration, ordered by increasing
job-to-machine ratio. Each method leads in a different band: CP at the
smallest configuration, SA at the transition, HLBB from $n/m\ge 10$ onward.
The crossover, not an aggregate average, is the substantive
result.}}\label{{fig:regime}}
\end{{figure}}
"""
    open(os.path.join(PAPER, "fig_regime.tex"), "w").write(tex)
    return "fig_regime.tex", order


def fig_tbest():
    """How the budget is used — the time of the last improvement.

    ⚠️ 2026-08-22 (user decision): REMOVED FROM THE PAPER, the generator STAYS.
    Why it was removed:
      (1) The three numbers it carries are already given IN WORDS by the §5.2
          paragraph (SA 6 s at 50x10; from 200x20 on SA >60%, HLBB >73%; on the
          two largest sizes both within 15 s of the cutoff) -> same information twice.
      (2) It can draw only two of the five methods: GA and CP do NOT report `tbest`
          (run_one.jl:123, -1 when not instrumented), HGA reports it but its curve
          zigzags (8/20/60/29/89/176/161/174 s) -> a blurry third curve. A figure
          with structural gaps invites questions.
      (3) Its job is not to present a finding but to deflect an objection ("would
          the loser have wanted more time") -> a defence is made with a sentence.
    Measured: removing it does NOT save a page (32 -> 32); it drops ~45 words of
    caption and one float. If needed back, `\input{fig_tbest}` in main.tex suffices.
    """
    tb = _tbest_by_size("results/niche_bench_v4.csv")
    sizes = sorted(tb, key=lambda s: int(s.split("x")[0]))
    body = []
    for m in ["HLBB", "SA"]:
        pts = [(i + 1, st.mean(tb[s][m])) for i, s in enumerate(sizes) if m in tb[s]]
        body.append(f"\\addplot[{_STYLE[m]}] coordinates {{{_coords(pts)}}};\n"
                    f"\\addlegendentry{{{m}}}")
    ticks = ",".join(str(i + 1) for i in range(len(sizes)))
    labels = ",".join("$" + s.replace("x", r"{\times}") + "$" for s in sizes)
    tex = rf"""% OTOMATIK URETILDI — paper_figs.py
\begin{{figure}}[t]\centering
\begin{{tikzpicture}}
\begin{{axis}}[width=0.86\linewidth,height=6.2cm,
  xlabel={{Instance size ($n\times m$)}}, ylabel={{Time of last improvement (s)}},
  xtick={{{ticks}}}, xticklabels={{{labels}}}, xticklabel style={{rotate=35,anchor=east,font=\scriptsize}},
  ymin=0, ymax=215, legend pos=south east, legend cell align=left,
  grid=major, grid style={{gray!25}}, tick label style={{font=\small}}, label style={{font=\small}}]
\addplot[gray,dashed,forget plot] coordinates {{(1,200) ({len(sizes)},200)}};
{chr(10).join(body)}
\end{{axis}}
\end{{tikzpicture}}
\caption{{Track~B, mean time at which each method last improved its incumbent,
against the $200\,$s budget (dashed line). Both methods use essentially the
whole budget on the larger instances, so neither result is an artefact of one
method converging early and idling.}}\label{{fig:tbest}}
\end{{figure}}
"""
    open(os.path.join(PAPER, "fig_tbest.tex"), "w").write(tex)
    return "fig_tbest.tex", sizes


if __name__ == "__main__":
    for f in (fig_scale, fig_regime, fig_tbest):
        name, meta = f()
        print(f"-> paper/{name}   ({len(meta)} nokta)")
