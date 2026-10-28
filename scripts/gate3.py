#!/usr/bin/env python3
"""Gate 3 — did retrieval help, hold, or hurt?

Paired comparison against the closed-book baseline on the identical 104 items, plus a
traceability check: every citation the model emits must point at a chunk that was
actually in its context. Per-category breakdown and exact McNemar.

Usage:
    python scripts/gate3.py --baseline results/v2_budget_768.jsonl \
        --retrieval results/panel_retrieval_768.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config  # noqa: E402
from materia.stats import wilson_str  # noqa: E402


def load(path: Path) -> dict[str, dict]:
    return {r["id"]: r for r in (json.loads(line) for line in open(path) if line.strip())}


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return min(1.0, 2 * tail)


def correctness(rec: dict) -> int:
    return 1 if rec.get("got") and rec.get("got") == rec.get("gold") else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default=str(config.RESULTS_DIR / "v2_budget_768.jsonl"))
    ap.add_argument("--retrieval", default=str(config.RESULTS_DIR / "panel_retrieval_768.jsonl"))
    ap.add_argument("--out", default=str(config.RESULTS_DIR / "gate3.json"))
    args = ap.parse_args(argv)

    base = load(Path(args.baseline))
    ret = load(Path(args.retrieval))
    ids = sorted(set(base) & set(ret))

    kb = sum(correctness(base[i]) for i in ids)
    kr = sum(correctness(ret[i]) for i in ids)
    fixed = [i for i in ids if not correctness(base[i]) and correctness(ret[i])]
    broke = [i for i in ids if correctness(base[i]) and not correctness(ret[i])]
    p = mcnemar_exact(len(fixed), len(broke))

    # traceability: cited S-ids must map onto the retrieved list for that item
    cited_total = cited_valid = answered_with_cite = 0
    for i in ids:
        r = ret[i]
        retrieved = r.get("retrieved") or []
        cites = r.get("cites") or []
        if cites:
            answered_with_cite += 1
        for c in cites:
            cited_total += 1
            try:
                idx = int(c[1:]) - 1
            except ValueError:
                continue
            if 0 <= idx < len(retrieved):
                cited_valid += 1

    def by_cat(recs: dict[str, dict]) -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        for i in ids:
            cat = recs[i].get("cat", "?")
            out.setdefault(cat, [0, 0])
            out[cat][0] += correctness(recs[i])
            out[cat][1] += 1
        return out

    cat_base, cat_ret = by_cat(base), by_cat(ret)
    cats = {
        c: {
            "n": cat_ret[c][1],
            "baseline": cat_base[c][0],
            "retrieval": cat_ret[c][0],
            "delta": cat_ret[c][0] - cat_base[c][0],
        }
        for c in sorted(cat_ret, key=lambda k: -cat_ret[k][1])
    }

    result = {
        "n": len(ids),
        "baseline": {"correct": kb, "score": wilson_str(kb, len(ids))},
        "retrieval": {"correct": kr, "score": wilson_str(kr, len(ids))},
        "paired": {
            "fixed": len(fixed),
            "broke": len(broke),
            "fixed_ids": fixed,
            "broke_ids": broke,
            "mcnemar_exact_p": round(p, 3),
            "delta_points": round(100 * (kr - kb) / len(ids), 1),
        },
        "traceability": {
            "answered_with_citation": answered_with_cite,
            "answered": sum(1 for i in ids if ret[i].get("got")),
            "citations_total": cited_total,
            "citations_in_context": cited_valid,
            "rate": round(cited_valid / cited_total, 3) if cited_total else 0.0,
        },
        "by_category": cats,
        "artifacts": {"baseline": args.baseline, "retrieval": args.retrieval},
    }
    Path(args.out).write_text(json.dumps(result, indent=1) + "\n")

    print(f"items: {len(ids)}")
    print(f"closed-book:  {result['baseline']['score']}")
    print(f"retrieval:    {result['retrieval']['score']}")
    print(f"paired: fixed {len(fixed)}, broke {len(broke)}, McNemar p={p:.3f}, delta {result['paired']['delta_points']:+.1f} pts")
    print(f"traceability: {cited_valid}/{cited_total} citations were in context "
          f"({100 * result['traceability']['rate']:.1f}%); {answered_with_cite}/{result['traceability']['answered']} answers cited")
    print("by category (baseline -> retrieval):")
    for c, d in cats.items():
        print(f"  {c:16s} {d['baseline']:2d}/{d['n']:2d} -> {d['retrieval']:2d}/{d['n']:2d}  ({d['delta']:+d})")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
