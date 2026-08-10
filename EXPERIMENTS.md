# Experiments — what was tested and what it showed

This is the experiment log behind [`BENCHMARKS.md`](BENCHMARKS.md). It records **what each
measurement campaign varied**, **what it measured**, and **what it concluded** — including the
campaigns that found nothing, which are the ones usually deleted.

- **Measurement window.** 2026-05-18 → 2026-07-01.
- **Runs.** 50 full-scale runs (n ≥ 90). Smoke runs at n = 2–16 are excluded; they are wiring
  checks and routinely score 1.000.
- **Raw data.** [`data/localization-runs.csv`](data/localization-runs.csv) — one row per run,
  with per-run configuration. Everything below is derived from it.

## Datasets

| Name | Instances | Function-evaluable | Source |
| --- | ---: | ---: | --- |
| `cm99` | 99 | 91 | 99 SWE-bench Django issues, function-level gold FQNs  |
| `n114` | 114 | 102 | Larger Django split used for ablations |

The function-evaluable count is lower because module-body and class-body patches have no
enclosing function; those instances are excluded from function-level metrics rather than
counted as misses.

## Metrics

`file_top{1,3,5,10}` — is a gold **file** in the first k? `fn_top{1,3,5,10}` — is a gold
**function FQN** in the first k? `file_top1_voted` — top-1 under multi-sample vote instead of
single ranked output. 95% CIs are bootstrap.

---

## Campaign 1 — Multi-anchor BFS (18 runs, `n114`)

**Question.** Does expanding retrieval from multiple graph anchors (rather than one) improve
localization? Modes: `off`, `calls-only`, `saturation-only`, `full`.

**Result — v0 (4 runs): a null result, and initially a false one.** All four modes returned
*byte-identical* metrics (file top-1 0.684, fn top-1 0.137). Four "different" configurations
scoring identically is not a finding about multi-anchor; it means the flag was not reaching
the retrieval path. The v1 re-run (10 runs) separated the modes only marginally
(fn top-1 0.137 → 0.147 for `full`/`saturation-only`), which is within noise at n = 114.

**Result — v1.5 (4 runs): actively harmful.** `full` and `saturation-only` collapsed to
file top-1 **0.430** and fn top-1 **0.029**, against `off` at 0.702 / 0.137. A 27pp file-level
regression.

**Conclusion.** Multi-anchor BFS was not shown to help at any version, and the v1.5 expansion
policy hurt badly. Retained as an off-by-default toggle. The lasting methodological lesson is
the v0 one: *identical scores across an ablation grid are a bug signal, not a null result.*

## Campaign 2 — Judge model and reasoning effort (9 runs, `cm99`)

**Question.** How much does the LLM listwise re-ranker choice move localization?

| Run | file top-1 | fn top-1 | wall clock |
| --- | ---: | ---: | ---: |
| `cm99_opus_sdk_max` | **0.848** | 0.231 | 1,637 s |
| `sonnet5_both_max_cm99` | 0.778 | 0.209 | 2,027 s |
| `glm52_both_high_cm99` | 0.737 | 0.220 | 2,062 s |
| `likely_both_cm99` | 0.737 | 0.231 | 984 s |
| `codex_both_cm99` | 0.727 | 0.231 | 920 s |
| `gpt55med_cm99` | 0.707 | 0.187 | 760 s |
| `gpt55dec_cm99` | 0.697 | 0.198 | 800 s |
| `glm52_both_low_cm99` | 0.687 | 0.231 | 1,876 s |
| `cm99_opus_sdk_xhigh` | **0.515** | 0.088 | 612 s |

**Conclusion.** The judge matters, but **the effort setting matters more than the model**: the
same Opus-class judge scored 0.848 at `max` and 0.515 at `xhigh` — a 33pp swing on identical
data and pipeline, larger than the spread across every other model tested. Any quoted number
is meaningless without its judge *and* effort setting; this is why
[`BENCHMARKS.md`](BENCHMARKS.md) publishes the configuration alongside each figure.

