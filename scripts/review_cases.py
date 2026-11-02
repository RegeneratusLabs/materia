#!/usr/bin/env python3
"""Interactive clinician review of the contract vignettes.

Prints one case at a time with the engine's proposal, then records agree/unsafe/missing
to a local JSONL file. This is the reference-standard workflow; the engine does not grade
itself.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import __version__
from materia.recommend import open_corpus, recommend, rules_fingerprint


def _line(label: str, value: str) -> str:
    return f"  {label:14s} {value}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/clinical_vignettes.json")
    ap.add_argument("--out", default=str(Path.home() / ".materia" / "reviews.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--reviewer", default=os.environ.get("MATERIA_REVIEWER", ""))
    args = ap.parse_args()
    data = json.loads(Path(args.data).read_text())
    cases = data["cases"][: args.limit or None]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    conn = open_corpus()
    counts = Counter()
    print(f"Reviewing {len(cases)} cases. a=agree u=unsafe m=missing s=skip q=quit\n")
    for index, case in enumerate(cases, start=1):
        a = recommend(case["rows"], intake=case.get("intake") or {}, conn=conn)
        print("=" * 72)
        print(f"[{index}/{len(cases)}] {case['id']}  intake={json.dumps(case.get('intake') or {})}")
        for f in a.findings:
            ref = ""
            if f.ref_low is not None or f.ref_high is not None:
                ref = f"lab {f.ref_low if f.ref_low is not None else ''}–{f.ref_high if f.ref_high is not None else ''}"
            print(_line(f.analyte, f"{f.value:g} {f.unit}  {f.direction}  {ref}"))
        print("  patterns:")
        for p in a.patterns:
            print(f"    - {p.label}: {p.status} ({p.confidence:.0%}), {p.severity}")
        print("  options:")
        for o in a.options:
            print(f"    - {o.intervention} [{o.grade}] {o.dose_text or 'no dose'}")
            if o.safety_flags:
                print(f"      flags: {'; '.join(o.safety_flags)}")
        if a.withheld:
            print("  withheld: " + "; ".join(f"{w.intervention} ({w.reason})" for w in a.withheld))
        if not a.patterns:
            print("  (no pattern matched)")
        while True:
            answer = input("  decision [a/u/m/s/q]: ").strip().lower()
            if answer in {"a", "u", "m", "s", "q"}:
                break
        if answer == "q":
            break
        if answer == "s":
            counts["skip"] += 1
            continue
        decision = {"a": "accept", "u": "unsafe", "m": "missing"}[answer]
        reason = input("  why / what is missing (optional): ").strip()
        row = {
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "case_id": case["id"],
            "option_id": a.options[0].id if a.options else "none",
            "decision": decision,
            "reason": reason,
            "reviewer": args.reviewer,
            "engine_version": __version__,
            "rules_hash": rules_fingerprint(),
        }
        with out.open("a") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        counts[decision] += 1
        print(f"  saved {decision}. total: {dict(counts)}\n")
    print(f"\nwrote {out}")
    print(f"counts: {dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
