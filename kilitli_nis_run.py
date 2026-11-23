# -*- coding: utf-8 -*-
"""LOCKED NICHE TEST runner (pre-registered protocol EK-B; see
ON_KAYIT_PROTOKOLU.md in the package root, in Turkish).

MATRIX: 14 cells × 6 fresh-seed instances (nis_kilit2026/, seeds kilit2026_*) = 84 instances.
  8 standard sizes (t99) + 2 boundary cells (800_40, 400_80; t99) + dose (400_20, 800_30 × t9, t49)
  HLBB / SA / HGA / GA : 3 repeats each (seeds 0,1,2), 200 s wall  -> 1008 runs
  CP                   : 1 run, 1000 s                             ->   84 runs
TOTAL 1092 runs ≈ 80 h. CONFIRMATORY FAMILY: only {400_20, 800_30} × t99 × 4 competitors
(m=8); everything else is PRE-DECLARED DESCRIPTIVE.

NICHE PARAMETER REGIME (EK-A lock): DELTAINS_FIX=1 + HGA_DINS=0.9 + GA_PM=0.3; Julia -t 1.
Capsule methods read the .nbin bridge (run_one.jl niche mode); HLBB and CP read the JSON
whose bridge equivalence was verified 84/84 (consider_compatibility=True,
consider_workload=True — identical to the niche pipeline).

HARDENING (same as the pure runner, plus additions):
- ACCEPTANCE GATE: if the shared check (feas_hook.check) is not True, the result is NOT written.
- FAILURE MATRIX: infrastructure -> 1 retry with the same identity; method crash -> failure
  record; on a harness timeout, partial output is accepted only if it passes the check.
- WRITE INTEGRITY: computation and recording are separate phases; a write error STOPS the
  runner and never re-runs the algorithm.
- TASK LIST on disk (shuffled with a fixed seed, validated on resume); flock single-runner
  lock + stale-process scan; 168 data hashes (84 JSON + 84 nbin) recomputed at every start.
- ADDITIONS: run identity (generated in the first session, preserved on resume); a backup of
  the record files after every 25 accepted results (results/kilitli_nis_yedek/); interim
  checks cover only completion/duration/health — NO looking at results to add instances,
  change settings, or stop early.
- CP: status / bound / gap / workers / solver time + LOG file; if there is no solution, a
  failure is recorded with a "no solution" reason.
- FINISH: no duplicates; 1092 = results ∪ failures; every result has an all-fields-OK,
  equal-claimed check record and a stored solution — "kosu bitti" is not printed otherwise.

USAGE (the USER starts the run; if interrupted, the same command resumes where it left off):
  cd /home/sarp/HLBB && nohup ./venv/bin/python3 -u kilitli_nis_run.py > kilitli_nis.log 2>&1 &
Smoke run: ./venv/bin/python3 kilitli_nis_run.py duman
Verification (no writes): ./venv/bin/python3 kilitli_nis_run.py dogrula
"""
import csv
import fcntl
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(_HERE, "results", "kilitli_nis.csv")
COLS = ["aralik", "size", "inst", "method", "seed", "makespan", "iters", "evals", "tbest",
        "wall_real", "budget", "durum", "bound", "gap_pct", "workers", "solve_s",
        "deneme", "sirali"]
# 14 cells: (size, aralik). Range label "t9"/"t49"/"t99" (generated folder {size}_{aralik}).
HUCRELER = ([(s, "t99") for s in ["50_10", "100_15", "150_15", "200_20", "250_20",
                                  "400_20", "640_25", "800_30", "800_40", "400_80"]] +
            [("400_20", "t9"), ("400_20", "t49"), ("800_30", "t9"), ("800_30", "t49")])
