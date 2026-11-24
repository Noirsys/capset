# Independent check of Holden's caps (arXiv:2611.19543)

**Date:** 2026-11-23. **Run by:** Harriet, on Michael A. Vega's machine `xai3`.

Matthew Holden's paper gives caps of 1104 points in F_3^9 and 5744 points in F_3^11.
We ran both of his point lists through both of our checkers. Those are the same two checkers
that verified our own caps. They share no code. Neither checker was changed for this run.

## Input

From https://github.com/holdenmatt/capset-constructions (`data/`), cloned 2026-11-23:

| file | rows | SHA-256 |
|---|---|---|
| `cap1104.csv` | 1104 | `5a5077411a9123d4e013c3f808bc159649e2acaeac153d271eba54c7617bd791` |
| `cap5744.csv` | 5744 | `95e04b9689ca83252fe4d14ddc69fc64785e933279cf77b80c8d1de2507cd736` |

Our checkers read one point per line with space-separated coordinates. The only change was
dropping the CSV header and replacing commas with spaces. No point was altered or reordered.

## Output

```
$ python3 verify_record.py h1104.txt
dimension n = 9; 1104 lines, 1104 distinct points
VALID CAP SET: 1104 points in F_3^9, no three on a line.

$ python3 indep_capcheck.py h1104.txt
[indep] backend: numpy
[indep] VALID CAP SET: 1104 points in F_3^9, no three distinct on a line (no constraint violated)

$ python3 verify_record.py h5744.txt
dimension n = 11; 5744 lines, 5744 distinct points
VALID CAP SET: 5744 points in F_3^11, no three on a line.

$ python3 indep_capcheck.py h5744.txt
[indep] backend: numpy
[indep] VALID CAP SET: 5744 points in F_3^11, no three distinct on a line (no constraint violated)
```

Four runs, four valid. Both of his bounds are confirmed independently, and both are larger than ours.
