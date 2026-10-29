#!/usr/bin/env python3
"""Per-item scoring state machine.

A single percentage hides the only thing that matters: whether an answer was supported by
evidence, invented without it, or rightly withheld. This classifies every item into one of
four states and reports the matrix.

States:
  grounded_correct    the gold set says the corpus can answer it, and the answer is right
  grounded_wrong      the corpus can answer it, and the answer is wrong
  ungrounded_answered the corpus cannot answer it (or evidence was absent) but it answered anyway
  abstained           it emitted NO_EVIDENCE

Usage:
    python scripts/score.py --results results/panel_retrieval_nothink.jsonl \
        --gold data/panel_grounding_gold.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config  # noqa: E402
from materia.stats import wilson_str  # noqa: E402


def load_gold(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        data = data.get("items", data)
    return {row["id"]: row for row in data}


def classify(rec: dict, gold: dict | None) -> str:
    if not rec.get("got"):
        return "abstained"
    grounded = bool(gold and gold.get("grounded"))
    correct = rec.get("got") == rec.get("gold")
    if grounded:
        return "grounded_correct" if correct else "grounded_wrong"
    return "ungrounded_answered"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--gold", default=str(config.DATA_DIR / "panel_grounding_gold.json"))
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    gold = load_gold(Path(args.gold)) if Path(args.gold).exists() else {}
    recs = [json.loads(line) for line in open(args.results) if line.strip()]

    rows = []
    for r in recs:
        g = gold.get(r["id"])
        rows.append({"id": r["id"], "cat": r.get("cat"), "gold": r.get("gold"),
                     "got": r.get("got"), "state": classify(r, g),
                     "grounded": bool(g and g.get("grounded"))})

    counts = Counter(x["state"] for x in rows)
    n = len(rows)
    grounded = [x for x in rows if x["grounded"]]
    ungrounded = [x for x in rows if not x["grounded"]]
    g_correct = sum(1 for x in grounded if x["state"] == "grounded_correct")
    g_abstained = sum(1 for x in grounded if x["state"] == "abstained")
    u_abstained = sum(1 for x in ungrounded if x["state"] == "abstained")
    u_answered = sum(1 for x in ungrounded if x["state"] == "ungrounded_answered")

    by_cat: dict[str, Counter] = defaultdict(Counter)
    for x in rows:
        by_cat[x["cat"]][x["state"]] += 1

    report = {
        "results": args.results,
        "gold_set": args.gold if gold else None,
        "n": n,
        "coverage": {
            "grounded": len(grounded),
            "ungrounded": len(ungrounded),
            "grounded_pct": round(100 * len(grounded) / n, 1) if n else 0.0,
        },
        "states": dict(counts),
        "grounded_accuracy": wilson_str(g_correct, len(grounded)) if grounded else None,
        "grounded_abstention": f"{g_abstained}/{len(grounded)}" if grounded else None,
        "ungrounded_answered": f"{u_answered}/{len(ungrounded)}" if ungrounded else None,
        "ungrounded_abstention": f"{u_abstained}/{len(ungrounded)}" if ungrounded else None,
        "by_category": {c: dict(v) for c, v in by_cat.items()},
        "items": rows,
    }
    out = Path(args.out) if args.out else Path(args.results).with_suffix(".score.json")
    out.write_text(json.dumps(report, indent=1) + "\n")

    print(f"items {n}  coverage {report['coverage']['grounded_pct']}% grounded")
    print("states:", dict(counts))
    if grounded:
        print(f"grounded accuracy: {report['grounded_accuracy']}  abstained {report['grounded_abstention']}")
    if ungrounded:
        print(f"ungrounded: answered {report['ungrounded_answered']}, abstained {report['ungrounded_abstention']}")
    for c, v in sorted(by_cat.items()):
        print(f"  {c:16s} {dict(v)}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
