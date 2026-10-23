#!/usr/bin/env python3
"""verify_record.py — independent, dependency-free check that a file of vectors is a cap set in F_3^n.

    python3 verify_record.py records/cap_n8_513_xxxx.txt

Format: one vector per line, digits 0/1/2 separated by spaces or commas (brackets ignored), e.g. "[1, 0, 2, ...]".
Prints the dimension, the number of distinct points, and whether any three distinct points x, y, z satisfy
x + y + z = 0 (mod 3) — if none do, the set is a cap. Pure Python, O(k^2 n); a 2,500-point cap takes a few seconds.
"""
import sys


def main(path):
    pts = []
    with open(path) as f:
        for line in f:
            line = line.strip().strip("[]()")
            if not line or line.startswith("#"):
                continue
            digits = [int(t) for t in line.replace(",", " ").split()]
            if any(d not in (0, 1, 2) for d in digits):
                print(f"bad line: {line!r}")
                return 2
            pts.append(tuple(digits))
    if not pts:
        print("no points")
        return 2
    n = len(pts[0])
    if any(len(p) != n for p in pts):
        print("inconsistent dimensions")
        return 2
    S = set(pts)
    print(f"dimension n = {n}; {len(pts)} lines, {len(S)} distinct points")
    plist = sorted(S)
    for i in range(len(plist)):
        x = plist[i]
        for j in range(i + 1, len(plist)):
            y = plist[j]
            z = tuple((-x[k] - y[k]) % 3 for k in range(n))
            if z in S and z != x and z != y:
                print(f"NOT A CAP: {x} + {y} + {z} = 0 (mod 3)")
                return 1
    print(f"VALID CAP SET: {len(S)} points in F_3^{n}, no three on a line.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
