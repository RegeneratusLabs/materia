#!/usr/bin/env python3
"""Write a blank CSV label sheet for the clinician review subset.

The clinician fills decision/reason in a spreadsheet, then:
    python scripts/import_reviews.py docs/review-labels.csv

Columns: case_id, option_id, decision, reason, reviewer.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia.recommend import open_corpus, recommend


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/review-labels.csv")
    ap.add_argument("--include-boundary", action="store_true",
                    help="include the non-review boundary cases too")
    args = ap.parse_args()
    data = json.loads(Path("data/clinical_vignettes.json").read_text())
    cases = [c for c in data["cases"] if args.include_boundary or c.get("review", True)]
    conn = open_corpus()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["case_id", "option_id", "decision", "reason", "reviewer"])
        for case in cases:
            assessment = recommend(case["rows"], intake=case.get("intake") or {}, conn=conn)
            option_id = assessment.options[0].id if assessment.options else "none"
            writer.writerow([case["id"], option_id, "", "", ""])
    print(f"wrote {out} ({len(cases)} rows; fill decision/reason/reviewer)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
