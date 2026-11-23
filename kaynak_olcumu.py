# -*- coding: utf-8 -*-
"""KAYNAK OLCUMU -- hakem Major concern 4: her yontem ANA KIYASTAKI ayariyla gercekte kac
cekirdek-saniye harciyor?

Ana kiyas dosyalarinda yalniz duvar saati var; islemci suresi hic kaydedilmedi. Bu betik
ana kiyasin AYNI cagrilarini (ayni ayar, baglama YOK) kisa bir ornek kumesinde yineler ve
surec agacinin (cocuk surecler dahil) islemci suresini olcer. SONUC URETMEZ: buradaki
makespan degerleri raporlanmaz, yalniz islemci kullanimi okunur.

  yontemimiz : 8 boyut x ornek 1, 200 sn (kullanim boyutla degistigi icin hepsi)
  SA/HGA/GA  : 3 boyut x ornek 1, 60 sn  (tek is parcacikli; kullanim butceye bagli degil)
  CP         : 3 boyut x ornek 1, 60 sn  (cozucu varsayilani: butun cekirdekler)

Cikti: results/kaynak_olcumu.csv   (yarida kesilirse ayni komut kaldigi yerden devam eder)
Kullanim: python3 kaynak_olcumu.py            (run_trackb_1core.sh ikinci asamada cagirir)
⚠️ Olcum sirasinda makinede baska agir is OLMAMALI; tek cekirdek kosusuyla AYNI ANDA kosmaz.
"""
import csv
import os
import resource
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(_HERE, "new_dataset_niche_v2")
OUT = os.environ.get("KAYNAK_CSV", os.path.join(_HERE, "results", "kaynak_olcumu.csv"))
SMOKE = os.environ.get("KAYNAK_SMOKE") == "1"
ALL = ["50_10", "100_15", "150_15", "200_20", "250_20", "400_20", "640_25", "800_30"]
THREE = ["50_10", "250_20", "800_30"]
COLS = ["method", "size", "budget", "wall_s", "cpu_s", "ort_cekirdek", "kapsam"]


def _inst(s):
    return os.path.join(DATA, f"{s}_1-99_e50_ron", "instance_1.json")


def _cpu_all():
    a = resource.getrusage(resource.RUSAGE_SELF)
    b = resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime


def child(kind, path, budget):
    """Ayri surecte: ornegi oku, SONRA saati baslat -> okuma suresi olcume girmez."""
    sys.path.insert(0, _HERE)
    os.chdir(_HERE)
    from readproblem import readproblem
    d = readproblem(path, consider_compatibility=True, consider_workload=True)
    nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
    c0, t0 = _cpu_all(), time.time()
    if kind == "HLBB":
        from hlbb_hm import run_integrated_sr          # uretim cagrisiyla birebir (niche_benchmark.run_hlbb)
        run_integrated_sr(nJob, nM, c1, c2, rt, pt, st, I_l, L_i, total_time_limit=budget,
                          kmach=3, arc_k=5, seed=0, return_solution=True)
    else:
        from CP_model import CP as CP_solve
        CP_solve(nJob, nM, c1, c2, rt, pt, st, I_l, L_i, time_limit=budget, return_solution=True)
    print(f"OLCUM {time.time() - t0:.2f} {_cpu_all() - c0:.2f}", flush=True)


def _done():
    if not os.path.exists(OUT):
        return set()
    return {(r["method"], r["size"]) for r in csv.DictReader(open(OUT, newline=""))}


def _write(row):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    new = not os.path.exists(OUT)
    with open(OUT, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow(row)


def main():
    sys.path.insert(0, _HERE)
    os.chdir(_HERE)
    import niche_benchmark as nb
    from niche_bridge import ensure_bin
    hb, sb = (15, 15) if SMOKE else (200, 60)
    jobs = [("HLBB", s, hb) for s in (ALL[:1] if SMOKE else ALL)]
    for s in (THREE[:1] if SMOKE else THREE):
        jobs += [("SA", s, sb), ("HGA", s, sb), ("GA", s, sb), ("CP", s, sb)]
    done = _done()
    todo = [j for j in jobs if (j[0], j[1]) not in done]
    left = sum(j[2] for j in todo)
    print(f"### KAYNAK OLCUMU | {len(todo)} olcum kaldi ({len(jobs) - len(todo)} hazir) | "
          f"butce toplami ~{left / 60:.0f} dk + yukleme | cikti {os.path.relpath(OUT, _HERE)} ###", flush=True)
    t_start = time.time()
    for k, (meth, s, bud) in enumerate(todo, 1):
        path = _inst(s)
        if meth in ("HLBB", "CP"):
            out = subprocess.run([sys.executable, os.path.abspath(__file__), "--child", meth, path, str(bud)],
                                 capture_output=True, text=True, cwd=_HERE)
            ln = [l for l in out.stdout.splitlines() if l.startswith("OLCUM")]
            if not ln:
                print(f"  HATA {meth} {s}: {out.stderr[-300:]}", flush=True)
                continue
            wall, cpu = (float(x) for x in ln[0].split()[1:3])
            kap = "algoritma (ornek okuma haric)"
        else:
            bp = ensure_bin(path)
            r0 = resource.getrusage(resource.RUSAGE_CHILDREN)
            t0 = time.time()
            out = subprocess.run([nb.JULIA, "-t", "auto", f"{nb.CODE}/run_one.jl", meth, bp, str(bud), "0"],
                                 capture_output=True, text=True, env=nb.ENV)
            wall = time.time() - t0
            r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
            cpu = (r1.ru_utime + r1.ru_stime) - (r0.ru_utime + r0.ru_stime)
            if not any(l.startswith("RESULT") for l in out.stdout.splitlines()):
                print(f"  HATA {meth} {s}: {out.stderr[-300:]}", flush=True)
                continue
            kap = "butun surec (Julia acilisi dahil)"
        _write(dict(method=meth, size=s.replace("_", "x"), budget=bud, wall_s=round(wall, 1),
                    cpu_s=round(cpu, 1), ort_cekirdek=round(cpu / wall, 2), kapsam=kap))
        left -= bud
        print(f"  [{k:2d}/{len(todo)}] {meth:4s} {s.replace('_', 'x'):7s} butce {bud:3d} sn -> "
              f"duvar {wall:6.1f} sn | islemci {cpu:7.1f} cekirdek-sn | ort {cpu / wall:5.2f} cekirdek "
              f"| gecen {(time.time() - t_start) / 60:4.1f} dk | kalan ~{left / 60:3.0f} dk", flush=True)
    print("=== KAYNAK OLCUMU BITTI ===", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    else:
        main()
