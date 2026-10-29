"""Run manifest: everything needed to reproduce a number.

The project rule is that a percentage without an artifact is not reportable. This makes the
artifact self-describing: which code, which corpus, which index, which prompt, which model,
which caps.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import config


def _sha256(path: Path) -> str | None:
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def git_sha() -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(config.ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip() or None
    except Exception:
        return None


def build(**overrides) -> dict:
    index = config.CORPUS_DIR / "index.sqlite"
    manifest_path = config.CORPUS_DIR / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError:
            manifest = {}

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": git_sha(),
        "corpus": {
            "manifest_generated": manifest.get("generated"),
            "documents": manifest.get("documents"),
            "chunks": manifest.get("chunks"),
            "manifest_sha256": _sha256(manifest_path),
            "index_bytes": index.stat().st_size if index.exists() else None,
            "index_mtime": datetime.fromtimestamp(index.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
            if index.exists() else None,
        },
        "prompt_sha256": _sha256(config.ROOT / "materia" / "prompt.py"),
        "rules_sha256": _sha256(config.ROOT / "rules" / "red_flags.yaml"),
        "model": {
            "reason_gguf": str(config.REASON_GGUF),
            "reason_bytes": config.REASON_GGUF.stat().st_size if config.REASON_GGUF.exists() else None,
            "ocr_gguf": str(config.OCR_GGUF),
            "ocr_bytes": config.OCR_GGUF.stat().st_size if config.OCR_GGUF.exists() else None,
        },
        "settings": {
            "reason_ctx": config.REASON_CTX,
            "reason_parallel": config.REASON_PARALLEL,
            "threads": config.THREADS,
            "temperature": config.TEMPERATURE,
            "rule_budget": config.RULE_BUDGET,
        },
    }
    data.update(overrides)
    return data


def write(path: str | Path, **overrides) -> dict:
    manifest = build(**overrides)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest
