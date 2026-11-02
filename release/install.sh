#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install materia-0.2.0-py3-none-any.whl

cat <<'EOF'

Installed. Add the model paths to your shell if you want uploads:

  export MATERIA_LLAMA_DIR="$HOME/bin/llamacpp/llama-b11936"
  export MATERIA_OCR_GGUF="$HOME/models/minicpm-ocr/MiniCPM-OCR-1_0-Q4_K_M.gguf"
  export MATERIA_OCR_MMPROJ="$HOME/models/minicpm-ocr/mmproj-model-f16-4x.gguf"

Then run:

  ./run.sh

The sample report works without any model. Uploads need the OCR weights.
EOF
