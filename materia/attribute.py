"""Post-hoc attribution for hint-mode answers.

In hint mode the model is not asked to cite; it is shown one reference sentence. That means
the system must decide, after the fact, whether the chosen option is actually supported by
what the model was shown. If it is, the answer can be rendered with that source. If it is
not, the answer is a memory answer and must be labelled as such.
"""
from __future__ import annotations

from .verify import claim_support

SUPPORT_THRESHOLD = 0.2


def attribute(option_text: str, chunk: dict | None) -> dict:
    if not chunk:
        return {"mode": "memory", "reason": "no reference was available", "score": 0.0,
                "chunk_id": None, "source": None}
    score = claim_support(option_text, chunk.get("text", ""))
    supported = score >= SUPPORT_THRESHOLD
    return {
        "mode": "grounded" if supported else "memory",
        "reason": "" if supported else "the shown reference does not carry the chosen option",
        "score": round(score, 3),
        "chunk_id": chunk.get("chunk_id"),
        "source": chunk.get("source"),
    }
