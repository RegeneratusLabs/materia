"""Answer parsing and citation extraction.

The lowercase trap (HANDOVER §8): a case-insensitive single-letter search matches the
article "a" and returns it as an answer. Only ever accept an UPPERCASE A-D, and prefer
an explicit answer marker.
"""
from __future__ import annotations

import re

_LETTER = r"[ABCD]"

# "Answer: C", "**Answer: (B)**", "the answer is D", "option C"
# Keyword matching is case-insensitive; the captured letter is NOT. That is the
# whole point: "answer: a" is the article, not option A.
_EXPLICIT = re.compile(
    r"(?i:(?:answer|option|choice)\s*(?:is|:|=)?)\s*\**\s*\(?(" + _LETTER + r")(?![A-Za-z])"
)

# A standalone uppercase letter alone on a line / at the start of text.
_STANDALONE = re.compile(r"(?:^|\n)[\s*(\"']*(" + _LETTER + r")(?![A-Za-z0-9])")

_TRAILING = re.compile(r"\b(" + _LETTER + r")(?![A-Za-z0-9])\s*[.)*]*\s*$")

_CITATION = re.compile(r"\bS(\d{1,2})\b")


def parse_letter(text: str, reasoning: str = "") -> str | None:
    """Return 'A'-'D' or None. Uppercase-only; never matches the article 'a'."""
    for blob in (text or "", _head(reasoning), _tail(reasoning)):
        if not blob:
            continue
        m = _EXPLICIT.search(blob)
        if m:
            return m.group(1)
        m = _STANDALONE.search(blob)
        if m:
            return m.group(1)
        m = _TRAILING.search(blob)
        if m:
            return m.group(1)
    return None


def _head(s: str, n: int = 300) -> str:
    return (s or "")[:n]


def _tail(s: str, n: int = 300) -> str:
    return (s or "")[-n:]


def parse_sources(text: str) -> list[str]:
    """Extract S1..S99 citation ids from an ANSWER/SOURCE block, order preserved."""
    out: list[str] = []
    for m in _CITATION.finditer(text or ""):
        cid = "S" + m.group(1)
        if cid not in out:
            out.append(cid)
    return out


def is_no_evidence(text: str) -> bool:
    return "NO_EVIDENCE" in (text or "").upper()
