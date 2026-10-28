#!/usr/bin/env python3
"""Build the panel grounding map: for each of the 104 items, which corpus chunks could
support the gold answer?

The support test is a transparent lexical overlap between the gold option and the
retrieved chunk, not a model judgement. It is a coverage instrument: it tells us which
items the corpus can ground at all, and it is spot-checked by hand (docs/corpus.md).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config  # noqa: E402
from materia.corpus.index import open_index  # noqa: E402
from materia.retrieve import Retriever  # noqa: E402

STOP = set(
    "the a an and or of in on for with to from by is are was were be been being this that these those "
    "as at it its their there which who whom what how why when where does do did can could should "
    "would may might will not no nor but if then than so such only also more most less least very "
    "may can will risk risks".split()
)


def content_tokens(text: str) -> set[str]:
    return {t for t in re.split(r"\W+", text.lower()) if len(t) > 3 and t not in STOP}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default=str(config.DATA_DIR / "herbal_set_104.json"))
    ap.add_argument("--index", default=str(config.CORPUS_DIR / "index.sqlite"))
    ap.add_argument("--out", default=str(config.DATA_DIR / "panel_grounding.json"))
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    conn = open_index(args.index)
    retriever = Retriever(conn, k=args.k, per_doc=2)
    items = json.loads(Path(args.panel).read_text())

    rows = []
    for it in items:
        chunks = retriever.search(it["q"])
        gold_text = it["o"][it["a"]]
        gt = content_tokens(gold_text)
        best = None
        for c in chunks:
            ct = content_tokens(c["text"])
            if not gt:
                continue
            score = len(gt & ct) / len(gt)
            if best is None or score > best["score"]:
                best = {"score": round(score, 3), "chunk_id": c["chunk_id"],
                        "section": c["section"], "source": c["source"],
                        "text": c["text"][:400]}
        rows.append(
            {
                "id": it["id"],
                "cat": it["cat"],
                "gold": it["a"],
                "gold_text": gold_text,
                "supported": bool(best and best["score"] >= 0.25),
                "score": best["score"] if best else 0.0,
                "chunk_ids": [c["chunk_id"] for c in chunks],
                "best": best,
            }
        )

    out = Path(args.out)
    out.write_text(json.dumps(rows, indent=1) + "\n")

    from collections import Counter

    by_cat: dict[str, list[bool]] = {}
    for r in rows:
        by_cat.setdefault(r["cat"], []).append(r["supported"])
    supported = sum(1 for r in rows if r["supported"])
    print(f"panel items: {len(rows)}  grounded: {supported}/{len(rows)} = {100 * supported / len(rows):.1f}%")
    for cat, vals in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
        k = sum(vals)
        print(f"  {cat:16s} {k:2d}/{len(vals):2d} = {100 * k / len(vals):5.1f}%")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
