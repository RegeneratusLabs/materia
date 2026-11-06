# materia — CPU chat model runbook

The recommendation engine is deterministic. The conversational layer is optional and runs on
**CPU only**. No GPU, no vLLM, no cloud endpoint is required.

**Rule:** do not lower the citation gate to make a model look better. If a model cannot
answer with a valid chunk citation, it is not ready for the chat surface.

## Current CPU baseline

The measured model is **MiniCPM5-2B** served by `llama.cpp`:

| quant | file size | RAM during chat | role |
|---|---:|---:|---|
| `Q4_K_M` | ~1.5 GB | ~2–3 GB | low-RAM CPU baseline |
| `Q8_0` | ~2.7 GB | ~3.5–4.5 GB | higher-quality CPU baseline |

Both are open weights and run on this machine with no GPU. The engine itself needs no model.

## Start the model

```bash
cd ~/bin/llamacpp/llama-b11936 && ./llama-server \
  -m ~/models/minicpm5/MiniCPM5-2B-Q4_K_M.gguf \
  -c 4096 -np 2 -t 4 --jinja --no-reasoning-preserve --port 8099
```

For the Q8 model, change `-m` to `MiniCPM5-2B-Q8_0.gguf` and `-t` to 6 on a 6-core host.

```bash
export MATERIA_CHAT_BASE_URL=http://127.0.0.1:8099/v1
export MATERIA_CHAT_MODEL=minicpm5-2b-q4
```

Or let materia start it:

```bash
MATERIA_REASON_GGUF=~/models/minicpm5/MiniCPM5-2B-Q4_K_M.gguf \
.venv/bin/python -m materia.cli serve --port 8765
```

See what is installed without starting anything:

```bash
.venv/bin/python -m materia.cli models --check
```

## Measure

```bash
.venv/bin/python scripts/eval_chat.py --out results/chat_q4.json
.venv/bin/python scripts/eval_chat_multiturn.py --out results/chat_multiturn_q4.json
```

The script reports pass rate with n and a 95% Wilson interval, mode counts and failures.

**Pass** = required phrase present, forbidden phrase absent, grounded, cited. A model answer
that adds a dose or citation outside the assessment is rejected and replaced by the
deterministic answer.

## Measured CPU results

| model | single-turn | multi-turn | notes |
|---|---:|---:|---|
| MiniCPM5-2B Q8_0 | **29/29 [88.3, 100.0]** | **17/17 [81.6, 100.0]** | 27 model / 2 rejected; 15 model / 2 rejected |
| MiniCPM5-2B Q4_K_M | **29/29 [88.3, 100.0]** | **17/17 [81.6, 100.0]** | 23 model / 1 deterministic / 5 rejected; 12 model / 5 rejected |

The Q4 model is smaller and faster but rejects more answers to the deterministic fallback. The
Q8 model uses more RAM and follows the contract more often. Neither is a prose-quality win over
the deterministic path; both are safe.

## Larger CPU models (optional)

If a host has more RAM and wants better prose, these open-weight instruct models run under
`llama.cpp` on CPU:

| model | Q4 file size | practical RAM | note |
|---|---:|---:|---|
| Qwen2.5-3B-Instruct | ~2 GB | ~4–5 GB | small step up from 2B |
| Llama-3.2-3B-Instruct | ~2 GB | ~4–5 GB | small step up |
| Qwen2.5-7B-Instruct | ~4.7 GB | ~8–10 GB | slower on CPU; measure before shipping |

Do not assume a larger model passes the citation contract. Run the same evaluation and compare
`model`, `rejected-model` and prose quality. The harness is model-agnostic:

```bash
export MATERIA_CHAT_BASE_URL=http://127.0.0.1:8000/v1
export MATERIA_CHAT_MODEL=Qwen2.5-3B-Instruct
.venv/bin/python scripts/eval_chat.py --out results/chat_3b.json
.venv/bin/python scripts/eval_chat_multiturn.py --out results/chat_multiturn_3b.json
```

## Interpretation

- **29/29 with mostly `mode=model`** — ready for the chat surface; compare prose quality.
- **29/29 with many `rejected-model`** — safe, but the model is not following the citation
  contract. Do not ship it as the primary voice.
- **below 29/29** — inspect the failures before changing the prompt. The benchmark is small;
  one failure is a hypothesis, not a verdict.

## Fine-tuning

Not yet. The binding constraints are clinician labels and evidence coverage, not model
weights. A CPU LoRA on 2B is possible, but a fine-tune on the synthetic contract set would
overfit it. Fine-tune only after the clinician label stream exists.
