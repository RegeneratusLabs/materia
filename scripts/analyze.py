#!/usr/bin/env python3
import json, glob, os, math, collections

R = os.path.expanduser("~/eval/minicpm-med/results")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d * 100, (c + m) / d * 100)


def load(tag):
    p = os.path.join(R, f"{tag}.jsonl")
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p)]


def report(tag, label):
    recs = load(tag)
    if not recs:
        return None
    k = sum(1 for r in recs if r["got"] == r["gold"])
    lo, hi = wilson(k, len(recs))
    unp = sum(1 for r in recs if not r["got"])
    print(f"{label:28s} {k:4d}/{len(recs):4d}  {100*k/len(recs):5.1f}%  95% CI [{lo:.1f}, {hi:.1f}]  unparsed {unp}")
    return recs


print("=== headline ===")
for tag, label in [("medqa_direct", "MedQA-USMLE (direct)"), ("medqa_think", "MedQA-USMLE (thinking)"),
                   ("herbal_direct", "Herbal/nutrient/lab (direct)"), ("herbal_think", "Herbal/nutrient/lab (thinking)"),
                   ("pubmedqa", "PubMedQA yes/no/maybe")]:
    report(tag, label)

print("\n=== herbal by category ===")
recs = load("herbal_direct")
data = {r["id"]: r for r in json.load(open(os.path.expanduser("~/eval/minicpm-med/data/herbal_set.json")))}
by = collections.defaultdict(lambda: [0, 0])
for r in recs:
    c = data[r["id"]]["cat"]
    by[c][1] += 1
    if r["got"] == r["gold"]:
        by[c][0] += 1
for c, (k, n) in sorted(by.items(), key=lambda x: -x[1][1]):
    lo, hi = wilson(k, n)
    print(f"  {c:16s} {k:2d}/{n:2d}  {100*k/n:5.1f}%  [{lo:.0f},{hi:.0f}]")

print("\n=== herbal errors (direct) ===")
for r in recs:
    if r["got"] != r["gold"]:
        d = data[r["id"]]
        print(f"  {r['id']:4s} gold {r['gold']} got {r['got']}  {d['q'][:90]}")

print("\n=== herbal direct vs think disagreement ===")
dd = {r["id"]: r["got"] for r in load("herbal_direct")}
tt = {r["id"]: r["got"] for r in load("herbal_think")}
flips = [i for i in dd if i in tt and dd[i] != tt[i]]
print(f"  items answered in both: {len(set(dd) & set(tt))}, flips: {len(flips)}")
for i in flips:
    print(f"    {i}: direct={dd[i]} think={tt[i]} gold={data[i]['a']}")

print("\n=== thinking length ===")
for r in load("herbal_think"):
    pass
tt_recs = load("herbal_think")
if tt_recs:
    toks = [r["ctok"] for r in tt_recs]
    print(f"  herbal think completion tokens: mean {sum(toks)/len(toks):.0f}, max {max(toks)}")
    tr = sum(1 for r in tt_recs if r["finish"] == "length")
    print(f"  truncated at max_tokens: {tr}/{len(tt_recs)}")

print("\n=== medqa by option-letter distribution (sanity) ===")
mr = load("medqa_direct")
if mr:
    print("  gold:", collections.Counter(r["gold"] for r in mr))
    print("  got :", collections.Counter(r["got"] for r in mr))
