#!/usr/bin/env python3
"""Abstention test: questions the corpus cannot answer must produce NO_EVIDENCE."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from materia import config, llm
from materia.corpus.index import open_index
from materia.parse import is_no_evidence
from materia.prompt import build_prompt_retrieval
from materia.retrieve import Retriever

items = json.loads((config.DATA_DIR / "abstention.json").read_text())
conn = open_index(config.CORPUS_DIR / "index.sqlite")
r = Retriever(conn, k=5, per_doc=2)
llm.ensure_reason(ctx=8192, parallel=2)
rows = []
for it in items:
    chunks = r.search(it["q"])
    prompt = build_prompt_retrieval({"q": it["q"], "o": {}}, chunks, config.RULE_BUDGET, evidence_words=90)
    out = llm.chat([{"role": "user", "content": prompt}], max_tokens=64, enable_thinking=False)
    abstained = is_no_evidence(out["text"])
    rows.append({"id": it["id"], "q": it["q"], "abstained": abstained, "text": out["text"][:160],
                 "retrieved": [c["chunk_id"] for c in chunks]})
    print(f"{it['id']} abstained={abstained} :: {out['text'][:90]!r}", flush=True)
k = sum(r["abstained"] for r in rows)
out = {"n": len(rows), "abstained": k, "rate": round(100 * k / len(rows), 1), "records": rows}
Path(config.RESULTS_DIR / "gate3_abstention.json").write_text(json.dumps(out, indent=1) + "\n")
print(f"\nabstention: {k}/{len(rows)} = {100*k/len(rows):.0f}% (gate >=90%)")
