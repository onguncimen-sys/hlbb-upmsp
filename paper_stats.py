# -*- coding: utf-8 -*-
"""B4 — statistical significance tests, from EXISTING data (NO new runs).

Input : results/track_a.csv, results/niche_bench_v4.csv
Output: report to screen + paper/stats_snippets.tex (numbers pasted into the paper)

Method: for each instance, each method's representative value (SA = mean of 3 seeds,
HLBB/CP = single run) is taken, converted to RPD, and the PAIRED Wilcoxon signed-rank
test is applied to the RPD pairs. The effect size (Cohen d_z) is read from the same base.

⚠️ FIX 2026-08-22: the test used to run on RAW MAKESPANS and this docstring claimed
"since Wilcoxon is rank-based both bases give the same p". WRONG: signed-rank ranks the
MAGNITUDE of the differences, and since RPD divides each instance by its own scale the
ranking changes. Measured difference (Track A, SA vs HLBB, 50 instances): raw base
p=3.07e-05, RPD base p=0.054. The five p-values in §5.1 of the paper had come from the
RPD base; the script was writing the raw base. The correct base is RPD: the raw
differences of 50-job and 250-job instances differ by an order of magnitude, so the raw
base weights large instances.
"""
import csv
import os
import statistics as stats
from collections import defaultdict

from scipy.stats import wilcoxon

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path, keyf):
    """-> {(inst_key): {method: [makespan, ...]}}"""
    d = defaultdict(lambda: defaultdict(list))
    with open(os.path.join(_HERE, path)) as f:
        for r in csv.DictReader(f):
            d[keyf(r)][r["method"]].append(float(r["makespan"]))
    return d


def _paired(data, a, b):
    """Per-instance representative values (means) of methods a and b, on common instances."""
    xs, ys, keys = [], [], []
    for k in sorted(data):
        if a in data[k] and b in data[k]:
            xs.append(stats.mean(data[k][a]))
            ys.append(stats.mean(data[k][b]))
            keys.append(k)
    return keys, xs, ys


def _rpd(data, keys, method):
    """RPD; the denominator is the best of ALL runs of ALL methods on that instance."""
    out = []
    for k in keys:
        B = min(v for vals in data[k].values() for v in vals)
        out.append(100.0 * (stats.mean(data[k][method]) - B) / B)
    return out


def _test(label, data, a, b, note=""):
    keys, xa, xb = _paired(data, a, b)
    if len(keys) < 6:
        print(f"{label}: yetersiz eslesme (n={len(keys)})")
        return None
    ra, rb = _rpd(data, keys, a), _rpd(data, keys, b)
    diff = [u - v for u, v in zip(xa, xb)]           # a - b, raw makespan
    rdiff = [u - v for u, v in zip(ra, rb)]          # a - b, RPD points
    wins_b = sum(1 for d in diff if d > 1e-9)        # smaller makespan for b = b wins
    wins_a = sum(1 for d in diff if d < -1e-9)
    ties = len(diff) - wins_a - wins_b
    try:
        # on RPD pairs: instance difficulty is normalized out (see docstring)
        W, p = wilcoxon(ra, rb, alternative="two-sided", zero_method="wilcox")
    except ValueError:
        W, p = float("nan"), float("nan")
    # effect size: mean of paired differences / std (Cohen d_z)
    dz = stats.mean(rdiff) / stats.stdev(rdiff) if len(rdiff) > 1 and stats.stdev(rdiff) > 0 else float("nan")
    print(f"\n{label}   n={len(keys)} instance {note}")
    print(f"  ort RPD: {a}={stats.mean(ra):6.2f}%   {b}={stats.mean(rb):6.2f}%   "
          f"fark={stats.mean(rdiff):+.2f} puan")
    print(f"  {b} kazandi/berabere/kaybetti: {wins_b}/{ties}/{wins_a}")
    print(f"  Wilcoxon signed-rank: W={W:.1f}  p={p:.3g}   Cohen d_z={dz:+.2f}")
    return dict(n=len(keys), a=a, b=b, rpd_a=stats.mean(ra), rpd_b=stats.mean(rb),
                d_rpd=stats.mean(rdiff), w=wins_b, t=ties, l=wins_a, W=W, p=p, dz=dz)


def main():
    # Pure numbers come from _kilitlisaf() (results/kilitli_saf.csv; Appendix C
    # pre-registration), niche numbers from _kilitlinis() (results/kilitli_nis.csv;
    # Appendix D pre-registration). track_a.csv / niche_bench_v4.csv = development-run
    # data; they do not produce the paper's main tables. _onecore/_b3/_sppstat remain
    # as older MEASUREMENTS; the text cites them with a scope label.
    res = {}
    extra = (_kilitlisaf() + _kilitlinis() + _b3() + _fairness() + _lowratio()
             + _sppstat() + _onecore())
    _snippets(res, extra)
    return res


