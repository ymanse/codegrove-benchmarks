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
| **Graph in production use** | **455,540 nodes · 1,131,482 edges · 181,464 embeddings**, across 12 repositories (one coherent snapshot). The live index has since grown to **605,486 nodes** across 38 `repo@branch` indexes (2026-08-11) |
| **Corpus** | A private multi-repo polyglot codebase — C++, Java, Kotlin, TypeScript in one graph |
| **Languages parsed** | 9 families |
| **Engine test suite** | 1,925 tests |
| **Agent surface** | Two MCP servers — a graph-building core (20 tools) and an agent-facing server (**80 tools, 12 exposed by default**) |
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

## 3. What it actually does — 80 tools, grouped by the question they answer

The graph is the substrate; these are the capabilities built on it. Grouped by the question a
developer actually asks, because that is how they get used.

### Understanding unfamiliar code
`understand_codebase` (first call in a repo you have never seen) · `search` (natural-language or
keyword) · `regex_search` · `find_definition` · `get_code_detail` (verbatim body, not a summary) ·
`document_symbols` · `get_smart_context`

### "If I change this, what breaks?" — the capability the graph exists for
`assess_impact` returns the blast radius *before* the edit: every affected caller and reference,
**the test files and QA test cases that must be re-run**, and architecture context.
`trace_call_flow` walks a request end to end, from endpoint through every hop to where the work
lands — or backwards from a function to everything that reaches it.
`analyze_dependencies` gives both directions of coupling and import cycles. `find_references`
finds every mention, not just calls. `find_path` answers whether A reaches B at all.

### "What do I have to re-run?"
`get_related_test_cases` maps a code symbol to the QA scenarios already attached to it, so
regression scope is a lookup rather than a guess. `coverage_explore` enters the graph from a
non-symbol node — a TestCase or a requirement — and walks out to the code it touches.

### Asynchronous boundaries and ordering — where call-graph tools give confidently wrong answers
`async_edges` finds where work hands off to another thread or queue. `eb_order` answers whether
event A is ordered before event B. A synchronous call-graph cannot see past a `post()`, so
race/deadlock/ordering questions asked of `trace_call_flow` return "no callers" — a false
negative. These two tools exist because that failure mode is silent.

### Agent memory — three tiers
`kg_remember` / `kg_recall` persist and retrieve *claims* across sessions, with durability chosen
per claim: **short** (ephemeral LRU) · **long** (durable) · **reasoning** (derived).
`kg_semantic_search` searches that memory by embedding. `memory_stats` exposes the working
hierarchy — **L1 hot prompt-resident** and **L2 session-scoped** — as tokens, entries, hits,
misses and evictions. Knowledge is kept in two deliberately separate layers: conversation-mined
claims, and human-curated domain pages.

### Domain vocabulary
`kg_ontology_rag` · `get_domain_knowledge` · `find_related_domain_terms` connect code symbols to
the product's domain terms, so a query phrased in business language reaches the right code.

### Data model in the same graph
`search_database_tables` · `get_table_schema` ingest MariaDB/MSSQL schemas alongside code, which
is what makes a cross-domain question — "which code writes this column" — answerable at all.

### Symbol-aware editing
`replace_symbol_body` · `insert_after_symbol` · `insert_before_symbol` · `replace_lines` ·
`create_file` — edits addressed by *symbol*, resolved through the graph, rather than by line
offset guessed from a file read.

### Cost-aware operation
`session_start` opens a token-budgeted session and signals at 30 / 70 / 90 % of budget.
**Only 12 of the 80 tools are exposed by default**; the rest are reachable through
`tool_search` → `invoke_tool`. That tiering is deliberate, and it was measured: trimming the
exposed set from 22 tools to 12 cut tool-schema tokens **10,494 → 2,016 (−81 %)** and *raised*
tool-selection accuracy by **+10 pp** (bootstrap CI [+3, +17]; 100 matched pairs). `get_health` / `get_metrics` /
`get_embedding_stats` cover observability.

### Escape hatch
`text_to_cypher` and `execute_cypher` for questions the typed tools do not cover.

---

## 4. How well it works

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

## 5. How it was measured

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

## 6. What did not work

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

## 7. Correction notice