Note also that file-level and function-level do not rank the same: `glm52_both_low` was the
worst-but-one on files (0.687) yet tied for best on functions (0.231).

## Campaign 3 — Candidate pool size (2 runs, `cm99`)

**Question.** Does a larger candidate pool before re-ranking help?

| Pool | file top-1 | fn top-1 |
| --- | ---: | ---: |
| p60 | 0.717 | **0.231** |
| p80 | 0.717 | **0.121** |

**Conclusion.** Enlarging the pool from 60 to 80 left file-level unchanged and **halved**
function-level top-1. More candidates gave the re-ranker more plausible-but-wrong siblings to
choose from. Pool size is a function-level precision knob, not a recall knob — and the
file-level metric is blind to the damage.

## Campaign 4 — HyDE query expansion (11 runs, `n114`)

**Question.** Does hypothetical-document expansion, including agentic multi-turn variants
(`agentic2`–`agentic7`) and a `swerank` variant, beat the control?

| Variant | file top-1 | fn top-1 |
| --- | --- | --- |
| control | 0.684 – 0.711 | 0.127 – 0.167 |
| agentic | 0.649 – 0.719 | 0.137 – 0.165 |
| flat p1p2 | 0.667 – 0.693 | 0.167 |

**Conclusion.** Fully overlapping ranges on both metrics. No variant separated from control at
n = 114. The agentic variants additionally cost 2–4× wall clock (up to 5,641 s vs 1,343 s).
Not adopted.

## Campaign 5 — Pipeline component ablations (8 runs, `n114`)

Prompt and stage variants (`truebase`, `full`, `p1`, `p1p2`, `instr`, `C`, `BDc`) plus a
reranker on/off check.

**Conclusion.** file top-1 spanned 0.728–0.789 and fn top-1 0.137–0.206 with no variant
reliably ahead of `truebase` (0.781 / 0.206). The reranker check (`phase1_reranker_on_sat`,
0.728 / 0.186) did not separate either. This band — roughly ±3pp around the baseline at
n = 114 — is the noise floor these datasets can resolve; distinguishing variants inside it
needs a larger evaluation set, not more runs of the same size.

---

## What the campaigns collectively show

1. **Function-level top-1 never exceeded 0.231** in any full-scale run across the entire
   measurement window, under any judge, pool size, expansion strategy or anchor mode.
2. **File-level top-1 reached 0.848**, and file-level top-10 reached 0.904. The system is
   good at narrowing to the right file.
3. **The gap between them is the product's real open problem** — ranking the right function
   among siblings inside an already-correct file. Function-level top-10 of 0.495 says the gold
   function is usually somewhere in the candidate set; it is the ordering that fails.
4. **Configuration dominates model choice.** The largest single swing observed (33pp) came
   from a reasoning-effort setting, not from switching model families.
5. **Most tested ideas did not work.** Multi-anchor BFS, HyDE expansion (including agentic
   variants), and larger candidate pools each failed to beat their control; two actively
   regressed. They are recorded here rather than deleted, because the negative results are
   what justify the current defaults.

## Reproducing

File-level results are reproducible offline from public SWE-bench Lite — see
[`BENCHMARKS.md` Tier 1](BENCHMARKS.md#tier-1--offline-file-level-harness).
Function-level scoring requires a live index; see
[Tier 2](BENCHMARKS.md#tier-2--live-function-level-how-the-numbers-above-were-produced).

## Superseded material

The following were removed on 2026-08-09 as stale or misleading, and are listed so their
absence is deliberate rather than silent:

| Removed | Why |
| --- | --- |
| "function-level top-1 ≈ 73% / top-3 ≈ 87% / top-10 ≈ 94%" | File-level number relabelled as function-level; top-3/top-10 untraceable to any run. Retracted in [`BENCHMARKS.md`](BENCHMARKS.md#correction-log) |
| Seeded-synthetic "scaffold" benchmark values | Produced by a seeded RNG in under 1 ms to test pipeline wiring. Never measurements; must not be cited |
| Smoke-run scores (n = 2–16) | Routinely 1.000 at file level; excluded from the CSV and from every table here |
