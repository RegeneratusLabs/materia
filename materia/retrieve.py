"""Entity lexicon and BM25 retrieval with section weighting.

Retrieval quality on monographs fails in two ways, both handled here: naming (St John's
wort vs Hypericum perforatum) and section blindness (a contraindication returned for a
dose question). The lexicon comes from the corpus's own entity fields plus a small
synonym table; the section is a weighted FTS column and is also returned for the prompt.
"""
from __future__ import annotations

import json
import re
import sqlite3

# Small, hand-checked synonym table. The corpus supplies scientific names; practitioners
# type common names. Extend from real queries, not from imagination.
SYNONYMS: dict[str, list[str]] = {
    "st john's wort": ["hypericum", "hyperici herba", "hypericum perforatum"],
    "st johns wort": ["hypericum", "hyperici herba", "hypericum perforatum"],
    "ginkgo": ["ginkgo biloba", "ginkgonis folium"],
    "echinacea": ["echinaceae", "echinacea purpurea", "echinacea angustifolia", "echinacea pallida"],
    "ginseng": ["panax ginseng", "ginseng radix", "asian ginseng"],
    "ashwagandha": ["withania somnifera", "withaniae somniferae radix"],
    "turmeric": ["curcuma longa", "curcumae longae rhizoma", "curcumin"],
    "garlic": ["allium sativum", "allii sativi bulbus"],
    "milk thistle": ["silybum marianum", "silybi marianae fructus", "silymarin"],
    "valerian": ["valeriana officinalis", "valerianae radix"],
    "kava": ["piper methysticum", "piperis methystici rhizoma"],
    "saw palmetto": ["serenoa repens", "serenoae repentis fructus"],
    "black cohosh": ["cimicifuga racemosa", "cimicifugae rhizoma"],
    "reishi": ["ganoderma lucidum", "ganoderma"],
    "rhodiola": ["rhodiola rosea", "rhodiolae roseae radix"],
    "licorice": ["glycyrrhiza glabra", "glycyrrhizae radix", "liquorice"],
    "chamomile": ["matricaria recutita", "matricariae flos", "chamomilla"],
    "lavender": ["lavandula angustifolia", "lavandulae flos", "lavandulae aetheroleum"],
    "passionflower": ["passiflora incarnata", "passiflorae herba"],
    "lemon balm": ["melissa officinalis", "melissae folium"],
    "elderberry": ["sambucus nigra", "sambuci flos"],
    "astragalus": ["astragalus membranaceus", "astragali membranacei radix"],
    "holy basil": ["ocimum tenuiflorum", "ocimum sanctum", "tulsi"],
    "5-htp": ["5-hydroxytryptophan", "5 hydroxytryptophan"],
    "sam-e": ["s-adenosylmethionine", "s adenosyl methionine"],
    "vitamin b12": ["cobalamin", "cyanocobalamin", "methylcobalamin"],
    "vitamin d": ["cholecalciferol", "ergocalciferol", "25-hydroxyvitamin d", "25 oh vitamin d"],
    "iron": ["ferritin", "ferrous", "haem iron", "heme iron"],
    "folate": ["folic acid", "methylfolate"],
    "magnesium": ["magnesium citrate", "magnesium glycinate"],
    "zinc": ["zinc citrate", "zinc picolinate"],
    "fish oil": ["omega-3", "omega 3", "epa", "dha", "krill oil"],
    "nac": ["n-acetylcysteine", "n acetyl cysteine", "acetylcysteine"],
    "coq10": ["coenzyme q10", "ubiquinone", "ubiquinol"],
    "melatonin": ["melatonine"],
    "ginger": ["zingiber officinale", "zingiberis rhizoma"],
    "boswellia": ["frankincense", "boswellia serrata"],
    "maca": ["lepidium meyenii"],
}

