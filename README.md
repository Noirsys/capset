# Noirsys Pipeline — Third Form: the cap-set harness

**Paper:** [paper/main.pdf](paper/main.pdf) · **Plain-English write-up:** [PUBLIC-WRITEUP.md](PUBLIC-WRITEUP.md) · **Repository:** [github.com/Noirsys/capset](https://github.com/Noirsys/capset)

The verification doctrine that came out of a reflexive agent laboratory, and the
cap-set search that was built to it. Includes both witnesses, both independent
checkers, and the paper.

**Headline results**

| | value | prior | verified by |
|---|---|---|---|
| $c(9,3)$ | **1084** | 1082 | two independent checkers |
| $c(11,3)$ | **5529** | 5504 | two independent checkers |

Both are **lower** bounds — a construction of size *N* proves $c(n,3) \ge N$. The
upper bounds (2070 at $n=9$, 16857 at $n=11$) are untouched and are a different
kind of artifact entirely.

**What's here**

```
paper/main.pdf            the paper (6 pp., IEEEtran)
paper/main.tex            LaTeX source
paper/figures/            vector figures, drawn from the same metrics file
paper/metrics.json        every number in the paper, machine-readable
paper/tables/numbers.tex  LaTeX macros the prose reads (no hand-typed numbers)

PUBLIC-WRITEUP.md         the plain-English version

evidence/                 both cap witnesses + both checkers + verification log
  indep_capcheck.py       pure stdlib, deliberately different algorithm
  verify_record.py        the project's own checker
  VERIFICATION.md         how to reproduce the verification

engine/                   the search harness
  capset.py               point representation, verify(), seed loading
  lns.py                  large-neighbourhood search + CP-SAT max independent set
  orbit_solver.py         symmetry-restricted exact search
  symmetry.py             symmetry group construction
  engine.py               orchestrator: tasks, workers, dashboard, records
  edel/                   published seed caps, including the two found here

make_figures.py           regenerates every figure and every macro
```

## Verify a witness yourself

Nothing needs installing. The independent checker is pure standard library.

```bash
cd evidence
python3 indep_capcheck.py cap_n9_1084_12d746361afb9eec.txt
python3 indep_capcheck.py cap_n11_5529_165b577837b4d3de.txt
```

Expected: `VALID` for both. Roughly 0.2 s and 2.2 s.

Then the project's own checker, which shares no code with it:

```bash
python3 verify_record.py cap_n11_5529_165b577837b4d3de.txt
```

Two implementations of the same property, independently written, agreeing. One
of them (the independent one) stores its algorithm on purpose as a base-3 integer
packing followed by a boolean membership table, because the project's checker
already uses a tuple set and an O(k²) pair scan. Two passes from one program prove
nothing.

## Rebuild the paper

```bash
/usr/bin/python3 make_figures.py     # rewrites figures/ and tables/numbers.tex
```

Figures require `matplotlib` and `numpy`. The system interpreter on the build box
has both; a venv does not.

LaTeX needs `pdflatex` and `bibtex` (three passes, `IEEEtranN` style). On a box
without TeX installed, the docker route used to build `paper/main.pdf` was:

```bash
docker create --name build -w /workdir texlive/texlive:latest \
  sh -c "pdflatex -interaction=nonstopmode main.tex && bibtex main && \
         pdflatex -interaction=nonstopmode main.tex && \
         pdflatex -interaction=nonstopmode main.tex"
docker cp main.tex build:/workdir/ && docker cp references.bib build:/workdir/
docker cp figures build:/workdir/ && docker cp tables build:/workdir/
docker start -ai build
docker cp build:/workdir/main.pdf .
```

## Run the search

```bash
cd engine
bash run.sh start          # installs deps into .venv, starts the engine
bash run.sh status
```

The dashboard serves on `:8170` and reads the state files. Two shells are worth
knowing about before you change anything:

- **The record bar is a constant in `engine.py`.** Every beats-record test, log
  line, artifact write and dashboard banner keys off it. If it is stale, the
  harness will announce a "record" for each size above it. This happened: see
  §VIII of the paper. Set it to the best known value, not the published one, and
  keep the published number in the attribution field so the citation survives.
- **The server class does not set `allow_reuse_address`.** A restart that lands
  inside the old socket's `TIME_WAIT` kills the dashboard thread permanently
  while the search keeps running. Known, unfixed here on purpose — this repo ships
  the code as it ran during the paper's results.

## Honest limits

- The $n=9$ clearance is **absence of evidence**: no paper in this niche states a
  $d=9$ result, and the most active group publishes corollaries for four
  dimensions and skips that one. The $n=11$ prior bound is a positive citation
  (Karapetyan & Karapetyan, CSIT 2023, Corollary 2). Different strengths; do not
  present them as equal.
- Margins of +2 and +25 on four-figure records are within reach of a competitor's
  afternoon of local search. They are rounding next to the unresolved gap.
- Both results came from descending off existing published constructions. No new
  construction family.
- There is **no language model anywhere in the search path**. That is deliberate,
  not an omission, and it is the whole point of the paper.

## Prior work

- Y. Edel, *Extensions of generalized product caps*, Des. Codes Cryptogr. 31(1):5–14, 2004.
- I. & K. Karapetyan, *Complete Caps in AG(n,3)*, CSIT 2023, doi:10.51408/csit2023_30.
- B. Romera-Paredes et al., *Mathematical discoveries from program search with LLMs*, Nature 625:468–475, 2024.

## Licence

Code and data: MIT. Paper: CC BY 4.0. See `LICENSE`.
