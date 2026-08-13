# CodeGrove code localization benchmark

*[한국어 문서](README.ko.md)*

CodeGrove turns a codebase into a queryable knowledge graph. Given the text of an issue, it
returns a ranked list of the functions that need to change. This repository measures that one
capability.

**Headline.** On 99 [SWE-bench](https://www.swebench.com/) Django issues (`cm99`), the first
function it returns is the correct one **73.7 % of the time** (73/99, 95 % CI 64–81 %). The
correct function is in its top 10 **93.9 % of the time** (93/99, CI 87–97 %).

One run among all those measured is designated the reference run in this document. The figures
above are `sonnet5_both_max`, measured 2026-07-01.

The engine source is private. The reason is [below](#why-the-engine-is-not-here).

---

## 1. What is measured

A coding agent told to fix an issue spends its context exploring. It lists files, greps, opens
one, and repeats. If the function it is handed first is already the right one, that loop
disappears. So the target is not file-level accuracy, and not whether the answer is somewhere in
the top 10, but whether the first function is correct.

```text
issue text ──► ranked function FQNs
  stage 1  hybrid retrieval (vector + graph) → candidate files
  stage 2  local cross-encoder reranker orders the functions inside those files
           (Qwen3-Reranker-0.6B, llama.cpp)
  stage 3  LLM listwise re-ranking → final function ranking
```

An FQN (Fully Qualified Name) is the full name in `path/to/file.py.Class.method` form. The LLM
that decides the order in stage 3 is called the **judge** throughout this document. It is part
of the pipeline, not the thing that scores it.

### What "function-level top-1" means exactly

> Take the issue text. Ask the system for a ranked list of functions. **Is the very first one a
> function the official fix actually changed?**

Gold labels come from the SWE-bench patch. Each changed line is resolved to the function
containing it **at the base commit** and recorded as `path/to/file.py.Class.method`. The same
labels can be rebuilt from public data alone.

## 2. Results

| Reference run (n=99) | top-1 | top-3 | top-10 |
| --- | :---: | :---: | :---: |
| **function-level** | **73.7 %** | 86.9 % | **93.9 %** |

At n=99 one instance moves the number 1.0 pp. The 95 % CI for top-3 is 79–92 %. File-level
scores are omitted because the scoring is defective (section 5).

A **configuration** here is one combination of judge model, `effort` setting and pipeline
options. One run of one configuration produces one **stream**, which is one row of data.

Eleven runs were scored at n=99. Function-level top-1 has a minimum of 23.2 %, a median of
76.8 % and a maximum of 84.9 %. Nine of them land between 72.7 % and 84.9 %; the other two are
badly degraded configurations (47.5 %, 23.2 %).

All 133 scored streams are in
[`data/localization-runs.csv`](data/localization-runs.csv), one per row. Every top-k number in
this section is a cell in that file. The 133 rows are not 133 independent measurements: 57 of
them carry a seed label, and those 57 come from 21 configurations. Folding the seed labels away
leaves 96 distinct configurations.

### Memorisation control

`cm99` is public and old enough to sit in model training data, so the same pipeline was measured
again on `fresh-2026` — 29 Django pull requests merged after the judges' training cutoffs.

Function-level top-1 there is 72.4–82.8 %, the same band as `cm99`'s 72.7–84.9 %. All 13
configurations are in [`data/fresh-2026-judges.csv`](data/fresh-2026-judges.csv).

This control is weak. At n=29 all 13 configurations land on 21–24 hits, and the CI for 24/29 is
65–92 %. A 10 pp memorisation effect fits inside that interval. The per-judge cutoff dates and
the list of 29 pull requests are not in this repository.

## 3. How it was measured

- **The gold set was audited and re-frozen.** The original labels (`gold v1`) were contaminated
  in 37 of 41 audited instances — functions had been resolved against the source *after* the
  patch was applied. It was rebuilt from base-commit resolution, frozen by SHA-256, and every
  stream was re-scored. The same run moved from 20.9 % to 73.7 %.
- **The `gold v2` audit was two independent samples, of 10 and 12.** All 22 were clean. The 95 %
  upper bound on an error rate given 22 clean draws is 12.7 %, so up to 12 of the 99 may still
  be mislabelled.
- **Significance testing was used.** McNemar for paired binary outcomes, paired bootstrap for
  paired comparisons within a campaign. Every 95 % interval printed in this document is a Wilson
  score interval on a single proportion.
- **Hypotheses and decision rules were written before each condition ran.** That record is not in
  this repository.
- **No ranking is claimed among the top configurations.** The best two differ by 2 instances out
  of 99 (84.9 % against 82.8 %, McNemar p = 0.607). That means a 2 pp difference is not
  significant here. It does not establish where this design's detection limit lies.

## 4. What did not work

The decomposition below was done on the `full-114` set (102 scored), not on the reference run,
and does not compare directly with the numbers in section 2.

The bottleneck is selection rather than retrieval. Per the oracle decomposition in
[`EXPERIMENTS.md`](EXPERIMENTS.md), the correct function reaches the candidate pool 82–83 % of
the time while top-1 on the same set is 58–67 %. The 15–25 pp lost in between goes to choosing
among several similar functions inside a file that was already identified correctly.

Six pre-registered interventions were tested against that bottleneck and all were null within
noise. The per-intervention numbers are in [`EXPERIMENTS.md`](EXPERIMENTS.md).

One of them exposed a confound. 22.8 % of the judge's decisions were non-deterministic at the
provider's default temperature, and that noise had been swallowing the effect size of every
earlier A/B. Pinning `temperature=0` raised run-to-run agreement. The interventions were then
re-tested in that state and were still null.

### Cost and latency

Three configurations tie at 82.8 % on `fresh-2026`. Running `grok-4.5` at `effort=high` scores
75.9 %, which is 6.9 pp lower, but finishes in a 2.5 s median at $0.015 per instance. The three
tied configurations take 16–27× the latency at 2–12× the price for that 6.9 pp. Since the top
configurations do not separate statistically (section 3), the judge should be chosen on cost and
latency.

## 5. What this repository cannot answer

- **There are no per-instance predictions.** Each run writes them to `*.stream.jsonl`, but only
  stream-level aggregates are published here. The `gold v2` file, the 29 `fresh-2026` instances
  and the 20 instances behind the comparison in section 6 are also absent. A third
  party can check the scoring rule and the aggregate tables, and nothing beyond that.
- **File-level scoring does not follow the published rule.** The rule is to de-duplicate the
  ranked FQN list to files; the actual scoring reads a `predicted_files_top10` field stored per
  run. If a function is correct then the file containing it is correct too, so a file-level score
  cannot fall below the function-level one. Of the 11 runs scored at n=99, 7 are inverted at
  top-1, and 9 once top-3 and top-10 are counted. The reference run is among them:
  at top-3 its file-level 84.9 % sits below its function-level 86.9 %, and at top-10 87.9 % sits
  below 93.9 %. File-level numbers are withheld until the raw predictions are re-scored.

## 6. Limits

- `cm99` is a 99-instance Django subset, not full SWE-bench.
- **The one head-to-head comparison was a loss.** On 20 public Django instances already inside
  training data, a frontier model with no index and only `Read`/`Grep`/`Glob` got 16 (80 %)
  against the pipeline's 10 (50 %). Same gold set, same instances, same scoring rule. Their
  confidence intervals overlap, at 58–92 % and 30–70 %. Details in
  [`EXPERIMENTS.md`](EXPERIMENTS.md#campaign-6--the-unflattering-comparison).
- Django is small, public and well structured, which is the regime where a knowledge graph adds
  least. The headline came from the same corpus, though. Calling Django an unfavourable condition
  means attaching that same caveat to the headline. There is no measurement yet on the large
  private cross-language codebases the graph is built for.
- These numbers characterise one pipeline at one point in time. They are not a leaderboard score.

---

## What is in this repository

| File | Contents |
| --- | --- |
| [`BENCHMARKS.md`](BENCHMARKS.md) | Scoring rules, measured numbers, correction log |
| [`EXPERIMENTS.md`](EXPERIMENTS.md) | Each campaign: what it varied and what it concluded, null results included |
| [`CONTEXT-COST.md`](CONTEXT-COST.md) | What answering "where is this?" costs — no index vs an LSP vs the graph |
| [`data/localization-runs.csv`](data/localization-runs.csv) | 133 scored streams: function- and file-level top-k, scored instance counts |
| [`data/fresh-2026-judges.csv`](data/fresh-2026-judges.csv) | 13 judge configurations on post-cutoff Django pull requests |
| [`data/context-cost-2026-08-11.csv`](data/context-cost-2026-08-11.csv) | Raw values behind `CONTEXT-COST.md` |
| [`scripts/measure_context_cost.py`](scripts/measure_context_cost.py) | Reproduces the listing and grep conditions on any git repository |

## Correction notice

On 2026-08-09 and 2026-08-10 the headline figures were retracted in error and replaced with
20.9 % / 33.0 % / 49.5 %. That retraction was withdrawn on 2026-08-10; the original figures were
correct. The cause was reading a stored field scored against the superseded gold set
(`gold v1`). The full record is in [`BENCHMARKS.md`](BENCHMARKS.md#correction-log).

## Why the engine is not here

CodeGrove is a private project under commercial evaluation. What is here is the scoring method
and the stream-level aggregates. What a third party can reproduce from that is stated in
section 5.

---

*Data and documents in this repository may be quoted with attribution.*
