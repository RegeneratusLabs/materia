#!/usr/bin/env python3
"""MiniCPM5-2B medical-knowledge assessment harness (llama-server, OpenAI API)."""
import json, glob, re, os, sys, time, argparse, random, threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "http://127.0.0.1:8099/v1/chat/completions"
OUT = os.path.expanduser("~/eval/minicpm-med/results")
os.makedirs(OUT, exist_ok=True)


def call(prompt, max_tokens=400, think=False, temperature=0.0, retries=3):
    body = json.dumps({
        "model": "minicpm5-2b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": think},
    }).encode()
    for a in range(retries):
        try:
            req = urllib.request.Request(BASE, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                d = json.loads(r.read())
            ch = d["choices"][0]
            return {
                "text": ch["message"]["content"] or "",
                "reasoning": ch["message"].get("reasoning_content") or "",
                "finish": ch.get("finish_reason"),
                "ctok": d["usage"]["completion_tokens"],
                "ptok": d["usage"]["prompt_tokens"],
            }
        except Exception as e:
            if a == retries - 1:
                return {"text": "", "reasoning": "", "finish": f"error:{e}", "ctok": 0, "ptok": 0}
            time.sleep(3)


def mcq_prompt(q, opts):
    lines = ["Answer with ONLY the letter of the single best option (A, B, C or D). No explanation.", "", q, ""]
    for k in sorted(opts):
        lines.append(f"{k}) {opts[k]}")
    lines += ["", "Answer:"]
    return "\n".join(lines)


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


# ---------- loaders ----------
def _rows(prefix):
    rows = []
    for f in sorted(glob.glob(os.path.expanduser(f"~/eval/minicpm-med/data/{prefix}_*.json"))):
        rows += [r["row"] for r in json.load(open(f)).get("rows", [])]
    return rows


def load_medqa():
    return [{"id": f"M{i}", "q": r["question"], "opts": r["options"], "a": r["answer_idx"]}
            for i, r in enumerate(_rows("medqa"))]


def load_pubmedqa():
    out = []
    for i, r in enumerate(_rows("pubmedqa")):
        out.append({"id": f"P{i}", "q": r["question"], "ctx": " ".join(r["context"]["contexts"]),
                    "a": {"yes": "A", "no": "B", "maybe": "C"}.get(str(r["final_decision"]).lower())})
    return out


def load_herbal():
    return [{"id": r["id"], "q": r["q"], "opts": r["o"], "a": r["a"], "cat": r["cat"]}
            for r in json.load(open(os.path.expanduser("~/eval/minicpm-med/data/herbal_set.json")))]


# ---------- runner ----------
def run_mcq(items, tag, n=None, seed=7, workers=3, think=False, max_tokens=400, fresh=False):
    if n and n < len(items):
        items = random.Random(seed).sample(items, n)
    path = os.path.join(OUT, f"{tag}.jsonl")
    if fresh and os.path.exists(path):
        os.remove(path)
    done = set()
    if os.path.exists(path):
        for line in open(path):
            try:
                done.add(json.loads(line)["id"])
            except Exception:
                pass
    todo = [it for it in items if it["id"] not in done]
    print(f"[{tag}] {len(items)} items ({len(todo)} to run, think={think})", flush=True)
    if not todo:
        pass
    else:
        fh = open(path, "a")
        lock = threading.Lock()

        def work(it):
            r = call(mcq_prompt(it["q"], it["opts"]), max_tokens=max_tokens, think=think)
            got = parse_letter(r["text"], r["reasoning"])
            rec = {"id": it["id"], "cat": it.get("cat", tag), "gold": it["a"], "got": got,
                   "text": r["text"][:400], "reason": r["reasoning"][:2000], "finish": r["finish"],
                   "ctok": r["ctok"]}
            with lock:
                fh.write(json.dumps(rec) + "\n"); fh.flush()
            return got == it["a"]

        t0 = time.time()
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, todo))
        print(f"[{tag}] ran {len(todo)} in {(time.time()-t0)/60:.1f} min", flush=True)
        fh.close()

    recs = [json.loads(l) for l in open(path)]
    corr = sum(1 for r in recs if r["got"] == r["gold"])
    unparsed = sum(1 for r in recs if not r["got"])
    print(f"[{tag}] RESULT {corr}/{len(recs)} = {100*corr/len(recs):.1f}% (unparsed {unparsed})", flush=True)
    return recs


