"""lns.py — large-neighbourhood search with exact regrow (CP-SAT).

Step: remove a structured chunk of the cap (a coordinate slice, a random affine subspace's intersection, or a
random subset), compute the free points F under the remaining cap R, then solve EXACTLY (within a time limit)
the largest subset of F that is itself a cap and is compatible with R — a maximum independent set in the
3-uniform "lines" hypergraph restricted to F. Since the removed chunk is one feasible answer, the result is never
smaller than before; any strictly larger answer is a new cap.
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

import capset as C

try:
    from ortools.sat.python import cp_model
    HAVE_CPSAT = True
except Exception:  # noqa: BLE001
    HAVE_CPSAT = False


def conflicts_within(space: C.Space, free: np.ndarray, fixed_member: np.ndarray) -> Tuple[List[Tuple[int, int, int]], List[Tuple[int, int]]]:
    """Constraints among `free` points given the fixed cap R:
    - lines {x, y, z} with all three in `free` (at most two may be chosen), each listed once;
    - pairs {x, y} in `free` whose third point lies in R (they cannot both be chosen)."""
    member = np.zeros(space.size, dtype=bool)
    member[free] = True
    lines, pairs = [], []
    fl = free.tolist()
    for i, x in enumerate(fl):
        rest = free[i + 1:]
        if rest.size == 0:
            break
        t = space.thirds(rest, x)
        hit = member[t]
        for y, z in zip(rest[hit].tolist(), t[hit].tolist()):
            if y < z:            # each line once: from its smallest point, with y < z
                lines.append((x, y, z))
        hitR = fixed_member[t]
        for y in rest[hitR].tolist():
            pairs.append((x, y))
    return lines, pairs


def max_cap_in(space: C.Space, free: np.ndarray, fixed_member: np.ndarray, time_limit: float, workers: int = 1,
               hint: Optional[Sequence[int]] = None, lower_bound: int = 0) -> Tuple[List[int], str]:
    """Largest cap inside `free` (all of which are compatible with the fixed part), by CP-SAT. Returns (points, status)."""
    if not HAVE_CPSAT:
        raise RuntimeError("ortools is not installed")
    fl = free.tolist()
    idx = {p: i for i, p in enumerate(fl)}
    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{i}") for i in range(len(fl))]
    lines, pairs = conflicts_within(space, free, fixed_member)
    for a, b, c in lines:
        m.AddBoolOr([x[idx[a]].Not(), x[idx[b]].Not(), x[idx[c]].Not()])
    for a, b in pairs:
        m.AddBoolOr([x[idx[a]].Not(), x[idx[b]].Not()])
    m.Maximize(sum(x))
    if lower_bound > 0:
        m.Add(sum(x) >= lower_bound)
    if hint:
        hs = set(int(h) for h in hint)
        for p, i in idx.items():
            m.AddHint(x[i], 1 if p in hs else 0)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = float(time_limit)
    s.parameters.num_workers = int(workers)
    s.parameters.random_seed = random.randrange(1 << 30)
    st = s.Solve(m)
    name = s.StatusName(st)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return [fl[i] for i in range(len(fl)) if s.Value(x[i])], name
    return list(hint or []), name


def remove_slice(st: C.CapState, rng: random.Random, kind: str) -> List[int]:
    """Remove a structured chunk. kinds: 'coord' (all cap points with v[i]==c), 'coords2' (v[i]==c and v[j]==d),
    'affine' (points on a random affine hyperplane a.v == b), 'random' (a random 20-35%)."""
    sp = st.sp
    pts = np.array(st.pts, dtype=np.int64)
    V = sp.V[pts].astype(np.int64)
    if kind == "coord":
        i, c = rng.randrange(sp.n), rng.randrange(3)
        mask = V[:, i] == c
    elif kind == "coords2":
        i, j = rng.sample(range(sp.n), 2)
        c, d = rng.randrange(3), rng.randrange(3)
        mask = (V[:, i] == c) & (V[:, j] == d)
    elif kind == "affine":
        a = np.array([rng.randrange(3) for _ in range(sp.n)], dtype=np.int64)
        if not a.any():
            a[0] = 1
        b = rng.randrange(3)
        mask = (V @ a) % 3 == b
    elif kind == "affine2":
        a1 = np.array([rng.randrange(3) for _ in range(sp.n)], dtype=np.int64)
        a2 = np.array([rng.randrange(3) for _ in range(sp.n)], dtype=np.int64)
        if not a1.any():
            a1[0] = 1
        if not a2.any():
            a2[1] = 1
        mask = ((V @ a1) % 3 == rng.randrange(3)) & ((V @ a2) % 3 == rng.randrange(3))
    else:
        k = max(1, int(len(pts) * rng.uniform(0.2, 0.35)))
        mask = np.zeros(len(pts), dtype=bool)
        mask[rng.sample(range(len(pts)), k)] = True
    removed = pts[mask].tolist()
    for p in removed:
        st.remove(p)
    return removed


def lns_step(st: C.CapState, rng: random.Random, kind: str, time_limit: float, workers: int = 1) -> Dict:
    """One LNS move on `st` in place. Never shrinks the cap. Returns a record of what happened."""
    before = len(st.pts)
    removed = remove_slice(st, rng, kind)
    free = st.free_points()
    t0 = time.time()
    if free.size == 0:
        for p in removed:
            st.add(p)
        return {"kind": kind, "removed": len(removed), "free": 0, "before": before, "after": before, "status": "EMPTY", "secs": 0.0}
    chosen, status = max_cap_in(st.sp, free, st.member, time_limit, workers, hint=removed, lower_bound=len(removed))
    if len(chosen) < len(removed):
        chosen = removed                      # solver found nothing better within the limit; restore
        status = status + "/restored"
    for p in chosen:
        if not st.can_add(p):
            raise RuntimeError("CP-SAT answer is not compatible with the fixed part")   # cannot happen if the constraints are complete
        st.add(p)
    return {"kind": kind, "removed": len(removed), "free": int(free.size), "before": before, "after": len(st.pts),
            "status": status, "secs": round(time.time() - t0, 2)}


if __name__ == "__main__":
    sp = C.Space(8)
    seeds = dict(C.seed_caps(8, sp))
    for name in ("product-20x20", "published-512"):
        st = C.CapState(sp, seeds[name])
        rng = random.Random(7)
        print(f"== {name}: {len(st.pts)}")
        for kind in ("coord", "affine", "coords2", "affine2", "random"):
            rec = lns_step(st, rng, kind, time_limit=20, workers=2)
            print(rec, "valid:", C.verify(sp, st.pts))
