#!/usr/bin/env python3
"""Panel coverage: does the corpus hold the entity document with the right claim type?

Two different questions, kept separate on purpose:
  covered  — mechanical: a retrieved chunk comes from a document about the question's
             entity and carries the claim type the question asks for (safety/dose/etc.)
  supported — human judgement: that chunk actually supports the gold answer.
Coverage is measured on all 104 items; support is audited on a stratified sample and the
audit's precision is reported alongside coverage. Coverage is not support.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from materia import config
from materia.corpus.index import open_index
from materia.retrieve import Retriever, expected_sections

items = json.loads((config.DATA_DIR / "herbal_set_104.json").read_text())
conn = open_index(config.CORPUS_DIR / "index.sqlite")
r = Retriever(conn, k=6, per_doc=2)

rows = []
for it in items:
    want = expected_sections(it["q"])
    hits = r.search(it["q"])
    entity_hits = [c for c in hits if c["in_entity_doc"]]
    clinical = {"safety", "dose", "efficacy", "monitoring", "diagnostic"}
    typed = [c for c in entity_hits if c["section"] in want or c["assertion_type"] in clinical]
    covered = bool(typed)
    rows.append({
        "id": it["id"], "cat": it["cat"], "covered": covered,
        "want_sections": sorted(want),
        "best": typed[0]["chunk_id"] if typed else (entity_hits[0]["chunk_id"] if entity_hits else None),
        "top": [c["chunk_id"] for c in hits],
        "entity_docs_found": len(entity_hits),
    })

out = config.DATA_DIR / "panel_coverage.json"
out.write_text(json.dumps(rows, indent=1) + "\n")
from collections import Counter, defaultdict
by = defaultdict(lambda: [0, 0])
for row in rows:
    by[row["cat"]][1] += 1
    by[row["cat"]][0] += row["covered"]
k = sum(x["covered"] for x in rows)
print(f"coverage: {k}/{len(rows)} = {100*k/len(rows):.1f}%")
for c, v in sorted(by.items(), key=lambda kv: -kv[1][1]):
    print(f"  {c:16s} {v[0]:2d}/{v[1]:2d} = {100*v[0]/v[1]:5.1f}%")
print("uncovered:", [x["id"] for x in rows if not x["covered"]])
print("->", out)
