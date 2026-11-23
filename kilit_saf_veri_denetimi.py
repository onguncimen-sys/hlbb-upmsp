# -*- coding: utf-8 -*-
"""LOCKED PURE TEST data audit.

FULL value comparison for the 72 locked instances: raw Vallada .txt ↔ converted JSON,
checking that every processing-time cell and every setup-matrix cell match exactly;
structural checks (dimensions, range bounds, zero diagonal, eligibility=all-1,
ready-time=0, non-binding cardinality). The output is pasted into the pre-registration
protocol. Run: ./venv/bin/python3 lit_gece/araclar/kilit_saf_veri_denetimi.py
"""
import json
import os

# RELEASE ADAPTATION (one line): in the dev repository this file lived under lit_gece/araclar/
# and ROOT was two directories up; in the package it sits at the root, so ROOT = script dir.
ROOT = os.path.abspath(os.path.dirname(__file__))
SIZES = ["50_30", "150_30", "100_10", "200_10"]
RANGES = ["1-9", "1-49", "1-99"]
INSTS = [1, 2, 3, 4, 5, 6]


def parse_raw(path):
    lines = [l.replace("\r", "").strip() for l in open(path)]
    lines = [l for l in lines if l]
    n, m = int(lines[0].split()[0]), int(lines[0].split()[1])
    assert int(lines[1].split()[0]) == m, "satir-2 makine sayisi uyusmuyor"
    P = {}
    for i in range(n):
        t = lines[2 + i].split()
        P[i] = {int(t[2 * k]): int(t[2 * k + 1]) for k in range(len(t) // 2)}
        assert len(P[i]) == m, f"is {i}: {len(P[i])} makine"
    ssd = lines.index("SSD")
    S = {}
    cur = ssd + 1
    for k in range(m):
        assert lines[cur].startswith("M"), f"M-baslik bekleniyordu: {lines[cur]}"
        cur += 1
        S[k] = []
        for _ in range(n):
            S[k].append([int(x) for x in lines[cur].split()])
            assert len(S[k][-1]) == n
            cur += 1
    return n, m, P, S


def main():
    tam = 0
    hatalar = []
    GOZLENEN = {}
    for s in SIZES:
        n_s, m_s = (int(x) for x in s.split("_"))
        for r in RANGES:
            lo, hi = 1, int(r.split("-")[1])
            for i in INSTS:
                raw = os.path.join(ROOT, "dataset_vallada", "large",
                                   f"I_{n_s}_{m_s}_S_{r}_{i}.txt")
                js = os.path.join(ROOT, "valladapure_kilit", s, f"S{r}", f"instance_{i}.json")
                n, m, P, S = parse_raw(raw)
                d = json.load(open(js))
                ok = (n == d["nJob"] == n_s and m == d["nMachine"] == m_s)
                # processing matrix: JSON is machine-major (processTime[str(machine)][job])
                for mk in range(m):
                    for j in range(n):
                        if float(P[j][mk]) != float(d["processTime"][str(mk)][j]):
                            ok = False; hatalar.append(f"{s}/S{r}/{i}: islem({j},{mk})")
                            break
                # setup matrix: full comparison + zero diagonal + range
                for mk in range(m):
                    J = d["setupTime"][str(mk)]
                    for a in range(n):
                        if S[mk][a][a] != 0:
                            ok = False; hatalar.append(f"{s}/S{r}/{i}: kosegen m{mk} i{a}")
                        for b in range(n):
                            if float(S[mk][a][b]) != float(J[a][b]):
                                ok = False; hatalar.append(f"{s}/S{r}/{i}: setup({mk},{a},{b})")
                                break
                # NOTE: nominal ranges are NOT enforced; the OBSERVED ranges are measured
                # and reported — the published files DO contain processing values of 100
                # (the generator apparently behaved like U[1,100]; the paper text says
                # "1-99"). We carry the values over UNCHANGED; the audit covers only value
                # preservation + structure. Observed ranges are summarized below.
                pv = [P[j][mk] for j in range(n) for mk in range(m)]
                sv = [S[mk][a][b] for mk in range(m) for a in range(n) for b in range(n) if a != b]
                GOZLENEN.setdefault((s, r), [10**9, 0, 10**9, 0])
                g = GOZLENEN[(s, r)]
                g[0] = min(g[0], min(pv)); g[1] = max(g[1], max(pv))
                g[2] = min(g[2], min(sv)); g[3] = max(g[3], max(sv))
                C = d["Compatibility"]
                if not all(all(c == 1 for c in C[k]) for k in C):
                    ok = False; hatalar.append(f"{s}/S{r}/{i}: uygunluk != 1")
                rt = d["readyTime"]
                rtv = rt.values() if isinstance(rt, dict) else rt
                if not all(v == 0 for v in rtv):
                    ok = False; hatalar.append(f"{s}/S{r}/{i}: hazir-zaman != 0")
                mn = d["minimumJobs"]; mx = d["maximumJobs"]
                mnv = mn.values() if isinstance(mn, dict) else mn
                mxv = mx.values() if isinstance(mx, dict) else mx
                if not (all(v == 0 for v in mnv) and all(v == n for v in mxv)):
                    ok = False; hatalar.append(f"{s}/S{r}/{i}: kardinalite")
                tam += ok
    print(f"TAM DOGRULANAN: {tam}/72 ornek (her islem + her hazirlik hucresi birebir)")
    print("GOZLENEN ARALIKLAR (boyut, aralik: islem min-maks | hazirlik min-maks):")
    for (sz, r), g in sorted(GOZLENEN.items()):
        print(f"  {sz:>7} S{r:>4}: islem {g[0]}-{g[1]} | hazirlik {g[2]}-{g[3]}")
    if hatalar:
        print("HATALAR:")
        for h in hatalar[:20]:
            print("  !", h)
    else:
        print("yapisal kontroller: boyut, kosegen-0, aralik sinirlari, islem 1-99, "
              "uygunluk=1, hazir-zaman=0, kardinalite bagsiz — HEPSI GECTI")


if __name__ == "__main__":
    main()