def _kilitlinis(path="results/kilitli_nis.csv"):
    """Locked NICHE test (Appendix D) -> statKN* macros. Definitions follow Appendix D
    exactly: unit = instance, mean over repeats; denominator = best repeat-mean of the
    five methods; confirmatory family m=8 paired t + Holm. Margin macros keep the old
    definition: (rival-HLBB)/rival*100 (percent of the rival's makespan)."""
    import math
    from scipy import stats as sps
    METS = ["SA", "HGA", "GA", "CP", "HLBB"]
    ANA = ["50_10", "100_15", "150_15", "200_20", "250_20", "400_20", "640_25", "800_30"]
    g = {}
    ham = list(csv.DictReader(open(os.path.join(_HERE, path))))
    assert len(ham) == 1092, len(ham)
    walls = {}
    tbest = {}
    for r in ham:
        k = (r["size"], r["aralik"], int(r["inst"]), r["method"])
        g.setdefault(k, []).append(float(r["makespan"]))
        walls.setdefault(r["method"], []).append(float(r["wall_real"]))
        if r["tbest"].strip():
            tbest.setdefault((r["size"], r["method"]), []).append(float(r["tbest"]))
    mo = {k: stats.mean(v) for k, v in g.items()}
    HUC = sorted({(k[0], k[1]) for k in mo})
    rpd = {}
    for (sz, ar) in HUC:
        for i in range(1, 7):
            b = min(mo[(sz, ar, i, m)] for m in METS)
            for m in METS:
                rpd[(sz, ar, i, m)] = 100.0 * (mo[(sz, ar, i, m)] - b) / b
    out = []

    # --- confirmatory m=8 (Appendix D) ---
    adlar = {"400_20": "Ft", "800_30": "Et"}
    pler = []
    for sz in ("400_20", "800_30"):
        for rv in ("SA", "HGA", "GA", "CP"):
            d = [rpd[(sz, "t99", i, rv)] - rpd[(sz, "t99", i, "HLBB")] for i in range(1, 7)]
            hamf = [mo[(sz, "t99", i, rv)] - mo[(sz, "t99", i, "HLBB")] for i in range(1, 7)]
            mu, sd = stats.mean(d), stats.stdev(d)
            t = mu / (sd / math.sqrt(6))
            p = 2 * sps.t.sf(abs(t), 5)
            h = sps.t.ppf(0.975, 5) * sd / math.sqrt(6)
            ad = adlar[sz] + rv.capitalize()
            out += [(f"KN{ad}Delta", f"{mu:+.2f}"), (f"KN{ad}CiLo", f"{mu-h:+.2f}"),
                    (f"KN{ad}CiHi", f"{mu+h:+.2f}"), (f"KN{ad}Ham", f"{stats.mean(hamf):+.1f}")]
            pler.append((f"KN{ad}PHolm", p))
    sira = sorted(range(8), key=lambda k: pler[k][1])
    enb = 0.0
    holm = {}
    for j, k in enumerate(sira):
        enb = max(enb, (8 - j) * pler[k][1])
        holm[pler[k][0]] = min(1.0, enb)
    out += [(ad, _texp(p)) for ad, p in holm.items()]

    # --- ranking (descriptive): t99, 60 instances, Wilcoxon ---
    def _wil(a, b2):
        keys = [(sz, ar, i) for (sz, ar) in HUC if ar == "t99" for i in range(1, 7)]
        d = [rpd[k + (a,)] - rpd[k + (b2,)] for k in keys]
        w = sum(1 for x in d if x > 1e-12); l = sum(1 for x in d if x < -1e-12)
        t = len(d) - w - l
        try:
            p = sps.wilcoxon([x for x in d if abs(x) > 1e-12]).pvalue
        except ValueError:
            p = float("nan")
        dz = stats.mean(d) / stats.stdev(d)
        return f"{w}/{t}/{l}", _texp(p), f"{abs(dz):.2f}", w, len(d)
    for a, b2, ad in (("HGA", "SA", "KNSaHga"), ("GA", "SA", "KNSaGa"), ("GA", "HGA", "KNHgaGa")):
        wtl, p, dz, w, n = _wil(a, b2)
        out += [(f"{ad}Wtl", wtl), (f"{ad}P", p), (f"{ad}Dzabs", dz),
                (f"{ad}W", str(w)), (f"{ad}N", str(n))]

    # --- margins (old definition: percent of the rival) ---
    def _marj(opp, szler, arlar=("t99",)):
        v = []
        for sz in szler:
            for ar in arlar:
                for i in range(1, 7):
                    o, h = mo[(sz, ar, i, opp)], mo[(sz, ar, i, "HLBB")]
                    v.append((o - h) / o * 100)
        return v
    out += [("KNSaMargLo", f"{stats.mean(_marj('SA', [ANA[0]])):.1f}"),
            ("KNSaMargHi", f"{stats.mean(_marj('SA', [ANA[-1]])):.1f}"),
            ("KNSaMargLoSize", r"50\times 10"), ("KNSaMargHiSize", r"800\times 30"),
            ("KNCpMarg", f"{stats.mean(_marj('CP', ANA)):.0f}")]

    # --- count of HLBB-best means over the standard 8 sizes ---
    nb = sum(1 for sz in ANA for i in range(1, 7)
             if abs(rpd[(sz, "t99", i, "HLBB")]) < 1e-9)
    out += [("KNStdBest", str(nb)), ("KNStdN", str(8 * 6))]

    # --- dose (descriptive; SA-HLBB cell-mean difference, t9) ---
    for sz, ad in (("400_20", "Ft"), ("800_30", "Et")):
        dh = stats.mean([rpd[(sz, "t9", i, "HLBB")] - rpd[(sz, "t9", i, "SA")]
                         for i in range(1, 7)])
        out.append((f"KNDozNine{ad}", f"{dh:+.1f}"))

    # --- boundary cells (vs SA, pre-declared) ---
    for sz, ad in (("800_40", "Ef"), ("400_80", "Fe")):
        d = [rpd[(sz, "t99", i, "SA")] - rpd[(sz, "t99", i, "HLBB")] for i in range(1, 7)]
        mu, sd = stats.mean(d), stats.stdev(d)
        h = sps.t.ppf(0.975, 5) * sd / math.sqrt(6)
        out += [(f"KN{ad}SaD", f"{mu:+.1f}"), (f"KN{ad}SaCiLo", f"{mu-h:+.1f}"),
                (f"KN{ad}SaCiHi", f"{mu+h:+.1f}"), (f"KN{ad}SaDAbs", f"{abs(mu):.1f}")]

    # --- times / overrun / spread ---
    ga_over = [w - 200 for w in walls["GA"] if w > 200]
    ga800 = [w - 200 for (szm), v in tbest.items() if False]  # dead expression: recomputed below
    ga800 = [float(r["wall_real"]) - 200 for r in ham
             if r["method"] == "GA" and r["size"] == "800_30" and float(r["wall_real"]) > 200]
    meta_walls = walls["SA"] + walls["HGA"]
    out += [("KNHlbbWallMax", f"{max(walls['HLBB']):.1f}"),
            ("KNMetaWallMax", f"{max(meta_walls):.1f}"),
            ("KNMetaLateMax", f"{max(meta_walls) - 200:.1f}"),
            ("KNGaOverMax", f"{max(ga_over):.0f}"),
            ("KNGaOverMeanEt", f"{stats.mean(ga800):.0f}")]
    spread = []
    for (sz, ar) in HUC:
        for i in range(1, 7):
            v = g[(sz, ar, i, "HLBB")]
            spread.append((max(v) - min(v), (max(v) - min(v)) / stats.mean(v) * 100))
    out += [("KNHlbbSpreadUnits", f"{stats.mean([x for x, _ in spread]):.1f}"),
            ("KNHlbbSpreadPct", f"{stats.mean([y for _, y in spread]):.1f}")]

    # --- budget use (tbest; GA excluded: the capsule reports -1) ---
    out.append(("KNSaTbestSmall", f"{stats.mean(tbest[('50_10', 'SA')]):.1f}"))
    buyuk = [sz for sz in ANA if int(sz.split("_")[0]) >= 400]
    for m, ad in (("SA", "KNSaLateShare"), ("HLBB", "KNHlbbLateShare")):
        v = [t for sz in buyuk for t in tbest[(sz, m)] if t >= 0]
        out.append((ad, f"{stats.mean(v) / 200 * 100:.0f}"))

    # --- CP ---
    opt = [(r["size"], r["aralik"]) for r in ham if r["method"] == "CP" and r["durum"] == "Optimal"]
    out += [("KNCpOptN", str(len(opt))),
            ("KNCpSolvedN", str(sum(1 for r in ham if r["method"] == "CP")))]
    print(f"[kilitlinis] {len(out)} makro; CP optimal: {opt}")
    return out


