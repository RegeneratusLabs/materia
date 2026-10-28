"""SQLite FTS5 index over the corpus.

BM25 first, deliberately. It needs no embedding model, no GPU and no extra 2 GB, and the
corpus is small enough that a well-tokenised lexical index with section weighting is a
fair test of whether retrieval helps at all. Dense retrieval gets added only if this
misses (see AGENTS.md).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .schema import load_docs

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS docs(
  doc_id TEXT PRIMARY KEY, source TEXT, tier TEXT, title TEXT, date TEXT, revised TEXT,
  jurisdiction TEXT, language TEXT, licence_name TEXT, redistributable INTEGER,
  url TEXT, identifier_type TEXT, identifier_value TEXT, checksum TEXT,
  entities TEXT, next_review_due TEXT
);
CREATE TABLE IF NOT EXISTS chunks(
  chunk_id TEXT PRIMARY KEY, doc_id TEXT, text TEXT, section TEXT, assertion_type TEXT,
  topics TEXT, entities TEXT, analytes TEXT, words INTEGER, page INTEGER
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  chunk_id UNINDEXED, text, section, entities, topics,
  tokenize='porter unicode61'
);
CREATE INDEX IF NOT EXISTS chunks_doc ON chunks(doc_id);
"""


def build_index(docs_dir: str | Path, out: str | Path, *, include_eval_only: bool = False) -> dict:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    docs = load_docs(Path(docs_dir))
    if include_eval_only:
        eval_dir = Path(docs_dir).parent / "eval_only"
        if eval_dir.exists():
            docs += load_docs(eval_dir)

    conn = sqlite3.connect(out)
    conn.executescript(SCHEMA)
    nchunks = 0
    for d in docs:
        lic = d.get("licence") or {}
        ident = d.get("identifier") or {}
        conn.execute(
            "INSERT OR REPLACE INTO docs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                d["doc_id"], d["source"], d["tier"], d["title"], d["date"], d.get("revised"),
                d["jurisdiction"], d["language"], lic.get("name"),
                1 if lic.get("redistributable") else 0,
                d["url"], ident.get("type"), ident.get("value"), d["checksum"],
                json.dumps(d.get("entities") or []), d.get("next_review_due"),
            ),
        )
        for c in d["chunks"]:
            conn.execute(
                "INSERT OR REPLACE INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    c["chunk_id"], d["doc_id"], c["text"], c["section"], c["assertion_type"],
                    json.dumps(c.get("topics") or []), json.dumps(c.get("entities") or []),
                    json.dumps(c.get("analytes") or []), c["words"], c.get("page"),
                ),
            )
            conn.execute(
                "INSERT INTO chunks_fts(chunk_id, text, section, entities, topics) VALUES (?,?,?,?,?)",
                (
                    c["chunk_id"], c["text"], c["section"],
                    " ".join(c.get("entities") or []), " ".join(c.get("topics") or []),
                ),
            )
            nchunks += 1
    conn.commit()
    conn.close()
    return {"docs": len(docs), "chunks": nchunks, "path": str(out)}


def open_index(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def stats(path: str | Path) -> dict:
    conn = open_index(path)
    docs = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    by_tier = dict(conn.execute("SELECT tier, COUNT(*) FROM docs GROUP BY tier").fetchall())
    by_jur = dict(conn.execute("SELECT jurisdiction, COUNT(*) FROM docs GROUP BY jurisdiction").fetchall())
    by_assert = dict(conn.execute("SELECT assertion_type, COUNT(*) FROM chunks GROUP BY assertion_type").fetchall())
    conn.close()
    return {"docs": docs, "chunks": chunks, "by_tier": by_tier, "by_jurisdiction": by_jur,
            "by_assertion": by_assert}


def _main() -> int:
    import argparse

    from .. import config

    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(config.CORPUS_DIR / "docs"))
    ap.add_argument("--out", default=str(config.CORPUS_DIR / "index.sqlite"))
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()
    print(json.dumps(build_index(args.docs, args.out), indent=1))
    print(json.dumps(stats(args.out), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
