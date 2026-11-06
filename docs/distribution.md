# materia — local product 1.0.0

A self-contained, local-only clinical decision-support product. One process, one browser tab,
no cloud calls, no telemetry, no GPU.

It is **not a medical device** and does not diagnose or prescribe. The engine is deterministic;
the conversational layer is optional. The measured/unmeasured boundary is in
`docs/validation.md`.

## What is in the box

- `materia` — the engine, rules, CLI and web app.
- `corpus/` — 401 licence-clear documents and the SQLite FTS index (5,207 chunks).
- `data/` — the 72-case contract set, 50-case clinician review set and chat sets.
- `samples/` — the public amino-acid sample and provenance.
- `docs/` — design, validation, review packet, runbook and rule audit.
- `scripts/` — evaluation, review, audit and release tooling.
- `tests/` — 164 tests.
- `install.sh`, `run.sh` — the local product entry points.

Model weights are **not** in the box. The default sample and the Plan work without a model.
Uploads need the optional OCR weights; the chat model is optional and CPU-only.

## Fedora

```bash
sudo dnf install -y git python3 python3-pip tar
git clone https://github.com/RegeneratusLabs/materia.git
cd materia
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/materia doctor
.venv/bin/materia serve --port 8765 --open
```

If `python3` is 3.13 and a wheel is missing, install `python3.12` and use
`PYTHON=python3.12 ./install.sh`.

## Requirements

- Python 3.12+
- ~1 GB free RAM for the engine and sample
- optional: `llama.cpp` + MiniCPM-OCR weights for uploads
- optional: a 2B CPU GGUF for chat (Q4 1.5 GB or Q8 2.7 GB)

No GPU, no vLLM, no hosted service.

## Install from the tarball

```bash
tar xzf materia-1.0.0-local.tar.gz
cd materia-1.0.0
./install.sh
./run.sh
```

`install.sh` creates `.venv` and installs this tree in editable mode. `run.sh` starts the local
app at `http://127.0.0.1:8765`.

## Install from the source checkout

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/materia serve --port 8765 --open
```

## Verify

```bash
.venv/bin/materia doctor
.venv/bin/python -m pytest -q
.venv/bin/python scripts/eval_recommend.py
.venv/bin/python scripts/eval_chat.py --no-model
.venv/bin/python scripts/audit_rules.py
```

## Optional CPU chat

```bash
cd ~/bin/llamacpp/llama-b11936 && ./llama-server \
  -m ~/models/minicpm5/MiniCPM5-2B-Q4_K_M.gguf \
  -c 4096 -np 2 -t 4 --jinja --no-reasoning-preserve --port 8099

export MATERIA_CHAT_BASE_URL=http://127.0.0.1:8099/v1
export MATERIA_CHAT_MODEL=minicpm5-2b-q4
./run.sh
```

## Licensing and attribution

The `corpus/manifest.json` records each document’s source, licence and redistribution status.
The engine ships only content that permits redistribution (NNHPD/OGL-Canada, EMA, CC-BY,
US federal public domain). Read `docs/attribution.md` before redistributing or rebranding.

## Scope

In scope: lab review, cited patterns, ranked supplement/herb/lifestyle/referral options, safety
gates, monitoring, grounded chat, clinician review.

Out of scope: diagnosis, prescription, dosing for children without clinician review, amino-acid
interpretation, a hosted multi-user service, and a claim of clinical accuracy before the
clinician label stream exists.
