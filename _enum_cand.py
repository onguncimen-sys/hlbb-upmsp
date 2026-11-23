"""PROBE: the best value reachable by different CANDIDATE LIST rules on the same exact
column pool.
  J3    : each job only on its 3 fastest machines (the production rule)
  M     : each machine takes only its own fastest ceil(3n/m) jobs (pair count same as J3: 3n)
  J3M2  : J3 UNION each machine's fastest ceil(2n/m) jobs (Fanjul-Peyro & Ruiz 2011 '3J2M')
  J2M1  : each job's 2 fastest machines UNION each machine's fastest ceil(n/m) jobs
          (pair count <= 3n)
T = the method's own result. Solutions are passed through the shared checker."""
import sys, time, csv, math
sys.path.insert(0, "/home/sarp/HLBB")
from readproblem import readproblem
from _enum_probe import enum_machine
from feasibility import check_assignment
import gurobipy as gp
from gurobipy import GRB
from collections import defaultdict

def solve(cols, nJob, nM, tl, d):
    by = defaultdict(list)
    for c, (l, mask, sp, sq) in enumerate(cols):
        for i in sq: by[i].append(c)
    if any(not by[i] for i in range(nJob)): return "kapsanamayan is var", None
    m = gp.Model(); m.Params.OutputFlag = 0; m.Params.TimeLimit = tl
    x = m.addVars(len(cols), vtype=GRB.BINARY); z = m.addVar()
    for i in range(nJob): m.addConstr(gp.quicksum(x[c] for c in by[i]) == 1)
    for l in range(nM):
        idx = [c for c, col in enumerate(cols) if col[0] == l]
        m.addConstr(gp.quicksum(x[c] for c in idx) <= 1)
        m.addConstr(z >= gp.quicksum(cols[c][2] * x[c] for c in idx))
    m.setObjective(z, GRB.MINIMIZE); m.optimize()
    if m.SolCount == 0: return f"cozum yok (durum {m.Status})", None
    ordered = [[] for _ in range(nM)]
    for c in range(len(cols)):
        if x[c].X > 0.5: ordered[cols[c][0]] = list(cols[c][3])
    res = check_assignment(ordered, d, claimed_obj=round(m.ObjVal))
    tag = "eniyi" if m.Status == GRB.OPTIMAL else ("sure doldu, alt sinir %.2f" % m.ObjBound if m.Status == GRB.TIME_LIMIT else f"durum {m.Status}")
    rec = dict(value=round(m.ObjVal), optimal=int(m.Status == GRB.OPTIMAL), bound=round(float(m.ObjBound), 3),
               checker_ok=int(not res['violations']))
    return f"{round(m.ObjVal)} ({tag}{'' if not res['violations'] else ' DENETIM IHLALI'})", rec

def main():
    size = sys.argv[1]; tl = float(sys.argv[2]); folder = size.replace("x", "_")
    rows = []
    hl = defaultdict(list)
    for r in csv.DictReader(open("/home/sarp/HLBB/results/track_a.csv")):
        if r["method"] == "HLBB": hl[(r["size"], int(r["rep"]))].append(int(r["makespan"]))
    for rep in range(1, 11):
        d = readproblem(f"/home/sarp/HLBB/valladapure/{folder}/S1-99/instance_{rep}.json", consider_compatibility=False, consider_workload=False)
        nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
        T = min(hl[(size, rep)])
        def jtop(k): return {(i, l) for i in range(nJob) for l in sorted(range(nM), key=lambda q: pt[q][i])[:k]}
        def mtop(c): return {(i, l) for l in range(nM) for i in sorted(range(nJob), key=lambda j: pt[l][j])[:math.ceil(c * nJob / nM)]}
        rules = {"J3": jtop(3), "M": mtop(3), "J3M2": jtop(3) | mtop(2), "J2M1": jtop(2) | mtop(1)}
        cols = []; ok = True
        for l in range(nM):
            b, nodes, comp = enum_machine(l, nJob, rt, pt, st, T, 5000000); ok &= comp
            cols += [(l, mask, sp, seq) for mask, (sp, seq) in b.items()]
        base = dict(size=size, rep=rep, T=T, enum_complete=int(ok),
                    hlbb_mean=round(sum(hl[(size, rep)]) / len(hl[(size, rep)]), 3))
        txt, rec = solve(cols, nJob, nM, tl, d)
        out = [f"{size} ornek {rep:2d} | T={T} sayim {'TAM' if ok else 'KESILDI'} | sinirsiz: {txt}"]
        rows.append({**base, "rule": "free", "pairs": nJob * nM, "columns": len(cols), **(rec or {})})
        for name, allowed in rules.items():
            sub = [c for c in cols if all((i, c[0]) in allowed for i in c[3])]
            txt, rec = solve(sub, nJob, nM, tl, d)
            out.append(f"{name} [{len(allowed)} cift]: {txt}")
            rows.append({**base, "rule": name, "pairs": len(allowed), "columns": len(sub), **(rec or {})})
        print(" | ".join(out), flush=True)
    if len(sys.argv) > 3:
        F = ["size", "rep", "T", "enum_complete", "hlbb_mean", "rule", "pairs", "columns", "value", "optimal", "bound", "checker_ok"]
        with open(sys.argv[3], "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=F); w.writeheader()
            for r in rows: w.writerow({k: r.get(k, "") for k in F})
        print("yazildi:", sys.argv[3])
if __name__ == "__main__":
    main()
