# Handoff to Codex — website + distribution

Repo is staged, committed, and self-verifying at `/home/tt/noirsys-pipeline-capset`.
Branch `master`, commit `dd0844e`, 41 tracked files, 1.7 MB.

Your job: get this onto the web and in front of people. Everything factual you may
need is below; **do not invent numbers** — every figure in the paper and the write-up
comes from `paper/metrics.json`, which is the single source of truth.

## What exists

| path | what it is | state |
|---|---|---|
| `paper/main.pdf` | 6-page IEEEtran paper | built, 0 errors, 0 undefined refs, 10 refs |
| `paper/main.tex` | source | complete |
| `PUBLIC-WRITEUP.md` | ~1,100-word plain-English piece | complete, needs publish |
| `README.md` | repo front page | complete |
| `evidence/` | both witnesses, both checkers, verification log | **verified working, run it** |
| `engine/` | the search harness as it ran | complete |
| `SHA256SUMS.txt` | 40-file manifest | `sha256sum -c SHA256SUMS.txt` passes |

## Hard constraints — read before you publish anything

1. **These are LOWER bounds.** 1084 and 5529 are lower bounds on c(9,3) and c(11,3).
   Do not write "upper bound." Do not write "solved." Do not write "proved optimal."
   The upper bounds are 2070 and 16857 and they are untouched.

2. **The two margins are not equal, and the write-up must say so.** At n=11 the prior
   record (5504) is a positive citation — Karapetyan & Karapetyan, CSIT 2023,
   Corollary 2. At n=9 the prior record (1082) rests on **absence of evidence**: no
   paper in this niche states a d=9 result. Never present the n=9 clearance as
   equivalent to the n=11 one.

3. **Do not claim the lab produced the cap sets.** It did not. The bounds are
   properties of F₃⁹ and F₃¹¹ and are independent of everything else in this repo.
   The lab contributed the checking regime. This distinction is the paper's central
   honesty claim — getting it wrong destroys the paper's argument.

4. **Zero graduations is a stated result, not an embarrassment.** 361 cycles, 53
   hypotheses, 23 negatives, 0 graduations. If you edit the write-up, that number
   stays.

5. **No claim of recursive self-improvement.** What transferred is a practice, not
   a mechanism.

6. Author is **Michael A. Vega, Noirsys Research Group, contact@noirsys.com** — sole
   author, that affiliation string, that email. Do not add or reorder authors.

## Suggested website structure

- `/research/pipeline-third-form` — the paper (PDF + HTML abstract)
- `/research/pipeline-third-form/verify` — "check it yourself" page. Embed the two
  `python3 indep_capcheck.py <file>` commands with expected output. This is the most
  persuasive page on the site; nothing needs installing.
- `/writing/we-caught-ourselves` — `PUBLIC-WRITEUP.md`
- Repo link in both.

## Distribution

- **Show HN** — title: "Building a verification doctrine, then using it to catch our own false record." Focus of the post: the 12/12 → 0/12 result and the 5492 false record. *Not* the cap set record; the cap set is the payoff, the harness bug is the hook.
- Reddit: `r/math` (lead with the bounds + the two-checker discipline + the honest margin caveat), `r/MachineLearning` (lead with the verifier-environment finding), `r/compsci`. Read each sub's self-promotion rules first — r/math will remove anything that smells like a product post.
- The 4-line spec in `PUBLIC-WRITEUP.md` is the shareable artifact. It fits in a tweet.

## Do not do

- Do not push to a public remote or deploy without Michael saying so explicitly.
- Do not regenerate the paper's figures without rerunning `/usr/bin/python3 make_figures.py` — the figures and the macros must come from the same run or numbers drift from plots.
- Do not "fix" `engine.py`'s missing `allow_reuse_address` in this repo. The code ships as it ran during the paper's results; the README documents the defect on purpose.

## Two known quirks if you rebuild

- matplotlib lives in `/usr/bin/python3`, not in any venv on this box.
- LaTeX is docker-only: `texlive/texlive:latest`, three passes with `bibtex` between. The exact command is in `README.md` under "Rebuild the paper."

## Open items for Michael, not you

- Public remote URL / org name
- Whether the write-up gets posted under his name or the Noirsys account
- Licence confirmation (currently MIT for code, CC BY 4.0 for paper)