def _kilitlisaf(path="results/kilitli_saf.csv"):
    """LOCKED PURE TEST (Appendix C pre-registration) -> statKS* macros.

    Follows the pre-registration exactly (lit_gece/ON_KAYIT_PROTOKOLU.md, Appendix C
    items 3-4; the same computation runs in lit_gece/araclar/kilit_saf_analiz.py with
    pandas/scipy, here as an INDEPENDENT second path with stdlib+scipy.t — the 2026-10-22
    cross-check agreed to 6 significant digits):
    unit = instance; repeats averaged within the instance; RPD denominator = best MEAN
    of the FIVE methods on the instance; d = RPD(rival) - RPD(HLBB), + = in HLBB's favor;
    stratified D=(1/4)*sum(dbar_h), SE=(1/4)*sqrt(sum s_h^2/6), nu Welch-Satterthwaite;
    a SINGLE Holm family m=8 ({SA,HGA,GA,CP} x {1-49,1-99}); 1-9 is DESCRIPTIVE;
    the flat 24-instance paired t = pre-declared sensitivity."""
    from scipy.stats import t as _t
    f = os.path.join(_HERE, path)
    if not os.path.exists(f):
        return []
    mk = defaultdict(lambda: defaultdict(list))   # (size,aralik,inst) -> {method: [mk]}
    wall_meta, wall_hlbb, spread_u, spread_p = [], [], [], []
    cp_opt_sizes = []
    with open(f) as fh:
        for r in csv.DictReader(fh):
            k = (r["size"], r["aralik"], int(r["inst"]))
            mk[k][r["method"]].append(float(r["makespan"]))
            w = float(r["wall_real"])
            if r["method"] == "HLBB":
                wall_hlbb.append(w)
            elif r["method"] != "CP":
                wall_meta.append(w)
            if r["method"] == "CP" and r["durum"] == "Optimal":
                cp_opt_sizes.append(r["size"])
    SIZES = ["50_30", "150_30", "100_10", "200_10"]
    METH = ["HLBB", "SA", "HGA", "GA", "CP"]
    rpd = {}                                      # (size,aralik,inst) -> {m: rpd}
    for k, runs in mk.items():
        mu = {m: stats.mean(runs[m]) for m in METH}
        Bst = min(mu.values())
        rpd[k] = {m: 100.0 * (mu[m] - Bst) / Bst for m in METH}
        s = runs["HLBB"]
        spread_u.append(max(s) - min(s))
        spread_p.append(100.0 * (max(s) - min(s)) / stats.mean(s))
    RNG = {"Low": "1-9", "Mid": "1-49", "Wide": "1-99"}
    RIV = {"Sa": "SA", "Hga": "HGA", "Ga": "GA", "Cp": "CP"}
    out, pler, kay = [], [], {}
    for rn, ra in RNG.items():
        for vn, v in RIV.items():
            dbars, s2n = [], []
            for sz in SIZES:
                d = [rpd[(sz, ra, i)][v] - rpd[(sz, ra, i)]["HLBB"] for i in range(1, 7)]
                dbars.append(stats.mean(d))
                s2n.append(stats.variance(d) / 6)
            D = sum(dbars) / 4
            se = 0.25 * (sum(s2n)) ** 0.5
            nu = sum(s2n) ** 2 / sum(x * x / 5 for x in s2n)
            p = 2.0 * _t.sf(abs(D / se), nu)
            ci = _t.ppf(0.975, nu) * se
            kay[(rn, vn)] = (D, se, nu, p, D - ci, D + ci)
            out += [("KS" + vn + rn + "Delta", f"{D:+.2f}"),
                    ("KS" + vn + rn + "DeltaAbs", f"{abs(D):.2f}"),
                    ("KS" + vn + rn + "CiLo", f"{D - ci:+.2f}"),
                    ("KS" + vn + rn + "CiHi", f"{D + ci:+.2f}")]
            if rn != "Low":
                pler.append(((rn, vn), p))
                # pre-declared sensitivity: flat 24-instance paired t
                d24 = [rpd[(sz, ra, i)][v] - rpd[(sz, ra, i)]["HLBB"]
                       for sz in SIZES for i in range(1, 7)]
                tf = stats.mean(d24) / (stats.stdev(d24) / len(d24) ** 0.5)
                pf = 2.0 * _t.sf(abs(tf), len(d24) - 1)
                out.append(("KS" + vn + rn + "FlatP",
                            f"{pf:.2f}" if pf >= 0.01 else _texp(pf)))
    m = len(pler)
    kmax = 0.0
    for j, (key, p) in enumerate(sorted(pler, key=lambda x: x[1])):
        kmax = max(kmax, (m - j) * p)
        out.append(("KS" + key[1] + key[0] + "PHolm", _texp(min(1.0, kmax))))
    # cell means + count of HLBB-best in the confirmatory cells
    hi_best = 0
    for sz in SIZES[1:]:                          # ratio >= 5
        for ra in ("1-49", "1-99"):
            cell = {m_: stats.mean([rpd[(sz, ra, i)][m_] for i in range(1, 7)]) for m_ in METH}
            if min(cell, key=cell.get) == "HLBB":
                hi_best += 1
    # published 2009 reference (DESCRIPTIVE): BoundsP_SDST_Large.xls -> skip if no csv copy
    ref = _ref2009()
    if ref:
        best_below, hlbb_cells, cells_below = [], 0, 0
        for sz in SIZES:
            for ra in ("1-9", "1-49", "1-99"):
                cb, ch = [], []
                for i in range(1, 7):
                    mu = {m_: stats.mean(mk[(sz, ra, i)][m_]) for m_ in METH}
                    rv = ref[(sz, ra, i)]
                    cb.append(100.0 * (min(mu.values()) - rv) / rv)
                    ch.append(100.0 * (mu["HLBB"] - rv) / rv)
                best_below += cb
                cells_below += stats.mean(cb) < 0
                hlbb_cells += stats.mean(ch) < 0
                if sz == "200_10" and ra == "1-9":
                    out.append(("KSRefHlbbExcPct", f"{stats.mean(ch):+.1f}"))
        out += [("KSRefBestAvgBelow", f"{-stats.mean(best_below):.1f}"),
                ("KSRefCellsBelow", cells_below), ("KSRefHlbbCellsBelow", hlbb_cells)]
    out += [("KSCpOptN", len(cp_opt_sizes)),
            ("KSCpOptFiftyThirty", sum(1 for s in cp_opt_sizes if s == "50_30")),
            ("KSHlbbWallMax", f"{max(wall_hlbb):.1f}"),
            ("KSMetaWallMax", f"{max(wall_meta):.1f}"),
            ("KSHlbbSpreadUnits", f"{stats.mean(spread_u):.1f}"),
            ("KSHlbbSpreadPct", f"{stats.mean(spread_p):.1f}"),
            ("KSHiConfCellsBest", hi_best)]
    print("\n--- KILITLI SAF (EK-C): katmanli D, Holm m=8 ---")
    for (rn, vn), (D, se, nu, p, lo_, hi_) in sorted(kay.items()):
        print(f"  {RNG[rn]:>5} vs {RIV[vn]:<3} D={D:+7.2f} SE={se:.3f} nu={nu:5.1f} "
              f"p={p:.3e} CI=[{lo_:+.2f},{hi_:+.2f}]")
    return out


