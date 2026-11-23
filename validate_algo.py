# -*- coding: utf-8 -*-
"""VALIDITY verifier for the niche extension of the capsule metaheuristics (SA / HGA / GA).

Two legs of the Rolim strawman guard:
  1) EQUIVALENCE: extended(pure mode) == original, bit-identical (best + trajectory
     checksum). -> the elig+ready additions did NOT break the pure core; the rival
     was not crippled.
  2) FEASIBILITY: in niche mode (restricted elig + nonzero ready) there is NO
     incompatible assignment, and MachineSpan = r_l + workload (ready exactly once).

Usage: python3 validate_algo.py <ALGO>     (ALGO: SA | HGA | GA)
"""
import subprocess
import os
import sys

# RELEASE ADAPTATION: overridable via environment variable; default = the recorded run path.
JULIA = os.environ.get("HLBB_JULIA", "/home/sarp/julia_install/julia-1.7.0/bin/julia")
_HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(_HERE, "rolim_capsule/code")
ENV = {**os.environ,
       "JULIA_DEPOT_PATH": os.environ.get("JULIA_DEPOT_PATH", "/home/sarp/julia_install/depot")}
SEEDS = [0, 1, 2, 3, 7, 42]

# (m, n, iters) -- (4,30) STAYS as the REGRESSION case, plus two benchmark scales.
# iters is low for population-based methods: each generation checks 2 individuals x O(n*m),
# and GA's Psize=80 initial population is costly on its own at n=800.
FEAS_SIZES = {
    "SA":  [(4, 30, 20000), (15, 200, 5000), (30, 800, 2000)],
    "HGA": [(4, 30, 500),   (15, 200, 200),  (30, 800, 50)],
    "GA":  [(4, 30, 300),   (15, 200, 100),  (30, 800, 30)],
}


def jl(harness, *args, timeout=900):
    out = subprocess.run([JULIA, harness, *args], capture_output=True, text=True,
                         env=ENV, timeout=timeout)
    return out


def grab(out, tag):
    for ln in out.stdout.splitlines():
        if ln.startswith(tag):
            return ln
    raise RuntimeError(f"'{tag}' cikmadi:\nSTDOUT:{out.stdout[-500:]}\nSTDERR:{out.stderr[-900:]}")


def equivalence(algo, ext, orig):
    harness = f"{CODE}/equiv_{algo.lower()}_test.jl"
    print(f"--- 1) EQUIVALENCE ({algo}): extended(pure) vs original, RNG birebir olmali ---", flush=True)
    ok = True
    for sd in SEEDS:
        be, ce = grab(jl(harness, ext, str(sd)), "EQUIV_RESULT").split()[1:]
        bo, co = grab(jl(harness, orig, str(sd)), "EQUIV_RESULT").split()[1:]
        same = (be == bo and ce == co)
        ok = ok and same
        print(f"  seed={sd:3d}: EXT(best={be}, chk={ce})  ORIG(best={bo}, chk={co})  "
              f"-> {'OZDES ✓' if same else 'FARKLI ✗ (RNG sapti)'}", flush=True)
    return ok


def feasibility(algo, ext):
    """Runs at three scales: (4,30) REGRESSION (kept comparable with earlier results) +
    the benchmark scales. The iteration count is reduced at large scale -- each iteration
    runs an O(n*m) check; the goal is to trigger the operators on a LARGE INSTANCE, not
    to run many iterations."""
    harness = f"{CODE}/feas_{algo.lower()}_test.jl"
    print(f"\n--- 2) FEASIBILITY ({algo}): nis-mod (kisitli elig + nonzero ready) ---", flush=True)
    ok = True
    for m, n, iters in FEAS_SIZES[algo]:
        line = grab(jl(harness, ext, str(m), str(n), str(iters), timeout=3600), "FEAS_RESULT")
        parts = dict(kv.split("=") for kv in line.split()[1:])
        ev, sm, ck = int(parts["elig_viol"]), int(parts["span_mismatch"]), int(parts["checks"])
        cv = int(parts["cov_viol"])
        good = (ev == 0 and sm == 0 and cv == 0)
        ok = ok and good
        tag = "REGRESYON" if (m, n) == (4, 30) else "benchmark olcegi"
        print(f"  {m:>2}x{n:<4} ({tag:<16}) {ck:>6} denetim: "
              f"elig_viol={ev}  span_mismatch={sm}  cov_viol={cv}  "
              f"-> {'TEMIZ ✓' if good else 'IHLAL ✗'}", flush=True)
    return ok


def main():
    algo = (sys.argv[1] if len(sys.argv) > 1 else "SA").upper()
    ext = f"{CODE}/Algorithms/{algo}/{algo}.jl"
    orig = f"{CODE}/Algorithms/{algo}/{algo}.jl.orig"
    for f in (ext, orig):
        if not os.path.exists(f):
            raise SystemExit(f"bulunamadi: {f}")
    print(f"### {algo} NIS-GENISLETMESI VALIDITY ###\n", flush=True)
    e = equivalence(algo, ext, orig)
    f_ = feasibility(algo, ext)
    print("\n" + "=" * 70, flush=True)
    print(f"  equivalence : {'GECTI ✓' if e else 'KALDI ✗'}", flush=True)
    print(f"  feasibility : {'GECTI ✓' if f_ else 'KALDI ✗'}", flush=True)
    print(f"=== {algo} {'VALID (nis benchmark icin hazir)' if (e and f_) else 'GECERSIZ -> duzeltilecek'} ===",
          flush=True)


if __name__ == "__main__":
    main()