INSTS = [1, 2, 3, 4, 5, 6]
SEEDS = [0, 1, 2]
WALL, CP_WALL = 200, 1000
YEDEK_HER = 25
# RELEASE ADAPTATION: can be overridden via environment variable; default = path recorded
# for the original runs.
JULIA = os.environ.get("HLBB_JULIA", "/home/sarp/julia_install/julia-1.7.0/bin/julia")
CODE = os.path.join(_HERE, "rolim_capsule", "code")
VERI = os.path.join(_HERE, "nis_kilit2026")
SOLDIR = os.path.join(_HERE, "results", "kilitli_nis_cozumler")
NIS_ENV = {"DELTAINS_FIX": "1",
           "JULIA_DEPOT_PATH": os.environ.get("JULIA_DEPOT_PATH", "/home/sarp/julia_install/depot"),
           "HGA_DINS": "0.9", "GA_PM": "0.3"}      # EK-A competitor parameter lock
INFRA_HATALAR = (OSError, BlockingIOError, InterruptedError, MemoryError)


class YontemBasarisizligi(Exception):
    pass


def _js(size, aralik, i):
    return os.path.join(VERI, f"{size}_{aralik}", f"instance_{i}.json")


def _nb(size, aralik, i):
    return os.path.join(VERI, f"{size}_{aralik}", f"instance_{i}.nbin")


def _oku(size, aralik, i):
    from readproblem import readproblem
    return readproblem(_js(size, aralik, i),
                       consider_compatibility=True, consider_workload=True)


def _anahtarlar():
    ks = []
    for (s, r) in HUCRELER:
        for i in INSTS:
            for m in ("HLBB", "SA", "HGA", "GA"):
                for sd in SEEDS:
                    ks.append((r, s, str(i), m, str(sd)))
            ks.append((r, s, str(i), "CP", "0"))
    return ks


def _yaz_dayanikli(path, satir, baslik):
    """Durable write: 3 attempts; on failure the runner STOPS (no inconsistent state left)."""
    for d in range(3):
        try:
            yeni = not os.path.exists(path)
            with open(path, "a", newline="") as fh:
                w = csv.writer(fh)
                if yeni:
                    w.writerow(baslik)
                w.writerow(satir)
                fh.flush()
                os.fsync(fh.fileno())
            return
        except Exception as e:
            if d == 2:
                sys.exit(f"⛔ KALICI KAYIT YAZILAMADI ({path}): {e} — kosucu durdu; "
                         f"ortam duzeltilip AYNI komutla devam edilir (son kosu yeniden alinir).")
            time.sleep(2)


def _deneme_kaydi(key, deneme, sinif, detay):
    _yaz_dayanikli(CSV_PATH[:-4] + ".denemeler.csv",
                   list(key) + [deneme, sinif, time.strftime("%F %T"), detay[:400]],
                   ["aralik", "size", "inst", "method", "seed", "deneme", "sinif",
                    "zaman", "detay"])


def _basarisiz(key, neden):
    _yaz_dayanikli(CSV_PATH[:-4] + ".basarisiz.csv",
                   list(key) + [neden, time.strftime("%F %T")],
                   ["aralik", "size", "inst", "method", "seed", "neden", "zaman"])


def _cozum_sakla(key, claimed, assign, sirali):
    os.makedirs(SOLDIR, exist_ok=True)
    p = os.path.join(SOLDIR, "cozumler.jsonl")
    for d in range(3):
        try:
            with open(p, "a") as f:
                f.write(json.dumps({"key": list(key), "claimed": claimed,
                                    "sirali": sirali, "assign": assign}) + "\n")
                f.flush()
                os.fsync(f.fileno())
            return
        except Exception as e:
            if d == 2:
                sys.exit(f"⛔ COZUM SAKLANAMADI: {e} — kosucu durdu (tutarsizlik onlenir).")
            time.sleep(2)


def _yedekle():
    """Periodic copy of the record files (single directory, overwritten in place)."""
    yd = os.path.join(_HERE, "results", "kilitli_nis_yedek")
    try:
        os.makedirs(yd, exist_ok=True)
        for ek in ("", "_feaslog"):
            p = CSV_PATH[:-4] + ek + ".csv"
            if os.path.exists(p):
                shutil.copy2(p, yd)
        for ek in (".denemeler.csv", ".basarisiz.csv", ".gorevler.txt", ".manifest.json"):
            p = CSV_PATH[:-4] + ek
            if os.path.exists(p):
                shutil.copy2(p, yd)
        cz = os.path.join(SOLDIR, "cozumler.jsonl")
        if os.path.exists(cz):
            shutil.copy2(cz, yd)
    except Exception as e:
        print(f"    [yedek] kopyalanamadi: {e}", flush=True)   # backup errors do not stop the run


