# Experiments — what was tested and what it showed

The experiment log behind [`BENCHMARKS.md`](BENCHMARKS.md). It records **what each campaign
varied**, **what it measured**, and **what it concluded** — including the campaigns that found
nothing, which are the ones usually deleted.

- **Measurement window.** 2026-05-18 → 2026-07-01.
- **Streams.** 133 scored streams at n ≥ 30, re-scored against frozen `gold v2`.
- **Raw data.** [`data/localization-runs.csv`](data/localization-runs.csv).

Campaigns were **pre-registered**: hypothesis, metric and decision rule written down before the
cell ran, with a standing rule that every executed cell gets reported — no drawer.

---

## Campaign 0 — The gold set was wrong, and everything downstream moved

**Finding.** An audit of the original gold set (`v1`) found it contaminated in **37 of 41**
audited instances: gold functions resolved against post-patch source rather than the base
commit. `gold v2` was rebuilt (changed lines → enclosing function **at base commit** → FQN),
audited at 10/10 and 12/12 on two independent samples, and frozen by SHA-256.

**Consequence.** Every stream was re-scored. The shift is not marginal — on the reference run,
function-level top-1 moves **0.209 → 0.737**. Run JSON files still carry the legacy v1-scored
field; it is kept for diffing and is not a result.

