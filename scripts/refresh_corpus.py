#!/usr/bin/env python3
"""Freshness check: which documents have changed, and which are past their review date.

No crawler, no mutation by default: fetch each manifest URL, hash it, and report. With
--rebuild it re-ingests changed documents through the source adapters (not implemented
per-source here; it prints the commands to run). Honest about what it does not do yet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config  # noqa: E402

UA = "materia-corpus/0.1 (+local research build)"


def fetch_sha(url: str, timeout: float = 60.0) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        return "sha256:" + hashlib.sha256(data).hexdigest()
    except Exception as e:
        print(f"  fetch failed: {url}: {e}", flush=True)
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(config.CORPUS_DIR / "manifest.json"))
    ap.add_argument("--out", default=str(config.CORPUS_DIR / "refresh_report.json"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.6)
    args = ap.parse_args(argv)

    manifest = json.loads(Path(args.manifest).read_text())
    entries = manifest["entries"]
    if args.limit:
        entries = entries[: args.limit]

    today = date.today().isoformat()
    changed, unchanged, failed, overdue = [], [], [], []
    for e in entries:
        if e.get("next_review_due") and e["next_review_due"] < today:
            overdue.append(e["doc_id"])
        sha = fetch_sha(e["url"])
        if sha is None:
            failed.append(e["doc_id"])
        elif sha == e["checksum"]:
            unchanged.append(e["doc_id"])
        else:
            changed.append({"doc_id": e["doc_id"], "url": e["url"], "old": e["checksum"], "new": sha})
        time.sleep(args.sleep)

    report = {
        "checked_at": today,
        "checked": len(entries),
        "changed": changed,
        "unchanged": len(unchanged),
        "failed": failed,
        "overdue_review": overdue,
        "note": "changed documents must be re-ingested with the source adapter before the corpus is rebuilt",
    }
    Path(args.out).write_text(json.dumps(report, indent=1) + "\n")
    print(f"checked {len(entries)}: {len(changed)} changed, {len(unchanged)} unchanged, "
          f"{len(failed)} failed, {len(overdue)} past review date")
    for c in changed[:10]:
        print(f"  changed: {c['doc_id']}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
