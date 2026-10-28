"""Paths and ports. Everything overridable by environment variable."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


MODELS_DIR = _env_path("MATERIA_MODELS_DIR", Path.home() / "models")
REASON_GGUF = _env_path(
    "MATERIA_REASON_GGUF", MODELS_DIR / "minicpm5" / "MiniCPM5-2B-Q8_0.gguf"
)
OCR_GGUF = _env_path(
    "MATERIA_OCR_GGUF", MODELS_DIR / "minicpm-ocr" / "MiniCPM-OCR-1_0-Q4_K_M.gguf"
)
OCR_MMPROJ = _env_path(
    "MATERIA_OCR_MMPROJ", MODELS_DIR / "minicpm-ocr" / "mmproj-model-f16-4x.gguf"
)

LLAMA_DIR = _env_path("MATERIA_LLAMA_DIR", Path.home() / "bin" / "llamacpp" / "llama-b11936")
LLAMA_SERVER = LLAMA_DIR / "llama-server"

REASON_PORT = int(os.environ.get("MATERIA_REASON_PORT", "8099"))
OCR_PORT = int(os.environ.get("MATERIA_OCR_PORT", "18499"))

REASON_CTX = int(os.environ.get("MATERIA_REASON_CTX", "4096"))
REASON_PARALLEL = int(os.environ.get("MATERIA_REASON_PARALLEL", "2"))
THREADS = int(os.environ.get("MATERIA_THREADS", "6"))
OCR_CTX = int(os.environ.get("MATERIA_OCR_CTX", "16384"))

RSS_LIMIT_MB = float(os.environ.get("MATERIA_RSS_LIMIT_MB", "3500"))
LOGS_DIR = ROOT / "logs"
RESULTS_DIR = ROOT / "results"
DATA_DIR = ROOT / "data"
CORPUS_DIR = ROOT / "corpus"
SAMPLES_DIR = ROOT / "samples"

# The one earned prompt instruction (HANDOVER §4). Do not add meta-instructions.
RULE_BUDGET = (
    "Think for at most 60 words, then reply with ONLY the letter of the single best "
    "option (A, B, C or D). No explanation after the letter."
)

# Fixed sampling: every eval is greedy, so runs are comparable.
TEMPERATURE = 0.0


def project_path(*parts: str) -> Path:
    return ROOT.joinpath(*parts)
