#!/usr/bin/env python3
"""For items whose entity document exists but coverage failed: is the claim there at all?

Oracle pass over every chunk of the entity's documents, scored against the gold option.
Distinguishes three failures: retrieval missed a chunk that supports the answer, the support
sits in a section we did not ask for, or the corpus genuinely lacks the claim.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from materia import config
from materia.corpus.index import open_index
from materia.retrieve import Retriever, expected_sections, find_entities
from materia.verify import claim_support

items = json.loads((config.DATA_DIR / "herbal_set_104.json").read_text())
gaps = json.loads((config.DATA_DIR / "coverage_gaps.json").read_text())
conn = open_index(config.CORPUS_DIR / "index.sqlite")
r = Retriever(conn, k=6, per_doc=2)

rows = []
for g in gaps:
    if "entity document exists" not in g["reason"]:
        continue
    it = next(i for i in items if i["id"] == g["id"])
    gold_text = it["o"][it["a"]]
    ents = find_entities(it["q"], r.lex)
    doc_ids = r._entity_docs(ents)
    if not doc_ids:
        rows.append({"id": it["id"], "verdict": "no entity doc", "entities": ents})
        continue
    marks = ",".join("?" for _ in doc_ids)
    chunks = conn.execute(
        f"""SELECT c.chunk_id, c.text, c.section, d.title
            FROM chunks c JOIN docs d ON d.doc_id=c.doc_id
            WHERE c.doc_id IN ({marks})""", list(doc_ids)).fetchall()
    want = expected_sections(it["q"])
    best = max(chunks, key=lambda c: claim_support(gold_text, c["text"])) if chunks else None
    score = claim_support(gold_text, best["text"]) if best else 0.0
    if score < 0.2:
        verdict = "content absent"
    elif best["section"] in want:
        verdict = "retrieval miss (right chunk, not retrieved)"
    else:
        verdict = f"section mismatch ({best['section']} not in {sorted(want)})"
    rows.append({"id": it["id"], "cat": it["cat"], "verdict": verdict, "score": round(score, 3),
                 "chunk": best["chunk_id"] if best else None, "section": best["section"] if best else None,
                 "entities": ents})

from collections import Counter
print(f"diagnosed {len(rows)}")
print(Counter(r["verdict"].split(" (")[0] for r in rows))
for r in rows:
    print(f"  {r['id']:4s} {r['verdict'][:62]:62s} score={r.get('score')} {r.get('chunk','')}")
Path(config.DATA_DIR / "gap_diagnosis.json").write_text(json.dumps(rows, indent=1) + "\n")
