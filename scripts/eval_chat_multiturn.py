#!/usr/bin/env python3
"""Evaluate multi-turn grounded chat.

Each case builds one assessment, then asks follow-up questions with prior turns in history.
The contract is the same as the single-turn set: grounded, cited, required phrase present.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config
from materia.chat import answer
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/chat_multiturn.json")
    ap.add_argument("--no-model", action="store_true")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if args.base_url:
        config.CHAT_BASE_URL = args.base_url
    if args.model:
        config.CHAT_MODEL = args.model
    use_model = not args.no_model and bool(config.CHAT_BASE_URL)
    data = json.loads(Path(args.data).read_text())
    conn = open_corpus()
    rows = []
    for case in data["cases"]:
        assessment = recommend(case["rows"], intake=case.get("intake") or {}, conn=conn).as_dict()
        history = []
        for index, turn in enumerate(case["turns"], start=1):
            result = answer(turn["question"], assessment, use_model=use_model, history=history)
            text = (result.get("answer") or "").lower()
            missing = [s for s in turn.get("must_include") or [] if s.lower() not in text]
            for group in turn.get("must_include_any") or []:
                if not any(s.lower() in text for s in group):
                    missing.append("one of: " + ", ".join(group))
            forbidden = [s for s in turn.get("must_not_include") or [] if s.lower() in text]
            cited = bool(result.get("citations"))
            if result.get("mode") == "model":
                cited = cited and ("#" in text)
            ok = not missing and not forbidden and result.get("grounded") is True and cited
            rows.append({"case": case["id"], "turn": index, "mode": result.get("mode"),
                         "ok": ok, "missing": missing, "forbidden": forbidden})
            print(f"{'PASS' if ok else 'FAIL'} {case['id']}#{index} mode={result.get('mode'):12s} "
                  f"missing={missing or '-'} forbidden={forbidden or '-'}")
            history.append({"role": "user", "text": turn["question"]})
            history.append({"role": "bot", "text": result.get("answer", "")})
    n = len(rows)
    k = sum(1 for r in rows if r["ok"])
    lo, hi = wilson(k, n)
    modes = {}
    for r in rows:
        modes[r["mode"]] = modes.get(r["mode"], 0) + 1
    print(f"\nmulti-turn chat: {k}/{n} = {k / n:.1%} [{lo:.1%}, {hi:.1%}]  "
          f"mode={'model' if use_model else 'deterministic'}  modes={modes}")
    if args.out:
        Path(args.out).write_text(json.dumps({
            "n": n, "passed": k, "pct": round(100 * k / n, 1),
            "ci95": [round(100 * lo, 1), round(100 * hi, 1)],
            "model": config.CHAT_MODEL if use_model else "deterministic",
            "base_url": config.CHAT_BASE_URL if use_model else "",
            "modes": modes, "rows": rows,
        }, indent=2) + "\n")
    return 0 if k == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
