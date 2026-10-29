# Gate 3 — does retrieval help, hold, or hurt?

**Run:** 2026-10-28 · **Model:** `MiniCPM5-2B-Q8_0` · CPU, 6 threads · `-c 8192 -np 2`
**Artifacts:** `results/panel_closed_nothink.jsonl`, `results/panel_retrieval_nothink.jsonl`, `results/gate3.json`

## Verdict

**Fail as specified.** Retrieval as configured does not hold the 95.2% baseline. On the like-for-like
(no-think) comparison it moves the panel from **90/104 (86.5%) to 86/104 (82.7%)** — a **-3.8 point**
change, 5 items fixed, 9 broken, McNemar p = 0.424 (not significant at n=104).

Two things did work, and they are the ones that were expensive to build:

- **Citation discipline is perfect.** 96/104 answers carried a citation; **127/127 cited S-ids were
  actually in the model's context**. Zero invented sources. The plumbing does what it claims.
- **Lab retrieval helps:** lab items went **20/30 → 24/30 (+4)**. That is the branch the corpus was
  built for first, and it responded.

The damage is all in herbs: herb–safety **19/20 → 16/20 (-3)**, herb–drug **25/26 → 23/26 (-2)**,
nutrient–drug **10/12 → 7/12 (-3)**.

## Conditions

| Condition | n | Score | Answered | Notes |
|---|---|---|---|---|
| Closed-book, thinking, 60-word budget, max_tokens 768 | 104 | **102/104 = 98.1% [93.3, 99.5]** | 102 | the clean baseline; 2 capped, 0 wrong |
| Closed-book, no thinking, max_tokens 64 | 104 | **90/104 = 86.5% [78.7, 91.8]** | 104 | 2 tokens mean, 2.2 min |
| Retrieval, no thinking, k=5, 90-word evidence | 104 | **86/104 = 82.7% [74.3, 88.8]** | 104 | 100% of citations in context |
| Retrieval, thinking, 60-word budget | 2 | **abandoned** | 0 | model never emits the answer: 2/2 hit the 768 cap, 96 s/item |

The last row is a finding, not a failure to run the experiment. When the 2B model is asked to both
deliberate and cite inside one budget, it spirals: the reasoning traces show it re-reading S1–S6 and
never concluding. With thinking disabled it answers in 11 tokens. Any future retrieval design for this
model has to pick one: evidence + immediate answer, or evidence + a much larger generation budget.

## By category (closed-book → retrieval, no-think)

| Category | n | Closed | Retrieval | Δ |
|---|---|---|---|---|
| lab | 30 | 20 | **24** | **+4** |
| herb–drug | 26 | 25 | 23 | −2 |
| herb–safety | 20 | 19 | 16 | −3 |
| nutrient–drug | 12 | 10 | 7 | −3 |
| referral | 8 | 8 | 8 | 0 |
| safety | 6 | 6 | 6 | 0 |

The pattern is coherent: when the question names an analyte and the corpus has a matching lab statement,
retrieval adds signal. When the question needs a safety judgement across a herb, the retrieved chunks
pull the model off a correct prior. Item-level notes in `results/gate3.json` (`fixed_ids`, `broke_ids`).

## Why it hurt, honestly

1. **Coverage is 29.8% by lexical grounding** (`docs/corpus.md`). For roughly two-thirds of the panel
   the retrieved evidence is not answering the question — it is adjacent text that reads authoritatively.
2. **A 2B model over-anchors.** Given a plausible-sounding contraindication chunk it will follow it over
   its own correct recall. The closed-book prior was already strong on this panel; evidence has to be
   *better* than the prior to help, and mostly it is not.
3. **Ranking is lexical.** BM25 with section and entity bonuses finds the right herb but not always the
   right claim; there is no reranker and no claim-level matching.
4. **The corpus is Canada-only for monographs.** For herb–drug questions the EU monograph set (deferred,
   see `docs/corpus.md`) is the one that would have carried the specific interaction statements.

## What this changes

- **Do not ship retrieval as the default path yet.** Closed-book + 60-word budget is still the better
  engine for herb questions; retrieval earns its place only on the lab branch.
- **The next experiment is category-gated retrieval**, not more documents: keep retrieval for lab items,
  closed-book elsewhere, and measure. That is a 30-minute run on the existing harness.
- **The prompt finding is reusable:** evidence + citation + thinking does not fit a 60-word budget on a
  2B model. Either raise the budget and accept latency, or answer immediately.
- **The corpus needs the EU set and a reranker** before a second full Gate 3 attempt; neither is a reason
  to widen the corpus blindly.

## Reproduce

```bash
.venv/bin/python scripts/run_panel.py --condition closed    --no-think --max-tokens 64 \
  --out results/panel_closed_nothink.jsonl
.venv/bin/python scripts/run_panel.py --condition retrieval --no-think --evidence-words 90 \
  --max-tokens 64 --out results/panel_retrieval_nothink.jsonl
.venv/bin/python scripts/gate3.py --baseline results/panel_closed_nothink.jsonl \
  --retrieval results/panel_retrieval_nothink.jsonl
```

