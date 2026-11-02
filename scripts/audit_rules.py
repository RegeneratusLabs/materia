#!/usr/bin/env python3
"""Audit the recommendation graph: citations, doses, freshness, and gaps.

This is a maintenance report, not a clinical validation. It answers: does every rule
resolve to a document, how old is the evidence, and which rules are missing a dose or a
citation? Exit code is non-zero if any rule fails the contract checks.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia.clinical import load_critical_values, load_patterns
from materia.recommend import load_recommendations, open_corpus, validate_rule

CURRENT_YEAR = 2026
STALE_YEARS = 5


def _chunk(conn: sqlite3.Connection, cid: str) -> dict | None:
    row = conn.execute(
        """SELECT c.chunk_id, c.text, c.section, d.source, d.tier, d.date, d.title
           FROM chunks c JOIN docs d ON d.doc_id = c.doc_id WHERE c.chunk_id = ?""",
        (cid,),
    ).fetchone()
    return dict(row) if row else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="corpus/index.sqlite")
    ap.add_argument("--out", default="docs/rules-audit.md")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    conn = open_corpus(args.index)
    patterns = load_patterns()
    rules = load_recommendations()
    critical = load_critical_values()

    pattern_by_id = {p["id"]: p for p in patterns}
    issues: list[str] = []
    stale: list[dict] = []
    option_rows = []
    for rule in rules:
        rule_issues = validate_rule(rule, conn)
        issues += [f"{rule['id']}: {x}" for x in rule_issues]
        dose = rule.get("dose") or {}
        dose_ids = dose.get("chunks") or ([dose["chunk"]] if dose.get("chunk") else [])
        dose_docs = [d for cid in dose_ids if (d := _chunk(conn, cid))]
        evidence = [d for cid in (rule.get("evidence") or []) if (d := _chunk(conn, cid))]
        years = []
        for doc in dose_docs + evidence:
            try:
                years.append(int(str(doc["date"])[:4]))
            except ValueError:
                pass
        oldest = min(years) if years else None
        if oldest is not None and CURRENT_YEAR - oldest > STALE_YEARS:
            stale.append({"rule": rule["id"], "oldest": oldest})
        option_rows.append({
            "id": rule["id"], "pattern": rule["pattern"],
            "kind": rule.get("kind", "nutrient"), "grade": rule.get("grade", "?"),
            "dose": dose.get("text") or None,
            "dose_source": dose_docs[0]["source"] if dose_docs else None,
            "evidence": len(evidence), "oldest": oldest,
            "issues": rule_issues,
        })

    pattern_rows = []
    for pattern in patterns:
        cited = []
        for cid in pattern.get("citations") or []:
            doc = _chunk(conn, cid)
            if doc:
                cited.append(doc)
            else:
                issues.append(f"{pattern['id']}: missing citation {cid}")
        pattern_rows.append({
            "id": pattern["id"], "label": pattern["label"],
            "severity": pattern.get("severity"), "citations": len(cited),
        })

    critical_issues = []
    for value in critical:
        cid = value.get("citation") or ""
        if not _chunk(conn, cid):
            critical_issues.append(f"{value['analyte']}: missing critical citation {cid}")
    issues += critical_issues

    payload = {
        "patterns": pattern_rows,
        "options": option_rows,
        "critical_values": len(critical),
        "issues": issues,
        "stale": stale,
        "grades": dict(Counter(r.get("grade", "?") for r in rules)),
        "kinds": dict(Counter(r.get("kind", "nutrient") for r in rules)),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        lines = [
            "# materia — rule audit",
            "",
            f"**Patterns:** {len(patterns)} · **Options:** {len(rules)} · **Critical values:** {len(critical)}",
            f"**Grades:** {payload['grades']} · **Kinds:** {payload['kinds']}",
            f"**Stale evidence (> {STALE_YEARS} years):** {len(stale)}",
            "",
            "## Options",
            "",
            "| option | pattern | kind | grade | dose | dose source | evidence | oldest |",
            "|---|---|---|---|---|---|---:|---:|",
        ]
        for row in option_rows:
            lines.append(
                f"| {row['id']} | {row['pattern']} | {row['kind']} | {row['grade']} | "
                f"{row['dose'] or '—'} | {row['dose_source'] or '—'} | {row['evidence']} | "
                f"{row['oldest'] or '—'} |"
            )
        lines += ["", "## Stale evidence", ""]
        if stale:
            for item in stale:
                lines.append(f"- `{item['rule']}` — oldest source {item['oldest']}")
        else:
            lines.append("None.")
        lines += ["", "## Contract issues", ""]
        lines += [f"- {x}" for x in issues] or ["None."]
        out = Path(args.out)
        out.write_text("\n".join(lines) + "\n")
        print(f"wrote {out} ({len(rules)} options, {len(patterns)} patterns, {len(issues)} issues)")
        print(f"stale: {len(stale)}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
