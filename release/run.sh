#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/materia serve --host 127.0.0.1 --port 8765 --open "$@"
