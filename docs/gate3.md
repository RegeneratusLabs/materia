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
