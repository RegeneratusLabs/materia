import sqlite3

from materia.corpus.index import build_index
from materia.retrieve import Retriever, build_lexicon, find_entities, group_conflicts
from materia.corpus.schema import make_chunk, make_doc


def _doc(doc_id, *, tier="regulatory", jurisdiction="eu", source="EMA", entities=None):
    return make_doc(
        doc_id=doc_id,
        source=source,
        tier=tier,
        title=doc_id,
        date_="2024-01-01",
        url=f"https://example.org/{doc_id}",
        identifier={"type": "ema", "value": "EMA/HMPC/1/2024"},
        jurisdiction=jurisdiction,
        language="en",
        licence={"name": "test", "redistributable": True, "evidence_url": "https://example.org"},
        retrieved_at="2026-10-28",
        checksum="sha256:" + "0" * 64,
        chunks=[
            make_chunk(f"{doc_id}#{i:03d}", text, section, assertion,
                       entities=entities or [])
            for i, (text, section, assertion) in enumerate(
                [
                    ("Do not use in patients taking warfarin because of increased bleeding risk.",
                     "contraindications", "safety"),
                    ("The usual dose is 300 mg once daily in the evening.",
                     "dosage", "dose"),
                    ("Used traditionally to help relieve nervousness and restlessness.",
                     "indications", "efficacy"),
                ],
                start=1,
            )
        ],
        entities=entities or [],
    )


def _conn(tmp_path, docs):
    import json

    d = tmp_path / "docs"
    d.mkdir()
    for doc in docs:
        (d / f"{doc['doc_id']}.json").write_text(json.dumps(doc))
    build_index(d, tmp_path / "index.sqlite")
    conn = sqlite3.connect(tmp_path / "index.sqlite")
    conn.row_factory = sqlite3.Row
    return conn


def test_retriever_prefers_matching_section(tmp_path):
    conn = _conn(tmp_path, [_doc("ema-sjw", entities=["St John's wort"])])
    r = Retriever(conn, k=3, per_doc=3)
    hits = r.search("Is St John's wort safe with warfarin? What is the bleeding risk?")
    assert hits, "expected hits"
    assert hits[0]["section"] in ("contraindications", "cautions", "interactions")


def test_lexicon_resolves_common_to_scientific():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE docs(doc_id TEXT, entities TEXT)")
    conn.execute("INSERT INTO docs VALUES ('x', ?)", ('["Hypericum perforatum"]',))
    lex = build_lexicon(conn)
    hits = find_entities("patient asks about st john's wort", lex)
    assert any("hypericum" in h.lower() or "st john" in h.lower() for h in hits)


def test_conflict_surfaces_two_sources():
    chunks = [
        {"chunk_id": "a#1", "doc_id": "a", "source": "EMA", "jurisdiction": "eu",
         "date": "2024-01-01", "assertion_type": "safety", "entities": ["Kava"],
         "text": "Contraindicated in patients with liver disease due to hepatotoxicity risk."},
        {"chunk_id": "b#1", "doc_id": "b", "source": "HC", "jurisdiction": "ca",
         "date": "2023-01-01", "assertion_type": "safety", "entities": ["Kava"],
         "text": "Not recommended for prolonged use; monitor for jaundice and dark urine."},
    ]
    conflicts = group_conflicts(chunks)
    assert conflicts and conflicts[0]["entity"] == "kava"
    assert len(conflicts[0]["sources"]) == 2


def test_boilerplate_filtered_from_results(tmp_path):
    docs = [_doc("ema-sjw", entities=["St John's wort"])]
    # add a boilerplate chunk to the same document
    import json
    d = docs[0]
    from materia.corpus.schema import make_chunk
    d["chunks"].append(make_chunk(f"{d['doc_id']}#004",
        "NCCIH Clearinghouse: provides information on NCCIH and complementary approaches. "
        "This publication is not copyrighted and is in the public domain.",
        "other", "other", entities=["St John's wort"]))
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ema-sjw.json").write_text(json.dumps(d))
    build_index(tmp_path / "docs", tmp_path / "index.sqlite")
    conn = sqlite3.connect(tmp_path / "index.sqlite"); conn.row_factory = sqlite3.Row
    r = Retriever(conn, k=6, per_doc=3)
    hits = r.search("NCCIH clearinghouse information St John's wort")
    assert hits
    assert all("Clearinghouse" not in h["text"] for h in hits)