def _denetim_kapisi(feas, kim):
    """feas_hook.check return: True=clean, False=violation, None=could not be checked."""
    if feas is True:
        return
    raise YontemBasarisizligi("denetim-ihlali" if feas is False else f"denetlenemedi:{kim}")


# ------------------------------------------------------------------ runners
def _capsule_cikti_ayristir(stdout):
    res = sol = None
    for ln in (stdout or "").splitlines():
        if ln.startswith("RESULT "):
            res = ln.split()
        elif ln.startswith("SOL "):
            sol = [[int(x) - 1 for x in mm.split(",") if x] for mm in ln[4:].split("|")]
    return res, sol


def run_capsule(algo, key, size, aralik, i, seed):
    import feas_hook
    cmd = [JULIA, "-t", "1", os.path.join(CODE, "run_one.jl"), algo,
           _nb(size, aralik, i), str(WALL), str(seed)]
    env = dict(os.environ)
    for k, v in NIS_ENV.items():
        env[k] = v
    kismi = ""
    try:
        p = subprocess.run(cmd, cwd=CODE, capture_output=True, text=True,
                           timeout=WALL + 900, env=env)
        out, rc, err = p.stdout, p.returncode, p.stderr
    except subprocess.TimeoutExpired as e:
        # HARNESS timeout: if the partial output holds a valid RESULT+SOL pair,
        # accept it after the feasibility check
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        rc, err, kismi = 0, "", "harness-zaman-asimi"
    res, sol = _capsule_cikti_ayristir(out)
    if rc != 0 or res is None:
        raise YontemBasarisizligi(f"cikti-yok rc={rc} err={(err or '')[-300:]}")
    mk, iters, evals, wall_real, tbest = (float(res[2]), res[3], res[4], res[5], res[6])
    d = _oku(size, aralik, i)
    feas = feas_hook.check("kilitli_nis", algo, f"{size}_{aralik}/i{i}", seed, sol, d, mk,
                           ordered=sol is not None)
    _denetim_kapisi(feas, algo)
    return dict(satir=[mk, iters, evals, tbest, wall_real, WALL,
                       kismi, "", "", "", "", None, int(sol is not None)],
                claimed=mk, assign=sol, sirali=sol is not None)


def run_hlbb(key, size, aralik, i, seed):
    import feas_hook
    from hlbb_hm import run_integrated_sr
    d = _oku(size, aralik, i)
    nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
    t0 = time.time()
    best, best_time, iters, assign = run_integrated_sr(
        nJob, nM, c1, c2, rt, pt, st, I_l, L_i,
        total_time_limit=WALL, seed=seed, return_solution=True, verbose=False)
    wall_real = round(time.time() - t0, 1)
    ordered = None
    for _ in range(2):                              # sequence extraction: 1 internal retry
        try:
            from tour_capture import sequence_solution
            ordered = sequence_solution(assign, pt, st)
            break
        except Exception as e:
            print(f"    [tour] sira cikarilamadi: {e}", flush=True)
    feas = feas_hook.check("kilitli_nis", "HLBB", f"{size}_{aralik}/i{i}", seed,
                           ordered or assign, d, float(best), ordered=ordered is not None)
    _denetim_kapisi(feas, "HLBB")
    return dict(satir=[float(best), iters, "", round(best_time, 1), wall_real, WALL,
                       "", "", "", "", "", None, int(ordered is not None)],
                claimed=float(best), assign=ordered or assign, sirali=ordered is not None)


CP_LAST = {}


