#!/usr/bin/env python3
"""Summarise the practitioner labels written by the Plan or Review modes.

No labels exist until a practitioner uses the app. This script is the bridge from those
labels to a calibration and safety report: accept rate per option with n and a 95% Wilson
interval, plus every unsafe/missing case and its reason.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def load(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        row["decision"] = (row.get("decision") or "?").lower()
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=str(Path.home() / ".materia" / "reviews.jsonl"))
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    args = ap.parse_args()
    path = Path(args.path)
    if not path.exists():
        print(f"no review file at {path}; use the Plan view or scripts/review_cases.py first")
        return 0
    rows = load(path)
    if not rows:
        print(f"no labels in {path}")
        return 0

    by_option: dict[str, Counter] = defaultdict(Counter)
    by_case: dict[str, Counter] = defaultdict(Counter)
    attention: list[dict] = []
    for row in rows:
        option = row.get("option_id") or "?"
        case = row.get("case_id") or ""
        decision = row["decision"]
        by_option[option][decision] += 1
        if case:
            by_case[case][decision] += 1
        if decision in ("unsafe", "reject", "missing") and row.get("reason"):
            attention.append({"case": case or "?", "option": option,
                              "decision": decision, "reason": str(row["reason"])[:300]})

    reviewers = Counter(row.get("reviewer") or "anonymous" for row in rows)
    hashes = Counter(row.get("rules_hash") or "unknown" for row in rows)
    if args.json:
        payload = {
            "path": str(path),
            "labels": len(rows),
            "cases": len(by_case),
            "decisions": dict(Counter(row["decision"] for row in rows)),
            "reviewers": dict(reviewers),
            "rules_hashes": dict(hashes),
            "options": {k: dict(v) for k, v in sorted(by_option.items())},
            "attention": attention,
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"labels: {len(rows)}  cases: {len(by_case)}  decisions: {dict(Counter(r['decision'] for r in rows))}")
    print(f"reviewers: {dict(reviewers)}  rules: {dict(hashes)}")
    print()
    print(f"{'option':34s} {'accept':>6s} {'reject':>6s} {'unsafe':>6s} {'modify':>6s} {'accept rate':>16s}")
    for option in sorted(by_option):
        c = by_option[option]
        decided = c["accept"] + c["reject"] + c["unsafe"]
        if decided:
            lo, hi = wilson(c["accept"], decided)
            rate = f"{c['accept'] / decided:.0%} [{lo:.0%}, {hi:.0%}]"
        else:
            rate = "—"
        print(f"{option:34s} {c['accept']:6d} {c['reject']:6d} {c['unsafe']:6d} {c['modify']:6d} {rate:>16s}")
    if attention:
        print("\nNEEDS ATTENTION")
        for item in attention:
            print(f"  [{item['decision']}] {item['case']} / {item['option']}: {item['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
