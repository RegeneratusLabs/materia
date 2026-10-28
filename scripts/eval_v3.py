#!/usr/bin/env python3
"""104-item herb/lab panel, option order shuffled, Q8, two prompt conditions."""
import json, os, re, time, threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "http://127.0.0.1:8099/v1/chat/completions"
D = os.path.expanduser("~/eval/minicpm-med")

RULE_BUDGET = ("Think for at most 60 words, then reply with ONLY the letter of the single best option "
               "(A, B, C or D). No explanation after the letter.")

RULE_UNITS = (RULE_BUDGET + "\nUse the reference interval stated in the question, where given, as authoritative.")


def call(prompt, max_tokens=500):
    body = json.dumps({"model": "minicpm5-2b",
                       "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.0, "max_tokens": max_tokens,
                       "chat_template_kwargs": {"enable_thinking": True}}).encode()
    req = urllib.request.Request(BASE, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    ch = d["choices"][0]
    return {"text": ch["message"]["content"] or "",
            "reasoning": ch["message"].get("reasoning_content") or "",
            "finish": ch.get("finish_reason"), "ctok": d["usage"]["completion_tokens"]}


def letter(text, reasoning=""):
    for blob in (text, reasoning[-300:], reasoning[:300]):
        if not blob:
            continue
        m = re.search(r"(?:answer|option|choice)\s*(?:is|:)?\s*\**\(?([ABCD])\)?\b", blob, re.I)
        if m:
            return m.group(1)
        m = re.search(r"\b([ABCD])\b", blob.strip())
        if m:
            return m.group(1)
    return None


def build(it, rule):
    lines = [rule, "", it["q"], ""]
    for k in sorted(it["o"]):
        lines.append(f"{k}) {it['o'][k]}")
    lines += ["", "Answer:"]
    return "\n".join(lines)


items = json.load(open(os.path.join(D, "data/herbal_set_104.json")))


def run(rule, tag):
    path = os.path.join(D, f"results/{tag}.jsonl")
    fh = open(path, "w")
    lock = threading.Lock()

    def work(it):
        r = call(build(it, rule))
        got = letter(r["text"], r["reasoning"])
        with lock:
            fh.write(json.dumps({"id": it["id"], "cat": it["cat"], "gold": it["a"], "got": got,
                                 "text": r["text"][:200], "reason": r["reasoning"][:800],
                                 "finish": r["finish"], "ctok": r["ctok"]}) + "\n")
            fh.flush()

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(work, items))
    recs = [json.loads(l) for l in open(path)]
    k = sum(1 for r in recs if r["got"] == r["gold"])
    cap = sum(1 for r in recs if r["finish"] == "length")
    print(f"{tag}: {k}/{len(recs)} = {100*k/len(recs):.1f}% | capped {cap} | "
          f"mean tok {sum(r['ctok'] for r in recs)/len(recs):.0f} | {(time.time()-t0)/60:.1f} min",
          flush=True)
    return recs


a = [json.loads(l) for l in open(os.path.join(D, "results/v2_budget.jsonl"))]
b = run(RULE_UNITS, "v2_positive")

import collections
da = {r["id"]: r for r in a}
db = {r["id"]: r for r in b}
flips = [i for i in da if da[i]["got"] != db[i]["got"]]
fixed = [i for i in flips if da[i]["got"] != da[i]["gold"] and db[i]["got"] == db[i]["gold"]]
broke = [i for i in flips if da[i]["got"] == da[i]["gold"] and db[i]["got"] != db[i]["gold"]]
print(f"\nunit-rule delta: fixed {len(fixed)}, broke {len(broke)}, flips {len(flips)}")
print("fixed ids:", fixed)
print("broke ids:", broke)
for tag, rs in (("budget", a), ("units", b)):
    by = collections.defaultdict(lambda: [0, 0])
    for r in rs:
        by[r["cat"]][1] += 1
        if r["got"] == r["gold"]:
            by[r["cat"]][0] += 1
    print(f"\n{tag} by category:")
    for c, (k, n) in sorted(by.items(), key=lambda x: -x[1][1]):
        print(f"   {c:16s} {k:2d}/{n:2d} {100*k/n:5.1f}%")
