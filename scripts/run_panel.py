#!/usr/bin/env python3
"""Run the herb/lab panel under one condition.

Replaces the hardcoded eval_v2/eval_v3 scripts (which point at a path that no longer
exists). Every record carries the condition, the cap, the ctx and the command, so a
score can be reproduced without archaeology.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config, llm  # noqa: E402
from materia.parse import parse_letter, parse_sources  # noqa: E402
from materia.prompt import (  # noqa: E402
    build_prompt, build_prompt_evidence_nocite, build_prompt_hint, build_prompt_retrieval,
)
from materia.stats import wilson_str  # noqa: E402

BATCH = 20


def make_retriever(args):
    if args.condition == "closed":
        return None
    try:
        from materia.retrieve import Retriever
    except ImportError as e:  # corpus/retrieval not built yet
        sys.exit(f"retrieval condition needs materia.retrieve ({e})")
    from materia.corpus.index import open_index

    # SQLite connections are thread-bound; one per worker thread.
    local = threading.local()

    def _retriever() -> "Retriever":
        if not hasattr(local, "retriever"):
            local.retriever = Retriever(open_index(args.index), k=args.k)
        return local.retriever

    def retrieve(q: str) -> list[dict]:
        return _retriever().search(q)

    return retrieve


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default=str(config.DATA_DIR / "herbal_set_104.json"))
    ap.add_argument("--condition", choices=["closed", "retrieval", "hybrid", "routed", "hint"], default="closed")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-tokens", type=int, default=768)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="", help="comma-separated item ids")
    ap.add_argument("--port", type=int, default=config.REASON_PORT)
    ap.add_argument("--k", type=int, default=6)
    ap.add_argument("--index", default=str(config.CORPUS_DIR / "index.sqlite"))
    ap.add_argument("--ctx", type=int, default=config.REASON_CTX)
    ap.add_argument("--no-guard", action="store_true", help="skip RSS restart between batches")
    ap.add_argument("--dry-run", action="store_true", help="print the first prompt and exit")
    ap.add_argument("--no-think", action="store_true", help="disable thinking (direct answer)")
    ap.add_argument("--no-cite", action="store_true", help="evidence without asking the model to cite")
    ap.add_argument("--smart-hint", action="store_true", help="pick the best-matching sentence for the hint")
    ap.add_argument("--evidence-words", type=int, default=100)
    ap.add_argument("--rerank", action="store_true", help="pointwise model reranking of candidates")
    ap.add_argument("--rerank-fetch", type=int, default=8)
    ap.add_argument("--hybrid-cats", default="lab,nutrient-lab",
                    help="categories that get retrieval in --condition hybrid")
    args = ap.parse_args(argv)

    items = json.load(open(args.panel))
    if args.only:
        keep = {s.strip() for s in args.only.split(",")}
        items = [i for i in items if i["id"] in keep]
    if args.limit:
        items = items[: args.limit]
    if not items:
        sys.exit("no items selected")

    out = Path(args.out) if args.out else config.RESULTS_DIR / (
        f"panel_{args.condition}_{args.max_tokens}.jsonl"
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    retrieve = make_retriever(args)
    if args.dry_run:
        chunks = retrieve(items[0]["q"]) if retrieve else []
        prompt = (
            build_prompt_retrieval(items[0], chunks, config.RULE_BUDGET)
            if retrieve
            else build_prompt(items[0], config.RULE_BUDGET)
        )
        print(prompt)
        return 0

    llm.ensure_reason(ctx=args.ctx)

    command = " ".join([sys.executable, *sys.argv])
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    t0 = time.time()
    fh = open(out, "w")

    hybrid_cats = {c.strip() for c in args.hybrid_cats.split(",") if c.strip()}
    reranker = None
    if args.rerank:
        from materia.rerank import Reranker
        reranker = Reranker()

    def use_retrieval(item: dict, chunks: list[dict]) -> bool:
        if retrieve is None:
            return False
        if args.condition == "hybrid":
            return item["cat"] in hybrid_cats
        if args.condition == "routed":
            from materia.retrieve import grounded_chunks
            return bool(grounded_chunks(chunks, item["q"]))
        return True

    def work(item: dict) -> None:
        chunks = retrieve(item["q"]) if retrieve else []
        use = use_retrieval(item, chunks)
        if use and reranker is not None:
            chunks = reranker.rank(item["q"], chunks, top_k=args.k)
        if args.condition == "hint":
            from materia.retrieve import grounded_chunks
            g = grounded_chunks(chunks, item["q"]) if chunks else []
            hint_chunk = g[0] if g else (chunks[0] if chunks else None)
            prompt = build_prompt_hint(item, hint_chunk, config.RULE_BUDGET, smart=args.smart_hint)
        elif use and args.no_cite:
            prompt = build_prompt_evidence_nocite(item, chunks, config.RULE_BUDGET, args.evidence_words)
        elif use:
            prompt = build_prompt_retrieval(item, chunks, config.RULE_BUDGET, args.evidence_words)
        else:
            prompt = build_prompt(item, config.RULE_BUDGET)
        r = llm.chat(
            [{"role": "user", "content": prompt}],
            port=args.port,
            max_tokens=args.max_tokens,
            enable_thinking=not args.no_think,
            timeout=1800,
        )
        record = {
            "id": item["id"],
            "cat": item["cat"],
            "gold": item["a"],
            "got": parse_letter(r["text"], r["reasoning"]),
            "cites": parse_sources(r["text"]),
            "retrieved": [c["chunk_id"] for c in chunks],
            "text": r["text"][:200],
            "reason": r["reasoning"][:800],
            "finish": r["finish"],
            "ctok": r["ctok"],
            "condition": args.condition + ("/nothink" if args.no_think else "/think"),
            "route": ("grounded" if use else "memory") if args.condition == "routed" else None,
            "max_tokens": args.max_tokens,
            "ctx": args.ctx,
            "model_gguf": str(config.REASON_GGUF),
            "command": command,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        fh.write(json.dumps(record) + "\n")
        fh.flush()

    for i in range(0, len(items), BATCH):
        batch = items[i : i + BATCH]
        if i and not args.no_guard:
            if llm.guard_rss(args.port, ctx=args.ctx, parallel=args.workers):
                print(f"[guard] RSS over limit; restarted server at ctx={args.ctx}", flush=True)
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            list(ex.map(work, batch))
        print(f"  {min(i + BATCH, len(items))}/{len(items)}", flush=True)

    fh.close()
    if reranker is not None:
        reranker.save()
    recs = [json.loads(line) for line in open(out) if line.strip()]
    correct = sum(1 for r in recs if r["got"] == r["gold"])
    answered = sum(1 for r in recs if r["got"])
    capped = sum(1 for r in recs if r["finish"] == "length")
    mean_tok = sum(r["ctok"] for r in recs) / max(len(recs), 1)
    minutes = (time.time() - t0) / 60

    summary = {
        "condition": args.condition,
        "file": str(out.relative_to(config.ROOT)) if out.is_relative_to(config.ROOT) else str(out),
        "n": len(recs),
        "correct": correct,
        "pct": round(100 * correct / len(recs), 1),
        "ci95": [round(x, 1) for x in _wilson(correct, len(recs))],
        "answered": answered,
        "hit_token_cap": capped,
        "mean_ctok": round(mean_tok, 0),
        "max_tokens": args.max_tokens,
        "ctx": args.ctx,
        "model_gguf": str(config.REASON_GGUF),
        "command": command,
        "started": started,
        "minutes": round(minutes, 1),
    }
    out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(
        f"{args.condition}: {wilson_str(correct, len(recs))} | answered {answered}/{len(recs)} "
        f"| capped {capped} | mean {mean_tok:.0f} tok | {minutes:.1f} min\n-> {out}"
    )
    return 0


def _wilson(k: int, n: int):
    from materia.stats import wilson

    return wilson(k, n)


if __name__ == "__main__":
    raise SystemExit(main())
