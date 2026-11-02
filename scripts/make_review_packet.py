#!/usr/bin/env python3
"""Build a practitioner review packet from the contract vignettes.

The engine's output is a proposal. This packet asks a clinician to label each case:
agree / unsafe / missing / notes. Those labels are the calibration and safety set; they
are not inferred from the engine's own answers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia.recommend import open_corpus, recommend


def main() -> int:
    data = json.loads(Path("data/clinical_vignettes.json").read_text())
    conn = open_corpus()
    out = Path("docs/practitioner-review.md")
    review_cases = [c for c in data["cases"] if c.get("review", True)]
    lines = [
        "# materia — practitioner review packet",
        "",
        "**Status:** generated from synthetic vignettes, not patient data. ",
        f"**Cases:** {len(review_cases)}. **Engine:** current `main` rules.",
        "",
        "**Reviewer:** ______________________  **Date:** ______________",
        "",
        "## How to review",
        "",
        "For each case, mark one: **agree**, **unsafe**, or **missing**.",
        "- **agree**: the top option is clinically reasonable and safe for this context.",
        "- **unsafe**: the option or dose should not be offered; write why.",
        "- **missing**: a more appropriate option or referral is absent; write it.",
        "",
        "Do not edit the case. The point is to measure the engine, not to make it look right.",
        "The ranking is a proposal; a clinician's judgement is the reference standard.",
        "",
    ]
    for case in review_cases:
        a = recommend(case["rows"], intake=case.get("intake") or {}, conn=conn)
        lines += [f"## {case['id']}", "", f"**Intake:** {json.dumps(case.get('intake') or {})}", ""]
        lines += ["| finding | value | unit | lab range | direction |", "|---|---:|---|---|---|"]
        for f in a.findings:
            ref = ""
            if f.ref_low is not None or f.ref_high is not None:
                ref = f"{f.ref_low if f.ref_low is not None else ''}–{f.ref_high if f.ref_high is not None else ''}"
            value = f"{f.value:g}" if f.value is not None else "—"
            lines.append(f"| {f.analyte} | {value} | {f.unit} | {ref} | {f.direction} |")
        lines += ["", "**Patterns:** " + ("; ".join(
            f"{p.label} ({p.status}, {p.confidence:.0%}, {p.severity})" for p in a.patterns
        ) or "none"), ""]
        lines.append("**Options (ranked):**")
        if not a.options:
            lines.append("- none offered")
        for o in a.options:
            dose = o.dose_text or "no dose (lifestyle/referral)"
            flags = "; ".join(o.safety_flags) or "none"
            lines.append(f"- **{o.intervention}** — grade {o.grade}; {dose}; flags: {flags}")
            evidence = ", ".join(e.chunk_id for e in (o.evidence or [])[:3])
            if evidence:
                lines.append(f"  - evidence: {evidence}")
            if o.monitoring_text:
                lines.append(f"  - monitor: {o.monitoring_text}")
        if a.withheld:
            lines.append("**Withheld:** " + "; ".join(f"{w.intervention} ({w.reason})" for w in a.withheld))
        if a.gaps:
            lines.append("**Gaps:** " + "; ".join(f"{g['label']} ({g['reason']})" for g in a.gaps))
        lines += [
            "",
            "**Review:** [ ] agree  [ ] unsafe  [ ] missing  ",
            "**Why / what is missing:** ",
            "",
            "---",
            "",
        ]
    out.write_text("\n".join(lines))
    print(f"wrote {out} ({len(lines)} lines, {len(review_cases)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
