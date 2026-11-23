# -*- coding: utf-8 -*-
"""
Converts the pure setup-makespan instances of Vallada & Ruiz (2011)
(dataset_vallada/{large,small}/I_*.txt) into HLBB's JSON schema (readproblem.py).

PURPOSE: external validity. Run HLBB on the pure benchmark used in the literature
(R_M | S_ijk | C_max, NO eligibility/release/cardinality) and compare it against
published BKS (FSS Jovanovic 2021 / WO Arnaout 2020 address the same problem class).

PURE-PROBLEM MAPPING:
  - Compatibility = all 1          (every job eligible on every machine)
  - readyTime     = all 0          (all machines ready at t=0)
  - minimumJobs=0, maximumJobs=nJob (cardinality not binding)
With readproblem(..., consider_compatibility=False, consider_workload=False) this runs
the pure problem exactly.

RAW VALLADA .txt FORMAT:
  line 1 : nJob  nMachine  <flag>
  line 2 : nMachine
  nJob lines: for each job  "0 p_{i,0}  1 p_{i,1} ..."   -> processTime[job][machine]
  "SSD"
  for each machine k:  "M{k}" + nJob x nJob setup matrix (setup[k][i][j], diagonal 0)

USAGE:
  python3 vallada_to_hlbb.py dataset_vallada/small/I_10_2_S_1-124_1.txt out.json      # single file
  python3 vallada_to_hlbb.py --batch dataset_vallada/large valladapure  10 100 20     # batch
      (source dir, target root, at most N replicates, [nJob filter], [nMachine filter])
"""
import sys, os, json, re


def parse_vallada(path):
    """Raw Vallada .txt -> (nJob, nMachine, processTime[job][machine], setup[machine][job][job])."""
    with open(path) as f:
        # drop \r and blank lines, split into tokens
        lines = [ln.replace("\r", "").strip() for ln in f]
    lines = [ln for ln in lines if ln != ""]

    hdr = lines[0].split()
    nJob, nMachine = int(hdr[0]), int(hdr[1])
    # line 2 = nMachine (validation)
    assert int(lines[1].split()[0]) == nMachine, f"satir2 != nMachine ({path})"

    # processTime block: the next nJob lines, each made of (idx, val) pairs
    pt = [[0.0] * nMachine for _ in range(nJob)]
    idx = 2
    for i in range(nJob):
        toks = lines[idx].split()
        # toks = [m0, v0, m1, v1, ...]
        for p in range(0, len(toks), 2):
            m = int(toks[p]); v = float(toks[p + 1])
            pt[i][m] = v
        idx += 1

    # "SSD" marker
    assert lines[idx].upper().startswith("SSD"), f"SSD bekleniyordu, bulundu: {lines[idx]!r}"
    idx += 1

    # setup: for each machine, "M{k}" + an nJob x nJob matrix
    setup = [[[0.0] * nJob for _ in range(nJob)] for _ in range(nMachine)]
    for k in range(nMachine):
        assert re.match(r"^M\d+$", lines[idx]), f"M{k} bekleniyordu, bulundu: {lines[idx]!r}"
        idx += 1
        for i in range(nJob):
            row = [float(x) for x in lines[idx].split()]
            assert len(row) == nJob, f"setup satir uzunlugu {len(row)} != {nJob} ({path})"
            setup[k][i] = row
            idx += 1

    return nJob, nMachine, pt, setup


def to_hlbb_json(nJob, nMachine, pt, setup):
    """Pure-problem HLBB JSON dict."""
    return {
        "nJob": nJob,
        "nMachine": nMachine,
        # processTime[machine][job]  (raw pt is job-major -> transpose)
        "processTime": {str(k): [pt[i][k] for i in range(nJob)] for k in range(nMachine)},
        "setupTime": {str(k): setup[k] for k in range(nMachine)},
        "Compatibility": {str(k): [1] * nJob for k in range(nMachine)},  # pure: all eligible
        "readyTime": {str(k): 0 for k in range(nMachine)},               # pure: t=0
        "minimumJobs": {str(k): 0 for k in range(nMachine)},             # pure: slack
        "maximumJobs": {str(k): nJob for k in range(nMachine)},
    }


def convert_file(src, dst):
    nJob, nMachine, pt, setup = parse_vallada(src)
    with open(dst, "w") as f:
        json.dump(to_hlbb_json(nJob, nMachine, pt, setup), f)
    return nJob, nMachine


def convert_batch(src_dir, out_root, max_rep=10, njob_filter=None, nmach_filter=None, sev_filter=None):
    """I_{nJob}_{nMachine}_S_{sev}_{rep}.txt -> out_root/{nJob}_{nMachine}/S{sev}/instance_{rep}.json

    The setup severity (sev, e.g. '1-124') is WRITTEN into the output path so the
    4 severities do not collide. If sev_filter is given (e.g. '1-124'), only that
    severity is converted.
    """
    pat = re.compile(r"^I_(\d+)_(\d+)_S_([\d\-]+)_(\d+)\.txt$")
    made = {}
    for fn in sorted(os.listdir(src_dir)):
        m = pat.match(fn)
        if not m:
            continue
        nj, nm, sev, rep = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4))
        if njob_filter and nj != njob_filter:
            continue
        if nmach_filter and nm != nmach_filter:
            continue
        if sev_filter and sev != sev_filter:
            continue
        if rep > max_rep:
            continue
        outdir = os.path.join(out_root, f"{nj}_{nm}", f"S{sev}")
        os.makedirs(outdir, exist_ok=True)
        convert_file(os.path.join(src_dir, fn), os.path.join(outdir, f"instance_{rep}.json"))
        made[f"{nj}_{nm}/S{sev}"] = made.get(f"{nj}_{nm}/S{sev}", 0) + 1
    for k in sorted(made):
        print(f"  {k}: {made[k]} instance")
    print(f"Donusturuldu: {sum(made.values())} instance (toplam) -> {out_root}/")
    return made


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--batch":
        src_dir = sys.argv[2]
        out_root = sys.argv[3]
        max_rep = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        njf = int(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] != "-" else None
        nmf = int(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] != "-" else None
        sevf = sys.argv[7] if len(sys.argv) > 7 and sys.argv[7] != "-" else None
        convert_batch(src_dir, out_root, max_rep, njf, nmf, sevf)
    else:
        src, dst = sys.argv[1], sys.argv[2]
        nJob, nMachine = convert_file(src, dst)
        print(f"{src} -> {dst}  ({nJob} is x {nMachine} makine)")