def _ref2009(path="results/ref2009_large.csv"):
    """Published 2009 reference values (for the descriptive column). Converted once from
    the source xls (lit_gece/araclar/ref2009_cevir.py); returns empty if absent."""
    f = os.path.join(_HERE, path)
    if not os.path.exists(f):
        return {}
    ref = {}
    with open(f) as fh:
        for r in csv.DictReader(fh):
            ref[(r["size"], r["aralik"], int(r["inst"]))] = float(r["ref2009"])
    return ref


def _fairness(path="results/fairness_probe.csv"):
    """The FAIRNESS numbers of §4.2-4.3. These come from one-off diagnostic probes, not
    from the benchmark CSVs; the probe outputs are written to results/fairness_probe.csv
    and the paper reads them from THERE (PAPER_STYLE §8.3: a hand-written number = an
    unproduced number). To rerun a probe: scratchpad/sacount/{grain.jl,probe.jl,
    temp_probe.jl} and scratchpad/{grain_hlbb.py,lang_probe.py} -- all named in the
    `note` field of the relevant row."""
    p = os.path.join(_HERE, path)
    if not os.path.exists(p):
        return []
    ad = {"sa_scan_us": "FairScanUs", "jl_dispatch_us": "FairDispatchUs",
          "hlbb_lkh_ms": "FairLkhMs", "abandon_max_pct": "FairAbandonMax",
          "abandon_big_pct": "FairAbandonBig", "regime_tol_pct": "FairRegimeTol",
          "budget_solver_lo_pct": "FairSolverLo", "budget_solver_hi_pct": "FairSolverHi"}
    out = []
    with open(p, newline="") as f:
        for r in csv.DictReader(f):
            if r["key"] in ad:
                out.append((ad[r["key"]], r["value"]))
    # the grain RATIO is also derived: "seventy times" is never hand-written
    d = {r[0]: float(r[1]) for r in out}
    if "FairDispatchUs" in d and "FairScanUs" in d:
        out.append(("FairGrainRatio", f"{d['FairDispatchUs'] / d['FairScanUs']:.0f}"))
    return out


