# -*- coding: utf-8 -*-
"""Yerel-eniyilik sondasi — KILITLI nis cozumleri uzerinde KESIFSEL SONRADAN ANALIZ.

Secim kurali ONCEDEN sabit (sonuclara bakilmadan): iki EN BUYUK STANDART hucre
(640_25/t99, 800_30/t99) x 6 ornek x 3 tohum = 36 HLBB final cozumunun TAMAMI.
Komsuluk eski sondayla ayni (_b2_polish_oracle.polish): darbogaz-odakli
tasima+takas, her aday GERCEK LKH yeniden-rotalamasiyla; butce 300 sn/cozum
(tam komsuluk taranirsa erken biter). Cikti: results/kilit_nis_sonda.csv.
Benchmark kosusu DEGILDIR; kilitli sonuclari degistirmez. __main__ korumasi SART."""
import csv
import json
import time

from _b2_polish_oracle import polish, spans_of
from readproblem import readproblem
from HLBB import clear_environment

HUCRELER = [("640_25", "t99"), ("800_30", "t99")]
BUTCE = 300.0


def main():
    coz = {}
    for satir in open("results/kilitli_nis_cozumler/cozumler.jsonl"):
        d = json.loads(satir)
        ar, sz, i, m, s = d["key"]
        if m == "HLBB" and (sz, ar) in HUCRELER:
            coz[(sz, ar, int(i), int(s))] = d
    beklenen = {(sz, ar, i, s) for sz, ar in HUCRELER for i in range(1, 7) for s in (0, 1, 2)}
    assert set(coz) == beklenen, (len(coz), len(beklenen))
    with open("results/kilit_nis_sonda.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["size", "aralik", "inst", "seed", "mk0", "mk1", "iyilesme",
                    "n_deger", "n_iyi", "tukendi", "sure_s"])
        for (sz, ar, i, s) in sorted(beklenen):
            d = coz[(sz, ar, i, s)]
            nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = readproblem(
                f"nis_kilit2026/{sz}_{ar}/instance_{i}.json", True, True)
            A = [list(m) for m in d["assign"]]
            h = spans_of(A, nM, rt, pt, st)
            mk0 = max(h)
            assert abs(mk0 - d["claimed"]) < 1e-6, (sz, i, s, mk0, d["claimed"])
            t0 = time.time()
            mk1, n_ev, n_imp, _ = polish(A, h, nJob, nM, c2, L_i, rt, pt, st, BUTCE)
            dt = time.time() - t0
            tukendi = dt < BUTCE - 1.0
            w.writerow([sz, ar, i, s, mk0, mk1, mk0 - mk1, n_ev, n_imp,
                        int(tukendi), round(dt, 1)])
            f.flush()
            print(f"{sz} i{i} s{s}: {mk0:.0f}->{mk1:.0f} ({n_ev} deger, "
                  f"{'tam tarandi' if tukendi else 'BUTCE DOLDU'}, {dt:.0f}s)", flush=True)
            clear_environment()


if __name__ == "__main__":
    main()
