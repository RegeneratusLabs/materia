#!/usr/bin/env python3
"""Extract clean adult dose rows from the Health Canada multi-vitamin/mineral monograph.

The monograph's dose tables are wide and split across cells. Chunking the flattened text
loses the row/column relationship, which makes a rule unable to quote a dose it can defend.
This adapter keeps the exact values, one row per nutrient, and cites the same page.

Run:
    .venv/bin/python scripts/ingest_nhpid_dose_rows.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup

from materia import config
from materia.corpus import hc
from materia.corpus.schema import dump_doc, make_chunk, make_doc, sha256_bytes

URL = hc.MONO.format(atid="multi_vitmin_suppl")

# (canonical id, table index, header token, min column, max column, unit, group)
TARGETS = [
    ("folate", 7, "Folate", 3, 4, "µg/day", "vitamins"),
    ("vitamin_b12", 10, "Vitamin B 12", 3, 4, "µg/day", "vitamins"),
    ("iron", 14, "Iron", 5, 6, "mg/day", "minerals"),
    ("magnesium", 15, "Magnesium", 1, 2, "mg/day", "minerals"),
    ("zinc", 17, "Zinc", 3, 4, "mg/day", "minerals"),
]

LICENCE = {
    "name": "Open Government Licence – Canada",
    "redistributable": True,
    "evidence_url": "https://open.canada.ca/en/open-government-licence-canada",
    "note": "Table rows extracted from the NNHPD multi-vitamin/mineral monograph; values unchanged.",
}


def _row(cells: list[str], label: str) -> list[str] | None:
    for row in cells:
        if row and row[0].strip().lower() == label:
            return row
    return None


def build() -> dict:
    page = hc.fetch(URL).decode("utf-8", "replace")
    soup = BeautifulSoup(page, "html.parser")
    tables = soup.find_all("table")
    retrieved_at = date.today().isoformat()
    chunks = []
    for nutrient, table_index, header_token, min_col, max_col, unit, group in TARGETS:
        table = tables[table_index]
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            cells = [c for c in cells if c]
            if cells:
                rows.append(cells)
        if not rows or header_token.lower() not in " ".join(rows[0]).lower():
            raise SystemExit(f"table {table_index} does not contain {header_token!r}; refusing to guess")
        adult = _row(rows, "19 years and older") or _row(rows, "Adults")
        if not adult:
            raise SystemExit(f"no adult row in table {table_index}")
        min_value, max_value = adult[min_col], adult[max_col]
        label = {
            "folate": "Folate", "vitamin_b12": "Vitamin B 12", "iron": "Iron",
            "magnesium": "Magnesium", "zinc": "Zinc (non-picolinate)",
        }[nutrient]
        text = (
            f"Table {'8' if group == 'vitamins' else '9'}. Daily doses for {group} — "
            f"Adults 19 years and older: {label} {min_value}–{max_value} {unit}."
        )
        chunks.append(make_chunk(
            f"hc-nhpid-multi-vitmin-doses#{len(chunks) + 1:03d}", text, "dosage", "dose",
            topics=[nutrient, "dose", "adult"],
            entities=[label, "multi-vitamin/mineral supplements"],
        ))
    doc = make_doc(
        doc_id="hc-nhpid-multi-vitmin-doses",
        source="Health Canada NNHPD",
        tier="regulatory",
        title="Multi-Vitamin/Mineral Supplements — adult dose rows",
        date_="2026-06-26",
        url=URL,
        identifier={"type": "nhpid", "value": "multi_vitmin_suppl"},
        jurisdiction="ca",
        language="en",
        licence=LICENCE,
        retrieved_at=retrieved_at,
        checksum=sha256_bytes(page.encode("utf-8", "replace")),
        chunks=chunks,
        entities=["Folate", "Vitamin B12", "Iron", "Magnesium", "Zinc"],
    )
    return doc


def main() -> int:
    doc = build()
    dump_doc(doc, config.CORPUS_DIR / "docs")
    print(json.dumps({"doc_id": doc["doc_id"], "chunks": len(doc["chunks"]),
                      "rows": [c["text"] for c in doc["chunks"]]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
