# -*- coding: utf-8 -*-
"""Produces paper/fig_arc.tex: why the master's span estimate falls below the true one
(Figure 3, §3.2).

Three panels, one machine, four jobs + dummy start node 0:
  (a) the cheapest TRUE sequence                          -> 49
  (b) in-degree only (eq:arc-deg)                         ->  7   (job 1 everyone's predecessor)
  (c) + out-degree (eq:outdeg)                            -> 48   (a sub-tour remains)
Forbidding the sub-tour as well yields 49, i.e. the ENTIRE remaining gap is that cycle.

All three values are verified by BRUTE FORCE on every generation (the asserts below).
Since the arc variables are continuous [0,1] in production, these values are LP optima:
in (b) the dummy attaches to the most expensive job and everyone picks their cheapest
incoming arc; in (c) the structure is an assignment polytope, which is integral.

Usage: python3 gen_arc.py    ->  paper/fig_arc.tex
"""
import itertools

OUT = "paper/fig_arc.tex"
J = [1, 2, 3, 4]
S = {(1, 2): 2, (1, 3): 3, (1, 4): 2,          # job 1's OUTGOING setups are CHEAP
     (2, 1): 25, (2, 3): 22, (2, 4): 30,
     (3, 1): 28, (3, 2): 24, (3, 4): 26,
     (4, 1): 27, (4, 2): 29, (4, 3): 23}
ORDER = [1, 4, 3, 2]                            # left to right -> panel (a) is a straight line
XS = {j: 1.32 * (k + 1) for k, j in enumerate(ORDER)}
XS[0] = 0.0
ROWY = {"a": 2.85, "b": 1.42, "c": 0.0}


def _acyclic(dummy, pairs):
    """pairs=[(predecessor, job)]: is it a SINGLE chain starting at the dummy (no sub-tour)?"""
    seen, cur = {dummy}, dummy
    while True:
        nxt = [i for p, i in pairs if p == cur and i not in seen]
        if not nxt:
            break
        cur = nxt[0]
        seen.add(cur)
    return len(seen) == len(J)


def verify():
    """Verify the three panels' values by brute force."""
    a = min(sum(S[p[k], p[k + 1]] for k in range(3)) for p in itertools.permutations(J))
    b = min(sum(min(S[j, i] for j in J if j != i) for i in J if i != dm) for dm in J)
    c, c_ac = None, None
    for dm in J:
        rest = [i for i in J if i != dm]
        for preds in itertools.permutations(J, len(rest)):
            if any(p == i for p, i in zip(preds, rest)):
                continue
            pairs = list(zip(preds, rest))
            tot = sum(S[p, i] for p, i in pairs)
            c = tot if c is None else min(c, tot)
            if _acyclic(dm, pairs):
                c_ac = tot if c_ac is None else min(c_ac, tot)
    assert (a, b, c, c_ac) == (49, 7, 48, 49), (a, b, c, c_ac)
    return a, b, c


