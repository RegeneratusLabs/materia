# Gate 1 — PubMedQA: can it read a paper and answer from it?

**Run:** 2026-10-28 · **Model:** `MiniCPM5-2B-Q8_0` · CPU · sample of 200, seed 20261028
**Artifact:** `results/pubmedqa_200.jsonl`, `results/pubmedqa_200.summary.json`

## Verdict

**Fail.** 100/200 = **50.0% [43.1, 56.9]**, against a gate of ≥70%. The majority-class baseline for
this sample is 49.5% (99 YES / 68 NO / 33 MAYBE), so the score is **indistinguishable from answering
"yes" every time**.

The breakdown is what matters:

| Gold | n | Correct | Rate |
|---|---|---|---|
| YES | 99 | 67 | 68% |
| NO | 68 | 24 | 35% |
| MAYBE | 33 | 9 | 27% |

It recognises an affirmative finding reasonably well and cannot say no or maybe. That is not reading
comprehension, it is a prior with a yes-shaped hole in it.

## Deviation from the planned condition, stated plainly

The plan specified the 60-word reasoning budget. That configuration was **abandoned after three items**:
with a ~1,500-token abstract plus deliberation it ran at ~2.5 minutes per item, i.e. ~2 hours for n=200
on this host. The run above therefore uses **direct answers** (`enable_thinking: false`, 2 output tokens
mean). That is a different condition and is labelled as such. A 40-item thinking subset is the fair test
and is listed as follow-up, not as a result.

## What this means

1. **The closed-book strength does not transfer to document reading.** The same model scores 98.1% on
   the herb/lab panel from its weights and cannot read a paper at better than chance. Those are different
   capabilities, and the project depends on the second one.
2. **It argues against "paste the whole paper in" retrieval.** Long, dense context is where this model
   fails. The Gate 3 design — short, labelled, claim-level chunks with citation ids — is the right shape,
   even though Gate 3 did not yet show a net win.
3. **It caps one-shot reading expectations.** Per the plan's fallback: the retrieval design is unchanged,
   but we should not build a "summarise this guideline" feature on this model without deliberation, and
   deliberation is currently too slow to be interactive.

## Known limitations

- Direct answering, not the planned reasoning budget (see above).
- Abstracts truncated at 6,000 characters; a few PubMedQA abstracts are longer.
- `MAYBE` is the minority class and the model over-uses it (64 predicted vs 33 actual), which is at least
  a sign it is not blindly copying the majority label — but it is not calibration we can use.
- No medical-QA domain prompt, deliberately: the project's rule is one earned instruction, not scaffolding
  per benchmark.

## Reproduce

```bash
.venv/bin/python scripts/pubmedqa.py --n 200 --no-think --max-tokens 64
```
