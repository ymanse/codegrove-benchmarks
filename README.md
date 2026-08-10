# CodeGrove — Localization Benchmarks

Measurement method and raw results for **code localization** in CodeGrove, a GraphRAG code
intelligence system: given an issue, surface the files and functions a change touches.

**This repository contains no source code.** It publishes the evaluation methodology and every
measured number so the results can be checked independently. The engine itself is a private
project.

---

## Headline results

`cm99` — 99 real [SWE-bench](https://www.swebench.com/) Django issues with function-level gold
FQNs. 91 of the 99 have an enclosing-function gold; the rest are module- or class-body patches,
so function-level metrics use n = 91 and file-level use n = 99.

Most recent full run, 2026-07-01:

| | top-1 | top-3 | top-5 | top-10 |
| --- | :---: | :---: | :---: | :---: |
| **file-level** (n=99) | **0.778** | 0.848 | 0.859 | 0.879 |
| **function-level** (n=91) | **0.209** | 0.330 | 0.374 | 0.495 |

file-level top-1 95% CI: **[0.686, 0.848]** (bootstrap). 2,028 s wall clock for 99 instances.

Across all 11 full-scale `cm99` runs:

| Metric | min | median | max |
| --- | :---: | :---: | :---: |
| file-level top-1 | 0.515 | **0.717** | 0.848 |
| function-level top-1 | 0.088 | **0.220** | 0.231 |

**[`data/localization-runs.csv`](data/localization-runs.csv) has one row per run — 50 rows,
2026-05-18 → 07-01, with each run's configuration.** Every number on this page is a cell in
that file.

---

## The result worth reading twice

These two metrics are not close, and the gap is the point:

```
file-level     top-1   0.778  ████████████████░░░░
function-level top-1   0.209  ████░░░░░░░░░░░░░░░░
function-level top-10  0.495  ██████████░░░░░░░░░░
```

The retriever reaches the correct **file** first about 78% of the time, but the correct
**function** first only about 21% — while reaching it within 10 candidates about half the time.
So the gold function is usually *retrieved*; it is **ranked poorly among its siblings inside a
file that was already correctly identified.**

Intra-file function discrimination is therefore the open problem, not file retrieval. Function-
level top-1 has **never exceeded 0.231** in any full-scale run, under any judge model, pool
size, query-expansion strategy or graph-anchor mode.

## Correction notice

An earlier public description of this system quoted **"function-level top-1 ≈ 73% / top-3 ≈ 87%
/ top-10 ≈ 94%"** on `cm99`. Those figures were retracted on 2026-08-09 and traced to their
source run on 2026-08-10. They came from a **single A/B reranker sample: file-level, 30
instances** — not `cm99`, and not function-level.

| | n | top-1 | top-3 | top-10 |
| --- | ---: | ---: | ---: | ---: |
| Published as "cm99, function-level" | *99* | *≈0.73* | *≈0.87* | *≈0.94* |
| **Actually — file-level, one A/B sample** | **30** | **0.733** | **0.867** | **0.933** |
| Same run, function-level (what was claimed) | 29 | **0.034** | 0.138 | 0.172 |

Wrong grain, wrong sample size, and a magnitude off by roughly 21×. This repository exists so
the replacements are checkable rather than merely asserted — see
[`BENCHMARKS.md`](BENCHMARKS.md#provenance-of-the-retracted-numbers).

---

## What's here

| File | Contents |
| --- | --- |
| [`BENCHMARKS.md`](BENCHMARKS.md) | What is measured, the measured numbers, how to reproduce, correction log |
| [`EXPERIMENTS.md`](EXPERIMENTS.md) | Each measurement campaign: what it varied, what it concluded — **including the ones that found nothing** |
| [`data/localization-runs.csv`](data/localization-runs.csv) | 50 full-scale runs × 20 columns: per-metric scores, CIs, wall clock, reranker/anchor configuration |

Smoke runs (n = 2–16) are excluded. They routinely score 1.000 at file level and are wiring
checks, not results — the CSV is filtered to n ≥ 90.

## Method in one paragraph

Queries are SWE-bench Django problem statements truncated to ~900 characters. Gold labels are
function FQNs (`path/to/file.py.Class.method`) derived from each instance's gold patch. Scoring
runs against a live index of `django@main` (graph + embeddings) through a three-stage hybrid
retrieval pipeline with a local reranker and an LLM listwise re-ranker. Significance uses
**McNemar** for paired binary outcomes and **paired bootstrap** for top-k confidence intervals.
Judge model and reasoning effort are recorded per run in the CSV.

## Why the source is not here

CodeGrove is a private project under commercial evaluation. Publishing the benchmark method and
the complete run data is the part that makes the claims falsifiable; publishing the engine is
not required for that, and would not be reversible.

If you are evaluating this work and want to go deeper than the data here, get in touch.

## Notes on reading these numbers

- Scores move with the judge model, reranker configuration and indexed snapshot. The spread
  across configurations is wide — file-level top-1 spans 0.515–0.848 on the *same* dataset — so
  a single number without its configuration is not meaningful.
- `cm99` is a 99-instance Django subset, not full SWE-bench.
- Treat these as a characterization of one pipeline at one point in time, not a leaderboard
  score.

---

*Data and documents in this repository may be quoted with attribution.*
