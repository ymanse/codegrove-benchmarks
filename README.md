# CodeGrove — Localization Benchmarks

Measurement method and raw results for **code localization** in CodeGrove, a GraphRAG code
intelligence system: given an issue, surface the exact function a change touches.

**This repository contains no source code.** It publishes the evaluation methodology and every
measured number so the results can be checked independently. The engine itself is a private
project under commercial evaluation.

---

## Headline results

`cm99` — 99 real [SWE-bench](https://www.swebench.com/) Django issues with function-level gold
FQNs. Reference run `sonnet5_both_max`, 2026-07-01:

| | top-1 | top-3 | top-10 |
| --- | :---: | :---: | :---: |
| **function-level** (n=99) | **73.7%** | **86.9%** | **93.9%** |
| file-level (n=99) | 87.9% | 94.9% | 98.0% |

Across the 9 full `cm99` runs, function-level top-1 spans **0.232 – 0.849** (median **0.768**).
The floor is one degraded configuration; every other run lands 0.727–0.849. Best measured
configuration across all 135 scored streams: **0.860** function-level top-1.

**[`data/localization-runs.csv`](data/localization-runs.csv) — 135 streams, one row each.**
Every number above is a cell in that file.

## What "function-level top-1" means here

Is the **first** predicted function FQN a gold function for that issue? That is the metric a
coding agent actually feels: fewer retrieval round-trips, fewer wasted tokens. Gold FQNs are
built from the SWE-bench gold patch by resolving each changed line to its enclosing function at
the base commit — derivable from public data alone.

## Where it still fails

Function-level 0.737 against file-level 0.879 on the reference run. The residual gap is
**intra-file sibling discrimination** — choosing among several plausible functions inside a file
that was already correctly identified.

That gap has resisted six pre-registered interventions (judge-prompt restructuring, call-
direction relations, value-provenance re-ranking, cross-variant agreement, issue-truncation
removal, temperature control). **All null within noise.** The measured conclusion is that the
ranking prior is intrinsic to the judge model rather than promptable. The negative results are
published in [`EXPERIMENTS.md`](EXPERIMENTS.md) rather than deleted, because they are what
justifies the current defaults.

## ⚠️ Correction notice — and a withdrawn correction

On 2026-08-09/10 the headline figures were **retracted in error** and replaced with
0.209 / 0.330 / 0.495. That retraction has itself been **withdrawn on 2026-08-10**; the original
figures were correct.

Cause: the retraction was built by reading the legacy `fn_top1` field stored in the run JSON
files. That field is scored against **`gold v1`, which an audit found contaminated in 37 of 41
instances** and which was superseded on 2026-06-12. Re-scoring the raw predictions against the
frozen `gold v2` returns 0.737 / 0.869 / 0.939 — matching the original claim.

Both the mistake and its withdrawal are recorded in
[`BENCHMARKS.md`](BENCHMARKS.md#correction-log). The operative lesson: **a stored metric field
is not a result.** Once a gold set is re-frozen, every previously written score is stale, and
only re-scoring raw predictions is trustworthy. This repository publishes re-scored values.

---

## What's here

| File | Contents |
| --- | --- |
| [`BENCHMARKS.md`](BENCHMARKS.md) | Scoring rules, measured numbers, correction log |
| [`EXPERIMENTS.md`](EXPERIMENTS.md) | Each campaign: what it varied, what it concluded — **including the null results** |
| [`data/localization-runs.csv`](data/localization-runs.csv) | 135 scored streams: fn/file top-k at each grain, scored instance counts |

## Notes on reading these numbers

- Scores move with the judge model and its effort setting; the `cm99` spread at function-level
  top-1 is 0.232–0.849. A single number without its configuration is not meaningful.
- `cm99` is a 99-instance Django subset, not full SWE-bench.
- Treat these as a characterization of one pipeline at one point in time, not a leaderboard
  score.

## Why the source is not here

CodeGrove is a private project under commercial evaluation. Publishing the benchmark method and
the complete run data is what makes the claims falsifiable; publishing the engine is not
required for that, and would not be reversible.

---

*Data and documents in this repository may be quoted with attribution.*
