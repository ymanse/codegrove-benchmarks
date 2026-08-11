# What it costs an agent to find code

Measured 2026-08-11. One question, one repository, three ways of answering it.

The question was **"where is access-group permission validation actually performed?"** — the
ordinary kind of question an agent gets before it can change anything. The target repository is
a private C++ service (~80k graph nodes, the largest single index in this corpus). Paths and
identifiers are omitted; only counts are published.

## The three arms

| | wall time | tool calls | tokens | what came back |
| --- | ---: | ---: | ---: | --- |
| **No index** — agent with grep/glob/read only | **201 s** | 30 | **73,508** | 33 validation sites, exhaustive |
| **LSP** — clangd | **24.9 s** *(per file)* | 1 | 60 | the 6 symbols **of one file you name** |
| **Code graph** — one query | **2.8 s** | 1 | **740** | 5 ranked candidates, correct one included |

Against the no-index arm that is **~72× the wall time and ~99× the tokens**.

### These are not the same answer

This is the honest caveat and it matters more than the ratio. The no-index agent enumerated
**33 validation sites**; the graph returned its **top 5**. One is an exhaustive sweep, the other
is a ranked entry point. What the comparison measures is the cost of *deciding which file to
open first* — not the cost of a complete audit.

Both landed on the same function: `…::checkByGroup`, lines 75–124. So did the LSP.

## What the LSP arm actually showed

The LSP is the interesting arm, because it is the tool most teams already have.

1. **Workspace-wide symbol search returned nothing.** `workspace/symbol` for the type name spent
   ~26 s and produced 0 results, because the repository has no `compile_commands.json` and clangd
   cannot build an index without one. In a polyglot multi-repo setup, standing that up *per
   repository* is itself the cost.
2. **It has to be told which file.** `documentSymbol` takes a file path as input. It cannot
   answer "where does this happen?" — knowing the file is the thing you were trying to find out.
3. **It did not warm up.** First file 24.9 s, second file 33.0 s. Each file is parsed again.
4. **What it returned was exactly right.** When pointed at the right file it gave the correct
   symbol with precise line ranges, at 60 tokens. Precision was never the problem.

So the three tools are not competitors so much as different stages: grep finds strings without
ranking them, an LSP resolves precisely once you know where to look, and the graph is what picks
*where to look* from a natural-language question.

## grep is fast — until the pattern is wrong

grep is not the slow part. A narrow pattern on the same C++ repository:

| grep pattern | wall time | hits | tokens |
| --- | ---: | ---: | ---: |
| narrow (`accessgroup.*permission`) | 573 ms | 62 | 2,237 |
| filenames only (`permission`, `-l`) | 531 ms | 225 files | 3,280 |
| broad (`embedding`, different repo) | **51,991 ms** | 3,818 | **133,401** |

A single badly-scoped grep cost **133k tokens** — more than the entire 30-call agent run. The
agent cannot know in advance how narrow to make the pattern, so it guesses, and a wrong guess is
the expensive case. That variance, not the median, is what a code index removes.

## Cost of the file listing alone

Before opening anything:

| repository | files | tokens | tokens/file |
| --- | ---: | ---: | ---: |
| CodeGrove engine | 1,271 | 13,369 | 10.5 |
| CodeGrove MCP server | 461 | 5,021 | 10.9 |

~10.5 tokens per path. A listing is the cheapest possible orientation step and it already costs
13k tokens on a mid-sized repository.

## Graph query: mode matters

Same query, same `limit`, back to back:

| mode | search | total incl. classifier |
| --- | ---: | ---: |
| `auto` | 5,621 ms | **6,610 ms** |
| `hybrid` | **2,816 ms** | — |

`auto` routes through an LLM classifier (`llm-haiku-v2`, confidence 0.85) which then selects
`hybrid` anyway. The classifier round-trip costs ~1.0 s *inside the same call* (6,610 − 5,621).
Naming the mode skips it.

Response size is bounded by `limit`, not by repository size: **~104 tokens per result plus a
~165-token envelope** — 740 tokens at `limit=5`, ~2,245 projected at `limit=20`.

## Limits of this measurement

State these before quoting the ratios.

- **n = 1 question, n = 1 repository.** No variance estimate. Run-to-run spread on the graph arm
  alone was 2,816 ms vs 5,536 ms for two hybrid calls.
- **Scope differs between arms** (33 sites vs top-5), as above.
- **Token accounting is not symmetric.** The agent's 73,508 is total subagent usage including its
  prompt and reasoning; the graph's 740 is the response payload only.
- **LSP timings include harness round-trip** (est. 2–5 s); the tool reports no latency of its own.
- **grep timings are Windows**, where filesystem traversal is slower than on Linux.
- The graph arm is **not free to build** — it needs parsing and indexing up front. This page
  measures query cost, not amortised total cost.

## Reproducing

[`scripts/measure_context_cost.py`](scripts/measure_context_cost.py) reproduces the file-listing
and grep arms on any git repository:

```bash
python scripts/measure_context_cost.py /path/to/repo --pattern permission
```

The LSP arm is any `documentSymbol` / `workspace/symbol` client. The graph arm requires a running
CodeGrove instance; its `latency_ms` field is the number recorded above.

Raw values: [`data/context-cost-2026-08-11.csv`](data/context-cost-2026-08-11.csv).
