#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="$(.venv/bin/python -c 'import materia; print(materia.__version__)')"
STAGE="$(mktemp -d)"
ROOT="$STAGE/materia-$VERSION"
trap 'rm -rf "$STAGE"' EXIT

.venv/bin/python -c 'import sqlite3; c=sqlite3.connect("corpus/index.sqlite"); c.execute("PRAGMA wal_checkpoint(TRUNCATE)"); c.close()'

mkdir -p "$ROOT"
cp -a materia data corpus samples scripts docs tests deploy "$ROOT/"
cp -a pyproject.toml README.md AGENTS.md HANDOVER.md NOTICE.md CHANGELOG.md "$ROOT/"
cp release/install.sh release/run.sh release/README.md "$ROOT/"

find "$ROOT" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$ROOT" -type f \( -name '*.pyc' -o -name '.DS_Store' -o -name '*.sqlite-wal' -o -name '*.sqlite-shm' \) -delete
rm -rf "$ROOT/.pytest_cache"

mkdir -p release
tar -C "$STAGE" -czf "release/materia-$VERSION-local.tar.gz" "materia-$VERSION"
( cd release && sha256sum "materia-$VERSION-local.tar.gz" > SHA256SUMS )
ls -lh "release/materia-$VERSION-local.tar.gz"
cat release/SHA256SUMS