def _lowratio(path="results/lowratio_k_probe.csv"):
    """§5.1 / §5.4: the price of the CANDIDATE-MACHINE restriction at a low job-machine
    ratio (exact measurement).
    Source: `python3 _enum_cand.py 50x20 30 results/lowratio_k_probe.csv` -- per machine,
    all job sequences whose completion time does not exceed T are enumerated (T = the
    method's own result), set partitioning over the columns is solved to optimality, and
    the solution passes the shared checker.
    Rules: free = unrestricted; J3 = each job on its 3 fastest machines (production);
    J3M2 = J3 + each machine's fastest ceil(2n/m) jobs (Fanjul-Peyro & Ruiz 2011, 3J2M).
    ⚠️ The macros are produced ONLY if every row is proven optimal (optimal=1), the
    enumeration is complete (enum_complete=1) and the checker is clean (checker_ok=1);
    otherwise it returns empty and the build BREAKS -- so that no unproven value enters
    the paper as an 'optimum'."""
    p = os.path.join(_HERE, path)
    if not os.path.exists(p):
        return []
    rows = [r for r in csv.DictReader(open(p, newline="")) if r["rule"] in ("free", "J3", "J3M2")]
    if not rows or any(r["optimal"] != "1" or r["enum_complete"] != "1" or r["checker_ok"] != "1"
                       for r in rows):
        return []
    by = {}
    for r in rows:
        by.setdefault(r["rule"], {})[int(r["rep"])] = r
    reps = sorted(by["free"])
    free = [float(by["free"][k]["value"]) for k in reps]
    j3 = [float(by["J3"][k]["value"]) for k in reps]
    mix = [float(by["J3M2"][k]["value"]) for k in reps]
    hl = [float(by["J3"][k]["hlbb_mean"]) for k in reps]
    at = sum(1 for a, b in zip(hl, j3) if abs(a - b) < 1e-9)
    cols = [int(by["free"][k]["columns"]) for k in reps]
    return [("LowN", str(len(reps))),
            ("LowOptFree", f"{stats.mean(free):.1f}"),
            ("LowOptK", f"{stats.mean(j3):.1f}"),
            ("LowOptMix", f"{stats.mean(mix):.1f}"),
            ("LowHLBB", f"{stats.mean(hl):.1f}"),
            ("LowAtOpt", str(at)),
            ("LowPrice", f"{100 * (stats.mean(j3) - stats.mean(free)) / stats.mean(free):.0f}"),
            ("LowColsMax", f"{max(cols):,}".replace(",", "{,}"))]