def main():
    a_val, b_val, c_val = verify()
    miss, rec = a_val - b_val, c_val - b_val      # 42 missing, 41 of it recovered
    o = []
    w = o.append
    w(r"%% OTOMATIK URETILDI == gen_arc.py.  Uc panelin toplamlari (49/7/48) her uretimde")
    w(r"%% kaba kuvvetle dogrulanir; alt-tur da yasaklansa 49 cikar (= kalan acik tam o dongu).")
    w(r"\begin{figure}[H]\centering")
    w(r"\footnotesize")
    w(r"\begin{tikzpicture}[")
    w(r"  >={Stealth[length=1.7mm]},")
    w(r"  jb/.style  = {draw=black, line width=0.5pt, circle, minimum size=5.4mm,")
    w(r"                inner sep=0pt, font=\scriptsize, fill=white},")
    w(r"  dm/.style  = {draw=black!55, line width=0.5pt, dashed, circle,")
    w(r"                minimum size=5.4mm, inner sep=0pt, font=\scriptsize, text=black!55},")
    w(r"  ar/.style  = {->, line width=0.6pt},")
    w(r"  dar/.style = {->, line width=0.5pt, draw=black!55, dashed},")
    w(r"  cl/.style  = {font=\scriptsize, inner sep=1.2pt},")
    w(r"  rl/.style  = {font=\scriptsize, align=right, inner sep=0pt},")
    w(r"  tl/.style  = {font=\scriptsize, align=left, inner sep=0pt}]")
    w("")
    w(r"%% ==== setup matrisi ====")
    w(r"\node[anchor=east, font=\scriptsize] at (-1.55, %.2f) {%%" % ROWY["b"])
    w(r"  \setlength{\tabcolsep}{3.4pt}\renewcommand{\arraystretch}{1.02}")
    w(r"  \begin{tabular}{r|rrrr}")
    w(r"  $s_{ij}$ & $1$ & $2$ & $3$ & $4$ \\")
    w(r"  \hline")
    for i in J:
        w(r"  $%d$ & " % i + " & ".join("--" if i == j else str(S[i, j]) for j in J) + r" \\")
    w(r"  \end{tabular}};")
    w("")

    def row(tag, y, label):
        w(r"\node[rl, anchor=east] at (-0.55, %.2f) {(%s)};" % (y, label))
        w(r"\node[dm] (%s0) at (%.2f,%.2f) {$0$};" % (tag, XS[0], y))
        for j in ORDER:
            w(r"\node[jb] (%s%d) at (%.2f,%.2f) {$%d$};" % (tag, j, XS[j], y, j))
        w(r"\draw[dar] (%s0) -- (%s1);" % (tag, tag))

    def arc(tag, i, j, bend=0, above=True, at=0.5):
        b = "" if bend == 0 else "[bend left=%d]" % bend
        w(r"\draw[ar] (%s%d) to%s node[cl, %s, pos=%.2f] {$%d$} (%s%d);"
          % (tag, i, b, "above" if above else "below", at, S[i, j], tag, j))

    w(r"%% ==== (a) gercek acik yol: 0 -> 1 -> 4 -> 3 -> 2 ====")
    row("a", ROWY["a"], "a")
    for i, j in ((1, 4), (4, 3), (3, 2)):
        arc("a", i, j)
    w(r"\node[tl, anchor=west] at (6.05, %.2f) {the cheapest sequence\\ $\sum s = %d$};"
      % (ROWY["a"], a_val))
    w("")
    w(r"%% ==== (b) yalniz ic-derece: is 1 uc isin birden onculu ====")
    row("b", ROWY["b"], "b")
    arc("b", 1, 4)
    arc("b", 1, 3, bend=26, at=0.86)
    arc("b", 1, 2, bend=40, at=0.90)
    w(r"\node[tl, anchor=west] at (6.05, %.2f) {in-degree only\\ $\sum s = %d$};"
      % (ROWY["b"], b_val))
    w("")
    w(r"%% ==== (c) + dis-derece: 1->4 parcasi ve 2<->3 alt-turu ====")
    row("c", ROWY["c"], "c")
    arc("c", 1, 4)
    arc("c", 3, 2, bend=46)
    w(r"\draw[ar] (c2) to[bend left=46] node[cl, below] {$%d$} (c3);" % S[2, 3])
    w(r"\node[cl, text=black!58, font=\scriptsize\itshape] at (%.2f, %.2f) {sub-tour};"
      % ((XS[3] + XS[2]) / 2, ROWY["c"] + 0.86))
    w(r"\node[tl, anchor=west] at (6.05, %.2f) {plus out-degree\\ $\sum s = %d$};"
      % (ROWY["c"], c_val))
    w(r"\end{tikzpicture}")
    w(r"\caption{Why the master's span estimate falls below the true one, on four jobs")
    w(r"with the setup costs shown. Node $0$ is the dummy start. Panel (a) is the")
    w(r"cheapest real sequence, which costs $%d$: every job has one predecessor" % a_val)
    w(r"\emph{and} at most one successor. The linking constraints \eqref{eq:arc-deg}")
    w(r"impose only the first half, so in (b) job $1$ is the predecessor of all three")
    w(r"others and its cheap outgoing setups are counted three times. No sequence")
    w(r"permits that, and the estimate collapses to $%d$. The out-degree inequality" % b_val)
    w(r"\eqref{eq:outdeg} lets each job serve once and recovers $%d$ of the $%d$ missing"
      % (rec, miss))
    w(r"units. The one that remains is the sub-tour in (c): jobs $2$ and $3$ point only")
    w(r"at each other and never reach the start, which is what keeps the master a")
    w(r"relaxation.}\label{fig:arc}")
    w(r"\end{figure}")
    open(OUT, "w").write("\n".join(o) + "\n")
    print(f"{OUT} yazildi | paneller {a_val}/{b_val}/{c_val} | kaba kuvvet dogrulamasi OK")


if __name__ == "__main__":
    main()
