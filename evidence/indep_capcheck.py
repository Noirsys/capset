#!/usr/bin/env python3
"""Independent cap-set check — deliberately NOT the project's verifier.

Algorithmic independence matters: if this file and verify_record.py shared a
bug, two "passes" would prove nothing. So this one uses a different data
representation throughout.

  verify_record.py : set of tuples, O(k^2) pair scan
  this file        : points packed to base-3 integers, membership keyed by
                     that integer

Numpy is used when available (fast path). It is NOT required — the pure-stdlib
fallback is the same algorithm and returns the same verdict, so anyone can
re-run this with a bare python3.

Usage:
    python3 indep_capcheck.py <capfile.txt>

File format: one vector per line, digits 0/1/2, separated by spaces or commas.
Brackets and parentheses are ignored; blank lines and '#' comments skipped.

Note: the self-pair (y == x) is excluded, and a z equal to x or to y is also
excluded. For x != y those two exclusions are redundant (z = x would force
y = x), but they are kept so the predicate matches the usual definition
literally: no three DISTINCT points sum to zero.
"""
import sys

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


def load(path):
    pts = []
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip().strip("[]()")
            if not s or s.startswith("#"):
                continue
            try:
                row = [int(t) for t in s.replace(",", " ").split()]
            except ValueError:
                raise SystemExit(f"bad line {lineno}: {line!r}")
            pts.append(row)
    if not pts:
        raise SystemExit("no points read")
    n = len(pts[0])
    if any(len(r) != n for r in pts):
        raise SystemExit("inconsistent vector lengths")
    for r in pts:
        for v in r:
            if v not in (0, 1, 2):
                raise SystemExit(f"coordinate outside {{0,1,2}} in {r}")
    return pts, n


def pack(row, powers):
    """Pack a point as a base-3 integer."""
    return sum(v * p for v, p in zip(row, powers))


def check_numpy(P, n):
    codes = P @ (3 ** np.arange(n))
    uniq = np.unique(codes)
    if len(uniq) != len(P):
        return False, f"{len(P) - len(uniq)} duplicate points", 0

    present = np.zeros(3 ** n, dtype=bool)
    present[uniq] = True

    powers = 3 ** np.arange(n)
    bad = 0
    first = None
    for i in range(len(P)):
        Z = (-P[i][None, :] - P) % 3          # z = -(x+y) mod 3 for every y at once
        zc = Z @ powers
        hit = present[zc]
        hit[i] = False                        # exclude y == x
        hit &= (zc != codes[i]) & (zc != codes)
        if hit.any():
            bad += 1
            if first is None:
                j = int(np.argmax(hit))
                first = (P[i].tolist(), P[j].tolist(), Z[j].tolist())
    if bad:
        return False, f"{bad} ordered-pair violations; first {first}", len(P)
    return True, "no constraint violated", len(P)


def check_pure(P, n):
    powers = [3 ** k for k in range(n)]
    codes = [pack(r, powers) for r in P]
    if len(set(codes)) != len(P):
        return False, f"{len(P) - len(set(codes))} duplicate points", 0

    present = set(codes)
    bad = 0
    first = None
    for i, x in enumerate(P):
        cx = codes[i]
        for j, y in enumerate(P):
            if j == i:
                continue
            z = [(-x[k] - y[k]) % 3 for k in range(n)]
            cz = pack(z, powers)
            if cz != cx and cz != codes[j] and cz in present:
                bad += 1
                if first is None:
                    first = (list(x), list(y), z)
    if bad:
        return False, f"{bad} ordered-pair violations; first {first}", len(P)
    return True, "no constraint violated", len(P)


def main(path):
    pts, n = load(path)
    print(f"[indep] {path}")
    print(f"[indep] dimension n = {n}; {len(pts)} lines")

    if HAVE_NUMPY:
        ok, msg, k = check_numpy(np.array(pts, dtype=np.int64), n)
        backend = "numpy"
    else:
        ok, msg, k = check_pure(pts, n)
        backend = "pure python (stdlib only)"

    print(f"[indep] backend: {backend}")
    if ok:
        print(f"[indep] VALID CAP SET: {k} points in F_3^{n}, no three distinct on a line ({msg})")
        return 0
    print(f"[indep] NOT A CAP: {msg}")
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