def _sppstat(path="results/capsoft.csv"):
    """§3.4: solver status of the recombination step and the reserve surplus, with the
    PRODUCTION setting.
    Source: `_capsoft_probe.py` -- the constrained comparison's 8 sizes x first 3
    instances x 3 repeats, 200 s.
    Only the `capsoft` arm is read: the soft cap became the production default on
    2026-08-23.
    ⚠️ The paper previously said "114 of 120" and "about 13 s"; both came from
    `results/reserve.csv`, i.e. from the setting BEFORE the soft cap (114/120 and
    13.2 s under the hard cap).
    mip_st: 2 = optimality proven, 9 = stopped at the time limit.
    Reserve surplus = reserve set aside - (column routing + model build + solver)."""
    p = os.path.join(_HERE, path)
    if not os.path.exists(p):
        return []
    rows = [r for r in csv.DictReader(open(p, newline="")) if r["arm"] == "capsoft"]
    if not rows:
        return []
    opt = [r for r in rows if float(r["mip_st"]) == 2.0]
    miss = [r for r in rows if float(r["mip_st"]) != 2.0]
    by = {}
    for r in miss:
        by[r["size"]] = by.get(r["size"], 0) + 1
    top = max(by, key=by.get) if by else None
    sur = [float(r["reserve"]) - float(r["spp_route_s"]) - float(r["spp_build_s"])
           - float(r["spp_mip_s"]) for r in rows]
    out = [("SppN", str(len(rows))), ("SppOpt", str(len(opt))), ("SppMiss", str(len(miss))),
           ("SppSurplus", f"{stats.mean(sur):.0f}")]
    if top:
        out += [("SppMissTop", str(by[top])), ("SppMissTopSize", top.replace("_", r"\times "))]
    return out


