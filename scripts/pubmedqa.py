#!/usr/bin/env python3
"""Gate 1 — PubMedQA: can it read a paper's abstract and answer from it?

Data is the HF datasets-server row dump already on disk (1000 items, full context).
Fixed sample of 200, seed recorded. No scaffolding beyond the 60-word budget.

Gate: >=70% (4B medical models sit at 71-77%). Below the gate, single-shot document
reading is capped; retrieval design is unchanged.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config, llm  # noqa: E402
from materia.stats import wilson_str  # noqa: E402

LABELS = {"yes": "YES", "no": "NO", "maybe": "MAYBE"}


def load_items(n: int, seed: int) -> list[dict]:
    rows: list[dict] = []
    for f in sorted(config.DATA_DIR.glob("pubmedqa_*.json")):
        data = json.loads(f.read_text())
        rows += [r["row"] for r in data["rows"]]
    rng = random.Random(seed)
    rng.shuffle(rows)
    out = []
    for r in rows[:n]:
        ctx = r.get("context") or {}
        contexts = ctx.get("contexts") if isinstance(ctx, dict) else None
        if not contexts:
            continue
        out.append(
            {
                "pubid": str(r["pubid"]),
                "question": r["question"],
                "context": "\n".join(contexts),
                "gold": LABELS.get(str(r.get("final_decision", "")).lower()),
            }
        )
    return [x for x in out if x["gold"]]


def build_prompt(item: dict) -> str:
    return (
        config.RULE_BUDGET.replace(
            "replying with ONLY the letter of the single best option (A, B, C or D)",
            "replying with ONLY one word: YES, NO or MAYBE",
        )
        .replace("Answer:", "")
        + "\n\nABSTRACT\n"
        + item["context"][:6000]
        + "\n\nQUESTION\n"
        + item["question"]
        + "\n\nAnswer with one word (YES, NO or MAYBE):"
    )


def parse_answer(text: str) -> str | None:
    up = (text or "").upper()
    for label in ("MAYBE", "YES", "NO"):
        if label in up:
            return label
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20261028)
    ap.add_argument("--max-tokens", type=int, default=768)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", default=str(config.RESULTS_DIR / "pubmedqa_200.jsonl"))
    args = ap.parse_args(argv)

    items = load_items(args.n, args.seed)
    llm.ensure_reason(ctx=8192, parallel=args.workers)

    out = Path(args.out)
    fh = open(out, "w")
    t0 = time.time()

    def work(item: dict) -> None:
        r = llm.chat(
            [{"role": "user", "content": build_prompt(item)}],
            max_tokens=args.max_tokens,
            timeout=1200,
        )
        rec = {
            "pubid": item["pubid"],
            "gold": item["gold"],
            "got": parse_answer(r["text"]),
            "text": r["text"][:200],
            "reason": r["reasoning"][:400],
            "finish": r["finish"],
            "ctok": r["ctok"],
            "condition": "pubmedqa_200",
            "max_tokens": args.max_tokens,
            "model_gguf": str(config.REASON_GGUF),
            "command": " ".join([sys.executable, *sys.argv]),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        fh.write(json.dumps(rec) + "\n")
        fh.flush()

    for i in range(0, len(items), 20):
        batch = items[i : i + 20]
        if i and llm.guard_rss(ctx=8192, parallel=args.workers):
            print("[guard] restarted server at ctx=8192", flush=True)
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            list(ex.map(work, batch))
        print(f"  {min(i + 20, len(items))}/{len(items)}", flush=True)
    fh.close()

    recs = [json.loads(line) for line in open(out) if line.strip()]
    correct = sum(1 for r in recs if r["got"] == r["gold"])
    answered = sum(1 for r in recs if r["got"])
    capped = sum(1 for r in recs if r["finish"] == "length")
    result = {
        "condition": "PubMedQA (200, seeded sample)",
        "file": str(out.relative_to(config.ROOT)),
        "seed": args.seed,
        "n": len(recs),
        "correct": correct,
        "pct": round(100 * correct / len(recs), 1),
        "ci95": [round(x, 1) for x in _wilson(correct, len(recs))],
        "answered": answered,
        "hit_token_cap": capped,
        "mean_ctok": round(sum(r["ctok"] for r in recs) / max(1, len(recs))),
        "minutes": round((time.time() - t0) / 60, 1),
        "gate": ">=70%",
        "pass": 100 * correct / len(recs) >= 70,
        "model_gguf": str(config.REASON_GGUF),
        "command": " ".join([sys.executable, *sys.argv]),
    }
    out.with_suffix(".summary.json").write_text(json.dumps(result, indent=1) + "\n")
    print(f"PubMedQA: {wilson_str(correct, len(recs))} | answered {answered}/{len(recs)} | capped {capped} "
          f"| {result['minutes']} min")
    return 0 if result["pass"] else 1


def _wilson(k: int, n: int):
    from materia.stats import wilson

    return wilson(k, n)


if __name__ == "__main__":
    raise SystemExit(main())
