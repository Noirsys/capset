# Cap set engine (v2)

A cap set is a set of points in F_3^n with no three on a line (x + y + z ≠ 0 mod 3 for distinct x, y, z).
Finding a bigger one than anyone has in a given dimension is a new mathematical result. This engine looks
for one, around the clock, and only ever claims what an independent checker has re-verified.

## The records to beat (largest known caps)

| n | size | where it comes from |
|---|------|---------------------|
| 7 | 236 | Edel 2004 |
| 8 | **512** | Romera-Paredes et al., *Nature* 2023 (FunSearch) — up from Edel's 496 |
| 9 | 1082 | Edel's 541-cap in PG(8,3), doubled (every projective cap gives an affine cap of twice the size) |
| 10 | 2432 | Edel's 1216-cap in PG(9,3), doubled |
| 11 | 5488 | Edel's 2744-cap in PG(10,3), doubled |

The seed caps in `edel/` were downloaded from Edel's tables, doubled, and verified here. Before announcing
any record, the literature should be re-checked for a larger cap in that dimension (the table above is from
Edel's pages, the FunSearch paper and the 2018 Huang–Tait–Won table; a later improvement may exist).

## Why the original v1 loop could not get there

The v1 loop (`../discovery_superloop.py`) evolves a priority function and builds a cap greedily, as in the
FunSearch paper. That recipe works at FunSearch's scale (millions of samples, islands, strong models). Run
with one child per generation it plateaued at 380 — below the plain 20×20 product construction (400). More
important: the record caps are **rigid**. Removing a 160-point slice of the 512-cap leaves exactly 160
candidate points; the exact solver puts the same slice back. Small moves do not escape these optima.

## What v2 does instead

1. **Exact search with symmetry.** Choose a symmetry group G of F_3^n — subgroups of the Singer cycle
   (multiplication by elements of the field F_{3^n}), products of those across a coordinate split, coordinate
   permutations, negation. A G-invariant cap is a union of G-orbits, so "the largest G-invariant cap" is an
   exact optimisation over a few hundred to a few thousand orbit variables, which CP-SAT (Google OR-Tools)
   solves, often to **proven optimality**. Example: the largest cap in F_3^8 invariant under the Singer
   subgroup of order 41 has exactly 410 points (proved in 105 s); the unique 112-cap in F_3^6 is found in
   seconds as a union of 8 orbits of a cyclic group of order 14, where unrestricted search finds only 87.
   Every task ends in a fact: a record, or a theorem of the form "no cap with symmetry G exceeds X".
2. **Large-neighbourhood search** from the best known caps: remove a structured chunk (a coordinate slice,
   an affine hyperplane section, a random subset), let CP-SAT refill it *optimally*. The cap never shrinks;
   any growth is a record. This is the lottery ticket on the published 512 and 2432 caps.

The task queue (`python3 engine.py --tasks`) has ~700 symmetry groups across n = 7…11, cheap first.
Unresolved tasks whose bound still allows a record get a second and third pass with more time.

## Honesty rules

- A record is written to `records/` only after `verify_record.py` — pure Python, no numpy, no shared code —
  re-reads the file and confirms no three points sum to zero. Anyone can run it.
- Every cap file is plain text, one vector per line, with a SHA-256 in its `.json`.
- Negative results are kept (`state/results/`), with the solver's proven bound.

## Running

    bash run.sh start     # first run installs numpy + ortools into .venv; stops the v1 loop; starts the service
    bash run.sh status
    bash run.sh stop

Dashboard: http://<this machine>:8170/ — progress per dimension, best caps, proven negatives, and a banner
the moment a record is verified. Config in `config.json` (dimensions, worker counts, time limits).