def _onecore(path="results/niche_bench_1core.csv", v4="results/niche_bench_v4.csv",
             multi="results/niche_bench_multi_v6.csv", kay="results/kaynak_olcumu.csv"):
    """§4.2 (iv) + §5.2 `Processor time`: reviewer item 4, the single-core control run.
    Source: `./run_trackb_1core.sh` (onecore_run.py + kaynak_olcumu.py); protocol fixed
    BEFORE the run in `results/m4_probe/PROTOKOL.md`, result in `results/m4_probe/SONUC.md`.
    Single-core HLBB (1 run/instance) is paired with the main comparison's (v4) annealing
    mean (INTERIM comparison; the locked runs supersede it) and with the SAME-VERSION
    multi-core run (multi, v6+v6, seed 0 paired). Large = 150 jobs and up (30 instances),
    small = 50x10 and 100x15.
    Core usage from `kaynak_olcumu.csv`: the main comparison's setting, no core pinning."""
    from scipy.stats import wilcoxon
    p1, p2, p3, p4 = (os.path.join(_HERE, x) for x in (path, v4, kay, multi))
    if not (os.path.exists(p1) and os.path.exists(p2) and os.path.exists(p4)):
        return []
    one = {(r["size"], r["rep"]): float(r["makespan"]) for r in csv.DictReader(open(p1, newline=""))}
    D = {}
    for r in csv.DictReader(open(p2, newline="")):
        D.setdefault((r["method"], r["size"], r["rep"]), []).append(float(r["makespan"]))
    big = sorted(k for k in one if int(k[0].split("x")[0]) >= 150)
    small = sorted(k for k in one if int(k[0].split("x")[0]) < 150)
    sa = {k: stats.mean(D[("SA",) + k]) for k in one}
    sab = {k: min(D[("SA",) + k]) for k in one}
    # single-vs-multi counterpart from the SAME version (v6): niche_bench_multi_v6.csv,
    # seed 0, 1 run/instance
    hm = {(r["size"], r["rep"]): float(r["makespan"]) for r in csv.DictReader(open(p4, newline=""))}
    def w(ks, ref):
        return sum(1 for k in ks if one[k] < ref[k])
    diff = [100 * (one[k] - hm[k]) / hm[k] for k in one]
    d800 = [100 * (one[k] - hm[k]) / hm[k] for k in one if k[0] == "800x30"]
    out = [("OcN", str(len(one))), ("OcBigN", str(len(big))), ("OcSmallN", str(len(small))),
           ("OcBigW", str(w(big, sa))), ("OcSmallW", str(w(small, sa))),
           ("OcBigP", _texp(wilcoxon([one[k] for k in big], [sa[k] for k in big]).pvalue)),
           ("OcBigMarg", f"{stats.mean([100 * (sa[k] - one[k]) / sa[k] for k in big]):.1f}"),
           ("OcDiff", f"{stats.mean(diff):.1f}"),
           ("OcDiffSE", f"{stats.stdev(diff) / len(diff) ** 0.5:.1f}"),
           ("OcDiffP", _texp(wilcoxon([one[k] for k in one], [hm[k] for k in one]).pvalue)),
           ("OcDiffLarge", f"{stats.mean(d800):.1f}"),
           ("OcBestThreeW", str(w(big, sab)))]
    if os.path.exists(p3):
        rows = list(csv.DictReader(open(p3, newline="")))
        hl = [float(r["ort_cekirdek"]) for r in rows if r["method"] == "HLBB"]
        mh = [float(r["ort_cekirdek"]) for r in rows if r["method"] in ("SA", "HGA", "GA")]
        cp = [float(r["ort_cekirdek"]) for r in rows if r["method"] == "CP"]
        if hl and mh and cp:
            out += [("RsHlbbLo", f"{min(hl):.1f}"), ("RsHlbbHi", f"{max(hl):.1f}"),
                    ("RsMeta", f"{max(mh):.1f}"), ("RsCpLo", f"{min(cp):.0f}"),
                    ("RsCpHi", f"{max(cp):.0f}")]
    return out


def _margins(B):
    """HLBB's PERCENT makespan margin over a rival: mean_i (opp_i - hlbb_i)/opp_i * 100.
    The 1.5 / 14.3 / 13 numbers in the Abstract/§5.2/§5.4/§7 are produced HERE; they are
    never hand-written (PAPER_STYLE §8.3). Sizes ordered by n."""
    sizes = sorted({k[0] for k in B}, key=lambda z: int(z.split("x")[0]))
    def per(opp, keys):
        out = []
        for k in keys:
            v = B[k]
            if opp in v and "HLBB" in v:
                o, h = stats.mean(v[opp]), stats.mean(v["HLBB"])
                if o > 0:
                    out.append((o - h) / o * 100)
        return out
    sa_lo = per("SA", [k for k in B if k[0] == sizes[0]])
    sa_hi = per("SA", [k for k in B if k[0] == sizes[-1]])
    cp_all = per("CP", list(B))
    return [("BmargSAlo", f"{stats.mean(sa_lo):.1f}"),
            ("BmargSAhi", f"{stats.mean(sa_hi):.1f}"),
            ("BmargCP",   f"{stats.mean(cp_all):.0f}"),
            ("BmargSAloSize", sizes[0].replace("x", r"\times ")),
            ("BmargSAhiSize", sizes[-1].replace("x", r"\times "))]


