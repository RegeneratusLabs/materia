# materia — chat model runbook

The recommendation engine is deterministic. The conversational layer is optional and
model-agnostic. This is the procedure for measuring a stronger local model when a GPU is
available.

**Rule:** do not lower the citation gate to make a model look better. If a model cannot
answer with a valid chunk citation, it is not ready for the chat surface.

## Baseline

Local MiniCPM5-2B, Q8_0, CPU:

```bash
.venv/bin/python -m materia.cli serve --port 8765
MATERIA_CHAT_BASE_URL=http://127.0.0.1:8099/v1 \
MATERIA_CHAT_MODEL=local \
.venv/bin/python scripts/eval_chat.py
```

Expected: **22/22 [85.1, 100.0]**, with roughly 20 model answers and 2 rejections to the
deterministic fallback. The 2B is a contract baseline, not a prose-quality target.

## vLLM, 24 GB

```bash
vllm serve Qwen/Qwen2.5-14B-Instruct \
  --port 8000 --max-model-len 8192 --gpu-memory-utilization 0.90
```

## vLLM, 48 GB

```bash
vllm serve Qwen/Qwen2.5-32B-Instruct \
  --port 8000 --max-model-len 8192 --gpu-memory-utilization 0.90
```

## vLLM, 80 GB

```bash
vllm serve meta-llama/Llama-3.3-70B-Instruct \
  --port 8000 --max-model-len 8192 --gpu-memory-utilization 0.90
```

All three are open-weight. No OpenAI or other closed endpoint is used.

## Measure

```bash
export MATERIA_CHAT_BASE_URL=http://127.0.0.1:8000/v1
export MATERIA_CHAT_MODEL=Qwen/Qwen2.5-14B-Instruct
.venv/bin/python scripts/eval_chat.py --out results/chat_14b.json
.venv/bin/python scripts/eval_chat_multiturn.py --out results/chat_multiturn_14b.json
```

The multi-turn set is only 17 turns; read it as a follow-up smoke test, not a prose-quality
benchmark.

The script reports:

- pass rate with n and a 95% Wilson interval;
- mode counts (`model` vs `rejected-model`);
- per-question failures.

**Pass** = required phrase present, forbidden phrase absent, grounded, cited. A model answer
that adds a dose or citation outside the assessment is rejected and replaced by the
deterministic answer.

## Interpretation

- **22/22 with mostly `mode=model`** — ready for the chat surface; compare prose quality.
- **22/22 with many `rejected-model`** — safe, but the model is not following the citation
  contract. Do not ship it as the primary voice.
- **below 22/22** — inspect the failures before changing the prompt. The benchmark is small;
  one failure is a hypothesis, not a verdict.

## Fine-tuning

Not yet. The binding constraints are clinician labels and evidence coverage, not model
weights. Fine-tune only after the retrieval/rules layer has its own labelled accuracy number
and the 14B baseline has been measured. A fine-tune on 22 synthetic questions would overfit
the contract set.