## Artifact note

The Gate 3 run used the index as built at 16:57, which still contained 131 NCCIH "Key References"
chunks that were removed from the corpus afterwards (a heading-classifier fix: reference lists were being
tagged as clinical content). The cleaned index has 3,527 chunks. The stale chunks were low-signal
bibliographies, so the direction of the result is unlikely to change, but a re-run on the cleaned index
is the honest next step before quoting these numbers as final.

## Fallback result — category-gated retrieval (added after the gate failed)

The plan's failure protocol says: cut the corpus/retrieval to the failing categories, retune, re-test. The
`lab` branch was the only positive signal, so the fallback is mechanical: retrieve only for lab items,
closed-book for everything else. `--condition hybrid` implements it and preserves the same no-think
condition as the paired baseline.

| Condition | n | Score | Δ vs closed | Fixed | Broke | McNemar p |
|---|---|---|---|---|---|---|
| Closed-book, no thinking | 104 | 90/104 = 86.5% [78.7, 91.8] | — | — | — | — |
| Retrieval, all categories | 104 | 86/104 = 82.7% [74.3, 88.8] | −3.8 | 5 | 9 | 0.424 |
| **Retrieval, lab categories only** | 104 | **93/104 = 89.4% [82.0, 94.0]** | **+2.9** | 5 | 2 | 0.453 |

Only lab items changed (20/30 → 23/30, +3); every other category is identical by construction. Citations:
37/37 in context, 27/104 answers cited (only the lab items had evidence to cite).

**This is the configuration to carry forward**, with the honest caveat that +3 points at n=104 is not
statistical significance (p = 0.45). It is a direction supported by the per-category data, not a proven
effect, and it does not close the gap to the 98.1% thinking baseline.

Artifact: `results/gate3_hybrid.json`.

## Abstention test

Ten questions deliberately outside the corpus (prescription dosing for ivermectin, apixaban, levothyroxine,
chemo, amoxicillin, insulin, sertraline, prednisolone, methotrexate, melatonin jet lag).

**9/10 abstained with `ANSWER: NO_EVIDENCE. SOURCE: NONE.`** — the gate is ≥90%. The one non-abstention
(AB10, melatonin for jet lag) is arguably not out-of-corpus at all: melatonin monographs are in the corpus
and the retrieved chunks address jet lag, so the answer was cited evidence rather than a guess. Nine of the
nine genuinely absent questions abstained.

Artifact: `results/gate3_abstention.json`. This is the strongest behavioural result of the day: the model
does not guess when the evidence is missing, which is the one failure the product cannot survive.

---

## Experiment 4 — coverage-gated routing (2026-10-29)

Corpus grew to 330 documents (EMA 21, CC-BY 16 after curation), retrieval was rewritten (normalised
entity matching, entity documents first, claim-type chunks injected, safety intent beating dose intent),
and `grounded_chunks()` became the single coverage definition: entity document **and** claim type
**and** at least one non-generic question term in the chunk.

**Coverage: 20/104 = 19.2%** (herb–drug 42%, herb–safety 25%, lab 0%, referral 0%).

I audited every covered item by hand (`data/panel_coverage_audit.json`): **6 supported, 5 clearly
unsupported, 9 unverifiable from the snippet.** A fish-oil *indications* chunk was labelled as covering a
warfarin-bleeding question; a licorice *dosage* chunk as covering a mineralocorticoid question. Mechanical
coverage is a routing hint, not evidence of support — precision is around 50% at best.

Routing on that signal:

| Condition | n | Score | Δ vs closed | Fixed | Broke | p |
|---|---|---|---|---|---|---|
| Closed-book, no thinking | 104 | 90/104 = 86.5% [78.7, 91.8] | — | — | — | — |
| Category-gated (lab only) | 104 | 93/104 = 89.4% [82.0, 94.0] | +2.9 | 5 | 2 | 0.45 |
| **Coverage-routed** | 104 | **87/104 = 83.7% [75.4, 89.5]** | **−2.8** | 0 | 3 | — |

The decomposition is the whole story. On the **17 items the router sent to evidence**, closed-book scored
**16/17** and routed scored **13/17** — evidence fixed **zero** and broke **three** (E07 yohimbe, E26
ginkgo, H11 ashwagandha). On the 87 memory-routed items the two conditions are identical by construction.

**Conclusion: on herb questions, this model's memory is better than this corpus.** Injection cannot help
while the evidence is weaker than the prior, and coverage flags are not accurate enough to route on. The
lab-only hybrid remains the best configuration (93/104), because lab questions benefit and herb questions
are left alone.

What this changes:

1. **Retrieval stays lab-only** in any shipped path until the herb corpus can beat a 98.1% prior.
2. **The route must be decided after seeing the answer**, not before: generate, verify the claim against
   the chunk, and fall back to a labelled memory answer when verification fails (`materia/verify.py`).
   That is the next experiment, not coverage gating.
