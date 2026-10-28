"""Corpus document/chunk schema and validation.

Additive to HANDOVER §2.1. The three fields that were not in the original schema and
that make the rest of the system possible: `assertion_type` (what kind of claim a chunk
makes — drives conflict grouping and the output contract), `licence` (what we are
allowed to ship), and the freshness triple `revised` / `retrieved_at` / `next_review_due`.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path

TIERS = ("primary", "regulatory", "compendium", "traditional")

SECTIONS = (
    "indications",
    "dosage",
    "contraindications",
    "cautions",
    "interactions",
    "adverse_effects",
    "pharmacology",
    "toxicology",
    "evidence",
    "monitoring",
    "red_flags",
    "reference_interval",
    "differential",
    "methodology",
    "other",
)

ASSERTION_TYPES = ("efficacy", "safety", "dose", "jurisdiction", "monitoring", "diagnostic", "other")

IDENTIFIER_TYPES = (
    "ema", "nhpid", "pmid", "doi", "nice", "nci", "odp", "artg", "nbk", "web", "other"
)

_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHA = re.compile(r"^sha256:[0-9a-f]{64}$")

# Review TTL by tier, in months (AGENTS.md Phase A decisions).
TTL_MONTHS = {"regulatory": 12, "compendium": 6, "primary": 120, "traditional": 120}


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def review_due(revised: str, tier: str) -> str:
    """revised + TTL, as ISO date. Regulatory documents are re-checked annually."""
    y, m, d = (int(x) for x in revised.split("-"))
    months = TTL_MONTHS.get(tier, 12)
    m2 = m - 1 + months
    y2 = y + m2 // 12
    m2 = m2 % 12 + 1
    # clamp day for short months
    for day in (d, 30, 29, 28):
        try:
            return date(y2, m2, day).isoformat()
        except ValueError:
            continue
    return date(y2, m2, 28).isoformat()


def make_chunk(
    chunk_id: str,
    text: str,
    section: str,
    assertion_type: str,
    *,
    page: int | None = None,
    topics: list[str] | None = None,
    entities: list[str] | None = None,
    analytes: list[str] | None = None,
) -> dict:
    return {
        "chunk_id": chunk_id,
        "text": text.strip(),
        "section": section,
        "assertion_type": assertion_type,
        "topics": topics or [],
        "entities": entities or [],
        "analytes": analytes or [],
        "page": page,
        "words": len(text.split()),
    }


def make_doc(
    *,
    doc_id: str,
    source: str,
    tier: str,
    title: str,
    date_: str,
    url: str,
    identifier: dict,
    jurisdiction: str,
    language: str,
    licence: dict,
    retrieved_at: str,
    checksum: str,
    chunks: list[dict],
    entities: list[str] | None = None,
    title_extra: str | None = None,
) -> dict:
    return {
        "doc_id": doc_id,
        "source": source,
        "tier": tier,
        "title": title,
        "title_extra": title_extra,
        "date": date_,
        "revised": date_,
        "retrieved_at": retrieved_at,
        # Review clock runs from when WE fetched it, not when the publisher wrote it:
        # a 2016 guideline downloaded today is not "overdue", it is due in 12 months.
        "next_review_due": review_due(retrieved_at, tier) if retrieved_at else "",
        "url": url,
        "identifier": identifier,
        "jurisdiction": jurisdiction,
        "language": language,
        "licence": licence,
        "checksum": checksum,
        "entities": entities or [],
        "chunks": chunks,
    }


def validate_doc(doc: dict) -> list[str]:
    e: list[str] = []
    doc_id = doc.get("doc_id", "")
    if not doc_id or not _SLUG.match(doc_id):
        e.append(f"doc_id invalid: {doc_id!r}")
    for field in ("source", "title", "url", "jurisdiction", "language"):
        if not str(doc.get(field) or "").strip():
            e.append(f"{field} missing")
    if doc.get("tier") not in TIERS:
        e.append(f"tier invalid: {doc.get('tier')!r}")
    if not _ISO_DATE.match(str(doc.get("date", ""))):
        e.append(f"date invalid: {doc.get('date')!r}")
    ident = doc.get("identifier") or {}
    if ident.get("type") not in IDENTIFIER_TYPES:
        e.append(f"identifier.type invalid: {ident.get('type')!r}")
    if not str(ident.get("value") or "").strip():
        e.append("identifier.value missing")
    lic = doc.get("licence") or {}
    if not lic.get("name"):
        e.append("licence.name missing")
    if not isinstance(lic.get("redistributable"), bool):
        e.append("licence.redistributable must be bool")
    if not lic.get("evidence_url"):
        e.append("licence.evidence_url missing")
    if not _SHA.match(str(doc.get("checksum", ""))):
        e.append("checksum missing or malformed")
    if not _ISO_DATE.match(str(doc.get("retrieved_at", ""))):
        e.append("retrieved_at invalid")
    if not _ISO_DATE.match(str(doc.get("next_review_due", ""))):
        e.append("next_review_due invalid")

    chunks = doc.get("chunks") or []
    if not chunks:
        e.append("no chunks")
    seen: set[str] = set()
    for i, c in enumerate(chunks, start=1):
        cid = c.get("chunk_id", "")
        expected = f"{doc_id}#{i:03d}"
        if cid != expected:
            e.append(f"chunk_id {cid!r} should be {expected!r} (stable ids)")
        if cid in seen:
            e.append(f"duplicate chunk_id {cid}")
        seen.add(cid)
        if c.get("section") not in SECTIONS:
            e.append(f"{cid}: section invalid {c.get('section')!r}")
        if c.get("assertion_type") not in ASSERTION_TYPES:
            e.append(f"{cid}: assertion_type invalid {c.get('assertion_type')!r}")
        words = c.get("words") or len(str(c.get("text", "")).split())
        if words < 8:
            e.append(f"{cid}: too short ({words} words)")
        if words > 800:
            e.append(f"{cid}: too long ({words} words)")
        if c.get("words") != len(str(c.get("text", "")).split()):
            e.append(f"{cid}: words field does not match text")
    return e


def validate_corpus(docs: list[dict]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for d in docs:
        errors += [f"{d.get('doc_id', '?')}: {x}" for x in validate_doc(d)]
        did = d.get("doc_id")
        if did in seen:
            errors.append(f"duplicate doc_id {did}")
        seen.add(did)
    return errors


def load_docs(path: Path) -> list[dict]:
    p = Path(path)
    if p.is_file():
        return [json.loads(p.read_text())]
    return [json.loads(f.read_text()) for f in sorted(p.glob("*.json"))]


def dump_doc(doc: dict, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    out = directory / f"{doc['doc_id']}.json"
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    return out


def _main(argv: list[str] | None = None) -> int:
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] != "validate":
        print("usage: python -m materia.corpus.schema validate <dir|file>")
        return 2
    target = Path(args[1]) if len(args) > 1 else Path("corpus/docs")
    docs = load_docs(target)
    errors = validate_corpus(docs)
    lic = sum(1 for d in docs if (d.get("licence") or {}).get("redistributable"))
    chunks = sum(len(d.get("chunks") or []) for d in docs)
    print(f"documents: {len(docs)}  redistributable: {lic}  chunks: {chunks}")
    if errors:
        print(f"ERRORS: {len(errors)}")
        for err in errors[:40]:
            print("  -", err)
        return 1
    print("schema OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
