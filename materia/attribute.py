"""Post-hoc attribution for hint-mode answers.

In hint mode the model is not asked to cite; it is shown one reference sentence. That means
the system must decide, after the fact, whether the chosen option is actually supported by
what the model was shown. If it is, the answer can be rendered with that source. If it is
not, the answer is a memory answer and must be labelled as such.
"""
from __future__ import annotations

import re

from .verify import claim_support

SUPPORT_THRESHOLD = 0.2


GENERIC_ENTITY_WORDS = {
    "test", "tests", "level", "levels", "blood", "serum", "total", "free", "oral", "topical",
    "monograph", "monographs", "union", "european", "herbal", "health", "professional",
    "version", "cancer", "therapy", "therapies", "interactions", "foods", "dietary",
    "supplements", "supplement", "products", "product", "fixed", "case", "report", "review",
    "narrative", "beyond", "pathophysiology", "diagnosis", "complexities", "and", "the",
}


SHORT_ANALYTES = {"tsh", "t3", "t4", "ft3", "ft4", "b12", "ggt", "alt", "ast", "alp",
                  "crp", "esr", "ldl", "hdl", "a1c"}


def _entity_tokens(text: str) -> set[str]:
    out = set()
    for w in re.split(r"\W+", text.lower()):
        if not w or w in GENERIC_ENTITY_WORDS:
            continue
        if len(w) > 3 or w in SHORT_ANALYTES or any(ch.isdigit() for ch in w):
            out.add(w)
    return out


def _entity_gap(question: str, chunk: dict) -> str | None:
    """Return the chunk's entity when none of its distinctive tokens appear in the question.

    A reference about a different herb can share generic vocabulary with the answer — an
    astragalus safety chunk next to an echinacea answer — and that must never count as
    grounded. Titles are wordy ("Free T4 test", "Union herbal monograph"), so only tokens
    that carry identity are compared.
    """
    ents = chunk.get("entities") or []
    if isinstance(ents, str):
        ents = [ents]
    if not ents or not question:
        return None
    q_tokens = _entity_tokens(question)
    if not q_tokens:
        return None
    for e in ents:
        # keep parentheticals: the acronym often lives there — "Gamma-glutamyl transferase (GGT)"
        ents_tokens = _entity_tokens(str(e))
        if not ents_tokens:
            return None  # nothing distinctive to compare; do not block on metadata
        if ents_tokens & q_tokens:
            return None
    return str(ents[0])


def attribute(option_text: str, chunk: dict | None, question: str = "") -> dict:
    if not chunk:
        return {"mode": "memory", "reason": "no reference was available", "score": 0.0,
                "chunk_id": None, "source": None}
    gap = _entity_gap(question, chunk)
    if gap:
        return {
            "mode": "memory",
            "reason": f"the reference is about {gap}, not about the subject of the question",
            "score": 0.0,
            "chunk_id": chunk.get("chunk_id"),
            "source": chunk.get("source"),
        }
    score = claim_support(option_text, chunk.get("text", ""))
    supported = score >= SUPPORT_THRESHOLD
    return {
        "mode": "grounded" if supported else "memory",
        "reason": "" if supported else "the shown reference does not carry the chosen option",
        "score": round(score, 3),
        "chunk_id": chunk.get("chunk_id"),
        "source": chunk.get("source"),
    }