def run_pubmedqa(n=200, workers=3, think=False):
    rows = load_pubmedqa()
    if n and n < len(rows):
        rows = random.Random(11).sample(rows, n)
    path = os.path.join(OUT, "pubmedqa.jsonl")
    fh = open(path, "w"); lock = threading.Lock()

    def work(ir):
        i, r = ir
        p = ("Read the abstract and answer the question with ONLY one letter: A) yes, B) no, C) maybe.\n\n"
             f"Abstract: {r['ctx']}\n\nQuestion: {r['q']}\n\nAnswer:")
        o = call(p, max_tokens=600, think=think)
        blob = (o["text"] + " " + o["reasoning"][-300:]).lower()
        if re.search(r"\bmaybe\b|\bperhaps\b|\bunclear\b", blob):
            got = "C"
        elif re.search(r"\byes\b", blob) and not re.search(r"\bno\b|\bnot\b", blob):
            got = "A"
        elif re.search(r"\bno\b", blob):
            got = "B"
        else:
            got = None
        rec = {"id": r["id"], "gold": r["a"], "got": got, "text": o["text"][:300], "finish": o["finish"]}
        with lock:
            fh.write(json.dumps(rec) + "\n"); fh.flush()

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, list(enumerate(rows))))
    recs = [json.loads(l) for l in open(path)]
    corr = sum(1 for r in recs if r["got"] == r["gold"])
    print(f"[pubmedqa] RESULT {corr}/{len(recs)} = {100*corr/len(recs):.1f}% in {(time.time()-t0)/60:.1f} min", flush=True)


def run_probes():
    probes = json.load(open(os.path.expanduser("~/eval/minicpm-med/data/probes.json")))
    path = os.path.join(OUT, "probes.jsonl")
    with open(path, "w") as fh:
        for p in probes:
            o = call(p["prompt"], max_tokens=900, think=True)
            fh.write(json.dumps({**p, **o}) + "\n"); fh.flush()
            print(f"[probe] {p['id']} ctok={o['ctok']} finish={o['finish']}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage")
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--maxtok", type=int, default=400)
    a = ap.parse_args()
    mode = "think" if a.think else "direct"

    if a.stage == "medqa":
        run_mcq(load_medqa(), f"medqa_{mode}", n=a.n, workers=a.workers,
                think=a.think, max_tokens=a.maxtok if a.think else 200)
    elif a.stage == "herbal":
        run_mcq(load_herbal(), f"herbal_{mode}", workers=a.workers,
                think=a.think, max_tokens=a.maxtok if a.think else 200)
    elif a.stage == "medqa_think_sub":
        # paired subset: reuse the exact items already answered in medqa_direct
        done = [json.loads(l) for l in open(os.path.join(OUT, "medqa_direct.jsonl"))]
        ids = [r["id"] for r in done][:a.n]
        allm = {it["id"]: it for it in load_medqa()}
        items = [allm[i] for i in ids if i in allm]
        run_mcq(items, "medqa_think_sub", workers=a.workers, think=True,
                max_tokens=a.maxtok if a.maxtok != 400 else 1000)
    elif a.stage == "pubmedqa":
        run_pubmedqa(n=a.n or 200, workers=a.workers, think=a.think)
    elif a.stage == "medqa_shuf":
        import string
        items = load_medqa()
        items = random.Random(7).sample(items, a.n or 200)
        shuf = []
        rng = random.Random(99)
        for it in items:
            keys = sorted(it["opts"])
            vals = [it["opts"][k] for k in keys]
            newlab = keys[:]
            rng.shuffle(newlab)
            opts = {keys[i]: vals[i] for i in range(len(keys))}
            # newlab[i] is the new letter for original option i
            newopts = {newlab[i]: vals[i] for i in range(len(keys))}
            newgold = newlab[keys.index(it["a"])]
            shuf.append({"id": it["id"], "q": it["q"], "opts": newopts, "a": newgold})
        run_mcq(shuf, "medqa_shuf", workers=a.workers, think=a.think, max_tokens=200)
    elif a.stage == "probes":
        run_probes()
    else:
        sys.exit(f"unknown stage {a.stage}")


if __name__ == "__main__":
    main()
