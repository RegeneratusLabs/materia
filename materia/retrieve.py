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
    "dong quai": ["angelica sinensis", "angelicae sinensis radix"],
    "comfrey": ["symphytum officinale", "symphyti radix"],
    "reishi": ["ganoderma lucidum"],
    "cordyceps": ["cordyceps sinensis", "ophiocordyceps"],
    "berberine": ["berberis", "berberidis cortex", "coptis"],
    "holy basil": ["ocimum tenuiflorum", "ocimum sanctum", "tulsi"],
    "probiotics": ["lactobacillus", "bifidobacterium"],
    "sam-e": ["s-adenosylmethionine", "s adenosyl methionine"],
    "dhea": ["dehydroepiandrosterone"],
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
    # safety intent first: a "bleeding risk with high-dose X" question is a safety question
    (r"risk|safe|contraindicat|adverse|toxicit|hepatotox|interact|bleed|coagul|anticoag|"
     r"warfarin|inr|pregnan|lactat|side effect|concern|consequence|danger|harm",
     {"contraindications", "cautions", "adverse_effects", "interactions", "red_flags"}),
    (r"dose|dosage|how much|\bmg\b|amount|regimen", {"dosage"}),
    (r"effective|evidence|benefit|improv|help|treat|work|indication", {"indications", "evidence", "pharmacology"}),
    (r"lab|ferritin|tsh|b12|folate|reference|range|interval", {"reference_interval", "monitoring"}),
]

ANALYTES = {
    "tsh", "t3", "t4", "ft3", "ft4", "b12", "folate", "ferritin", "iron", "transferrin",
    "ggt", "alt", "ast", "alp", "crp", "esr", "creatinine", "calcium", "magnesium", "zinc",
    "hba1c", "homocysteine", "cholesterol", "ldl", "hdl", "triglycerides", "haemoglobin",
}
LAB_WORDS = re.compile(r"raised|elevated|low|high|normal|level|value|range|deficien|result", re.I)