# Query-side expansion for terms practitioners use and monographs do not.
TOPIC_ALIASES: dict[str, list[str]] = {
    "hepatotoxic": ["liver", "hepatic", "jaundice", "hepatotoxicity"],
    "hepatotoxicity": ["liver", "hepatic", "jaundice", "hepatotoxic"],
    "bleeding": ["bleed", "platelet", "inr", "anticoagulant", "haemorrhage"],
    "anticoagulant": ["warfarin", "bleeding", "inr"],
    "pregnancy": ["pregnan", "lactation", "breastfeeding"],
    "contraindicated": ["contraindication", "do not use", "must not"],
    "interaction": ["interact", "cyp3a4", "cyp2c9", "pgp"],
    "thyroid": ["tsh", "levothyroxine", "hypothyroid"],
    "insomnia": ["sleep", "sedative", "hypnotic"],
    "iron deficiency": ["ferritin", "transferrin", "anaemia", "anemia"],
    "b12": ["cobalamin", "methylmalonic"],
    "folate": ["folic acid", "homocysteine"],
}

SECTION_FOR_QUESTION: list[tuple[str, set[str]]] = [
    (r"risk|safe|contraindicat|adverse|toxicit|hepatotox|interact|bleed|pregnan|lactat|side effect",
     {"contraindications", "cautions", "adverse_effects", "interactions", "red_flags"}),
    (r"dose|dosage|how much|mg\b|amount|regimen", {"dosage"}),
    (r"effective|evidence|benefit|improv|help|treat|work", {"indications", "evidence", "pharmacology"}),
    (r"lab|ferritin|tsh|b12|folate|reference|range|interval", {"reference_interval", "monitoring"}),
]

STOP = set(
    "a an the of and or in on for with to from by is are was were be been being this that these those "
    "what which who whom how why when where does do did can could should would may might will patient "
    "taking take taken start starts started start taking given ask asks about best most likely main "
    "concern risk effect effects using use used use increase decrease increases decreases".split()
)


def build_lexicon(conn: sqlite3.Connection) -> dict[str, str]:
    """alias (lowercase) -> canonical entity string, from corpus entities + synonyms."""
    lex: dict[str, str] = {}
    for row in conn.execute("SELECT entities FROM docs"):
        try:
            ents = json.loads(row["entities"] or "[]")
        except json.JSONDecodeError:
            continue
        for e in ents:
            e = (e or "").strip()
            if not e:
                continue
            lex.setdefault(e.lower(), e)
            lowered = re.sub(r"\s*\([^)]*\)", "", e).strip().lower()
            lex.setdefault(lowered, e)
    for common, aliases in SYNONYMS.items():
        canon = common
        lex.setdefault(common, canon)
        for a in aliases:
            lex.setdefault(a.lower(), canon)
    return lex


def find_entities(text: str, lex: dict[str, str]) -> list[str]:
    low = " " + re.sub(r"[^a-z0-9' -]", " ", text.lower()) + " "
    hits: list[str] = []
    for alias, canon in lex.items():
        if len(alias) < 3:
            continue
        if f" {alias} " in low or alias in text.lower():
            if canon not in hits:
                hits.append(canon)
    return hits


def _expand(text: str) -> list[str]:
    low = text.lower()
    extra: list[str] = []
    for key, aliases in TOPIC_ALIASES.items():
        if key in low:
            extra += aliases
    return extra


def expected_sections(question: str) -> set[str]:
    for pattern, sections in SECTION_FOR_QUESTION:
        if re.search(pattern, question, re.I):
            return sections
    return set()


def _fts_query(text: str, entities: list[str]) -> str:
    terms: list[str] = []
    for e in entities:
        terms += [t for t in re.split(r"\W+", e.lower()) if t and t not in STOP and len(t) > 2]
    terms += [t for t in re.split(r"\W+", text.lower()) if t and t not in STOP and len(t) > 2]
    terms += [t for t in re.split(r"\W+", " ".join(_expand(text))) if t and t not in STOP and len(t) > 2]
    seen: list[str] = []
    for t in terms:
        if t not in seen:
            seen.append(t)
    return " OR ".join(f'"{t}"' for t in seen[:24])


