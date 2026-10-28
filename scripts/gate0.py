#!/usr/bin/env python3
"""Gate 0 — does the OCR path survive a real lab report?

Metrics are field-level and the pass condition is asymmetric: a missing field is a
review item, a *silently wrong* numeric field is a fail. That is the whole point of the
gate (HANDOVER §6, Gate 0).

Usage:
    python scripts/gate0.py --image samples/pages/nutripath-p2.png \
        --truth samples/ground_truth/nutripath-p2.json --pdf samples/raw/nutripath-aminoacids.pdf
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config, extract, llm, ocr  # noqa: E402
from materia.stats import wilson_str  # noqa: E402


def norm(s: str) -> str:
    s = (s or "").lower().replace("µ", "u").replace("μ", "u")
    s = re.sub(r"[^a-z0-9/ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def compare(predicted: list[dict], truth: dict) -> dict:
    trows = {norm(r["analyte"]): r for r in truth["rows"]}
    prows = {norm(r["analyte"]): r for r in predicted if r.get("analyte")}

    matched, missing, spurious, wrong_value, wrong_ref, silent_wrong = [], [], [], [], [], []
    for key, t in trows.items():
        p = prows.get(key)
        if not p:
            missing.append(t["analyte"])
            continue
        matched.append(t["analyte"])
        value_ok = p.get("value") is not None and abs(float(p["value"]) - float(t["value"])) < 1e-9
        ref_ok = (
            p.get("ref_low") is not None
            and p.get("ref_high") is not None
            and abs(p["ref_low"] - t["ref_low"]) < 1e-9
            and abs(p["ref_high"] - t["ref_high"]) < 1e-9
        )
        issues = extract.check(p, collected_at=truth.get("collected_at"))
        if not value_ok:
            wrong_value.append(
                {"analyte": t["analyte"], "expected": t["value"], "got": p.get("value"), "issues": issues}
            )
            if not issues:
                silent_wrong.append(t["analyte"])
        if not ref_ok:
            wrong_ref.append(
                {"analyte": t["analyte"], "expected": [t["ref_low"], t["ref_high"]],
                 "got": [p.get("ref_low"), p.get("ref_high")]}
            )
    for key, p in prows.items():
        if key not in trows:
            spurious.append(p["analyte"])

    n = len(trows)
    values_correct = n - len(wrong_value) - len(missing)
    refs_correct = n - len(wrong_ref) - len(missing)
    return {
        "rows_expected": n,
        "rows_found": len(prows),
        "matched": len(matched),
        "missing": missing,
        "spurious": spurious,
        "wrong_value": wrong_value,
        "wrong_ref": wrong_ref,
        "silent_wrong": silent_wrong,
        "value_accuracy": values_correct / n if n else 0.0,
        "ref_accuracy": refs_correct / n if n else 0.0,
        "value_accuracy_str": wilson_str(values_correct, n),
        "ref_accuracy_str": wilson_str(refs_correct, n),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--pdf", default="")
    ap.add_argument("--out", default=None)
    ap.add_argument("--label", default="clean")
    ap.add_argument("--reuse", default="", help="reuse raw OCR text from a previous result JSON")
    args = ap.parse_args()

    truth = json.loads(Path(args.truth).read_text())
    llm.ensure_ocr()
    t0 = time.time()
    if args.reuse:
        prior = json.loads(Path(args.reuse).read_text())
        page = {"text": prior["raw_otsl"], "ctok": prior.get("ocr_tokens"),
                "finish": prior.get("ocr_finish"), "truncated": prior.get("ocr_truncated")}
        raw = page["text"]
        elapsed = 0.0
    else:
        page = ocr.ocr_page(args.image, mode="table", max_tokens=3000)
        raw = page["text"]
        elapsed = time.time() - t0

    rows = ocr.parse_otsl(raw)
    predicted = ocr.extract_lab_rows(rows)
    result = compare(predicted, truth)

    # Two-read cross-check: the text layer is a second, independent read. On this
    # document it is structurally scrambled, so the check is completeness of the
    # numbers, not row alignment.
    two_read = {}
    if args.pdf:
        tl = ocr.pdf_text(args.pdf)
        def canon(ns):
            out = set()
            for n in ns:
                try:
                    out.add(str(float(n)))
                except ValueError:
                    pass
            return out

        truth_numbers = canon(
            {r["value"] for r in truth["rows"]}
            | {r[k] for r in truth["rows"] for k in ("ref_low", "ref_high")}
        )
        in_text = canon(ocr.numbers_in(tl))
        in_ocr = canon(ocr.numbers_in(raw))
        two_read = {
            "truth_numbers": len(truth_numbers),
            "found_in_text_layer": len(truth_numbers & in_text),
            "found_in_ocr": len(truth_numbers & in_ocr),
            "text_layer_structurally_usable": False,
            "note": "text layer present but column order scrambled; completeness check only",
        }

    result.update(
        {
            "label": args.label,
            "image": args.image,
            "ocr_seconds": round(elapsed, 1),
            "ocr_tokens": page.get("ctok"),
            "ocr_finish": page.get("finish"),
            "ocr_truncated": page.get("truncated"),
            "model": str(config.OCR_GGUF),
            "two_read": two_read,
            "pass_value": result["value_accuracy"] == 1.0 and not result["silent_wrong"],
            "pass_silent": not result["silent_wrong"],
        }
    )

    out = Path(args.out) if args.out else config.RESULTS_DIR / f"gate0_{args.label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**result, "raw_otsl": raw, "predicted": predicted}, indent=1) + "\n")

    print(f"[{args.label}] {args.image}")
    print(f"  rows: {result['rows_found']} found / {result['rows_expected']} expected, {result['matched']} matched")
    print(f"  values: {result['value_accuracy_str']}")
    print(f"  ref intervals: {result['ref_accuracy_str']}")
    print(f"  missing: {result['missing']}")
    print(f"  spurious: {result['spurious']}")
    print(f"  silent wrong: {result['silent_wrong']}")
    print(f"  wrong value: {[w['analyte'] for w in result['wrong_value']]}")
    if two_read:
        print(f"  two-read: text layer {two_read['found_in_text_layer']}/{two_read['truth_numbers']}, "
              f"OCR {two_read['found_in_ocr']}/{two_read['truth_numbers']}")
    print(f"  {result['ocr_seconds']}s, {result['ocr_tokens']} tokens, finish={result['ocr_finish']}, "
          f"truncated={result['ocr_truncated']} -> {out}")
    return 0 if result["pass_value"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