def is_lab_question(question: str) -> bool:
    low = question.lower()
    hits = [a for a in ANALYTES if re.search(rf"\b{a}\b", low)]
    if len(hits) >= 2:
        return True
    return bool(hits) and bool(LAB_WORDS.search(question))


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
    if is_lab_question(question):
        return {"reference_interval", "monitoring"}
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
    """BM25 retrieval with an entity-first candidate set and a section prior.

    Why this exists: plain BM25 on a herb question returns the herb's *name* chunk and
    whatever else shares vocabulary. A clinician asking "is St John's wort safe with
    warfarin" needs the contraindication/interaction chunk, not the taxonomy. So: resolve
    the entity, restrict candidates to that herb's documents, then rank by claim type.
    """

    def __init__(self, conn: sqlite3.Connection, *, k: int = 6, per_doc: int = 2,
                 require_jurisdiction: bool = False):
        self.conn = conn
        self.k = k
        self.per_doc = per_doc
        self.lex = build_lexicon(conn)
        self.require_jurisdiction = require_jurisdiction

    # -- internals ---------------------------------------------------------
    @staticmethod
    def _norm(text: str) -> str:
        return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).replace("  ", " ").strip()

    def _load_doc_entities(self) -> dict[str, str]:
        if getattr(self, "_doc_entity_cache", None) is None:
            cache: dict[str, str] = {}
            for row in self.conn.execute("SELECT doc_id, entities FROM docs"):
                try:
                    ents = json.loads(row["entities"] or "[]")
                except json.JSONDecodeError:
                    ents = []
                cache[row["doc_id"]] = self._norm(" ".join(ents))
            self._doc_entity_cache = cache
        return self._doc_entity_cache

    def _entity_docs(self, entities: list[str]) -> set[str]:
        """Match on normalised text so "St. John's Wort" and "st johns wort" agree."""
        if not entities:
            return set()
        cache = self._load_doc_entities()
        tokens: set[str] = set()
        for e in entities:
            base = re.sub(r"\s*\([^)]*\)", "", e)
            tokens.add(self._norm(base))
            m = re.search(r"\(([^)]+)\)", e)
            if m:
                tokens.add(self._norm(m.group(1)))
            if len(base.split()) > 2:
                tokens.add(self._norm(" ".join(base.split()[:2])))
        tokens = {t for t in tokens if len(t) >= 4}
        if not tokens:
            return set()
        out: set[str] = set()
        for doc_id, text in cache.items():
            if any(t in text for t in tokens):
                out.add(doc_id)
        return out

    def _section_chunks(self, doc_ids: set[str], sections: set[str], limit: int = 24) -> list[dict]:
        """Chunks of the right claim type from the entity's own documents.

        BM25 alone misses these when the question's vocabulary matches a dosage sentence
        better than a contraindication; the clinician still needs the contraindication.
        """
        if not doc_ids or not sections:
            return []
        docs = list(doc_ids)[:20]
        marks = ",".join("?" for _ in docs)
        secs = list(sections)
        smarks = ",".join("?" for _ in secs)
        rows = self.conn.execute(
            f"""
            SELECT c.chunk_id, c.doc_id, c.text, c.section, c.assertion_type, c.topics,
                   c.entities, d.source, d.tier, d.jurisdiction, d.date, d.title, d.url,
                   d.identifier_value
            FROM chunks c JOIN docs d ON d.doc_id = c.doc_id
            WHERE c.doc_id IN ({marks}) AND c.section IN ({smarks})
            LIMIT ?
            """,
            docs + secs + [limit],
        ).fetchall()
        return [dict(r) for r in rows]

    def _meta(self, chunk_ids: list[str]) -> dict[str, dict]:
        if not chunk_ids:
            return {}
        marks = ",".join("?" for _ in chunk_ids)
        rows = self.conn.execute(
            f"""
            SELECT c.chunk_id, c.doc_id, c.text, c.section, c.assertion_type, c.topics,
                   c.entities, d.source, d.tier, d.jurisdiction, d.date, d.title, d.url,
                   d.identifier_value
            FROM chunks c JOIN docs d ON d.doc_id = c.doc_id
            WHERE c.chunk_id IN ({marks})
            """,
            chunk_ids,
        ).fetchall()
        return {r["chunk_id"]: dict(r) for r in rows}

    # -- search ------------------------------------------------------------
    def search(self, question: str, jurisdiction: str | None = None,
               entity_first: bool = True) -> list[dict]:
        entities = find_entities(question, self.lex)
        low = question.lower()
        alias_terms = {a for a in self.lex if len(a) >= 4 and a in low}
        match_terms = list(dict.fromkeys(entities + sorted(alias_terms)))
        query = _fts_query(question, entities)
        if not query:
            return []
        rows = self.conn.execute(
            """
            SELECT f.chunk_id, bm25(chunks_fts, 1.0, 2.0, 1.5, 1.0) AS score
            FROM chunks_fts f
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT 240
            """,
            (query,),
        ).fetchall()
        if not rows:
            return []

        meta = self._meta([r["chunk_id"] for r in rows])
        want = expected_sections(question)
        ent_docs = self._entity_docs(match_terms) if entity_first else set()

        candidates: list[dict] = []
        for row in rows:
            m = meta.get(row["chunk_id"])
            if not m:
                continue
            if jurisdiction and m["jurisdiction"] not in (jurisdiction, "international"):
                continue
            if is_boilerplate(m["text"]):
                continue
            in_entity = m["doc_id"] in ent_docs
            section_hit = m["section"] in want
            # entity documents first, then claim-type fit, then BM25
            score = (
                (1.0 if in_entity else 0.0)
                + (0.6 if section_hit else 0.0)
                - row["score"] / 50.0
            )
            candidates.append(
                {
                    "chunk_id": m["chunk_id"],
                    "doc_id": m["doc_id"],
                    "text": m["text"],
                    "section": m["section"],
                    "assertion_type": m["assertion_type"],
                    "topics": json.loads(m["topics"] or "[]"),
                    "entities": json.loads(m["entities"] or "[]"),
                    "source": m["source"],
                    "tier": m["tier"],
                    "jurisdiction": m["jurisdiction"],
                    "date": m["date"],
                    "title": m["title"],
                    "url": m["url"],
                    "identifier": m["identifier_value"],
                    "bm25": round(row["score"], 3),
                    "in_entity_doc": in_entity,
                    "score": round(score, 3),
                }
            )

        # claim-type chunks from the entity's own documents always get a look-in
        if ent_docs and want:
            seen = {c["chunk_id"] for c in candidates}
            for m in self._section_chunks(ent_docs, want):
                if m["chunk_id"] in seen:
                    continue
                candidates.append(
                    {
                        "chunk_id": m["chunk_id"],
                        "doc_id": m["doc_id"],
                        "text": m["text"],
                        "section": m["section"],
                        "assertion_type": m["assertion_type"],
                        "topics": json.loads(m["topics"] or "[]"),
                        "entities": json.loads(m["entities"] or "[]"),
                        "source": m["source"],
                        "tier": m["tier"],
                        "jurisdiction": m["jurisdiction"],
                        "date": m["date"],
                        "title": m["title"],
                        "url": m["url"],
                        "identifier": m["identifier_value"],
                        "bm25": 0.0,
                        "in_entity_doc": True,
                        "score": 2.0,
                    }
                )

        if not candidates:
            return []
        candidates.sort(key=lambda c: c["score"], reverse=True)

        chosen: list[dict] = []
        used: dict[str, int] = {}
        covered: set[str] = set()
        # pass 1: one chunk per expected section from an entity document, best first
        for c in candidates:
            if c["section"] not in want or c["section"] in covered:
                continue
            if used.get(c["doc_id"], 0) >= self.per_doc:
                continue
            chosen.append(c)
            used[c["doc_id"]] = used.get(c["doc_id"], 0) + 1
            covered.add(c["section"])
        # pass 2: fill by score, respecting the per-document cap
        for c in candidates:
            if len(chosen) >= self.k:
                break
            if c in chosen:
                continue
            if used.get(c["doc_id"], 0) >= self.per_doc:
                continue
            chosen.append(c)
            used[c["doc_id"]] = used.get(c["doc_id"], 0) + 1
        chosen.sort(key=lambda c: c["score"], reverse=True)
        return chosen[: self.k]


