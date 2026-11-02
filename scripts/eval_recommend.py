#!/usr/bin/env python3
"""Evaluate the recommendation engine on synthetic contract vignettes.

This is not a clinical validation set. It measures the invariants the engine claims:
pattern match, top-option agreement, withheld options, safety flags, citation integrity.
Success is reported with n and a 95% Wilson interval.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia.recommend import open_corpus, recommend


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def main() -> int:
    data = json.loads(Path("data/clinical_vignettes.json").read_text())
    conn = open_corpus()
    rows = []
    for case in data["cases"]:
        a = recommend(case["rows"], intake=case.get("intake") or {}, conn=conn)
        actual_patterns = {p.id for p in a.patterns}
        expected_patterns = set(case.get("expect_patterns") or [])
        pattern_ok = expected_patterns <= actual_patterns
        top = a.options[0].id if a.options else None
        top_ok = top == case.get("expect_top")
        withheld = {w.id for w in a.withheld}
        withheld_ok = set(case.get("expect_withheld") or []) <= withheld
        alerts = {x.get("canonical") for x in a.critical_alerts}
        alerts_ok = set(case.get("expect_alerts") or []) == alerts
        age_groups = {x.get("canonical"): x.get("age_group") for x in a.critical_alerts}
        age_ok = all(age_groups.get(k) == v for k, v in (case.get("expect_age_groups") or {}).items())
        flags_ok = True
        for oid, wanted in (case.get("expect_flags") or {}).items():
            option = next((o for o in a.options if o.id == oid), None)
            if option is None or not set(wanted) <= set(option.safety_flags):
                flags_ok = False
                break
        severity_ok = True
        for pid, wanted in (case.get("expect_severity") or {}).items():
            pat = next((p for p in a.patterns if p.id == pid), None)
            if pat is None or pat.severity != wanted:
                severity_ok = False
                break
        gap_ok = True
        if case.get("expect_gap"):
            gap_ok = any(g["pattern"] == case["expect_gap"] for g in a.gaps)
        citations_ok = all(
            o.evidence and (o.dose_chunk or o.kind in ("lifestyle", "referral"))
            for o in a.options
        )
        row = {
            "id": case["id"], "patterns": sorted(actual_patterns), "top": top,
            "withheld": sorted(withheld), "flags": {o.id: o.safety_flags for o in a.options},
            "pattern_ok": pattern_ok, "top_ok": top_ok, "withheld_ok": withheld_ok,
            "flags_ok": flags_ok, "gap_ok": gap_ok, "severity_ok": severity_ok,
            "alerts_ok": alerts_ok, "age_ok": age_ok, "citations_ok": citations_ok,
        }
        rows.append(row)
        mark = "PASS" if all(row[k] for k in ("pattern_ok", "top_ok", "withheld_ok", "flags_ok", "gap_ok", "severity_ok", "alerts_ok", "age_ok", "citations_ok")) else "FAIL"
        print(f"{mark} {case['id']:38s} top={top or '-':24s} patterns={','.join(sorted(actual_patterns)) or '-'}")

    n = len(rows)
    checks = ["pattern_ok", "top_ok", "withheld_ok", "flags_ok", "gap_ok", "severity_ok", "alerts_ok", "age_ok", "citations_ok"]
    print()
    for key in checks:
        k = sum(1 for r in rows if r[key])
        lo, hi = wilson(k, n)
        print(f"{key:14s} {k}/{n} = {k / n:.1%} [{lo:.1%}, {hi:.1%}]")
    overall = sum(1 for r in rows if all(r[k] for k in checks))
    lo, hi = wilson(overall, n)
    print(f"{'all':14s} {overall}/{n} = {overall / n:.1%} [{lo:.1%}, {hi:.1%}]")
    return 0 if overall == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
