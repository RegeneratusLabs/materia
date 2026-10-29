#!/usr/bin/env python3
"""Build the candidate file for hand-labelling the panel's gold grounding set."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from materia import config
from materia.corpus.index import open_index
from materia.retrieve import Retriever

items = json.loads((config.DATA_DIR / "herbal_set_104.json").read_text())
conn = open_index(config.CORPUS_DIR / "index.sqlite")
r = Retriever(conn, k=6, per_doc=2)
out = []
for it in items:
    chunks = r.search(it["q"])
    out.append({
        "id": it["id"], "cat": it["cat"], "question": it["q"],
        "gold_letter": it["a"], "gold_text": it["o"][it["a"]],
        "candidates": [
            {"chunk_id": c["chunk_id"], "source": c["source"], "section": c["section"],
             "date": c["date"], "snippet": c["text"][:320]}
            for c in chunks
        ],
    })
path = config.DATA_DIR / "gold_candidates.json"
path.write_text(json.dumps(out, indent=1) + "\n")
print(f"{len(out)} items -> {path}")
