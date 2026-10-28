#!/usr/bin/env python3
"""Re-score a results JSONL using the generation-time `got` field.

DO NOT re-parse the stored `text` / `reason` fields: they are head-truncated at write
time, so a re-parse disagrees with what the model actually answered on any record
whose finish == "length". See HANDOVER.md §8.

Usage:
    python3 docs/rescore.py results/v2_budget.jsonl
    python3 docs/rescore.py results/*.jsonl
"""
import json
import math
import sys
import os


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d * 100, (c + m) / d * 100)


def normalise(rec):
    got = rec.get("got")
    return str(got).upper() if got else None


def main(paths):
    print(f"{'file':34s} {'n':>4s} {'correct':>8s} {'score':>7s}  95% CI          ans  cap")
    for path in paths:
        if not os.path.exists(path):
            print(f"{path}: MISSING")
            continue
        recs = [json.loads(line) for line in open(path) if line.strip()]
        if not recs:
            print(f"{path}: empty")
            continue
        if "gold" not in recs[0]:
            print(f"{os.path.basename(path):34s}    -        -       -   no gold key (free-text probe set)")
            continue
        n = len(recs)
        k = sum(1 for r in recs if normalise(r) == r.get("gold"))
        lo, hi = wilson(k, n)
        answered = sum(1 for r in recs if normalise(r))
        capped = sum(1 for r in recs if r.get("finish") == "length")
        print(f"{os.path.basename(path):34s} {n:4d} {k:8d} {100 * k / n:6.1f}%  "
              f"[{lo:4.1f}, {hi:5.1f}] {answered:4d} {capped:4d}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["results/v2_budget.jsonl"])