On 2026-08-09/10 the headline figures were **retracted in error** and replaced with
0.209 / 0.330 / 0.495. That retraction was **withdrawn on 2026-08-10**; the original figures were
correct.

Cause: the retraction read the legacy `fn_top1` field stored in the run JSON files — scored
against the superseded, contaminated `gold v1`. Re-scoring the raw predictions against `gold v2`
returns 0.737 / 0.869 / 0.939.

Both the error and its withdrawal are kept in
[`BENCHMARKS.md`](BENCHMARKS.md#correction-log) rather than deleted.


### A failure this project found in itself

While preparing this repository, the run JSON's stored `fn_top1` field was read as the final
score. On that basis the headline figures were declared wrong and **a retraction was published
here** — twice, the second time escalating to a claim of "21× overstatement".

The original figures were correct. `fn_top1` is scored against the superseded, contaminated
`gold v1`.

The part worth recording is not the mistake but where the answer was. **Both the correct numbers
and an explicit warning — "ignore the kg_t1 field" — had been sitting in this project's own
knowledge graph as a stored claim for five weeks.** The knowledge was in the system. It was not
retrieved, because retrieval was a thing someone had to remember to do.

The retraction was withdrawn and both the error and its withdrawal were kept in the
[correction log](BENCHMARKS.md#correction-log) rather than deleted. The root cause was treated
as architectural rather than behavioural: a memory that only works when you remember to query it
does not work. Relevant claims are now injected into every request automatically, and each
session's conclusions are captured back as claims when it ends.

**Searchable memory and memory that actually gets searched are different things.** That
difference cost three days, and it is the strongest argument this project has for building the
retrieval into the pipeline rather than leaving it to discipline.

---

## What's in this repository

| File | Contents |
| --- | --- |
| [`BENCHMARKS.md`](BENCHMARKS.md) | Scoring rules, measured numbers, correction log |
| [`EXPERIMENTS.md`](EXPERIMENTS.md) | Each campaign: what it varied, what it concluded — including the null results |
| [`CONTEXT-COST.md`](CONTEXT-COST.md) | What answering "where is this?" costs with no index vs an LSP vs the graph — 3 arms, one question |
| [`data/localization-runs.csv`](data/localization-runs.csv) | 133 scored streams: fn/file top-k, scored instance counts |
| [`data/fresh-2026-judges.csv`](data/fresh-2026-judges.csv) | 13 judge configurations on post-cutoff Django PRs: top-k, latency, cost |
| [`data/context-cost-2026-08-11.csv`](data/context-cost-2026-08-11.csv) | Raw values behind `CONTEXT-COST.md` |
| [`scripts/measure_context_cost.py`](scripts/measure_context_cost.py) | Reproduces the listing and grep arms on any git repository |

## Why the engine is not here

CodeGrove is a private project under commercial evaluation. What makes a benchmark claim
falsifiable is the **method plus the complete run data**, and both are here — including the gold-
label derivation rule, so a third party can reimplement the scoring. Publishing the engine is not
required for that, and is not reversible.

## Honest limits

- Scores move with the judge model and its effort setting; `cm99` spans 0.232 – 0.849. A number
  without its configuration is not meaningful.
- `cm99` is a 99-instance Django subset, not full SWE-bench.
- **On a 20-instance slice of this benchmark, a frontier model with plain `Read`/`Grep`/`Glob`
  and no index scored higher than the pipeline — 0.80 against 0.50.** Same gold set, same
  instances, same rule. At n=20 one instance is 5 pp, so that gap is six instances; treat the
  direction as real and the magnitude as unresolved. Django is also small, public and
  well-structured — the regime where a code graph adds least, and not the large private
  cross-language codebases the graph exists for. Published rather than omitted:
  [`EXPERIMENTS.md`](EXPERIMENTS.md#campaign-6--the-unflattering-comparison).
- A separate fresh-data run scored the frontier model at 0.75, which rules out memorisation as
  its explanation. **That run has no pipeline counterpart** — re-indexing was a blocker — so it
  is a memorisation control, not a second comparison.
- Treat these as a characterization of one pipeline at one point in time, not a leaderboard score.

---

*Data and documents may be quoted with attribution.*