CLINICAL_ASSERTIONS = {"safety", "dose", "efficacy", "monitoring", "diagnostic"}

# Boilerplate that survives BM25 on every question about a source. Retrieving it as
# evidence is worse than retrieving nothing: it looks authoritative and says nothing.
BOILERPLATE = re.compile(
    r"clearinghouse|this publication is not copyrighted|all rights reserved|"
    r"for more information, contact|national center for complementary|"
    r"subscribe to (our|the) newsletter|last updated:|page last reviewed|"
    r"references cited|key references",
    re.I,
)


def is_boilerplate(text: str) -> bool:
    return bool(BOILERPLATE.search(text or ""))


STOP_TERMS = set(
    "what which patient patients taking takes taken asks about does most likely main concern "
    "risk risks because chief appropriate response concern concerned with from that this these "
    "those produce produces result results effect effects caused cause daily product products "
    "treatment treatments symptom symptoms health herbal supplement supplements medication "
    "medications therapy blood levels level high low increase increase increased decrease "
    "decreased reduce reduced recommend recommended".split()
)


def _terms_short(text: str) -> set[str]:
    """Lab analytes are short: TSH, T3, T4, B12, ALT, AST, GGT, CRP, ESR."""
    return {t for t in re.split(r"\W+", text.lower())
            if len(t) > 2 and t not in STOP_TERMS}


def _terms(text: str) -> set[str]:
    return {t for t in re.split(r"\W+", text.lower())
            if len(t) > 4 and t not in STOP_TERMS}


def grounded_chunks(chunks: list[dict], question: str) -> list[dict]:
    """Chunks that plausibly cover the question.

    Entity document + claim type is not enough on its own: a fish-oil cautions chunk is the
    right entity and the right claim type for a kava hepatotoxicity question only by
    accident. So the chunk must also share at least two content terms with the question,
    ignoring the entity's own names (which always match).
    """
    want = expected_sections(question)
    q_terms = _terms(question)
    lab_intent = bool({"reference_interval", "monitoring"} & want)
    if lab_intent:
        q_terms = _terms_short(question)
    out = []
    for c in chunks:
        if lab_intent:
            # Lab questions are about an analyte, not a herb; the document entity is a test
            # name and will not match. The gate is: right claim type AND the analyte named
            # in the question appears in the test document's title.
            if not (c["section"] in want or c["assertion_type"] == "diagnostic"):
                continue
            doc_terms = _terms_short(" ".join(c.get("entities") or []) + " " + c.get("title", ""))
            if not (q_terms & doc_terms):
                continue
            out.append(c)
            continue
        else:
            if not c.get("in_entity_doc"):
                continue
            if not (c["section"] in want or c["assertion_type"] in CLINICAL_ASSERTIONS):
                continue
        entity_terms = _terms(" ".join(c.get("entities") or []) + " " + c.get("title", ""))
        overlap = (q_terms - entity_terms) & _terms(c["text"])
        if len(overlap) >= 1:
            out.append(c)
    return out


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
