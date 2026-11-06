# materia — validation status

**As of 2026-11-06.** This page separates what has been measured from what has not. Read it
before quoting any percentage.

## What is measured

| layer | n | result | 95% CI | what it actually means |
|---|---:|---:|---|---|
| Unit / contract tests | 164 | 164 pass | — | Code paths, citations, doses, safety gates, web routes, review import. |
| Recommendation contract | 73 | 73/73 | 95.0–100.0 | Expected pattern, top option, withheld set, flags, gaps, severity and citations on a **self-authored synthetic set**. |
| Single-turn chat, deterministic | 29 | 29/29 | 88.3–100.0 | Fallback answers contain the required phrase, no forbidden phrase, and cite the assessment. |
| Single-turn chat, MiniCPM5-2B Q8, CPU | 29 | 29/29 | 88.3–100.0 | 27 model answers, 2 rejected. |
| Single-turn chat, MiniCPM5-2B Q4, CPU | 29 | 29/29 | 88.3–100.0 | 23 model answers, 1 deterministic answer, 5 rejected. |
| Multi-turn chat, deterministic | 17 | 17/17 | 81.6–100.0 | Follow-up turns carry bounded history and preserve the contract. |
| Multi-turn chat, Q8, CPU | 17 | 17/17 | 81.6–100.0 | 15 of 17 turns used the model, 2 rejected. |
| Multi-turn chat, Q4, CPU | 17 | 17/17 | 81.6–100.0 | 12 of 17 turns used the model, 5 rejected. |
| Rule audit | 24 patterns / 31 options / 9 critical values | 0 issues | — | Every rule citation resolves; no dose or note is unsupported; no evidence older than 5 years. |

All intervals are Wilson 95% intervals. The contract set is **not** a random sample of patients
and was written by the same project that wrote the engine. It is a regression suite, not a
clinical accuracy estimate.

All chat measurements are **CPU-only** (`llama.cpp`, no GPU, no vLLM, no cloud).

## What is not measured

| gap | current state |
|---|---|
| Clinician agreement | **0 of 50 review cases labelled.** The packet, web mode, CLI and CSV import are ready. |
| External patient data | None. No real patient records have been run. |
| Larger CPU model | A 3B–7B CPU model has not been measured. Q4 and Q8 2B are the measured models. |
| Amino-acid interpretation | No defensible open evidence in the corpus; the sample panel returns a coverage gap. |
| Paediatric 1–12 critical values | Adult limits are used with an explicit age note; no validated paediatric thresholds. |
| Fine-tuning | Not performed. The binding constraints are labels and evidence coverage. |

## How the contract set is built

- `data/clinical_vignettes.json` — 72 cases, of which 50 are in the clinician review subset
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

For a CPU model endpoint:

```bash
export MATERIA_CHAT_BASE_URL=http://127.0.0.1:8099/v1
export MATERIA_CHAT_MODEL=minicpm5-2b-q4

.venv/bin/python scripts/eval_chat.py --out results/chat_q4.json
.venv/bin/python scripts/eval_chat_multiturn.py --out results/chat_multiturn_q4.json
```

## Claim policy

Say **“73/73 contract checks”**, not **“100% accurate”**. Say **“29/29 grounded-chat contract”**,
not **“the model answers every question correctly”**. The clinician label stream is the first
number that can support an accuracy claim; it does not exist yet.