def _b3(path="results/niche_b3.csv"):
    """B3 paired constraint experiment (v6 run of 2026-10-15) -> PER-CELL macros.
    PRE-REGISTERED analysis (lit_gece/ON_KAYIT_PROTOKOLU.md, package 4): unit = base
    instance (n=5, seeds averaged within the instance); A = mean(SA) - mean(HLBB)
    (makespan units, + = HLBB ahead); D = A_on - A_off; uncertainty 95% t-interval
    = 2.776*SE.
    Instances use the SAME processTime/setupTime in both regimes (md5 verified) -> paired.
    The old pooled macros (BthreeLoD/HiD/Scale/FlipW) were removed: they came from an
    old-version run (archive: niche_b3_ESKI_v4donem_2026-08-24.csv) and did not match
    the pre-registered analysis."""
    import os
    f = os.path.join(_HERE, path)
    if not os.path.exists(f):
        return []
    B = _load(path, lambda r: (r["size"], r["elig"], r["rho"], r["rep"]))
    def gap(sz, e, rh, i):
        k = (sz, e, rh, str(i))
        return stats.mean(B[k]["SA"]) - stats.mean(B[k]["HLBB"])
    out = [("BthreeN", sum(len(v) for k in B for v in B[k].values()))]
    for sz, nm in (("50x20", "Fifty"), ("100x20", "Hundred"),
                   ("400x20", "FourH"), ("800x30", "EightH")):
        off = [gap(sz, "eoff", "r0", i) for i in range(1, 6)]
        on = [gap(sz, "e50", "ron", i) for i in range(1, 6)]
        d = [a - b for a, b in zip(on, off)]
        se = stats.stdev(d) / len(d) ** .5
        out += [("Bthree" + nm + "Off", f"{stats.mean(off):+.1f}"),
                ("Bthree" + nm + "On", f"{stats.mean(on):+.1f}"),
                ("Bthree" + nm + "D", f"{stats.mean(d):+.1f}"),
                ("Bthree" + nm + "Ci", f"{2.776 * se:.1f}")]
    return out


def _texp(p):
    """Convert a p-value into a LaTeX fragment for MATH MODE.

    $p = \\statAhip$  ->  $p = 1.9\\times 10^{-9}$
    Threshold 0.001: plain decimal above it (0.054), scientific notation below.
    """
    if p != p:                       # NaN
        return "\\mathrm{n/a}"
    if p >= 1e-3:
        return f"{p:.2g}"
    m, e = f"{p:.1e}".split("e")
    return f"{m}\\times 10^{{{int(e)}}}"


def _winners(data, methods):
    """Counts of STRICT winners per instance (over means) + ties."""
    w = {m: 0 for m in methods}
    ties = 0
    for k in data:
        mu = {m: stats.mean(v) for m, v in data[k].items() if m in methods}
        if len(mu) < len(methods):
            continue
        best = min(mu.values())
        top = [m for m in mu if mu[m] <= best + 1e-9]
        if len(top) == 1:
            w[top[0]] += 1
        else:
            ties += 1
    return w, ties


def _snippets(res, extra=()):
    out = os.path.join(_HERE, "paper", "stats_snippets.tex")
    with open(out, "w") as f:
        f.write("% OTOMATIK URETILDI — paper_stats.py. ELLE DUZENLEME YOK.\n")
        f.write("% main.tex bu dosyayi \\input eder; makaledeki istatistik sayilari\n")
        f.write("% BURADAN okunur, elle yazilmaz (2026-08-22: elle yazilan p-degerleri\n")
        f.write("% betikten ayrismisti, bkz. PAPER_STYLE.md §8.2).\n")
        f.write("% p makrolari MATEMATIK MODU icindir: $p = \\statKSSaWidePHolm$\n")
        for tag, r in res.items():
            if not r:
                continue
            t = tag.replace("_", "")
            f.write(f"\\newcommand{{\\stat{t}p}}{{{_texp(r['p'])}}}\n")
            f.write(f"\\newcommand{{\\stat{t}n}}{{{r['n']}}}\n")
            f.write(f"\\newcommand{{\\stat{t}w}}{{{r['w']}}}\n")
            f.write(f"\\newcommand{{\\stat{t}t}}{{{r['t']}}}\n")
            f.write(f"\\newcommand{{\\stat{t}l}}{{{r['l']}}}\n")
            f.write(f"\\newcommand{{\\stat{t}wtl}}{{{r['w']}/{r['t']}/{r['l']}}}\n")
            f.write(f"\\newcommand{{\\stat{t}drpd}}{{{r['d_rpd']:+.2f}}}\n")
            f.write(f"\\newcommand{{\\stat{t}dz}}{{{r['dz']:+.2f}}}\n")
            f.write(f"\\newcommand{{\\stat{t}dzabs}}{{{abs(r['dz']):.2f}}}\n")
        for name, val in extra:
            f.write(f"\\newcommand{{\\stat{name}}}{{{val}}}\n")
    print(f"\n-> {out} yazildi")


if __name__ == "__main__":
    main()
