# materia — validation status

**As of 2026-10-31.** This page separates what has been measured from what has not. Read it
before quoting any percentage.

## What is measured

| layer | n | result | 95% CI | what it actually means |
|---|---:|---:|---|---|
| Unit / contract tests | 155 | 155 pass | — | Code paths, citations, doses, safety gates, web routes, review import. |
| Recommendation contract | 70 | 70/70 | 94.8–100.0 | The engine returns the expected pattern, top option, withheld set, flags, gaps, severity and citations on a **self-authored synthetic set**. |
| Single-turn chat, deterministic | 26 | 28/28 | 87.1–100.0 | The fallback answers contain the required phrase, no forbidden phrase, and cite the assessment. |
| Single-turn chat, local MiniCPM5-2B | 26 | 28/28 | 87.1–100.0 | Same contract; 24 answers used the model, 2 were rejected to the fallback. |
| Multi-turn chat, deterministic | 17 | 17/17 | 81.6–100.0 | Follow-up turns carry bounded history and preserve the contract. |
| Multi-turn chat, local MiniCPM5-2B | 17 | 17/17 | 81.6–100.0 | 15 of 17 turns used the model, 2 were rejected to the fallback. |
| Rule audit | 23 patterns / 30 options / 9 critical values | 0 issues | — | Every rule citation resolves; no dose or note is unsupported; no evidence older than 5 years. |

All intervals are Wilson 95% intervals. The contract set is **not** a random sample of patients
and was written by the same project that wrote the engine. It is a regression suite, not a
clinical accuracy estimate.

## What is not measured

| gap | current state |
|---|---|
| Clinician agreement | **0 of 48 review cases labelled.** The packet, web mode, CLI and CSV import are ready. |
| External patient data | None. No real patient records have been run. |
| 14B / 32B chat model | Not run. The 2B is the only measured model. |
| Amino-acid interpretation | No defensible open evidence in the corpus; the sample panel returns a coverage gap. |
| Paediatric 1–12 critical values | Adult limits are used with an explicit age note; no validated paediatric thresholds. |
| Fine-tuning | Not performed. The binding constraints are labels and evidence coverage. |

## How the contract set is built

- `data/clinical_vignettes.json` — 70 cases, of which 48 are in the clinician review subset
  (`review: true`) and 22 are boundary/negative regression cases.
- Each case declares the expected patterns, top option, withheld options, safety flags, coverage
  gaps, severity, critical alerts and citation integrity.
- A case fails if any of those checks fails. The top-option check is agreement with the case
  author, not with a clinician.

## Reproduce

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/eval_recommend.py
.venv/bin/python scripts/eval_chat.py --no-model
.venv/bin/python scripts/eval_chat_multiturn.py --no-model
.venv/bin/python scripts/audit_rules.py
```

For a model endpoint:

```bash
.venv/bin/python scripts/eval_chat.py --base-url http://127.0.0.1:8000/v1 \
  --model Qwen/Qwen2.5-14B-Instruct --out results/chat_14b.json
.venv/bin/python scripts/eval_chat_multiturn.py --base-url http://127.0.0.1:8000/v1 \
  --model Qwen/Qwen2.5-14B-Instruct --out results/chat_multiturn_14b.json
```

## Claim policy

Say **“70/70 contract checks”**, not **“100% accurate”**. Say **“28/28 grounded-chat contract”**,
not **“the model answers every question correctly”**. The clinician label stream is the first
number that can support an accuracy claim; it does not exist yet.
