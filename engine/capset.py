"""capset.py — the mathematics, fast and independently checkable.

A cap set in F_3^n is a set of points with no three on a line, i.e. no distinct x, y, z with x + y + z = 0 (mod 3).
Equivalently: for every pair {x, y} in the set, the "third point" -(x + y) mod 3 is not in the set.

Everything here works on integer indices 0 .. 3^n - 1 (base 3, most significant coordinate first, the same order
as itertools.product, so index == vector @ [3^(n-1), ..., 1]).

    Space(n)            — the ambient space: vectors, powers, third(x, y)
    verify(space, pts)  — independent O(k^2) check that `pts` is a cap (used before any record is claimed)
    CapState            — a cap with incremental "block counts": for every point q, how many pairs of the cap
                          have q as their third point. q is addable iff q is not in the cap and its count is 0.
                          add / remove are O(|cap|) numpy operations, which makes local search fast.
    greedy_from_priority(space, priority_fn) — the FunSearch skeleton: add points in priority order when legal
    local_search(...)   — kick-and-regrow / targeted-swap search that never leaves the space of valid caps
    known constructions — the published 512-cap in n=8 (DeepMind, 2023), the 1082-cap in n=9, product caps
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
import time
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

import numpy as np


class Space:
    """The ambient space F_3^n with precomputed vectors and the third-point map."""

    def __init__(self, n: int):
        self.n = n
        self.size = 3 ** n
        self.V = np.array(list(itertools.product((0, 1, 2), repeat=n)), dtype=np.int8)      # [3^n, n]
        self.powers = (3 ** np.arange(n - 1, -1, -1)).astype(np.int64)                    # [n]

    def index(self, vec: Sequence[int]) -> int:
        return int(np.dot(np.asarray(vec, dtype=np.int64) % 3, self.powers))

    def indices(self, vecs) -> np.ndarray:
        return (np.asarray(vecs, dtype=np.int64) % 3) @ self.powers

    def thirds(self, idx_array: np.ndarray, p: int) -> np.ndarray:
        """Third points of the pairs (x, p) for every x in idx_array: -(V[x] + V[p]) mod 3, as indices."""
        return ((-(self.V[idx_array].astype(np.int64) + self.V[p].astype(np.int64))) % 3) @ self.powers

    def vectors_of(self, idx_array) -> np.ndarray:
        return self.V[np.asarray(idx_array, dtype=np.int64)]


def verify(space: Space, pts: Iterable[int]) -> bool:
    """Independent cap check, O(k^2): for every pair, the third point must not be in the set. Also rejects duplicates."""
    pts = [int(p) for p in pts]
    if len(set(pts)) != len(pts):
        return False
    if any(p < 0 or p >= space.size for p in pts):
        return False
    arr = np.array(pts, dtype=np.int64)
    member = np.zeros(space.size, dtype=bool)
    member[arr] = True
    for i in range(len(arr)):
        t = space.thirds(arr[i + 1:], int(arr[i]))
        if member[t].any():
            return False
    return True


def verify_vectors(n: int, vectors) -> bool:
    """Same check from explicit vectors (the form a record is published in)."""
    sp = Space(n)
    return verify(sp, sp.indices(vectors).tolist())


def cap_digest(space: Space, pts: Iterable[int]) -> str:
    """Canonical SHA-256 of a cap (sorted indices), for naming and de-duplication."""
    s = ",".join(str(int(p)) for p in sorted(int(p) for p in pts))
    return hashlib.sha256(s.encode()).hexdigest()[:16]


# --------------------------------------------------------------------------------------------- incremental state

class CapState:
    """A valid cap plus, for every point of the space, the number of cap pairs whose third point it is."""

    def __init__(self, space: Space, pts: Iterable[int] = ()):
        self.sp = space
        self.count = np.zeros(space.size, dtype=np.int32)
        self.member = np.zeros(space.size, dtype=bool)
        self.pts: List[int] = []
        self._pos = {}
        for p in pts:
            if not self.can_add(int(p)):
                raise ValueError(f"point {p} cannot be added: the seed is not a cap")
            self.add(int(p))

    # --- queries
    def __len__(self):
        return len(self.pts)

    def can_add(self, p: int) -> bool:
        return (not self.member[p]) and self.count[p] == 0

    def free_points(self) -> np.ndarray:
        """All points that could be added right now."""
        f = np.flatnonzero(self.count == 0)
        return f[~self.member[f]]

    def blockers_of(self, q: int) -> List[Tuple[int, int]]:
        """The cap pairs {x, y} with third point q (what must be broken before q can be added)."""
        if not self.pts:
            return []
        arr = np.array(self.pts, dtype=np.int64)
        t = self.sp.thirds(arr, q)
        hit = self.member[t]
        pairs = []
        for x, y in zip(arr[hit].tolist(), t[hit].tolist()):
            if x < y:
                pairs.append((x, y))
        return pairs

    # --- mutations (both O(|cap|))
    def add(self, p: int):
        if self.pts:
            arr = np.array(self.pts, dtype=np.int64)
            t = self.sp.thirds(arr, p)
            np.add.at(self.count, t, 1)
        self.member[p] = True
        self._pos[p] = len(self.pts)
        self.pts.append(p)

    def remove(self, p: int):
        i = self._pos.pop(p)
        last = self.pts.pop()
        if i < len(self.pts):
            self.pts[i] = last
            self._pos[last] = i
        self.member[p] = False
        if self.pts:
            arr = np.array(self.pts, dtype=np.int64)
            t = self.sp.thirds(arr, p)
            np.add.at(self.count, t, -1)

    def snapshot(self):
        return (self.count.copy(), self.member.copy(), list(self.pts), dict(self._pos))

    def restore(self, snap):
        self.count, self.member, self.pts, self._pos = snap[0].copy(), snap[1].copy(), list(snap[2]), dict(snap[3])

    def check(self) -> bool:
        """Recompute the counts from scratch and compare (a self-test; not used in the hot loop)."""
        other = CapState(self.sp, list(self.pts))
        return bool(np.array_equal(other.count, self.count)) and bool(np.array_equal(other.member, self.member))


# --------------------------------------------------------------------------------------------- greedy (FunSearch)

def greedy_from_priority(space: Space, priority_fn: Callable, time_limit: float = 60.0) -> List[int]:
    """The FunSearch skeleton: compute a priority for every point, then add points from highest priority down,
    skipping any that would close a line. Ties break by index, exactly as in the published notebook."""
    t0 = time.time()
    pr = np.empty(space.size, dtype=np.float64)
    n = space.n
    for i in range(space.size):
        v = priority_fn(tuple(int(x) for x in space.V[i]), n)
        pr[i] = float(v)
        if (i & 1023) == 0 and time.time() - t0 > time_limit:
            raise TimeoutError("priority evaluation too slow")
    if not np.all(np.isfinite(pr)):
        raise ValueError("priority returned a non-finite value")
    order = np.lexsort((np.arange(space.size), -pr))   # highest priority first, index as tie-break
    st = CapState(space)
    for p in order.tolist():
        if st.can_add(p):
            st.add(p)
    return list(st.pts)


# --------------------------------------------------------------------------------------------- local search

def regrow(st: CapState, rng: random.Random, tabu: Optional[set] = None, strategy: str = "minconflict") -> int:
    """Add free points until none remain. Returns how many were added.
    minconflict: prefer the free point that blocks the fewest other free points (ties random)."""
    added = 0
    while True:
        free = st.free_points()
        if tabu:
            free = np.array([f for f in free.tolist() if f not in tabu], dtype=np.int64)
        if free.size == 0:
            return added
        if free.size == 1 or strategy == "random":
            p = int(free[rng.randrange(free.size)])
        else:
            # conflict of candidate c = number of other free points that adding c would block
            member_free = np.zeros(st.sp.size, dtype=bool)
            member_free[free] = True
            arr = np.array(st.pts, dtype=np.int64)
            best, bestc = [], None
            # cap the work: sample up to 64 candidates
            cand = free if free.size <= 64 else np.array(rng.sample(free.tolist(), 64), dtype=np.int64)
            for c in cand.tolist():
                t = st.sp.thirds(arr, c) if arr.size else np.empty(0, dtype=np.int64)
                conf = int(member_free[t].sum()) if t.size else 0
                if bestc is None or conf < bestc:
                    best, bestc = [c], conf
                elif conf == bestc:
                    best.append(c)
            p = best[rng.randrange(len(best))]
        st.add(p)
        added += 1


def kick_random(st: CapState, rng: random.Random, r: int) -> List[int]:
    """Remove r random points. Returns the removed points."""
    r = min(r, len(st.pts))
    removed = rng.sample(st.pts, r)
    for p in removed:
        st.remove(p)
    return removed


def kick_targeted(st: CapState, rng: random.Random, max_pairs: int = 3) -> List[int]:
    """Pick an outside point q with few blocking pairs (cheap to free), break every pair by removing one member,
    so that q (and possibly others) become addable. Returns the removed points."""
    cnt = st.count
    outside = ~st.member
    for k in (1, 2, 3, 4):
        if k > max_pairs:
            break
        cand = np.flatnonzero((cnt == k) & outside)
        if cand.size:
            q = int(cand[rng.randrange(cand.size)])
            pairs = st.blockers_of(q)
            removed = []
            for x, y in pairs:
                if st.member[x] and st.member[y]:
                    victim = x if rng.random() < 0.5 else y
                    st.remove(victim)
                    removed.append(victim)
            return removed
    return kick_random(st, rng, 1)


def local_search(space: Space, seed_pts: Sequence[int], seconds: float, rng: random.Random,
                 on_improve: Optional[Callable[[List[int]], None]] = None, temperature: float = 0.35,
                 report: Optional[Callable[[dict], None]] = None, report_every: float = 5.0,
                 target: Optional[int] = None) -> Tuple[List[int], dict]:
    """Kick-and-regrow local search that never leaves valid caps.

    Each step: snapshot; remove a few points (targeted at nearly-free outside points most of the time, random
    otherwise); regrow greedily (min-conflict); accept if not smaller, or with a small probability if smaller
    (simulated annealing on size); otherwise restore. Removed points are tabu for the regrow of that step.
    Returns the best cap found and statistics."""
    st = CapState(space, seed_pts)
    best = list(st.pts)
    best_len = len(best)
    stats = {"steps": 0, "accepted": 0, "improved": 0, "start": len(best), "best": best_len, "seconds": 0.0, "last_improve_step": 0}
    t0 = time.time()
    last_report = t0
    while True:
        now = time.time()
        if now - t0 >= seconds:
            break
        if report and now - last_report >= report_every:
            stats["seconds"] = now - t0
            stats["rate"] = stats["steps"] / max(1e-9, stats["seconds"])
            stats["current"] = len(st.pts)
            report(dict(stats))
            last_report = now
        stats["steps"] += 1
        before = len(st.pts)
        snap = st.snapshot()
        u = rng.random()
        if u < 0.55:
            removed = kick_targeted(st, rng, max_pairs=rng.choice((1, 1, 2, 2, 3)))
        elif u < 0.85:
            removed = kick_random(st, rng, rng.choice((1, 1, 2, 2, 3, 4)))
        else:
            removed = kick_random(st, rng, rng.choice((4, 5, 6, 8)))
        regrow(st, rng, tabu=set(removed), strategy="minconflict" if rng.random() < 0.8 else "random")
        after = len(st.pts)
        if after >= before or rng.random() < math.exp(-(before - after) / max(1e-6, temperature)):
            stats["accepted"] += 1
            if after > best_len:
                best, best_len = list(st.pts), after
                stats["improved"] += 1
                stats["best"] = best_len
                stats["last_improve_step"] = stats["steps"]
                if on_improve:
                    on_improve(list(best))
                if target is not None and best_len >= target:
                    break
        else:
            st.restore(snap)
    stats["seconds"] = time.time() - t0
    stats["rate"] = stats["steps"] / max(1e-9, stats["seconds"])
    stats["current"] = len(st.pts)
    return best, stats


# --------------------------------------------------------------------------------------------- known constructions

def build_512_cap_n8() -> List[Tuple[int, ...]]:
    """The explicit 512-point cap in n=8 (Romera-Paredes et al., Nature 2023, Supplementary Information;
    reproduced from google-deepmind/funsearch/cap_set/cap_set.ipynb)."""
    n = 8
    V = list(itertools.product(range(3), repeat=n))
    support = lambda v: tuple(i for i in range(n) if v[i] != 0)                      # noqa: E731
    reflections = lambda v: sum(1 for i in range(1, n // 2) if v[i] == v[-i])        # noqa: E731
    weight8 = [v for v in V if len(support(v)) == 8 and reflections(v) >= 2]
    supports_16 = [(0, 1, 2, 3), (0, 1, 2, 5), (0, 3, 6, 7), (0, 5, 6, 7), (1, 3, 4, 6), (1, 4, 5, 6), (2, 3, 4, 7), (2, 4, 5, 7)]
    weight4 = [v for v in V if support(v) in supports_16]
    supports_8 = [(0, 1, 2, 7), (0, 1, 2, 6), (0, 1, 3, 7), (0, 1, 6, 7), (0, 1, 5, 7), (0, 2, 3, 6), (0, 2, 6, 7), (0, 2, 5, 6),
                  (1, 2, 4, 7), (1, 2, 4, 6), (1, 3, 4, 7), (1, 4, 6, 7), (1, 4, 5, 7), (2, 3, 4, 6), (2, 4, 6, 7), (2, 4, 5, 6)]
    weight4b = [v for v in V if support(v) in supports_8 and reflections(v) == 1]
    allowed_zeros = [(0, 4, 7), (0, 2, 4), (0, 1, 4), (0, 4, 6), (1, 2, 6), (2, 6, 7), (1, 2, 7), (1, 6, 7)]
    weight5 = [v for v in V if tuple(i for i in range(n) if v[i] == 0) in allowed_zeros and reflections(v) <= 1
               and (v[1] * v[7]) % 3 != 1 and (v[2] * v[6]) % 3 != 1]
    return weight8 + weight4 + weight4b + weight5


def priority_n9_1082(el: Tuple[int, ...], n: int) -> float:
    """The FunSearch priority that builds the 1082-cap in n=9 (same notebook)."""
    el = np.array(el, dtype=np.float32)
    weight = (el @ el) % 3
    a = n // 3
    b = n - n // 3
    s_1 = (el[:b] @ el[:b]) % 3
    s_3 = (2 * (el[:a] @ el[:a])) % 3
    s_4 = (el[:a] @ el[a:b]) % 3
    s_5 = np.sum(el[:a] == el[-1]) % 3
    return float(-3 ** 3 * s_1 + 3 ** 2 * weight + 3 ** 3 * s_3 + 3 ** 2 * s_4 + s_5)


def priority_n8_512(el: Tuple[int, ...], n: int) -> float:
    """The FunSearch-discovered priority that greedily builds the 512-cap in n=8 (same notebook)."""
    score = n
    in_el = 0
    el_count = el.count(0)
    if el_count == 0:
        score += n ** 2
        if el[1] == el[-1]:
            score *= 1.5
        if el[2] == el[-2]:
            score *= 1.5
        if el[3] == el[-3]:
            score *= 1.5
    else:
        if el[1] == el[-1]:
            score *= 0.5
        if el[2] == el[-2]:
            score *= 0.5
    for e in el:
        if e == 0:
            if in_el == 0:
                score *= n * 0.5
            elif in_el == el_count - 1:
                score *= 0.5
            else:
                score *= n * 0.5 ** in_el
            in_el += 1
        else:
            score += 1
    if el[1] == el[-1]:
        score *= 1.5
    if el[2] == el[-2]:
        score *= 1.5
    return float(score)


BEST_KNOWN = {1: 2, 2: 4, 3: 9, 4: 20, 5: 45, 6: 112, 7: 236, 8: 512, 9: 1082}   # lower bounds (largest known caps)


def small_caps() -> dict:
    """Largest caps for n <= 4 by exhaustive-ish greedy with restarts (used only as product-construction factors)."""
    out = {}
    for n, target in ((1, 2), (2, 4), (3, 9), (4, 20)):
        sp = Space(n)
        rng = random.Random(n)
        best: List[int] = []
        for _ in range(400):
            order = list(range(sp.size))
            rng.shuffle(order)
            st = CapState(sp)
            for p in order:
                if st.can_add(p):
                    st.add(p)
            if len(st.pts) > len(best):
                best = list(st.pts)
            if len(best) >= target:
                break
        out[n] = sp.vectors_of(best).tolist()
    return out


def product_cap(cap_a: List[Sequence[int]], cap_b: List[Sequence[int]]) -> List[Tuple[int, ...]]:
    """If A is a cap in F_3^a and B a cap in F_3^b then A x B is a cap in F_3^(a+b)."""
    return [tuple(list(u) + list(v)) for u in cap_a for v in cap_b]


def seed_caps(n: int, space: Space) -> List[Tuple[str, List[int]]]:
    """Named starting caps for dimension n, as index lists, all verified before return."""
    seeds: List[Tuple[str, List[int]]] = []
    if n == 8:
        seeds.append(("published-512", space.indices(build_512_cap_n8()).tolist()))
        seeds.append(("greedy-512-priority", greedy_from_priority(space, priority_n8_512)))
    if n == 9:
        seeds.append(("greedy-1082-priority", greedy_from_priority(space, priority_n9_1082)))
    small = small_caps()
    if n == 8 and 4 in small:
        seeds.append(("product-20x20", space.indices(product_cap(small[4], small[4])).tolist()))
    if n == 9 and 4 in small and 1 in small:
        # 20 x 20 x 2 = 800 (weak but a different basin)
        seeds.append(("product-20x20x2", space.indices(product_cap(product_cap(small[4], small[4]), small[1])).tolist()))
    out = []
    for name, pts in seeds:
        if verify(space, pts):
            out.append((name, pts))
    return out


if __name__ == "__main__":
    # self-test
    sp = Space(8)
    c512 = sp.indices(build_512_cap_n8()).tolist()
    assert len(c512) == 512 and verify(sp, c512)
    g = greedy_from_priority(sp, priority_n8_512)
    assert len(g) == 512 and verify(sp, g)
    st = CapState(sp, c512)
    assert st.free_points().size == 0
    rng = random.Random(1)
    best, stats = local_search(sp, c512, seconds=5, rng=rng)
    assert verify(sp, best)
    print(json.dumps(stats), "best", len(best))
    assert st.check()
