#!/usr/bin/env python3
"""Does a reasoning-budget instruction rescue thinking mode on the herbal set?"""
import json, os, re, time, threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "http://127.0.0.1:8099/v1/chat/completions"
BASE_DIR = os.path.expanduser("~/eval/minicpm-med")


def call(prompt, max_tokens=500, think=True):
    body = json.dumps({
        "model": "minicpm5-2b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0, "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": think},
    }).encode()
    req = urllib.request.Request(BASE, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    ch = d["choices"][0]
    return {"text": ch["message"]["content"] or "",
            "reasoning": ch["message"].get("reasoning_content") or "",
            "finish": ch.get("finish_reason"),
            "ctok": d["usage"]["completion_tokens"]}


def parse_letter(text, reasoning=""):
    for blob in (text, reasoning[-400:], reasoning[:400]):
        if not blob:
            continue
        m = re.search(r"(?:answer|option|choice)\s*(?:is|:)?\s*\**\(?([ABCD])\)?\b", blob, re.I)
        if m:
            return m.group(1)
        m = re.search(r"\b([ABCD])\b", blob.strip())
        if m:
            return m.group(1)
    return None


items = [{"id": r["id"], "q": r["q"], "opts": r["o"], "a": r["a"], "cat": r["cat"]}
         for r in json.load(open(os.path.join(BASE_DIR, "data/herbal_set.json")))]

PREFIX = ("Think for at most 60 words, then reply with ONLY the letter of the single best option "
          "(A, B, C or D). No explanation after the letter.")


def prompt_for(it):
    lines = [PREFIX, "", it["q"], ""]
    for k in sorted(it["opts"]):
        lines.append(f"{k}) {it['opts'][k]}")
    lines += ["", "Answer:"]
    return "\n".join(lines)


path = os.path.join(BASE_DIR, "results/herbal_brief.jsonl")
fh = open(path, "a")
lock = threading.Lock()


def work(it):
    r = call(prompt_for(it), max_tokens=500)
    got = parse_letter(r["text"], r["reasoning"])
    with lock:
        fh.write(json.dumps({"id": it["id"], "cat": it["cat"], "gold": it["a"], "got": got,
                             "text": r["text"][:200], "reason": r["reasoning"][:1000],
                             "finish": r["finish"], "ctok": r["ctok"]}) + "\n")
        fh.flush()


t0 = time.time()
with ThreadPoolExecutor(max_workers=2) as ex:
    list(ex.map(work, items))
recs = [json.loads(l) for l in open(path)]
k = sum(1 for r in recs if r["got"] == r["gold"])
ans = sum(1 for r in recs if r["got"])
print(f"herbal brief-think: {k}/{len(recs)} = {100*k/len(recs):.1f}% | answered {ans}/{len(recs)} | "
      f"mean ctok {sum(r['ctok'] for r in recs)/len(recs):.0f} | {(time.time()-t0)/60:.1f} min")
