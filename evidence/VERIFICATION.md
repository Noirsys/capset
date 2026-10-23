# Verification record

**Date:** 2026-10-22, ~15:47 EDT
**Verified by:** Harriet (audit), on Michael A. Vega's machine `xai3`
**Purpose:** allow anyone — including a sceptical referee — to confirm the two claims in
`../NOTE-new-cap-lower-bounds-dim9-11.md` without trusting us, the search code, or each other.

---

## 1. The claims under test

| claim | meaning | what would falsify it |
|---|---|---|
| **c(9,3) ≥ 1084** | a valid cap of 1084 points exists in F₃⁹ | any three distinct points in the file summing to 0 mod 3 |
| **c(11,3) ≥ 5529** | a valid cap of 5529 points exists in F₃¹¹ | same |

Nothing about optimality is claimed, so nothing about upper bounds is being verified here.

---

## 2. Files

| file | what it is | SHA-256 |
|---|---|---|
| `cap_n9_1084_12d746361afb9eec.txt` | 1084 points, one vector per line | `8668467e43c6832d942ce11a3c6ba06427bf034be1395789ac73e087ce097f5f` |
| `cap_n9_1084_12d746361afb9eec.json` | harness metadata for the above | `755eb2a2d08cf5c1444bfabc8d2197f3e21feaa89bf496ba43bc689d5ea5d8ff` |
| `cap_n11_5529_165b577837b4d3de.txt` | 5529 points, one vector per line | `c015d369db57b9bb1aeacb2f60b4df54677d8cff7a0142d934231ab68ef3dbf9` |
| `cap_n11_5529_165b577837b4d3de.json` | harness metadata for the above | `36ade13943407bc4beab5cae69c73e36e8d12f324c0295cfce8e86c5d2913477` |
| `verify_record.py` | Check A — project verifier, stdlib only | `6e0dd702a23fd9dc7b0b481efc97b5046a2fc741dcd18978699842b31acbc50d` |
| `indep_capcheck.py` | Check B — independent checker, numpy fast path + stdlib fallback | `402ffce6a24d2deb8ad3bdc214cce594e26863e717998540da52841a0672c515` |
| `indep_capcheck_v1_numpyonly.py` | earlier Check B, numpy-only. Superseded; kept for provenance | `c13015e1341dfe53815f75317f8db54d0cc3ead40b24c6af3e2839f20058023e` |
| `checkA_n11.log` | raw output of the slowest run | `1c79957e13d0552c9d0fb0aecab4083aa05a4bbd522ac8f9e4647fc26d75b796` |

The SHA-256 values recorded inside the harness's own `.json` metadata match the `.txt` files exactly. The
copies here are byte-identical to the originals in
`~/capset_project/v2/state/remote/xai4/records/`, confirmed by pairwise hashing at copy time. **The originals
were not moved, modified, or deleted.**

Check the whole directory against the manifest. `SHA256SUMS.txt` sits at the **top level** of
`~/research-papers/capset/` and its paths are relative to that directory, so run it from there:

```
cd ~/research-papers/capset
sha256sum -c SHA256SUMS.txt
```

It covers all eleven files — both documents, both cap files, both metadata records, both checkers, the log,
this file, and itself excluded.

---

## 3. Two checks, no shared code

Two passes only mean something if a single bug cannot produce both. These were written separately and differ
in representation, data structure and failure mode:

| | Check A (`verify_record.py`) | Check B (`indep_capcheck.py`) |
|---|---|---|
| point representation | Python tuple of ints | base-3 integer |
| membership test | `z in S` over a set of tuples | lookup in a boolean array / int set keyed by packed code |
| construction of z | tuple comprehension per pair | vectorised numpy, or packed-int arithmetic |
| author | the search harness | written for this audit |
| dependencies | none (stdlib) | numpy if present, otherwise pure stdlib |
| complexity | O(k²·n) plain loops | O(k²) with O(1) membership |

Both also check the things that quietly undo a cap result: line count, duplicate points, and that every
coordinate is in {0, 1, 2}.

The predicate both implement: no three **distinct** points **x, y, z** with **x + y + z ≡ 0 (mod 3)**.
For each ordered pair (x, y), y ≠ x, it forms z = −(x+y) mod 3 and asks whether z is in the set and differs
from both x and y. Note z = x would force y = x, so for distinct pairs those last two conditions are redundant —
they are kept so the predicate reads exactly as the definition.

---

## 4. Results

All runs below used **`/usr/bin/python3` directly** — no virtualenv, no project environment. numpy 2.5.2
present on this machine.

**Check A — 1084 points, F₃⁹**

```
$ python3 verify_record.py cap_n9_1084_12d746361afb9eec.txt
dimension n = 9; 1084 lines, 1084 distinct points
VALID CAP SET: 1084 points in F_3^9, no three on a line.
```

**Check A — 5529 points, F₃¹¹**  (pure-Python O(k²); took roughly 8 minutes)

```
$ python3 verify_record.py cap_n11_5529_165b577837b4d3de.txt
dimension n = 11; 5529 lines, 5529 distinct points
VALID CAP SET: 5529 points in F_3^11, no three on a line.
exit=0
```

**Check B — 1084 points, F₃⁹**

```
$ python3 indep_capcheck.py cap_n9_1084_12d746361afb9eec.txt
[indep] dimension n = 9; 1084 lines
[indep] backend: numpy
[indep] VALID CAP SET: 1084 points in F_3^9, no three distinct on a line (no constraint violated)
```

**Check B — 5529 points, F₃¹¹**  (2.2 s)

```
$ python3 indep_capcheck.py cap_n11_5529_165b577837b4d3de.txt
[indep] dimension n = 11; 5529 lines
[indep] backend: numpy
[indep] VALID CAP SET: 5529 points in F_3^11, no three distinct on a line (no constraint violated)
```

**Both caps pass both checks.** Four independent passes, two per claim.

If numpy is unavailable, Check B falls back to a pure-stdlib implementation of the same algorithm and gives
the same verdict — slower, but it means a referee with a bare `python3` can still run it. On the 5529-point
file expect that fallback to take tens of minutes.

---

## 5. Who found what, and how much that matters

The caps are outputs of `~/capset_project/v2`: large-neighbourhood search that removes a structured chunk of a
known cap and refills it **optimally** with CP-SAT, so the cap can only grow. Every intermediate step is in the
harness's own record store. Verification above is of the **product**, not the search — if the search were
buggy, these files would still be either valid caps or not, and they are valid.

What verification does *not* establish, and no amount of checking these files will:

- that 1084 or 5529 is optimal, or close to it;
- that these caps are complete (maximal) — not checked, not attempted;
- that no larger cap has been published. That is a literature question, answered in
  `../RECORDS-FRONTIER-2026-10-22.md` §4 and §5, and for n = 9 it rests on the absence of any contrary claim
  in the literature, not on a proof.

---

## 6. A note on the n = 11 trajectory

The n = 11 search was seeded from Edel's 5488, which is **16 below** the actual record of 5504. The walk
5488 → 5529 therefore crossed 5504 partway. The result is a record, but it was not aimed at one. Any future
run in this dimension should be seeded from 5504 so that the first acceptance above 5504 is the record, not
the last one.
