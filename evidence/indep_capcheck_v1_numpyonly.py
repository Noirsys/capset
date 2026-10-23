#!/usr/bin/env python3
"""Independent cap-set check — deliberately NOT the project's verifier.

Different algorithm: encode each point as a base-3 integer, build a boolean
membership table of size 3^n, then for every ordered pair (x,y) compute
z = -(x+y) mod 3 and test membership in O(1).

Reads one vector per line, digits 0/1/2 separated by spaces or commas.
"""
import sys
import numpy as np


def load(path):
    pts = []
    with open(path) as f:
        for line in f:
            line = line.strip().strip("[]()")
            if not line or line.startswith("#"):
                continue
            pts.append([int(t) for t in line.replace(",", " ").split()])
    return np.array(pts, dtype=np.int64)


def main(path):
    P = load(path)
    N, n = P.shape
    print(f"[indep] file={path}")
    print(f"[indep] {N} lines, dimension n={n}")

    # duplicate check
    codes = P @ (3 ** np.arange(n))
    uniq = np.unique(codes)
    if len(uniq) != N:
        print(f"[indep] FAIL: {N - len(uniq)} duplicate points")
        return 1
    if P.min() < 0 or P.max() > 2:
        print("[indep] FAIL: digit outside {0,1,2}")
        return 1

    present = np.zeros(3 ** n, dtype=bool)
    present[uniq] = True

    powers = 3 ** np.arange(n)
    violations = 0
    first = None
    for i in range(N):
        # z = -(x + y) mod 3 for every y at once
        Z = (-P[i][None, :] - P) % 3
        zc = Z @ powers
        hit = present[zc]
        # exclude the self-pair (y == x) and any degenerate z == x or z == y
        hit[i] = False
        hit &= (zc != codes[i]) & (zc != codes)
        if hit.any():
            j = int(np.argmax(hit))
            violations += 1
            if first is None:
                first = (i, j, P[i], P[j], Z[j])
    if violations:
        i, j, x, y, z = first
        print(f"[indep] NOT A CAP: {violations} ordered-pair violations")
        print(f"[indep]   {x.tolist()} + {y.tolist()} + {z.tolist()} = 0 mod 3")
        return 1
    print(f"[indep] VALID: {N} points in F_3^{n}, no three distinct on a line")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
