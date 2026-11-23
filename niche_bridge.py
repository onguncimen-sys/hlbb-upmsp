# -*- coding: utf-8 -*-
"""Niche instance JSON -> compact binary bridge (for the Julia capsule, NO PACKAGE
DEPENDENCY).

Julia has no JSON.jl here; instead of parsing JSON we write a fixed-layout binary that
Julia reads directly with read!. Much faster/smaller than a text bridge (800x30 setup =
19.2M numbers).

LAYOUT (all little-endian):
  n:Int32, m:Int32
  ready : Int32[m]
  elig  : Int8[m,n]  (Julia reads E[machine, job])
  proc  : Int32[m,n] (Julia reads P[machine, job])
  setup : Int32[n,n] x m  (Julia reads S[l][i,j] = i->j setup)

RULE: we write the numpy array as the TRANSPOSE of the shape Julia must see
(numpy is C-order row-major, Julia is column-major -> the transpose aligns the two).
"""
import json
import struct
import os
import numpy as np


def json_to_bin(json_path, bin_path):
    """Converts a niche JSON instance to the binary Julia will read. Returns (n, m)."""
    with open(json_path) as f:
        d = json.load(f)
    n, m = int(d["nJob"]), int(d["nMachine"])

    ready = np.array([d["readyTime"][str(l)] for l in range(m)], dtype=np.int32)
    # What Julia must see: E[machine, job] -> build numpy (m,n) and write the transpose
    elig = np.array([d["Compatibility"][str(l)] for l in range(m)], dtype=np.int8)   # (m,n)
    proc = np.array([d["processTime"][str(l)] for l in range(m)], dtype=np.int32)    # (m,n)

    with open(bin_path, "wb") as f:
        f.write(struct.pack("<ii", n, m))
        f.write(ready.tobytes())
        f.write(np.ascontiguousarray(elig.T).tobytes())
        f.write(np.ascontiguousarray(proc.T).tobytes())
        for l in range(m):
            A = np.array(d["setupTime"][str(l)], dtype=np.int32)                     # A[i][j] = i->j
            f.write(np.ascontiguousarray(A.T).tobytes())
    return n, m


def ensure_bin(json_path, cache_dir=None):
    """Produces the binary for a JSON (skipped if present and up to date); returns its path."""
    if cache_dir is None:
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".niche_bin")
    os.makedirs(cache_dir, exist_ok=True)
    rel = os.path.relpath(json_path).replace(os.sep, "_").replace(".json", "")
    bin_path = os.path.join(cache_dir, rel + ".nbin")
    if (not os.path.exists(bin_path)
            or os.path.getmtime(bin_path) < os.path.getmtime(json_path)):
        json_to_bin(json_path, bin_path)
    return bin_path


if __name__ == "__main__":
    import sys
    jp = sys.argv[1]
    bp = sys.argv[2] if len(sys.argv) > 2 else ensure_bin(jp)
    if len(sys.argv) > 2:
        json_to_bin(jp, bp)
    print(f"{jp} -> {bp}  ({os.path.getsize(bp)/1e6:.1f} MB)")
