"""symmetry.py — symmetry groups on F_3^n as permutations of point indices, and their orbits.

A cap invariant under a group G is a union of G-orbits, so the search for the largest G-invariant cap is an
exact problem over orbit indicator variables (see orbit_solver.py). The groups here:

    singer(n)            — the Singer cycle: multiplication by a primitive element of F_{3^n} acting on nonzero
                           vectors (one cycle of length 3^n - 1); its subgroup of order k (k | 3^n - 1) acts
                           freely on nonzero vectors, so all orbits have size k (plus the fixed point 0).
    negation             — v -> -v (caps closed under negation are exactly preimages of projective caps)
    coordinate maps      — cyclic shift, reversal, arbitrary permutations of coordinates
    product groups       — a Singer subgroup on the first a coordinates and another on the last b

All of them are returned as index permutations (numpy int64 arrays of length 3^n), and `orbits()` takes any
list of generator permutations and returns the orbit id of every point.
"""
from __future__ import annotations

import itertools
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

import capset as C

_PRIMITIVE: Dict[int, List[int]] = {}


def _polymul_mod(a: List[int], b: List[int], f: List[int], n: int) -> List[int]:
    r = [0] * (2 * n - 1)
    for i, x in enumerate(a):
        if x:
            for j, y in enumerate(b):
                if y:
                    r[i + j] = (r[i + j] + x * y) % 3
    for d in range(2 * n - 2, n - 1, -1):
        c = r[d]
        if c:
            for k in range(n + 1):
                r[d - n + k] = (r[d - n + k] - c * f[k]) % 3
    return r[:n]


