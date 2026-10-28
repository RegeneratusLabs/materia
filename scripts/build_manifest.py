#!/usr/bin/env python3
"""Build corpus/manifest.json — the rebuild-and-refresh ledger.

One entry per document: where it came from, what it hashed to when fetched, when it is
due for review, and whether we are allowed to ship it. Raw files are not committed, so
this manifest is what makes the corpus reproducible.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config  # noqa: E402
from materia.corpus.schema import load_docs  # noqa: E402


def build(docs_dir: Path) -> dict:
    docs = load_docs(docs_dir)
    entries = []
    for d in docs:
        lic = d.get("licence") or {}
        entries.append(
            {
                "doc_id": d["doc_id"],
                "source": d["source"],
                "tier": d["tier"],
                "title": d["title"],
                "url": d["url"],
                "identifier": d.get("identifier"),
                "jurisdiction": d["jurisdiction"],
                "language": d["language"],
                "revised": d.get("revised"),
                "retrieved_at": d.get("retrieved_at"),
                "next_review_due": d.get("next_review_due"),
                "checksum": d["checksum"],
                "licence": {"name": lic.get("name"), "redistributable": lic.get("redistributable"),
                            "evidence_url": lic.get("evidence_url")},
                "chunks": len(d.get("chunks") or []),
            }
        )
    today = date.today().isoformat()
    due = sum(1 for e in entries if e["next_review_due"] and e["next_review_due"] < today)
    return {
        "generated": today,
        "documents": len(entries),
        "chunks": sum(e["chunks"] for e in entries),
        "redistributable": sum(1 for e in entries if e["licence"]["redistributable"]),
        "review_due": due,
        "entries": sorted(entries, key=lambda e: e["doc_id"]),
    }


def main() -> int:
    out = config.CORPUS_DIR / "manifest.json"
    manifest = build(config.CORPUS_DIR / "docs")
    out.write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{manifest['documents']} documents, {manifest['chunks']} chunks, "
          f"{manifest['redistributable']} redistributable, {manifest['review_due']} past review date")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
