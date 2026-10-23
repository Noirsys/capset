"""orbit_solver.py — the largest G-invariant cap, exactly, by CP-SAT over orbit indicator variables.

For a group G (given by its orbit ids), a G-invariant cap is a union of orbits. A line {x, y, z} forbids the
orbit triple {o(x), o(y), o(z)} from being wholly chosen. By symmetry it suffices to take x over one
representative per orbit and y over all points. Triples with repeated orbits become 2-clauses or forced zeros.

    build_model(space, orbit_ids, orbits)  -> (clauses summary, model data)
    solve(...)                             -> dict with status, size, bound, chosen points, timings
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Sequence

import numpy as np

import capset as C

from ortools.sat.python import cp_model


def orbit_clauses(space: C.Space, orbit_ids: np.ndarray, orbits: List[np.ndarray], chunk: int = 64) -> Dict:
    """Deduplicated orbit-level constraints: forced-zero orbits, 2-clauses, 3-clauses."""
    m = len(orbits)
    M = np.int64(m)
    allpts = np.arange(space.size, dtype=np.int64)
    keys = []
    reps = np.array([int(o[0]) for o in orbits], dtype=np.int64)
    for start in range(0, m, chunk):
        rep_chunk = reps[start:start + chunk]
        for x in rep_chunk.tolist():
            y = allpts[allpts != x]
            z = space.thirds(y, x)
            keep = (z != x) & (z != y)
            y, z = y[keep], z[keep]
            a = np.full(y.size, orbit_ids[x], dtype=np.int64)
            b = orbit_ids[y].astype(np.int64)
            c = orbit_ids[z].astype(np.int64)
            tri = np.sort(np.stack([a, b, c], axis=1), axis=1)
            keys.append(np.unique(tri[:, 0] * M * M + tri[:, 1] * M + tri[:, 2]))
        keys = [np.unique(np.concatenate(keys))]
    k = keys[0] if keys else np.empty(0, dtype=np.int64)
    a = k // (M * M)
    b = (k // M) % M
    c = k % M
    zero = np.unique(a[(a == b) & (b == c)])
    two_mask = ((a == b) | (b == c)) & ~((a == b) & (b == c))
    two = np.unique(np.stack([np.where(a == b, a, b)[two_mask], np.where(a == b, c, a)[two_mask]], axis=1), axis=0)
    three = np.stack([a, b, c], axis=1)[(a != b) & (b != c)]
    return {"n_orbits": m, "zero": zero, "two": two, "three": three}


def solve(space: C.Space, orbit_ids: np.ndarray, orbits: List[np.ndarray], time_limit: float, workers: int = 2,
          hint_pts: Optional[Sequence[int]] = None, at_least: Optional[int] = None, log=None) -> Dict:
    t0 = time.time()
    cl = orbit_clauses(space, orbit_ids, orbits)
    t_build = time.time() - t0
    m = cl["n_orbits"]
    sizes = np.array([len(o) for o in orbits], dtype=np.int64)
    model = cp_model.CpModel()
    y = [model.NewBoolVar(f"o{i}") for i in range(m)]
    for i in cl["zero"].tolist():
        model.Add(y[i] == 0)
    for i, j in cl["two"].tolist():
        model.AddBoolOr([y[i].Not(), y[j].Not()])
    for i, j, k in cl["three"].tolist():
        model.AddBoolOr([y[i].Not(), y[j].Not(), y[k].Not()])
    obj = sum(int(sizes[i]) * y[i] for i in range(m))
    if at_least is not None:
        model.Add(obj >= int(at_least))
    model.Maximize(obj)
    if hint_pts:
        chosen = set(int(orbit_ids[p]) for p in hint_pts)
        for i in range(m):
            model.AddHint(y[i], 1 if i in chosen else 0)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = float(time_limit)
    s.parameters.num_workers = int(workers)
    s.parameters.random_seed = int(time.time() * 1000) % (1 << 30)
    best_seen = {"size": 0, "t": None}

    class CB(cp_model.CpSolverSolutionCallback):
        def __init__(self):
            super().__init__()

        def on_solution_callback(self):
            v = int(self.ObjectiveValue())
            if v > best_seen["size"]:
                best_seen["size"] = v
                best_seen["t"] = round(time.time() - t0, 1)
                if log:
                    log(f"  solution {v} at {best_seen['t']}s")

    st = s.Solve(model, CB())
    name = s.StatusName(st)
    out = {"status": name, "n_orbits": m, "clauses": {"zero": int(cl["zero"].size), "two": int(len(cl["two"])), "three": int(len(cl["three"]))},
           "build_seconds": round(t_build, 1), "solve_seconds": round(time.time() - t0 - t_build, 1), "size": 0, "bound": None, "points": []}
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        pts = [int(p) for i in range(m) if s.Value(y[i]) for p in orbits[i].tolist()]
        out["size"] = len(pts)
        out["points"] = pts
        out["bound"] = int(s.BestObjectiveBound())
        out["valid"] = C.verify(space, pts)
    elif st == cp_model.INFEASIBLE:
        out["bound"] = (int(at_least) - 1) if at_least is not None else 0
    return out


if __name__ == "__main__":
    import sys
    import symmetry as S
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 41
    tl = float(sys.argv[3]) if len(sys.argv) > 3 else 120
    sp = C.Space(n)
    g = S.singer_subgroup_generator(sp, k)
    ids, orbs = S.orbits(sp.size, [g])
    print(f"n={n} Singer order {k}: {len(orbs)} orbits")
    r = solve(sp, ids, orbs, time_limit=tl, workers=2, log=print)
    r.pop("points")
    print(r)