3. **Corpus quality, not quantity.** The herb branch needs the EU monographs that were missing from the
   sitemap (hypericum, panax, withania, piper, cimicifuga, rhodiola) and a reranker, before another
   retrieval gate.

---

## Experiment 5 — evidence + deliberation, isolated (2026-10-29)

Yesterday's readings showed that retrieval with thinking never produced answers. Two controls were run on
the same 20 items (H01–H20) to find out whether the evidence or the citation obligation was the trigger.

| Condition | Score (n=20) | Capped |
|---|---|---|
| Closed-book, thinking | **20/20** | 0 |
| Closed-book, no thinking | **20/20** | 0 |
| Evidence (3 chunks, 40 words) + thinking + cite | **4/20** | 14 |
| Evidence (3 chunks, 40 words) + thinking, no cite | **11/20** | 11 |

The results are unambiguous: **with reasoning enabled, the presence of evidence in the context is itself
the failure**, not the citation instruction. The model fills its budget deliberating over passages and
never emits an answer. Dropping the citation requirement halves the damage but does not fix it.

Design consequence, now settled rather than suspected: **any evidence-in-prompt path must run with thinking
disabled.** Deliberation is for closed-book answering and for short prompts where the model has a chance to
finish. This is why every retrieval number in this project is a no-think number, and why they must be
compared to a no-think closed-book baseline (86.5%), never to the 98.1% thinking baseline.

Artifacts: `results/tmp/ret_thinking_lean20.jsonl`, `results/tmp/ret_thinking_nocite20.jsonl`.

## Experiment 6 — the precision package (2026-10-29)

Three fixes aimed at evidence quality rather than quantity: entity documents first (already in), a
boilerplate filter that removes chunks like the NCCIH clearinghouse blurb, and a leaner evidence block
(k=3, 60 words) instead of six long chunks.

Lab-only retrieval, re-run with the package:

| Condition | n | Score | Δ vs closed | Fixed | Broke | p |
|---|---|---|---|---|---|---|
| Closed-book, no thinking | 104 | 90/104 = 86.5% [78.7, 91.8] | — | — | — | — |
| Lab-only, original settings | 104 | 93/104 = 89.4% [82.0, 94.0] | +2.9 | 5 | 2 | 0.45 |
| **Lab-only, precision package** | 104 | **94/104 = 90.4% [83.2, 94.7]** | **+3.8** | **5** | **1** | **0.22** |

This is the best panel result under any single configuration, and the first time retrieval is a net positive
with no collateral damage: only lab items moved (20/30 → 24/30), every other category is identical by
construction. Citations: 38/38 in context. It is still not statistically significant at n=104 (p = 0.22),
and it runs in 5.6 minutes rather than 35 — the leaner evidence block is most of that speed.

Artifact: `results/gate3_hybrid_v2.json`, `results/panel_hybrid_v2.jsonl`.

### Full retrieval with the same package

For completeness, all categories retrieved with k=3/60-word evidence and the boilerplate filter:
**89/104 = 85.6% [77.6, 91.1]**, fixed 5, broke 6, delta −1.0, p = 1.0. Lab +4, herb–safety −4,
nutrient–drug −1. The precision package lifted full retrieval from 82.7% to 85.6% and nearly closed the
gap, but herb–safety still loses more than lab gains.

So the ordering is stable across three independent runs: **lab-only 94 > closed 90 > full retrieval 89**.
Gating by category remains the correct configuration until the herb corpus can beat the prior.
Artifact: `results/gate3_retrieval_v2.json`.

## Experiment 7 — model-based reranker: rejected (2026-10-29)

A pointwise reranker (`materia/rerank.py`) scored each of 8 candidates with the local model — "does this
passage help answer the question? YES/NO", thinking off, one token, disk-cached — then kept the top 3.
Measured against a matched control on the same corpus and code:

| Condition | n | Score | Time |
|---|---|---|---|
| Lab-only retrieval, no reranker | 104 | **94/104 = 90.4% [83.2, 94.7]** | 5.4 min |
| Lab-only retrieval, model reranker | 104 | 93/104 = 89.4% [82.0, 94.0] | 8.3 min |

**Rejected: it costs one item and 50% more wall clock.** The likely reason is that a 2B model's yes/no
judgement over a 70-word passage is barely better than the retrieval ordering it is second-guessing, and
its errors are not symmetric — dropping a good chunk costs an answer, keeping a bad one usually does not.

The useful reranking turned out to be deterministic and cheap: entity-document restriction, claim-type
injection, section priors and the boilerplate filter. Those are kept; the model pass is not. `rerank.py`
stays in the tree with this result recorded so it is not re-invented.

Artifacts: `results/panel_hybrid_v3.jsonl` (control), `results/panel_hybrid_rerank2.jsonl`.