**Why this campaign is listed first.** A benchmark's gold set is a dependency like any other,
and a silent change to it invalidates every stored number. This is also exactly the trap that
produced the [withdrawn retraction](BENCHMARKS.md#correction-log) in August.

## Campaign 1 — Where the ceiling actually is

Oracle analysis separates *retrieval* failure from *selection* failure.

| Measure | Value | Reading |
| --- | ---: | --- |
| gold present in the judge's candidate pool | 0.824 – 0.833 | retrieval mostly succeeds |
| function-level top-1 | 0.58 – 0.67 *(full-114)* | selection loses 17–25 pp of it |
| pool-union top-10 across 9 variants | 0.892 | recall headroom is real |
| oracle selector on that pool | 0.804 | a perfect selector would recover ~12 pp more |

**Conclusion.** The binding constraint is **selection, not recall** — specifically
discrimination among structural siblings inside an already-correct file. A failure taxonomy on
43 misses put discrimination-type failures at **53.5 %** against recall-type at 41.9 %.

## Campaign 2 — Six attempts on the selection bottleneck, all null

Every intervention below was pre-registered with a go/no-go rule. None passed.

| # | Intervention | Result |
| --- | --- | --- |
| 1 | **Judge temperature = 0** | Accuracy **unchanged** (0.5752 both, paired Δ −0.00 pp, CI [−2.61, +2.61]) |
| 2 | **Call-direction relations injected into the judge** | Decisive **NO-GO**. Named-case net transfer **+0** (b0), **−1** (b1). Relations reached 26–36 of 40 candidates and the judge demonstrably saw them |
| 3 | **Value-provenance re-ranking** (body-token overlap) | NO-GO. 1–3 of 11 separated; negative control ~1/23. Siblings share the issue's vocabulary, so token overlap cannot separate them |
| 4 | **Cross-variant agreement selector** | Recall GO, selection NO-GO. Agreement selector 0.6765 vs single-best 0.6667 (+0.98 pp) — variants converge on the *same wrong sibling* when they fail |
| 5 | **Dataflow produce-vs-consume separability** | Strongest signal of the four (3/11, negative control a clean 0/23) but under the 6/11 gate. Kept as a last +3 pp candidate |
| 6 | **Removing issue truncation** (1500 → 8000 chars) | Net **+0**. One case recovered, one lost to added distraction. The worst case — where the judge had seen only 31 % of the issue — stayed wrong on the full text |

**Conclusion.** Six independent levers, all null within noise. The measured reading is that the
judge's ranking prior is **intrinsic to the model, not promptable**: the information is in the
prompt and the judge does not use it for sibling discrimination. Budget was redirected from
judge-prompting to recall/pool-union work.

## Campaign 3 — The non-determinism that was hiding every result

A fidelity gate built to validate the A/B replay harness exposed something more fundamental:
the judge was **22.8 % non-deterministic** run-to-run (77.2 % top-1 agreement, full-114).

Root cause: temperature was never pinned, so the judge ran at the provider default (~1.0).
Setting `temperature=0` raised agreement to **91.3 %** on the hard subset (+21.7 pp).

**This retroactively explains the preceding day's null results** — the noise floor was
swallowing the effect sizes. But when the interventions were re-run *at* temperature 0 they
were **still null**, which is what makes the Campaign 2 conclusion trustworthy rather than an
artefact. Temperature control is a statistical-power lever, not a quality lever; even at 0, the
judge retained 15.5 % residual non-determinism.

## Campaign 4 — Re-ranking helps recall and does nothing for top-1

A candidate-budget census over 9 variants, RRF-fused:

- Re-ranking contributes **+10.8 pp to recall@10** (stage-3 order 0.696 → re-ranked 0.804).
- The same re-ranking moves **top-1 not at all**.
- recall@10 saturates at ~0.80 regardless of variant; union across variants only helps at
  K ≥ 15 (+1 pp at 15, +2.9 pp at 40).

**Conclusion.** Recall is healthy and saturated; further gains need retrieval-level change
(embeddings/search), not more re-ranking or more variants.

## Campaign 5 — Is the model reasoning, or has it memorised Django?

SWE-bench Django is public and old enough to be in training data, so a contamination A/B was
run: a fresh-2026 Django issue set against the contaminated public set, difference-in-differences
between a strong and a weak judge.

- **First attempt was invalid** and is reported as such: the candidate pool was built from the
  gold file's functions, which handed file-localization to the model for free, and the
  designated "strong" model turned out weaker than the baseline.
- **Corrected attempt**: strong-model selection **did not collapse** on fresh data
  (0.767 contaminated → 0.793 fresh), while the weak model gained. Δgap +9.8 pp, marginally
  under the 10 pp memorisation gate.

**Conclusion — real reasoning, borderline.** The earlier read that "selection is exhausted" was
a property of the weak judge, not of the task.

**The stronger test came later.** Rather than a difference-in-differences on a synthetic pool,
the full pipeline was re-run end-to-end on **`fresh-2026`** — 29 Django pull requests merged
after the judges' training cutoffs — across 13 judge configurations
([`data/fresh-2026-judges.csv`](data/fresh-2026-judges.csv), through 2026-07-09).

Function-level top-1 there spans **0.724 – 0.828**, against `cm99`'s 0.727 – 0.849. Same band.
Whatever the pipeline is doing, it is not recall of memorised Django. n=29 makes one instance
worth 3.4 pp, so this rules out memorisation as the *dominant* explanation rather than
resolving judge-to-judge differences.

**The cost finding is the actionable one.** `grok-4.5` at `effort=high` reaches 0.759 in a
**2.5 s** median at **$0.015**/instance; `Kimi-K2.7-Code` reaches 0.828 at 64 s and twice the
price — 7 pp of accuracy for a **26×** latency difference. Combined with the `cm99` result that
the top configurations are statistically indistinguishable (McNemar p = 0.607, bootstrap CI
spanning zero), the operational conclusion is that **the judge should be selected on cost and
latency, not on top-1**.

## Campaign 6 — The unflattering comparison

A frontier model given only `Read`/`Grep`/`Glob` on a Django checkout — no graph, no index —
was scored on the same instances as the CodeGrove pipeline.

| | Hit@1 |
| --- | ---: |
| Frontier model, direct repository exploration | **0.80** (contaminated) / **0.75** (fresh) |
| CodeGrove pipeline, same instances | **0.50** |

The fresh run rules out memorisation as the explanation (0.80 → 0.75 only), so the gap is real
on this benchmark.

**Three confounds, stated because they bound the claim rather than excuse it:** the frontier
model was far stronger than the pipeline's judge (swapping it in gives the pipeline +6.9 pp);
direct exploration was **~16× slower**; and Django is a small, public, well-structured
repository where grep is close to sufficient — which is precisely the regime where a code
knowledge graph adds least. The benchmark does not measure the large, private, cross-language
codebases the graph exists for.

Publishing this is deliberate. It is the strongest available argument *against* the system, and
the honest reading is that on public-Python-monorepo localization a strong agent with grep is
competitive.

---

## What the campaigns collectively show

1. **Function-level top-1 ≈ 0.74** on the reference cm99 run, 0.727–0.849 across configurations
   (one degraded outlier at 0.232), best measured 0.860.
2. **Retrieval is not the bottleneck** — gold reaches the candidate pool ~82 % of the time.
   Selection loses 17–25 pp of that.
3. **Sibling discrimination resisted six pre-registered interventions**, all null even after
   the non-determinism confound was removed.
4. **A stale gold set moved every number by ~3×.** Re-scoring, not stored fields, is the source
   of truth.
5. **Most tested ideas did not work.** They are recorded here because negative results are what
   justify the current defaults — and because a benchmark page that only lists wins is not a
   benchmark page.
