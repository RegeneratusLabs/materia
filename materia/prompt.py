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


def _trim(text: str, words: int = 100) -> str:
    parts = text.split()
    return " ".join(parts[:words]) + (" …" if len(parts) > words else "")


def build_prompt_retrieval(
    item: dict, chunks: list[dict], rule: str = RULE_BUDGET, evidence_words: int = 100
) -> str:
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
        lines += [evidence_header(i, c), _trim(c.get("text", "").strip(), evidence_words), ""]
    lines += ["QUESTION", item["q"], ""]
    for k in sorted(item["o"]):
        lines.append(f"{k}) {item['o'][k]}")
    lines += [
        "",
        "Reply with exactly one line: ANSWER: <letter>. SOURCE: <S-ids or NONE>.",
        "Example: ANSWER: C. SOURCE: S2",
    ]
    return "\n".join(lines)


def build_freeform(question: str, chunks: list[dict] | None = None, *, evidence_words: int = 90) -> str:
    """Free-text answer prompt. Evidence mode cites; memory mode says it has no source."""
    if chunks:
        head = (
            "Answer the question in at most 60 words. Every clinical claim must cite the evidence "
            "it came from as [S<n>]. If the evidence does not answer it, reply exactly NO_EVIDENCE."
        )
        return "\n".join([head, "", "EVIDENCE"]) + "\n" + "\n".join(
            f"[S{i}] {evidence_header(i, c)}\n{_trim(c.get('text', ''), evidence_words)}"
            for i, c in enumerate(chunks, start=1)
        ) + f"\n\nQUESTION\n{question}\n\nANSWER (<=60 words, cite [S<n]>):"
    head = (
        "Answer the question in at most 60 words. No sources are available for this question, so "
        "do not cite anything; state the answer plainly."
    )
    return f"{head}\n\nQUESTION\n{question}\n\nANSWER:"
