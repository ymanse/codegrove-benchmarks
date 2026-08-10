# Benchmarks — Code Localization

CodeGrove is built for **code localization**: given an issue, surface the files and
functions a change touches. This page states **what we measure**, the **measured
numbers**, and **how to reproduce them**.

> **2026-08-09 correction.** An earlier version of this page and of the README quoted
> "function-level top-1 ≈ 73% / top-3 ≈ 87% / top-10 ≈ 94%". **Those figures were wrong.**
> 73% was a *file-level* result relabelled as function-level, and the 87 / 94 values did not
> correspond to any single measured run. Every number below is now traceable to a row in
> [`data/localization-runs.csv`](data/localization-runs.csv). See
> [Correction log](#correction-log).

---

## The distinction that matters: file-level vs function-level

These are two different metrics and they are **not close to each other**. Conflating them is
what produced the retracted numbers, so this page states both everywhere.

| Metric | Question it answers |
| --- | --- |
| **file-level top-k** | Is a gold *file* among the first k returned files? |
| **function-level top-k** | Is a gold *function FQN* among the first k returned functions? |

Function-level is the strictly harder metric, and the gap between them is large — see
[The file→function gap](#the-filefunction-gap).

---

## Measured results

**Dataset `cm99`** — 99 real SWE-bench Django issues with function-level gold FQNs.
91 of the 99 have at least one enclosing-function gold; the remaining 8 are module- or
class-body patches, so function-level metrics use **n = 91** and file-level use **n = 99**.

### Most recent full run (2026-07-01, `sonnet5_both_max`)

| | top-1 | top-3 | top-5 | top-10 |
| --- | :---: | :---: | :---: | :---: |
| **file-level** (n=99) | **0.778** | 0.848 | 0.859 | 0.879 |
| **function-level** (n=91) | **0.209** | 0.330 | 0.374 | 0.495 |

file-level top-1 95% CI: **[0.686, 0.848]** (bootstrap). Wall clock 2,028 s for 99 instances.

### Across all 11 full-scale `cm99` runs

| Metric | min | median | max |
| --- | :---: | :---: | :---: |
| file-level top-1 | 0.515 | **0.717** | 0.848 |
| file-level top-10 | 0.848 | 0.879 | **0.879** |
| function-level top-1 | 0.088 | **0.220** | 0.231 |
| function-level top-10 | 0.198 | 0.429 | **0.495** |

A second, larger Django split (`n114`, 114 instances / 102 function-evaluable) was used for
ablations; across its 38 runs file-level top-1 ranges 0.430–0.789 (median 0.693) and
function-level top-1 ranges 0.029–0.206 (median 0.147).

**All 50 full-scale runs, with per-run configuration, are in
[`data/localization-runs.csv`](data/localization-runs.csv).** Every number on this page
is a cell in that file.

> **Read the `n` before the score.** Smoke runs at n = 2–16 routinely show file-level top-1 =
> 1.000. They are wiring checks, not results, and are excluded from the CSV (which is filtered
> to n ≥ 90).

---

## The file→function gap

The most useful thing these measurements say about the system is **where it fails**:

```
file-level    top-1 0.778  ████████████████░░░░
function-level top-1 0.209  ████░░░░░░░░░░░░░░░░
function-level top-10 0.495 ██████████░░░░░░░░░░
```

The retriever identifies the correct **file** first about 78% of the time, but the correct
**function** first only about 21% of the time — while reaching it within 10 candidates about
half the time. So the gold function is usually *retrieved*; it is **ranked poorly among its
siblings inside a file that was already correctly identified**.

That makes intra-file function discrimination the open problem, not file retrieval. We publish
the gap rather than the flattering half of it because it is the number that tells you what the
system is actually good at today: **narrowing to the right file**, not picking the right
function on the first try.

---

## Tier 1 — Offline file-level harness

**What it measures.** File-level top-1 / top-5 localization on
[SWE-bench Lite](https://www.swebench.com/), comparing a BM25 baseline against CodeGrove's
hybrid ranker with a paired bootstrap significance test. It needs no graph DB, embeddings, or
LLM — it runs in a single process, which makes it the tier an outside reader can rebuild most
easily.

**Dataset.** `princeton-nlp/SWE-bench_Lite` (HuggingFace, MIT) — public. Gold **files** are
extracted from each instance's patch: take the patch's changed-file list as the gold set. That
is the whole ground-truth construction for this tier, and it is reproducible from the public
dataset alone.

**Ranker.** Reciprocal-rank fusion over a lexical and a structural channel, scored against the
gold file set. The harness implementation lives in the private engine repository, but the
metric definition above is complete enough to reimplement: for each instance, rank candidate
files, then check whether a gold file appears in the first k.

**Significance.** Paired bootstrap over instances (10k resamples) for top-k confidence
intervals; McNemar for paired binary win/loss between two configurations on the same instance
set.

---

## Tier 2 — Live function-level (how the numbers above were produced)

Function-level scoring needs the full engine, so it is **not turnkey**. It requires the
CodeGrove engine and its MCP server (both private), a graph backend with `django@main` ingested
and embeddings generated, and an LLM provider key for the listwise re-ranker. The pipeline's
ranked FQNs are then scored against the gold FQN set for each instance.

The **gold set itself is derivable from public data**: for each SWE-bench Django instance, take
the gold patch, resolve each changed hunk to its enclosing function, and record the FQN as
`path/to/file.py.Class.method`. Instances whose patches touch only module- or class-body code
have no enclosing function and are excluded — that is why n = 91 rather than 99.

**Configuration of the quoted runs.** Three-stage retrieval (5 files × 20 functions per file),
multi-anchor BFS in `full` mode with `soft_score` local filtering, a local llama.cpp reranker
(Qwen3-Reranker-0.6B-Q8_0), and an LLM listwise re-ranker on top. The judge model differs per
run and is recorded in the CSV's `run` column — measured judges include Claude Opus/Sonnet
class, GLM-5.2, and GPT-5.5 class models.

**Honesty notes.**

- Function-level top-1 has **never exceeded 0.231** on any full-scale run in the measurement history published here (50 runs, 2026-05-18 → 2026-07-01).
- Scores move with the judge model, the reranker configuration and the indexed snapshot.
  The spread across configurations is wide — file-level top-1 spans 0.515–0.848 on the *same*
  dataset — so a single number without its configuration is not meaningful.
- `cm99` is a 99-instance Django subset, not full SWE-bench. It derives from public SWE-bench
  data (problem statements + gold patches), so the goldset is open; only the *scoring* needs a
  live index.
- Treat these as a characterization of the current pipeline, not a leaderboard score.

---

## Correction log

| Date | Change |
| --- | --- |
| **2026-08-09** | Retracted "function-level top-1 ≈ 73% / top-3 ≈ 87% / top-10 ≈ 94%". Root cause: a file-level result was labelled function-level, and top-3/top-10 were not traceable to any run. Replaced with per-metric measured values, ranges over 11 `cm99` runs, and a published per-run CSV. Added the file→function gap section, which the retracted framing had hidden. |

Re-deriving the retracted figures: file-level top-1 on the strongest `cm99` configuration is
0.848 and the median is 0.717 — the "73%" was in that neighbourhood, but it is a **file**
number. The corresponding function-level value is 0.209–0.231.

---

## What is intentionally **not** here

**Engine source.** CodeGrove is a private project under commercial evaluation. What makes the
claims falsifiable is the method plus the complete run data, and both are here.

**Seeded-synthetic "scaffold" values.** An earlier internal document produced placeholder
benchmark numbers from a seeded RNG in under a millisecond, to test pipeline wiring. They were
labelled as such in prose but sat in result-shaped tables, and were mistaken for measurements.
None appear here, and none should ever be cited.

**Smoke runs.** n = 2–16 wiring checks routinely score 1.000 at file level. The CSV is filtered
to n ≥ 90.

**Internal corpora.** Numbers measured against private codebases are not published. Everything
in this repository is measured on public SWE-bench Django data.

See [`EXPERIMENTS.md`](EXPERIMENTS.md) for what each measurement campaign tested and what it
concluded.
