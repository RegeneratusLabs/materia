#!/usr/bin/env python3
"""Gate 4 — symptom workflow behaviour.

Deterministic parts are scored exactly (red-flag recall, emergency stop, safety vetoes).
The generated sheet is checked against the output contract (citations, doses, diagnosis
language, vetoed options). Clinical acceptability is human-scored, not automated.

Usage:
    python scripts/gate4.py --limit 30
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config, llm, symptom  # noqa: E402
from materia.corpus.index import open_index  # noqa: E402
from materia.retrieve import Retriever, group_conflicts  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vignettes", default=str(config.DATA_DIR / "symptom_vignettes.json"))
    ap.add_argument("--index", default=str(config.CORPUS_DIR / "index.sqlite"))
    ap.add_argument("--out", default=str(config.RESULTS_DIR / "gate4.json"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--max-tokens", type=int, default=900)
    args = ap.parse_args(argv)

    rules = symptom.load_rules()
    conn = open_index(args.index)
    retriever = Retriever(conn, k=args.k, per_doc=2)
    vignettes = json.loads(Path(args.vignettes).read_text())["vignettes"]
    if args.limit:
        vignettes = vignettes[: args.limit]

    llm.ensure_reason(ctx=8192, parallel=2)

    records = []
    t0 = time.time()
    for n, v in enumerate(vignettes, start=1):
        intake = symptom.parse_intake(v["text"])
        red_hits = symptom.red_flag_check(v["text"], rules["red_flags"])

        if red_hits and red_hits[0]["urgency"] == "emergency":
            records.append(
                {
                    "id": v["id"],
                    "kind": v["kind"],
                    "stopped": True,
                    "red_flags": [h["id"] for h in red_hits],
                    "contract_issues": [],
                    "model_called": False,
                }
            )
            print(f"[{n}/{len(vignettes)}] {v['id']} STOPPED ({red_hits[0]['id']})", flush=True)
            continue

        chunks = retriever.search(v["text"])
        interventions = symptom.candidate_interventions(v["text"], chunks, retriever.lex)
        findings = symptom.safety_screen(intake, interventions, conn, rules["safety"])
        prompt = symptom.build_prompt(v["text"], chunks, findings, red_hits, intake)
        r = llm.chat([{"role": "user", "content": prompt}], max_tokens=args.max_tokens, timeout=1200)
        issues = symptom.contract_check(r["text"], chunks, findings)
        records.append(
            {
                "id": v["id"],
                "kind": v["kind"],
                "stopped": False,
                "red_flags": [h["id"] for h in red_hits],
                "intake": intake.as_dict(),
                "interventions": interventions,
                "findings": findings,
                "contract_issues": issues,
                "conflicts": group_conflicts(chunks),
                "sheet": r["text"],
                "finish": r["finish"],
                "ctok": r["ctok"],
                "model_called": True,
            }
        )
        print(f"[{n}/{len(vignettes)}] {v['id']} issues={len(issues)} finish={r['finish']}", flush=True)

    # deterministic expectations
    rf_expected = [v for v in vignettes if v.get("expect", {}).get("red_flags")]
    rf_hit = sum(
        1
        for v in rf_expected
        if set(v["expect"]["red_flags"]) & set(
            next(r for r in records if r["id"] == v["id"])["red_flags"]
        )
    )
    emergency = [v for v in vignettes if v.get("expect", {}).get("emergency")]
    emergency_stopped = sum(
        1 for v in emergency if next(r for r in records if r["id"] == v["id"])["stopped"]
    )
    veto_expected = [(v, v["expect"]["must_veto"]) for v in vignettes if v.get("expect", {}).get("must_veto")]
    veto_ok = 0
    for v, wanted in veto_expected:
        rec = next(r for r in records if r["id"] == v["id"])
        got = {f["intervention"].lower() for f in rec.get("findings", []) if f["severity"] == "veto"}
        if all(any(w.split()[0] in g for g in got) for w in wanted):
            veto_ok += 1

    generated = [r for r in records if r["model_called"]]
    clean = [r for r in generated if not r["contract_issues"]]
    summary = {
        "n": len(records),
        "generated": len(generated),
        "stopped_on_emergency": len([r for r in records if r["stopped"]]),
        "red_flag_cases": len(rf_expected),
        "red_flag_matched": rf_hit,
        "emergency_cases": len(emergency),
        "emergency_stopped": emergency_stopped,
        "veto_cases": len(veto_expected),
        "veto_ok": veto_ok,
        "contract_clean": len(clean),
        "contract_violations": sum(len(r["contract_issues"]) for r in generated),
        "minutes": round((time.time() - t0) / 60, 1),
        "model": str(config.REASON_GGUF),
    }
    Path(args.out).write_text(json.dumps({"summary": summary, "records": records}, indent=1) + "\n")

    print("\nGate 4")
    print(f"  red-flag matched:    {rf_hit}/{len(rf_expected)}")
    print(f"  emergency stopped:   {emergency_stopped}/{len(emergency)}")
    print(f"  vetoes correct:      {veto_ok}/{len(veto_expected)}")
    print(f"  contract-clean:      {len(clean)}/{len(generated)} ({summary['contract_violations']} violations)")
    print(f"  {summary['minutes']} min -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
