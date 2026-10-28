"""Prompt assembly.

Closed-book and retrieval prompts are separate functions on purpose: the retrieval
prompt adds labelled evidence and a citation obligation, and nothing else. No
meta-instructions (distrust priors, reinterpret units) — every one tested lowered the
score (HANDOVER §4).
"""
from __future__ import annotations

from .config import RULE_BUDGET


def build_prompt(item: dict, rule: str = RULE_BUDGET) -> str:
    lines = [rule, "", item["q"], ""]
    for k in sorted(item["o"]):
        lines.append(f"{k}) {item['o'][k]}")
    lines += ["", "Answer:"]
    return "\n".join(lines)


def evidence_header(i: int, c: dict) -> str:
    parts = [
        f"[S{i}]",
        c.get("chunk_id", ""),
        c.get("source", ""),
        c.get("tier", ""),
        c.get("jurisdiction", ""),
        c.get("date", ""),
    ]
    if c.get("section"):
        parts.append(f"section={c['section']}")
    return " · ".join(p for p in parts if p)


def build_prompt_retrieval(item: dict, chunks: list[dict], rule: str = RULE_BUDGET) -> str:
    """Evidence blocks are labelled; citing an S-id is mandatory for a clinical claim."""
    lines = [
        rule,
        "",
        "Use the numbered evidence below. Cite the evidence you used as SOURCE: S1, S3.",
        "If the evidence does not address the question, reply NO_EVIDENCE instead of guessing.",
        "",
        "EVIDENCE",
    ]
    for i, c in enumerate(chunks, start=1):
        lines += [evidence_header(i, c), c.get("text", "").strip(), ""]
    lines += ["QUESTION", item["q"], ""]
    for k in sorted(item["o"]):
        lines.append(f"{k}) {item['o'][k]}")
    lines += ["", "Answer with: ANSWER: <letter> and SOURCE: <S-ids or NONE>."]
    return "\n".join(lines)
