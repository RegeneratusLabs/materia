#!/usr/bin/env python3
"""Why is each panel item uncovered, and what would fix it?

A coverage number without a cause is not actionable. This classifies each uncovered item:
no entity document, entity document but no claim-type chunk, or lab analyte absent from the
corpus, and names the source that could close it.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from materia import config
from materia.corpus.index import open_index
from materia.retrieve import Retriever, expected_sections, find_entities, grounded_chunks

items = json.loads((config.DATA_DIR / "herbal_set_104.json").read_text())
conn = open_index(config.CORPUS_DIR / "index.sqlite")
r = Retriever(conn, k=6, per_doc=2)
cov = {row["id"]: row for row in json.loads((config.DATA_DIR / "panel_coverage.json").read_text())}

HERB_FIX = "EMA monograph for the herb, or Health Canada if absent"
LAB_FIX = "MedlinePlus lab article for the analyte, or a CC-BY reference-interval study"
REF_FIX = "NICE CKS / NHS referral guidance (currently geo-blocked)"

rows = []
for it in items:
    if cov[it["id"]]["covered"]:
        continue
    ents = find_entities(it["q"], r.lex)
    hits = r.search(it["q"])
    entity_docs = sum(1 for c in hits if c["in_entity_doc"])
    if it["cat"].startswith("lab") or it["cat"] == "nutrient-lab":
        reason = "lab analyte not covered by a test document"
        fix = LAB_FIX
    elif entity_docs == 0:
        reason = "no corpus document about this entity"
        fix = REF_FIX if it["cat"] == "referral" else HERB_FIX
    else:
        reason = "entity document exists but no chunk with the right claim type and terms"
        fix = HERB_FIX
    rows.append({"id": it["id"], "cat": it["cat"], "question": it["q"], "entities": ents,
                 "entity_docs_retrieved": entity_docs, "reason": reason, "fix": fix})

out = config.DATA_DIR / "coverage_gaps.json"
out.write_text(json.dumps(rows, indent=1) + "\n")
from collections import Counter
print(f"uncovered {len(rows)}/{len(items)}")
print("reasons:", dict(Counter(x["reason"] for x in rows)))
print("by category:", dict(Counter(x["cat"] for x in rows)))
for x in rows[:10]:
    print(f"  {x['id']:4s} {x['cat'][:12]:12s} {x['reason'][:55]:55s} entities={x['entities'][:2]}")
print("->", out)