class Retriever:
    def __init__(self, conn: sqlite3.Connection, *, k: int = 6, per_doc: int = 2,
                 require_jurisdiction: bool = False):
        self.conn = conn
        self.k = k
        self.per_doc = per_doc
        self.lex = build_lexicon(conn)
        self.require_jurisdiction = require_jurisdiction

    def search(self, question: str, jurisdiction: str | None = None) -> list[dict]:
        entities = find_entities(question, self.lex)
        query = _fts_query(question, entities)
        if not query:
            return []
        rows = self.conn.execute(
            """
            SELECT f.chunk_id, bm25(chunks_fts, 1.0, 2.0, 1.5, 1.0) AS score
            FROM chunks_fts f
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT 80
            """,
            (query,),
        ).fetchall()

        want = expected_sections(question)
        candidates: list[dict] = []
        per_doc: dict[str, int] = {}
        for row in rows:
            meta = self.conn.execute(
                """
                SELECT c.chunk_id, c.doc_id, c.text, c.section, c.assertion_type, c.topics,
                       d.source, d.tier, d.jurisdiction, d.date, d.title, d.url, d.identifier_value
                FROM chunks c JOIN docs d ON d.doc_id = c.doc_id
                WHERE c.chunk_id = ?
                """,
                (row["chunk_id"],),
            ).fetchone()
            if meta is None:
                continue
            if jurisdiction and meta["jurisdiction"] not in (jurisdiction, "international"):
                continue
            n = per_doc.get(meta["doc_id"], 0)
            if n >= self.per_doc:
                continue
            per_doc[meta["doc_id"]] = n + 1
            candidates.append(
                {
                    "chunk_id": meta["chunk_id"],
                    "doc_id": meta["doc_id"],
                    "text": meta["text"],
                    "section": meta["section"],
                    "assertion_type": meta["assertion_type"],
                    "topics": json.loads(meta["topics"] or "[]"),
                    "source": meta["source"],
                    "tier": meta["tier"],
                    "jurisdiction": meta["jurisdiction"],
                    "date": meta["date"],
                    "title": meta["title"],
                    "url": meta["url"],
                    "identifier": meta["identifier_value"],
                    "bm25": round(row["score"], 3),
                }
            )
        # re-rank: BM25 is negative (lower is better); section fit is a real signal on
        # monographs, where a contraindication and a dose sentence share vocabulary.
        for c in candidates:
            c["score"] = -c["bm25"] + (0.6 if c["section"] in want else 0.0)
        candidates.sort(key=lambda c: c["score"], reverse=True)
        chosen: list[dict] = []
        used: dict[str, int] = {}
        for c in candidates:
            n = used.get(c["doc_id"], 0)
            if n >= self.per_doc:
                continue
            used[c["doc_id"]] = n + 1
            chosen.append(c)
            if len(chosen) >= self.k:
                break
        return chosen


def group_conflicts(chunks: list[dict]) -> list[dict]:
    """Group by entity + assertion type; flag divergence between sources.

    This is a v0 heuristic: it surfaces that two sources are talking about the same kind
    of claim and share little vocabulary. It does not decide who is right, which is the
    point (AGENTS.md: show, never synthesise).
    """
    by_key: dict[tuple[str, str], list[dict]] = {}
    for c in chunks:
        ents = c.get("entities") or []
        entity = ents[0].split("(")[0].strip().lower() if ents else c["doc_id"]
        by_key.setdefault((entity, c["assertion_type"]), []).append(c)

    conflicts: list[dict] = []
    for (entity, assertion), group in by_key.items():
        sources = {c["doc_id"]: c for c in group}
        if len(sources) < 2:
            continue
        texts = list(sources.values())
        if len({c["source"] for c in texts}) < 2:
            continue
        a, b = texts[0], texts[1]
        ta = {t for t in re.split(r"\W+", a["text"].lower()) if len(t) > 4}
        tb = {t for t in re.split(r"\W+", b["text"].lower()) if len(t) > 4}
        overlap = len(ta & tb) / max(1, len(ta | tb))
        if overlap < 0.15:
            conflicts.append(
                {
                    "entity": entity,
                    "assertion_type": assertion,
                    "sources": [
                        {"chunk_id": c["chunk_id"], "source": c["source"],
                         "jurisdiction": c["jurisdiction"], "date": c["date"]}
                        for c in texts
                    ],
                    "overlap": round(overlap, 3),
                    "note": "sources address the same claim type with little shared wording; shown, not resolved",
                }
            )
    return conflicts
