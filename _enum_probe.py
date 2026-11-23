"""PROBE (NOT a run): FULL enumeration of short columns + set partitioning.
All job sequences on a machine whose completion time does not exceed T are enumerated
depth-first (prefix pruning is valid: completion time only grows along a sequence). For
each job set the shortest sequence is kept. Then set partitioning is solved over all
columns. LKH is NOT called."""
import sys, time, csv
sys.path.insert(0, "/home/sarp/HLBB")
from readproblem import readproblem
import gurobipy as gp
from gurobipy import GRB

def enum_machine(l, nJob, rt, pt, st, T, budget):
    best = {}            # bitmask -> (span, seq)
    dom = {}             # (bitmask, last) -> smallest completion time
    nodes = 0
    P = [float(pt[l][i]) for i in range(nJob)]
    S = st[l]
    stack = []
    for i in range(nJob):
        c = rt[l] + P[i]
        if c <= T: stack.append((1 << i, i, c, (i,)))
    while stack:
        mask, last, c, seq = stack.pop()
        k = (mask, last)
        if dom.get(k, 1e18) <= c: continue
        dom[k] = c; nodes += 1
        if nodes > budget: return best, nodes, False
        if mask not in best or c < best[mask][0]: best[mask] = (c, seq)
        row = S[last]
        for j in range(nJob):
            if mask >> j & 1: continue
            c2 = c + float(row[j]) + P[j]
            if c2 <= T: stack.append((mask | (1 << j), j, c2, seq + (j,)))
    return best, nodes, True

def main():
    inst, T, budget = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
    mip_tl = float(sys.argv[4]) if len(sys.argv) > 4 else 120
    d = readproblem(f"/home/sarp/HLBB/valladapure/{inst}.json", consider_compatibility=False, consider_workload=False)
    nJob, nM, c1, c2, rt, pt, st, mx, I_l, L_i, es = d
    t0 = time.time(); cols = []; complete = True; tot_nodes = 0
    for l in range(nM):
        b, nodes, ok = enum_machine(l, nJob, rt, pt, st, T, budget)
        complete &= ok; tot_nodes += nodes
        cols += [(l, mask, sp, seq) for mask, (sp, seq) in b.items()]
    t_enum = time.time() - t0
    m = gp.Model(); m.Params.OutputFlag = 0; m.Params.TimeLimit = mip_tl
    x = m.addVars(len(cols), vtype=GRB.BINARY); z = m.addVar()
    for i in range(nJob):
        m.addConstr(gp.quicksum(x[c] for c, (l, mask, sp, sq) in enumerate(cols) if mask >> i & 1) == 1)
    for l in range(nM):
        idx = [c for c, col in enumerate(cols) if col[0] == l]
        m.addConstr(gp.quicksum(x[c] for c in idx) <= 1)
        m.addConstr(z >= gp.quicksum(cols[c][2] * x[c] for c in idx))
    m.setObjective(z, GRB.MINIMIZE); t1 = time.time(); m.optimize(); t_mip = time.time() - t1
    if m.SolCount == 0:
        print(f"{inst}: T={T:.0f} sutun={len(cols)} tam={complete} -> COZUM YOK (durum {m.Status})"); return
    sel = [cols[c] for c in range(len(cols)) if x[c].X > 0.5]
    # independent verification: coverage + the sequence's duration
    cov = [0] * nJob; mk = 0.0
    for l, mask, sp, seq in sel:
        t = rt[l] + pt[l][seq[0]]
        for a, b in zip(seq, seq[1:]): t += st[l][a][b] + pt[l][b]
        assert abs(t - sp) < 1e-6
        mk = max(mk, t)
        for i in seq: cov[i] += 1
    assert all(v == 1 for v in cov)
    # SHARED checker (feasibility.py) -- project rule: every reported solution passes through it
    from feasibility import check_assignment
    ordered = [[] for _ in range(nM)]
    for l, mask, sp, seq in sel: ordered[l] = list(seq)
    res = check_assignment(ordered, d, claimed_obj=mk)
    ok_chk = (not res.get("violations")) if isinstance(res, dict) else res
    rank_out = sum(1 for l, mask, sp, seq in sel for i in seq
                   if sorted(range(nM), key=lambda q: pt[q][i]).index(l) >= 3)
    sizes = sorted(len(seq) for *_, seq in sel)
    print(f"{inst}: T={T:.0f} | sutun {len(cols):>8} dugum {tot_nodes:>9} sayim {'TAM' if complete else 'KESILDI'} {t_enum:5.1f}s | "
          f"MIP {t_mip:5.1f}s durum {'eniyi' if m.Status==2 else m.Status} alt sinir {m.ObjBound:.1f} | "
          f"MAKESPAN {mk:.0f} | en hizli 3 makinesi DISINDAKI is {rank_out}/{nJob} | bos makine {nM-len(sel)} | "
          f"makine basina is {sizes[0]}..{sizes[-1]} | ortak denetleyici: {res if not isinstance(res, dict) else {k: res[k] for k in res if k in ('violations','ok','seq_makespan','n_viol')}}")
if __name__ == "__main__":
    main()
