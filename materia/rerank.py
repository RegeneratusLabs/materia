"""Pointwise reranker using the local model.

BM25 with entity and section priors gets the right document; it does not reliably get the
right *claim*. The reranker asks the model one narrow question per candidate — "does this
passage help answer this?" — with thinking disabled and a one-word answer, then keeps the
top few.

Deliberately narrow: it selects among passages that already passed retrieval, it does not
invent, and it runs with thinking off because evidence in the prompt plus deliberation is
the failure mode documented in docs/gate3.md (Experiment 5).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import config, llm

CACHE_PATH = config.RESULTS_DIR / "rerank_cache.json"
PROMPT = (
    "PASSAGE: {passage}\n\n"
    "QUESTION: {question}\n\n"
    "Does the passage contain information that helps answer the question? "
    "Reply with one word: YES or NO."
)


def _key(question: str, chunk_id: str) -> str:
    return hashlib.sha1(f"{question}||{chunk_id}".encode()).hexdigest()[:16]


def _trim(text: str, words: int = 70) -> str:
    parts = text.split()
    return " ".join(parts[:words])


class Reranker:
    def __init__(self, *, cache_path: Path | None = None, use_cache: bool = True, max_tokens: int = 4):
        self.path = Path(cache_path or CACHE_PATH)
        self.use_cache = use_cache
        self.max_tokens = max_tokens
        self.cache: dict[str, int] = {}
        if use_cache and self.path.exists():
            try:
                self.cache = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                self.cache = {}
        self.dirty = False

    def score(self, question: str, chunk: dict) -> int:
        key = _key(question, chunk["chunk_id"])
        if key in self.cache:
            return self.cache[key]
        prompt = PROMPT.format(passage=_trim(chunk.get("text", "")), question=question)
        try:
            out = llm.chat([{"role": "user", "content": prompt}],
                           max_tokens=self.max_tokens, enable_thinking=False, timeout=120)
            verdict = 1 if re.match(r"\s*yes", out["text"], re.I) else 0
        except Exception:
            verdict = 1  # fail open: keep the passage rather than silently dropping evidence
        self.cache[key] = verdict
        self.dirty = True
        return verdict

    def rank(self, question: str, chunks: list[dict], top_k: int = 3) -> list[dict]:
        scored = [(self.score(question, c), i, c) for i, c in enumerate(chunks)]
        # stable: YES first, then original retrieval order
        scored.sort(key=lambda t: (-t[0], t[1]))
        kept = [c for verdict, _, c in scored if verdict == 1][:top_k]
        if not kept:  # never return nothing solely because the reranker disliked everything
            kept = [c for _, _, c in scored[:top_k]]
        return kept

    def save(self) -> None:
        if self.use_cache and self.dirty:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.cache, indent=0) + "\n")
            self.dirty = False