def primitive_polynomial(n: int) -> List[int]:
    """A monic degree-n polynomial over F_3 (coefficients low -> high, f[n] = 1) whose root generates F_{3^n}^*."""
    if n in _PRIMITIVE:
        return _PRIMITIVE[n]
    order = 3 ** n - 1
    # prime factors of the group order, to test primitivity by t^(order/p) != 1
    m, primes, p = order, [], 2
    while p * p <= m:
        if m % p == 0:
            primes.append(p)
            while m % p == 0:
                m //= p
        p += 1
    if m > 1:
        primes.append(m)
    one = [1] + [0] * (n - 1)
    t = [0, 1] + [0] * (n - 2)

    def power(e: int, f: List[int]) -> List[int]:
        res, base = one[:], t[:]
        while e:
            if e & 1:
                res = _polymul_mod(res, base, f, n)
            base = _polymul_mod(base, base, f, n)
            e >>= 1
        return res

    for coeffs in itertools.product(range(3), repeat=n):
        f = list(coeffs) + [1]
        if f[0] == 0:
            continue
        if power(order, f) != one:
            continue
        if all(power(order // q, f) != one for q in primes):
            _PRIMITIVE[n] = f
            return f
    raise RuntimeError("no primitive polynomial found")


def singer(space: C.Space) -> np.ndarray:
    """Permutation of indices for v -> t * v in F_{3^n} = F_3[t]/(f). Coordinates are taken low -> high as the
    space's digits reversed (any fixed identification works)."""
    n = space.n
    f = primitive_polynomial(n)
    V = space.V[:, ::-1].astype(np.int64)                 # digit i = coefficient of t^i
    top = V[:, n - 1:n]                                  # coefficient of t^(n-1)
    shifted = np.concatenate([np.zeros((space.size, 1), dtype=np.int64), V[:, :n - 1]], axis=1)   # multiply by t
    fcoef = np.array(f[:n], dtype=np.int64)[None, :]
    new = (shifted - top * fcoef) % 3
    return space.indices(new[:, ::-1])


def compose(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """(p o q)(i) = p[q[i]]"""
    return p[q]


def power(p: np.ndarray, e: int) -> np.ndarray:
    res = np.arange(p.size, dtype=np.int64)
    base = p
    while e:
        if e & 1:
            res = base[res]
        base = base[base]
        e >>= 1
    return res


def singer_subgroup_generator(space: C.Space, k: int) -> np.ndarray:
    """Generator of the unique subgroup of order k of the Singer cycle (k must divide 3^n - 1)."""
    order = space.size - 1
    if order % k:
        raise ValueError(f"{k} does not divide 3^{space.n} - 1 = {order}")
    return power(singer(space), order // k)


def negation(space: C.Space) -> np.ndarray:
    return space.indices((-space.V.astype(np.int64)) % 3)


def coordinate_permutation(space: C.Space, perm: Sequence[int]) -> np.ndarray:
    """v -> (v[perm[0]], v[perm[1]], ...)"""
    return space.indices(space.V[:, list(perm)])


def cyclic_shift(space: C.Space) -> np.ndarray:
    return coordinate_permutation(space, [(i + 1) % space.n for i in range(space.n)])


def reversal(space: C.Space) -> np.ndarray:
    return coordinate_permutation(space, list(range(space.n))[::-1])


def translation(space: C.Space, vec: Sequence[int]) -> np.ndarray:
    return space.indices((space.V.astype(np.int64) + np.asarray(vec, dtype=np.int64)[None, :]) % 3)


def product_singer(space: C.Space, a: int, k1: int, k2: int) -> List[np.ndarray]:
    """Generators of C_k1 x C_k2 where C_k1 is the Singer subgroup of order k1 on the first a coordinates and
    C_k2 the Singer subgroup of order k2 on the remaining n - a coordinates."""
    n = space.n
    b = n - a
    sa, sb = C.Space(a), C.Space(b)
    ga = singer_subgroup_generator(sa, k1) if k1 > 1 else np.arange(sa.size)
    gb = singer_subgroup_generator(sb, k2) if k2 > 1 else np.arange(sb.size)
    ia = space.V[:, :a].astype(np.int64) @ sa.powers
    ib = space.V[:, a:].astype(np.int64) @ sb.powers
    gens = []
    if k1 > 1:
        gens.append(space.indices(np.concatenate([sa.V[ga[ia]], space.V[:, a:]], axis=1)))
    if k2 > 1:
        gens.append(space.indices(np.concatenate([space.V[:, :a], sb.V[gb[ib]]], axis=1)))
    return gens


def orbits(size: int, generators: Sequence[np.ndarray]) -> Tuple[np.ndarray, List[np.ndarray]]:
    """Orbit id for every point under the group generated by `generators` (label propagation until stable).
    Returns (orbit_id array, list of orbits as index arrays)."""
    label = np.arange(size, dtype=np.int64)
    while True:
        changed = False
        for g in generators:
            # points i and g[i] are in the same orbit: both get the min label
            m = np.minimum(label, label[g])
            if not np.array_equal(m, label):
                label = m
                changed = True
            # also pull back along the inverse direction
            m2 = label.copy()
            np.minimum.at(m2, g, label)
            if not np.array_equal(m2, label):
                label = m2
                changed = True
        if not changed:
            break
    uniq, inv = np.unique(label, return_inverse=True)
    orbs = [np.flatnonzero(inv == j) for j in range(uniq.size)]
    return inv, orbs


def divisors(m: int) -> List[int]:
    out = []
    for d in range(1, int(m ** 0.5) + 1):
        if m % d == 0:
            out.append(d)
            if d != m // d:
                out.append(m // d)
    return sorted(out)


def invariant(pts: Sequence[int], generators: Sequence[np.ndarray]) -> bool:
    """Is the point set invariant under every generator?"""
    s = set(int(p) for p in pts)
    arr = np.array(sorted(s), dtype=np.int64)
    return all(set(g[arr].tolist()) == s for g in generators)


if __name__ == "__main__":
    for n in (4, 6, 8):
        sp = C.Space(n)
        g = singer(sp)
        # the Singer cycle must be a single cycle on the nonzero vectors
        seen, i, steps = set(), 1, 0
        while i not in seen:
            seen.add(i); i = int(g[i]); steps += 1
        assert steps == 3 ** n - 1 and 0 not in seen and g[0] == 0, (n, steps)
        print(f"n={n}: Singer cycle ok, primitive poly {primitive_polynomial(n)}")
    sp = C.Space(8)
    g41 = singer_subgroup_generator(sp, 41)
    ids, orbs = orbits(sp.size, [g41])
    print("n=8, order 41:", len(orbs), "orbits; sizes", sorted(set(len(o) for o in orbs)))
    c512 = sp.indices(C.build_512_cap_n8()).tolist()
    for name, gens in (("negation", [negation(sp)]), ("reversal", [reversal(sp)]), ("shift", [cyclic_shift(sp)])):
        print(" 512-cap invariant under", name, ":", invariant(c512, gens))