def _cp_solve_yamasi():
    from docplex.cp.model import CpoModel
    _orig = CpoModel.solve

    def _solve(self, **kw):
        logp = CP_LAST.get("_logp")                  # read BEFORE clearing
        CP_LAST.clear()
        lf = None
        try:
            if logp:
                lf = open(logp, "w")
                kw = dict(kw); kw["LogVerbosity"] = "Normal"; kw["log_output"] = lf
            sol = _orig(self, **kw)
        finally:
            if lf:
                lf.close()
        try:
            CP_LAST["durum"] = str(sol.get_solve_status()) if sol else "cozum_yok"
            CP_LAST["bound"] = sol.get_objective_bound() if sol else None
            inf = sol.get_solver_infos() if sol else {}
            CP_LAST["workers"] = inf.get("EffectiveWorkers")
            CP_LAST["solve_s"] = inf.get("TotalTime")
        except Exception as e:
            CP_LAST["durum"] = f"okunamadi:{type(e).__name__}"
        return sol

    CpoModel.solve = _solve


def run_cp(key, size, aralik, i):
    import feas_hook
    from CP_model import CP as CP_solve
    d = _oku(size, aralik, i)
    nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
    os.makedirs(SOLDIR, exist_ok=True)
    CP_LAST["_logp"] = os.path.join(SOLDIR, f"cp_log_{size}_{aralik}_i{i}.txt")
    t0 = time.time()
    obj, _g, assign = CP_solve(nJob, nM, c1, c2, rt, pt, st, I_l, L_i,
                               time_limit=CP_WALL, return_solution=True)
    wall_real = round(time.time() - t0, 1)
    if obj is None or assign is None:
        raise YontemBasarisizligi(f"cp-cozum-yok durum={CP_LAST.get('durum', '?')}")
    bound = CP_LAST.get("bound")
    gap = (abs(obj - bound) / obj * 100) if (bound is not None and obj and obj > 0) else ""
    feas = feas_hook.check("kilitli_nis", "CP", f"{size}_{aralik}/i{i}", 0, assign, d,
                           float(obj), ordered=True)
    _denetim_kapisi(feas, "CP")
    return dict(satir=[float(obj), "", "", "", wall_real, CP_WALL,
                       CP_LAST.get("durum", ""), bound if bound is not None else "",
                       (f"{gap:.2f}" if gap != "" else ""), CP_LAST.get("workers", ""),
                       CP_LAST.get("solve_s", ""), None, 1],
                claimed=float(obj), assign=assign, sirali=True)


# ------------------------------------------------------------------ identity / lock / tasks
def _sha_dosya_dogrula():
    """The 84 JSON + 84 nbin hashes are RECOMPUTED and compared against the recorded lists."""
    def _kontrol(liste):
        for ln in open(os.path.join(VERI, liste)):
            h, yol = ln.split(None, 1)
            p = os.path.join(VERI, yol.strip())
            hh = hashlib.sha256()
            with open(p, "rb") as f:
                for b in iter(lambda: f.read(1 << 20), b""):
                    hh.update(b)
            if hh.hexdigest() != h:
                sys.exit(f"⛔ VERI KIMLIGI UYUSMUYOR: {yol.strip()}")
    _kontrol("JSON_SHA256.txt")
    _kontrol("NBIN_SHA256.txt")


_KILIT_FH = None


