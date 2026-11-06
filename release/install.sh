#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
"$PYTHON" -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"

cat <<'EOF'

Installed. Start the local app:

  ./run.sh

The default sample is a synthetic nutrient/lipid panel and works with no model.
Uploads need the OCR weights and --start-ocr. Optional CPU chat model:

  export MATERIA_CHAT_BASE_URL="http://127.0.0.1:8099/v1"
  export MATERIA_CHAT_MODEL="minicpm5-2b-q4"

No GPU, no cloud, no telemetry.
EOF
