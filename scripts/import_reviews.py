#!/usr/bin/env python3
"""Import clinician labels from CSV into the same JSONL format as the web review mode.

CSV columns: case_id, decision, option_id (optional), reason (optional), reviewer (optional).
Decisions: accept, reject, unsafe, modify, missing, skip.

This lets a clinician work in a spreadsheet without running the local app. Labels are tied to
the engine version and rule hash, exactly like the web/CLI labels.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import __version__
from materia.recommend import open_corpus, recommend, rules_fingerprint

DECISIONS = {"accept", "reject", "unsafe", "modify", "missing", "skip"}


def build_rows(csv_path: Path, *, reviewer: str = "", allow_unknown: bool = False) -> tuple[list[dict], list[str]]:
    cases = json.loads(Path("data/clinical_vignettes.json").read_text())["cases"]
    by_id = {c["id"]: c for c in cases}
    conn = open_corpus()
    rows: list[dict] = []
    errors: list[str] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        for line_no, raw in enumerate(csv.DictReader(fh), start=2):
            case_id = (raw.get("case_id") or "").strip()
            decision = (raw.get("decision") or "").strip().lower()
            if not case_id:
                errors.append(f"line {line_no}: missing case_id")
                continue
            if decision not in DECISIONS:
                errors.append(f"line {line_no}: decision must be one of {sorted(DECISIONS)}")
                continue
            case = by_id.get(case_id)
            if case is None and not allow_unknown:
                errors.append(f"line {line_no}: unknown case_id {case_id!r}")
                continue
            option_id = (raw.get("option_id") or "").strip()
            if not option_id and case is not None:
                assessment = recommend(case["rows"], intake=case.get("intake") or {}, conn=conn)
                option_id = assessment.options[0].id if assessment.options else "none"
            rows.append({
                "case_id": case_id,
                "option_id": option_id or "none",
                "decision": decision,
                "reason": (raw.get("reason") or "").strip()[:300],
                "reviewer": (raw.get("reviewer") or reviewer).strip()[:120],
                "engine_version": __version__,
                "rules_hash": rules_fingerprint(),
            })
    return rows, errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--out", default=str(Path.home() / ".materia" / "reviews.jsonl"))
    ap.add_argument("--reviewer", default=os.environ.get("MATERIA_REVIEWER", ""))
    ap.add_argument("--allow-unknown", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    rows, errors = build_rows(args.csv, reviewer=args.reviewer, allow_unknown=args.allow_unknown)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 2
    if args.dry_run:
        from collections import Counter
        print(f"would import {len(rows)} labels: {dict(Counter(r['decision'] for r in rows))}")
        return 0
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"imported {len(rows)} labels into {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
