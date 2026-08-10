# CodeGrove — what it is, and how well it works

*[한국어 문서](README.ko.md)*

**CodeGrove turns a codebase into a queryable knowledge graph, so a coding agent can be told
*"the bug is in this function"* instead of being handed files to grep.**

This repository is the **evidence half** of that project: the evaluation method, every measured
number, and the experiments that failed. The engine source is private — see
[why](#why-the-engine-is-not-here).

**Headline: on 99 real SWE-bench Django issues, the first function it returns is the correct one
73.7 % of the time; the correct function is in its top 10 93.9 % of the time.**

---

## 1. What it is

Grep finds strings. Embeddings find code that *looks* similar. Neither can tell an agent **what
calls what**, **what a change breaks**, or **which module a symbol really belongs to**. CodeGrove
builds those relationships once and keeps them current.

```text
Source repositories  (9 language families: Python, Java, Kotlin, Scala, JS, TS, C/C++, Go, Rust)
        │
        ▼  Tree-sitter parsers
Language-neutral entities & relations
        │   files · modules · classes · functions · calls · imports · inheritance · provenance
        ▼
Graph store  (Neo4j / Memgraph → later migrated to PostgreSQL + pgvector)
        │
        ├── Embeddings            Ollama · OpenAI-compatible · UniXcoder
        ├── Community detection   Leiden / Louvain
        ├── DB schema ingestion   MariaDB / MSSQL schemas into the same graph
        ├── Incremental sync      git-diff driven — re-parses only what changed
        └── MCP server            queried directly by coding agents
        │
        ▼
Localization pipeline  ── issue text ──► ranked function FQNs
   stage 1  hybrid retrieval (vector + graph) → candidate files
   stage 2  local cross-encoder reranker (Qwen3-Reranker-0.6B, llama.cpp)
   stage 3  LLM listwise re-ranking → final function ranking
```

**The problem it solves.** A coding agent asked to fix an issue normally burns its context
window exploring: list files, grep, open, repeat. If the first thing it opens is already the
right function, that whole loop disappears. That is why **function-level top-1** — not file-level,
not top-10 — is the metric this project optimises.

## 2. What I built, and at what scale

Designed and implemented **solo**, orchestrating AI agents as the development team. 2026 – ongoing.

| | |
| --- | --- |
| **Graph in production use** | **455,540 nodes · 1,131,482 edges · 181,464 embeddings**, across 12 repositories |
| **Corpus** | A private multi-repo polyglot codebase — C++, Java, Kotlin, TypeScript in one graph |
| **Languages parsed** | 9 families |
| **Engine test suite** | 1,925 tests |
| **Agent surface** | MCP server, 20 built-in tools (plus a separate agent-facing server) |
| **Backend migration** | In-memory graph DB → PostgreSQL + pgvector, lossless: **51 PASS / 0 FAIL**, differential equivalence **255/256**, vector **recall@10 0.955** |

Engineering decisions worth naming, because they are what the numbers rest on:

- **Cypher variable-length traversal was replaced with PostgreSQL `WITH RECURSIVE` CTEs.** The
  premise was that the product needs *edge facts*, not a graph *engine* — which removed a
  licence, a RAM ceiling and an operational burden at once.
- **The migration shipped behind a differential-equivalence harness**: both backends run the same
  code and their outputs are diffed. It caught real bugs before production — a serialisation
  crash, a collation mismatch, incorrect edge deletion.
- **Evaluation is a first-class subsystem**, not a script. That is what the rest of this
  repository documents.

## 3. How well it works

`cm99` — 99 real [SWE-bench](https://www.swebench.com/) Django issues, each labelled with the
**function** the official fix actually changed. Reference run `sonnet5_both_max`, 2026-07-01:

| | top-1 | top-3 | top-10 |
| --- | :---: | :---: | :---: |
| **function-level** (n=99) | **73.7 %** | **86.9 %** | **93.9 %** |
| file-level (n=99) | 77.8 % | 84.8 % | 87.9 % |

Across the 9 full `cm99` runs, **function-level top-1 spans 0.727 – 0.849** (one degraded
configuration sits at 0.232). Best measured configuration overall: **0.860**.

**[`data/localization-runs.csv`](data/localization-runs.csv) — 133 scored streams, one row each.**
Every number on this page is a cell in that file.

### "function-level top-1" means exactly this

> Take the issue text. Ask the system for a ranked list of functions. **Is the very first one a
> function the official fix actually changed?**

Not the right file — the right *function*, first try. Gold labels come from the SWE-bench patch:
each changed line is resolved to its enclosing function **at the base commit**, recorded as
`path/to/file.py.Class.method`. Derivable from public data alone.

### It is not memorisation

`cm99` is public and old enough to sit in model training data, so the same pipeline was re-run on
**`fresh-2026`: 29 Django pull requests merged after the judges' training cutoffs**.

Function-level top-1 there: **0.724 – 0.828** — the same band as `cm99`'s 0.727 – 0.849. 13
configurations in [`data/fresh-2026-judges.csv`](data/fresh-2026-judges.csv).

*(n=29, so one instance moves the number 3.4 pp. This rules out memorisation as the dominant
explanation; it does not resolve small judge-to-judge differences.)*

## 4. How it was measured

Measurement was treated as the deliverable, not an afterthought.

- **Gold set audited and re-frozen.** The original labels were found contaminated in **37 of 41**
  audited instances — functions had been resolved against post-patch source. Rebuilt from
  base-commit resolution, frozen by SHA-256, and **every stream re-scored**. The same run moved
  from 0.209 to 0.737. The rule learned: **a stored metric field is not a result.**
- **Significance testing, not eyeballing.** McNemar for paired binary outcomes, paired bootstrap
  for top-k confidence intervals.
- **Pre-registered experiments.** Hypothesis, metric and decision rule written before each cell
  ran, with a standing rule that every executed cell gets reported.
- **The ceiling was located.** The top four judge configurations are **statistically
  indistinguishable** (McNemar p = 0.607, bootstrap CI spanning zero). So 0.82 – 0.85 is the
  pipeline's selection ceiling, and "our number is highest" would be a false claim.

## 5. What did not work

Published because negative results are what justify the current defaults — and because a
benchmark page that only lists wins is not a benchmark page.

Oracle analysis showed the bottleneck is **not retrieval**: the correct function reaches the
candidate pool ~82 % of the time, while top-1 is 17–25 pp below that. The loss is **sibling
discrimination** — choosing among several plausible functions inside a file already identified
correctly.

Six pre-registered attempts on that bottleneck. **All null within noise:** judge-prompt
restructuring, call-direction relation injection, value-provenance re-ranking, cross-variant
agreement selection, issue-truncation removal, temperature control.

One of them exposed something more useful than a win: the judge was **22.8 % non-deterministic**
at default temperature, which had been silently swallowing the effect size of every earlier A/B.
Pinning `temperature=0` restored determinism (69.6 % → 91.3 % agreement) **without changing
accuracy** — a statistical-power lever, not a quality one. The interventions were re-run at
temperature 0 and were *still* null, which is what makes the conclusion trustworthy: the ranking
prior is intrinsic to the judge model, not promptable.

**A cost finding that outranks the accuracy ranking.** `grok-4.5` at `effort=high` reaches 0.759
in a **2.5 s** median at **$0.015**/instance; the best configuration reaches 0.828 at 64 s and
twice the price — 7 pp for a **26×** latency difference. Since the top configurations are
statistically indistinguishable anyway, **the judge is a cost-and-latency decision, not an
accuracy one.**

## 6. Correction notice

On 2026-08-09/10 the headline figures were **retracted in error** and replaced with
0.209 / 0.330 / 0.495. That retraction was **withdrawn on 2026-08-10**; the original figures were
correct.

Cause: the retraction read the legacy `fn_top1` field stored in the run JSON files — scored
against the superseded, contaminated `gold v1`. Re-scoring the raw predictions against `gold v2`
returns 0.737 / 0.869 / 0.939.

Both the error and its withdrawal are kept in
[`BENCHMARKS.md`](BENCHMARKS.md#correction-log) rather than deleted.

---

## What's in this repository

| File | Contents |
| --- | --- |
| [`BENCHMARKS.md`](BENCHMARKS.md) | Scoring rules, measured numbers, correction log |
| [`EXPERIMENTS.md`](EXPERIMENTS.md) | Each campaign: what it varied, what it concluded — including the null results |
| [`data/localization-runs.csv`](data/localization-runs.csv) | 133 scored streams: fn/file top-k, scored instance counts |
| [`data/fresh-2026-judges.csv`](data/fresh-2026-judges.csv) | 13 judge configurations on post-cutoff Django PRs: top-k, latency, cost |

## Why the engine is not here

CodeGrove is a private project under commercial evaluation. What makes a benchmark claim
falsifiable is the **method plus the complete run data**, and both are here — including the gold-
label derivation rule, so a third party can reimplement the scoring. Publishing the engine is not
required for that, and is not reversible.

## Honest limits

- Scores move with the judge model and its effort setting; `cm99` spans 0.232 – 0.849. A number
  without its configuration is not meaningful.
- `cm99` is a 99-instance Django subset, not full SWE-bench.
- On this benchmark a frontier model with plain `Read`/`Grep`/`Glob` and no index scores higher
  (0.75 fresh / 0.80 contaminated) than the pipeline on the same instances. Django is small,
  public and well-structured — the regime where a code graph adds least. That comparison is in
  [`EXPERIMENTS.md`](EXPERIMENTS.md#campaign-6--the-unflattering-comparison), published rather
  than omitted.
- Treat these as a characterization of one pipeline at one point in time, not a leaderboard score.

---

*Data and documents may be quoted with attribution.*