def _tek_kosucu_kilidi():
    global _KILIT_FH
    p = CSV_PATH[:-4] + ".KILIT"
    _KILIT_FH = open(p, "a+")
    try:
        fcntl.flock(_KILIT_FH.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("⛔ baska bir kosucu calisiyor (flock); once onu durdurun.")
    _KILIT_FH.seek(0); _KILIT_FH.truncate(); _KILIT_FH.write(str(os.getpid())); _KILIT_FH.flush()
    for desen in ("run_one.jl", "cpoptimizer"):
        q = subprocess.run(["pgrep", "-f", desen], capture_output=True, text=True)
        artik = [x for x in q.stdout.split() if x and int(x) != os.getpid()]
        if artik:
            sys.exit(f"⛔ onceki kosudan artik surec var ({desen}: {artik}); "
                     f"once 'pkill -f {desen}' ile temizleyin.")


def _gorev_dosyasi():
    p = CSV_PATH[:-4] + ".gorevler.txt"
    beklenen = _anahtarlar()
    if os.path.exists(p):
        satirlar = [tuple(l.strip().split(",")) for l in open(p) if l.strip()]
        if satirlar != list(dict.fromkeys(satirlar)) or set(satirlar) != set(beklenen):
            sys.exit("⛔ gorev dosyasi beklenen anahtar kumesiyle uyusmuyor")
        return satirlar
    sira = list(beklenen)
    random.Random("kilitlinis2026").shuffle(sira)
    with open(p, "w") as f:
        for k in sira:
            f.write(",".join(k) + "\n")
        f.flush(); os.fsync(f.fileno())
    return sira


def _onceki_denemeler():
    sayac = {}
    p = CSV_PATH[:-4] + ".denemeler.csv"
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            k = (r["aralik"], r["size"], r["inst"], r["method"], r["seed"])
            sayac[k] = max(sayac.get(k, 0), int(r["deneme"]))
    return sayac


def _tamamlananlar():
    sonuc, cift = set(), []
    if os.path.exists(CSV_PATH):
        for r in csv.DictReader(open(CSV_PATH)):
            k = (r["aralik"], r["size"], r["inst"], r["method"], r["seed"])
            if k in sonuc:
                cift.append(k)
            sonuc.add(k)
    bas = set()
    bp = CSV_PATH[:-4] + ".basarisiz.csv"
    if os.path.exists(bp):
        for r in csv.DictReader(open(bp)):
            bas.add((r["aralik"], r["size"], r["inst"], r["method"], r["seed"]))
    if cift:
        sys.exit(f"⛔ CSV'de cift anahtar: {cift[:5]} — elle incelenmeli")
    if sonuc & bas:
        sys.exit(f"⛔ ayni anahtar hem sonuc hem basarisiz: {list(sonuc & bas)[:5]}")
    return sonuc | bas


def _kosucu_sha():
    return hashlib.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest()[:16]


def _manifest(gorev_sha, bekleyen):
    man_p = CSV_PATH[:-4] + ".manifest.json"
    eski = json.load(open(man_p)) if os.path.exists(man_p) else []
    ksha = _kosucu_sha()
    if eski and eski[0].get("kosucu_sha256") not in (None, ksha):
        sys.exit("⛔ kosucu dosyasi ilk oturumdan farkli — devam insan karariyla "
                 "(manifest'teki kosucu_sha256 ile karsilastirin).")
    if eski and eski[0].get("gorev_listesi_sha256") not in (None, gorev_sha):
        sys.exit("⛔ gorev listesi ilk oturumdan farkli.")
    kimlik = (eski[0]["kosu_kimligi"] if eski else
              f"kilitli_nis_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}")
    man = {
        "zaman": time.strftime("%F %T"),
        "kosu_kimligi": kimlik,                      # generated in the first session, preserved
        "git": subprocess.run(["git", "rev-parse", "HEAD"], cwd=_HERE,
                              capture_output=True, text=True).stdout.strip(),
        "kirli": subprocess.run(["git", "status", "--short"], cwd=_HERE,
                                capture_output=True, text=True).stdout.splitlines()[:40],
        "kosucu_sha256": ksha,
        "butce": {"stokastik": WALL, "CP": CP_WALL},
        "tohumlar": SEEDS,
        "ortam_istenen": NIS_ENV,
        "rejim": "NIS (EK-A ayarli rakipler: HGA_DINS=0.9, GA_PM=0.3; DELTAINS_FIX=1)",
        "julia": JULIA + " -t 1",
        "gorev_listesi_sha256": gorev_sha,
        "veri_kimligi": "baslatmada 168 sha256 (84 JSON + 84 nbin) yeniden dogrulandi",
        "bekleyen": bekleyen,
        "islemci": open("/proc/cpuinfo").read().split("model name")[1]
                   .split("\n")[0].split(":")[1].strip(),
    }
    eski.append(man)
    json.dump(eski, open(man_p, "w"), indent=1, ensure_ascii=False)


# ------------------------------------------------------------------ final verification
def _dogrulama(yazdir=True):
    """Returns (passed, report). CONDITIONS: no duplicates; 1092 = results ∪ failures
    (empty intersection); every result has a check record with the same key, all fields OK
    and an equal claimed value; every result has a stored solution."""
    sorunlar = []
    beklenen = set(_anahtarlar())
    rows, gorulen = [], set()
    if os.path.exists(CSV_PATH):
        for r in csv.DictReader(open(CSV_PATH)):
            k = (r["aralik"], r["size"], r["inst"], r["method"], r["seed"])
            if k in gorulen:
                sorunlar.append(f"cift satir: {k}")
            gorulen.add(k); rows.append((k, r))
    bas = set()
    bp = CSV_PATH[:-4] + ".basarisiz.csv"
    if os.path.exists(bp):
        for r in csv.DictReader(open(bp)):
            bas.add((r["aralik"], r["size"], r["inst"], r["method"], r["seed"]))
    if gorulen & bas:
        sorunlar.append(f"sonuc∩basarisiz: {list(gorulen & bas)[:3]}")
    eksik = beklenen - gorulen - bas
    if eksik:
        sorunlar.append(f"eksik {len(eksik)}: {list(eksik)[:3]}")
    fazla = gorulen - beklenen
    if fazla:
        sorunlar.append(f"beklenmeyen anahtar: {list(fazla)[:3]}")
    feas = {}
    fp = CSV_PATH[:-4] + "_feaslog.csv"
    if os.path.exists(fp):
        for r in csv.DictReader(open(fp)):
            kk = (r["method"], r["inst"], r["seed"])
            tamiz = (r["kapsama"] == "OK" and r["uygunluk"] == "OK"
                     and r["route_ok"] in ("OK",) and r["seq_ok"] in ("OK", "n/a"))
            feas[kk] = (r["claimed"], tamiz)          # last record wins (the accepted attempt)
    coz = set()
    cp_j = os.path.join(SOLDIR, "cozumler.jsonl")
    if os.path.exists(cp_j):
        for ln in open(cp_j):
            try:
                coz.add(tuple(json.loads(ln)["key"]))
            except Exception:
                sorunlar.append("cozum satiri bozuk")
    for k, r in rows:
        aralik, size, inst, meth, seed = k
        fk = (meth, f"{size}_{aralik}/i{inst}", seed)
        if fk not in feas:
            sorunlar.append(f"denetim kaydi yok: {k}")
        else:
            cl, tamiz = feas[fk]
            if not tamiz:
                sorunlar.append(f"denetim OK degil: {k}")
            try:
                if abs(float(cl) - float(r["makespan"])) > 1e-6:
                    sorunlar.append(f"iddia≠denetim: {k} ({r['makespan']} vs {cl})")
            except ValueError:
                sorunlar.append(f"iddia okunamadi: {k}")
        if k not in coz:
            sorunlar.append(f"saklanmis cozum yok: {k}")
    if yazdir:
        print(f"DOGRULAMA: beklenen {len(beklenen)} | sonuc {len(gorulen)} | "
              f"basarisiz {len(bas)} | sorun {len(sorunlar)}", flush=True)
        for s in sorunlar[:25]:
            print("  !", s, flush=True)
    return (not sorunlar), sorunlar


def main():
    if shutil.disk_usage(_HERE).free < 4 << 30:
        sys.exit("⛔ disk < 4 GB (CP gunlukleri + cozum arsivi icin yer gerekli)")
    _tek_kosucu_kilidi()
    _sha_dosya_dogrula()
    import feas_hook
    feas_hook.LOG_PATH = CSV_PATH[:-4] + "_feaslog.csv"
    _cp_solve_yamasi()
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    gorevler = _gorev_dosyasi()
    gsha = hashlib.sha256(open(CSV_PATH[:-4] + ".gorevler.txt", "rb").read()).hexdigest()[:16]
    done = _tamamlananlar()
    denemeler = _onceki_denemeler()
    bekleyen = [k for k in gorevler if k not in done]
    _manifest(gsha, len(bekleyen))
    _yedekle()
    print(f"### KILITLI NIS | {len(_anahtarlar())} kosu ({len(done)} var, {len(bekleyen)} "
          f"kalan) | stokastik {WALL}s x tohum {SEEDS} | CP {CP_WALL}s | gorev-sha {gsha} "
          f"| kosucu-sha {_kosucu_sha()} ###", flush=True)
    t0 = time.time()
    kabul = 0
    for n, key in enumerate(bekleyen, 1):
        aralik, size, i, meth, seed = key
        taban = denemeler.get(key, 0)
        sonuc = None
        for d in (1, 2):
            deneme_no = taban + d
            sonuc = None                             # candidate result is RESET on every attempt
            try:
                if meth == "CP":
                    sonuc = run_cp(key, size, aralik, int(i))
                elif meth == "HLBB":
                    sonuc = run_hlbb(key, size, aralik, int(i), int(seed))
                else:
                    sonuc = run_capsule(meth, key, size, aralik, int(i), int(seed))
                break                                # done computing; record below, SEPARATE phase
            except YontemBasarisizligi as e:
                _deneme_kaydi(key, deneme_no, "yontem", str(e))
                _basarisiz(key, f"yontem: {str(e)[:200]}")
                break
            except INFRA_HATALAR as e:
                _deneme_kaydi(key, deneme_no, "altyapi", f"{type(e).__name__}: {e}")
                if d == 2:
                    _basarisiz(key, f"altyapi-2-deneme: {type(e).__name__}")
                else:
                    print(f"    [altyapi] {type(e).__name__}, ayni kimlikle tekrar", flush=True)
                    time.sleep(5)
            except Exception as e:
                _deneme_kaydi(key, deneme_no, "yontem", f"{type(e).__name__}: {e}")
                _basarisiz(key, f"yontem: {type(e).__name__}: {str(e)[:200]}")
                break
        if sonuc is None:
            print(f"[{n}/{len(bekleyen)}] {size} {aralik} i{i} {meth} sd{seed} "
                  f"*** BASARISIZ (kayitli) ***", flush=True)
            continue
        # ---- DURABLE RECORD PHASE (the algorithm is NOT re-run; error = stop) ----
        _cozum_sakla(key, sonuc["claimed"], sonuc["assign"], sonuc["sirali"])
        satir = sonuc["satir"]; satir[-2] = deneme_no
        _yaz_dayanikli(CSV_PATH, list(key[:3]) + [meth, seed] + satir, COLS)
        _deneme_kaydi(key, deneme_no, "basari", "")
        kabul += 1
        if kabul % YEDEK_HER == 0:
            _yedekle()
        el = time.time() - t0
        eta = el / n * (len(bekleyen) - n)
        print(f"[{n}/{len(bekleyen)}] {size:>7} {aralik:>4} i{i} {meth:>4} sd{seed} "
              f"mk={satir[0]:7.1f}  [{el/3600:.1f}sa, ~{eta/3600:.1f}sa kaldi]", flush=True)
    _yedekle()
    gecti, _ = _dogrulama()
    if gecti:
        print("kosu bitti", flush=True)
    else:
        print("KOSU TURU BITTI — DOGRULAMA GECMEDI (yukarida liste)", flush=True)


# ------------------------------------------------------------------ smoke run
def duman():
    global CSV_PATH, WALL, CP_WALL, HUCRELER, INSTS, SEEDS, SOLDIR
    CSV_PATH = os.path.join(_HERE, "results", "kilitli_nis_DUMAN.csv")
    SOLDIR = os.path.join(_HERE, "results", "kilitli_nis_DUMAN_cozumler")
    WALL, CP_WALL = 25, 40
    HUCRELER, INSTS, SEEDS = [("50_10", "t99")], [1], [0]
    main()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "duman":
        duman()
    elif len(sys.argv) > 1 and sys.argv[1] == "dogrula":
        import feas_hook
        gecti, _ = _dogrulama()
        print("SONUC:", "GECTI" if gecti else "GECEMEDI")
    else:
        main()
