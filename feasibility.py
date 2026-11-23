# -*- coding: utf-8 -*-
"""FEASIBILITY CHECKER — her algoritmanin cozumunu (atama) TUM kisitlara gore denetler.

check_assignment(assignment, data, claimed_obj) sunlari dogrular:
  1. KAPSAMA   : her is tam 1 kez atanmis (eksik/coklu/gecersiz indeks yok)
  2. UYGUNLUK  : her is yalnizca uygun makinede (l in L_i[i])
  3. KARDINALITE: c1[l] <= |makine l'deki is| <= c2[l]
  4. MAKESPAN  : (a) verilen SIRANIN makespan'i (readyTime dahil) = algoritmanin
                 iddia ettigi obj mi?  (b) EXACT en iyi rota <= iddia (imkansiz-dusuk mu?)

Donus dict: feasible, violations[], seq_makespan, exact_makespan, claimed, obj_ok, exact_ok.

Kullanim: bkz verify_feasibility.py (GA/CP/SA/HLBB cozumlerini cekip buraya besler).
"""
from collections import Counter

from HLBB import JobsOnMachinesDistMat
from exact_atsp import exact_atsp_dfj


def sequence_makespan(seq, l, readyTime, processTime, setupTime):
    """Verilen is SIRASININ makine l'deki tamamlanma zamani (readyTime dahil).
    GA/HLBB/SA'nin makespan tanimiyla ayni: rDate + proc[ilk] + sum(setup+proc)."""
    if not seq:
        return 0.0
    t = readyTime[l] + processTime[l][seq[0]]
    for k in range(1, len(seq)):
        t += setupTime[l][seq[k - 1]][seq[k]] + processTime[l][seq[k]]
    return float(t)


def check_assignment(assignment, data, claimed_obj=None, ex_tl=10.0, tol=1.0):
    """assignment: nMachine uzunlugunda liste; her eleman o makinedeki islerin SIRASI."""
    (nJob, nMachine, c1, c2, readyTime, processTime, setupTime, matrix, I_l, L_i, estSetup) = data
    V = []

    # 1) KAPSAMA
    alljobs = [j for m in assignment for j in m]
    cnt = Counter(alljobs)
    missing = [j for j in range(nJob) if cnt.get(j, 0) == 0]
    dup = [j for j in cnt if cnt[j] > 1]
    bad = [j for j in cnt if j < 0 or j >= nJob]
    if missing:
        V.append(f"KAPSAMA: {len(missing)} is ATANMAMIS -> {missing[:12]}")
    if dup:
        V.append(f"KAPSAMA: COKLU-atanmis -> {[(j, cnt[j]) for j in dup[:12]]}")
    if bad:
        V.append(f"KAPSAMA: gecersiz is indeksi -> {bad[:12]}")

    # 2) UYGUNLUK + 3) KARDINALITE
    for l in range(nMachine):
        for j in assignment[l]:
            if 0 <= j < nJob and l not in L_i[j]:
                V.append(f"UYGUNLUK: is {j} makine {l}'de ama L_i[{j}]={L_i[j]}")
        k = len(assignment[l])
        lo, hi = int(c1[str(l)]), int(c2[str(l)])
        if k < lo:
            V.append(f"KARDINALITE-alt: makine {l} {k} is < {lo}")
        if k > hi:
            V.append(f"KARDINALITE-ust: makine {l} {k} is > {hi}")

    # 4) MAKESPAN — verilen sira + exact yeniden rota
    seq_comps, ex_comps = [], []
    for l in range(nMachine):
        seq_comps.append(sequence_makespan(assignment[l], l, readyTime, processTime, setupTime))
        if assignment[l]:
            dm = JobsOnMachinesDistMat(processTime, setupTime, assignment[l], l)
            ex_comps.append(readyTime[l] + exact_atsp_dfj(dm, ex_tl))
        else:
            ex_comps.append(0.0)
    seq_mk = max(seq_comps) if seq_comps else 0.0
    ex_mk = max(ex_comps) if ex_comps else 0.0

    obj_ok = exact_ok = None
    if claimed_obj is not None:
        # (a) algoritmanin iddiasi kendi sirasinin makespan'i mi (readyTime dahil)?
        obj_ok = abs(seq_mk - claimed_obj) <= max(tol, 0.005 * claimed_obj)
        if not obj_ok:
            V.append(f"OBJ-TUTARSIZ: iddia={claimed_obj} ama verilen siranin gercek makespan'i={seq_mk:.0f} "
                     f"(readyTime dahil). Fark={seq_mk-claimed_obj:+.0f}")
        # (b) EXACT en iyi rota, iddiadan BUYUK olamaz (imkansiz-dusuk iddia)
        exact_ok = ex_mk <= claimed_obj + tol
        if not exact_ok:
            V.append(f"IMKANSIZ-DUSUK: iddia={claimed_obj} ama bu atamanin EXACT en iyi makespan'i "
                     f"{ex_mk:.0f} (iddia bundan kucuk -> gecersiz)")

    return {"feasible": len([v for v in V if not v.startswith('OBJ-TUTARSIZ')]) == 0,
            "no_violation": len(V) == 0,
            "violations": V,
            "seq_makespan": round(seq_mk, 1),
            "exact_makespan": round(ex_mk, 1),
            "claimed": claimed_obj,
            "obj_ok": obj_ok, "exact_ok": exact_ok}


def summarize(name, res):
    """Tek satirlik ozet dizesi."""
    flag = "OK" if (res["no_violation"]) else ("FEASIBLE-ama-obj-tutarsiz" if res["feasible"] else "INFEASIBLE")
    return (f"{name:<16} {flag:<26} seq_mk={res['seq_makespan']:<9} exact_mk={res['exact_makespan']:<9} "
            f"iddia={res['claimed']}")


def verify_solution(name, assignment, data, claimed, verbose=True):
    """Benchmark'a GOMULU kullanim: cozumu denetle, JSON'a yazilabilir KOMPAKT kayit dondur.
    assignment None ise (cozum cikarilamadi) atlar. Infeasible ise uyari basar.
    Not: HLBB/CP gibi KUME-tabanli (sirasiz) cozumlerde makespan denetimi exact_mk<=iddia
    ile yapilir; seq_mk (liste sirasi) yanil_ci olabilir -> feasible bayragi kisitlara bakar."""
    if assignment is None:
        return {"feasible": None, "n_violations": None, "exact_makespan": None, "violations": []}
    r = check_assignment(assignment, data, claimed)
    if verbose and not r["feasible"]:
        print(f"      [!] {name} INFEASIBLE -> {r['violations'][:3]}", flush=True)
    return {"feasible": bool(r["feasible"]), "no_violation": bool(r["no_violation"]),
            "n_violations": len(r["violations"]), "exact_makespan": r["exact_makespan"],
            "violations": r["violations"][:6]}
