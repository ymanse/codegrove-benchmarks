# Benchmarks — Code Localization

CodeGrove is built for **code localization**: given an issue, surface the files and functions a
change touches. This page states **what is measured**, the **measured numbers**, and **how
scoring works**.

> **2026-08-10 — a retraction published here on 2026-08-09/10 has itself been withdrawn.**
> The headline figures (`73 / 87 / 94`) were **correct**. They were briefly retracted on the
> basis of a stale scoring column and are now reinstated. See
> [Correction log](#correction-log) — the episode is documented rather than deleted.

---

## Scoring, and the one thing that trips people up

Every run writes its per-instance predictions to a `*.stream.jsonl` file. Those predictions are
scored **against a frozen gold set**, `gold v2` — rebuilt on 2026-06-12 after an audit found the
previous gold (`v1`) contaminated in **37 of 41** audited instances.

Run JSON files still carry a legacy `fn_top1` field scored against the **contaminated v1 gold**.
It is retained only for historical diffing and **must not be read as a result**; on the run
below it reads 0.209 where the correct value is 0.737. All numbers on this page come from
re-scoring the raw predictions against `gold v2`.

**Gold construction (v2).** For each SWE-bench Django instance: take the gold patch, resolve
each changed line to its enclosing function *at the base commit*, and record the FQN as
`path/to/file.py.Class.method`. Test files and non-Python files are excluded.

**Metrics.** `fn_top{k}` — is a gold *function FQN* among the first k predicted FQNs?
`file_top{k}` — same question at file granularity, after de-duplicating the predicted FQN list
to files.

---

## Measured results

**Dataset `cm99`** — 99 real SWE-bench Django issues with function-level gold FQNs.

### Reference run — `sonnet5_both_max`, 2026-07-01, n=99

| | top-1 | top-3 | top-5 | top-10 |
| --- | :---: | :---: | :---: | :---: |
| **function-level** | **0.737** | **0.869** | 0.889 | **0.939** |
| file-level | 0.778 | 0.849 | — | 0.879 |

This is the run behind the published **≈73 % / ≈87 % / ≈94 %**.

### Across the 9 full `cm99` runs (n=99 each)

| Metric | min | median | max |
| --- | :---: | :---: | :---: |
| function-level top-1 | 0.232 | **0.768** | **0.849** |
| function-level top-3 | 0.455 | 0.889 | 0.919 |
| function-level top-10 | 0.616 | 0.929 | 0.939 |
| file-level top-1 | 0.465 | 0.788 | 0.879 |

The 0.232 floor is a single degraded configuration (`opus_sdk_xhigh`); every other cm99 run
lands between 0.727 and 0.849. Best measured configuration overall across all 133 scored
streams is **0.860** function-level top-1 (`medium62_truebase`, n=57).

**[`data/localization-runs.csv`](data/localization-runs.csv) has one row per scored stream —
133 rows, n ≥ 30.** Every number on this page is a cell in that file.

---

## Where it actually fails

Function-level top-1 ≈ 0.74 and file-level top-1 ≈ 0.78 on the reference run: the residual gap
is **intra-file sibling discrimination** — picking the right function among several plausible
ones inside a file that was already correctly identified.

That gap has been probed hard and has not moved. A pre-registered campaign ran judge-prompt
restructuring, call-direction relation injection, value-provenance re-ranking, cross-variant
agreement selection, issue-truncation removal and judge temperature control. **All returned
null within noise.** The measured diagnosis is that the ranking prior is intrinsic to the judge
model rather than promptable — see [`EXPERIMENTS.md`](EXPERIMENTS.md).

One methodological finding from that campaign is worth repeating: the judge was **22.8 %
non-deterministic** at default temperature, which was silently swallowing the effect sizes of
every earlier A/B. Setting `temperature=0` recovered determinism (69.6 % → 91.3 % agreement on
the hard subset) **without moving accuracy** — it is a statistical-power lever, not a quality
lever.

---

## Contamination check — does it hold on unseen code?

`cm99` is drawn from public SWE-bench Django, which is old enough to sit inside model training
data. The obvious objection is that the scores measure memorisation rather than localization.

They are therefore also measured on **`fresh-2026`: 29 Django pull requests merged after the
judges' training cutoffs**, scored by the same rule.

| judge configuration | fn top-1 | top-3 | top-10 | median latency | $/instance |
| --- | :---: | :---: | :---: | ---: | ---: |
| Kimi-K2.7-Code (thinking=on) | **0.828** | 0.862 | 0.897 | 64.1 s | 0.030 |
| gpt-5.3-codex (thinking=on) | **0.828** | 0.828 | 0.931 | 40.5 s | 0.059 |
| gpt-5.5 (thinking=on) | **0.828** | 0.897 | 0.931 | 66.2 s | 0.182 |
| GLM-5.2 (thinking=on) | 0.793 | 0.828 | 0.897 | 14.9 s | 0.019 |
| grok-4.5 (high, neutral framing) | 0.793 | 0.862 | 0.897 | 32.9 s | 0.053 |
| **grok-4.5 (effort=high)** | 0.759 | 0.897 | 0.897 | **2.5 s** | **0.015** |
| gpt-5.5 (no router) | 0.724 | 0.897 | 0.897 | 2.8 s | 0.059 |

All 13 measured configurations are in
[`data/fresh-2026-judges.csv`](data/fresh-2026-judges.csv).

**Result: the scores hold.** `fresh-2026` spans 0.724–0.828 against `cm99`'s 0.727–0.849 — the
same band. Whatever the pipeline is doing, it is not recall of memorised Django.

**Caveat, stated plainly:** n=29, so one instance moves the number by 3.4 pp. This set is three
times noisier than `cm99` and is the weaker of the two measurements. It rules out memorisation
as the *dominant* explanation; it does not resolve small differences between judges.

**A cost finding that matters more than the ranking.** `grok-4.5` at `effort=high` reaches 0.759
in a **2.5 s** median at **$0.015** per instance — against Kimi's 0.828 at 64 s and twice the
price. That is 7 pp of accuracy for a **26×** latency difference. Since the top configurations
on `cm99` are statistically indistinguishable anyway (McNemar p = 0.607 between the best two,
bootstrap CI spanning zero), **the judge should be chosen on cost and latency, not on top-1** —
the accuracy differences between serious candidates are not real.

---

## Reproducing

**Gold set.** Derivable from public SWE-bench data alone: gold patch → changed lines →
enclosing function at base commit → FQN. No private data is involved.

**Function-level scoring.** Requires the CodeGrove engine (private) with `django@main` ingested
plus an LLM provider key for the listwise re-ranker. The ranked FQNs it emits are then scored
against the gold set with the rule above.

**Configuration of the reference run.** Three-stage retrieval (5 files × 20 functions per
file), multi-anchor BFS in `full` mode with `soft_score` local filtering, a local llama.cpp
reranker (Qwen3-Reranker-0.6B-Q8_0), and an LLM listwise re-ranker. Judge models measured
across the run set include Claude Opus/Sonnet class, GLM-5.2, GPT-5.5 class, Codex and
MiniMax-M3.

**Honesty notes.**

- Scores move with the judge model and its effort setting. The `cm99` spread is 0.232–0.849 at
  function-level top-1, and the low end is one specific degraded configuration — a single
  number without its configuration is not meaningful.
- `cm99` is a 99-instance Django subset, not full SWE-bench.
- Treat these as a characterization of one pipeline at one point in time, not a leaderboard
  score.

---

## Correction log

| Date | Change |
| --- | --- |
| **2026-06-12** | `gold v1` audited and found contaminated (37/41). `gold v2` rebuilt from base-commit resolution and frozen (SHA-256 `417f5980…`). All streams re-scored. Run JSONs keep the legacy v1-scored `fn_top1` field for diffing only. |
| **2026-08-09** | *(withdrawn)* Published a retraction of "function-level 73 / 87 / 94", replacing it with 0.209 / 0.330 / 0.495. |
| **2026-08-10** | *(withdrawn)* Attributed the retracted figures to a 30-instance file-level A/B sample. |
| **2026-08-10** | **Both retractions withdrawn; original figures reinstated.** Root cause: the retraction was built by reading the legacy `fn_top1` field out of the run JSONs — the **v1-contaminated** column — instead of re-scoring predictions against `gold v2`. Re-scoring `sonnet5_both_max_cm99` against `gold v2` returns **0.737 / 0.869 / 0.939**, matching the original claim. The audit trail that would have prevented this (`_LEDGER.md`, `_TRACE_FNT1.md`, `_master_table_v2.txt`) sat beside the JSON files and was not read. |

The lesson worth keeping: **a stored metric field is not a result.** When a gold set is
re-frozen, every previously written score becomes stale, and only re-scoring the raw
predictions is trustworthy. This repository therefore publishes re-scored values and the
per-stream prediction counts they came from, not the numbers the runners happened to write.

---

## What is intentionally **not** here

**Engine source.** CodeGrove is a private project under commercial evaluation. The method plus
the complete run data is what makes the claims falsifiable, and both are here.

**The legacy `fn_top1` field.** Scored against contaminated `gold v1`. Retained in the private
run archive for diffing; never published as a result.

**Seeded-synthetic "scaffold" values.** Placeholder numbers from a seeded RNG used to test
pipeline wiring. Never measurements.

**Smoke runs.** n < 30 wiring checks are excluded from the CSV.
