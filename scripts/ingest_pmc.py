#!/usr/bin/env python3
"""Ingest CC-BY full-text articles from Europe PMC into the materia corpus.

Why full text: an abstract rarely carries the dose table, the ferritin threshold, or the
contraindication. The recommendation engine needs those sentences, and every one must be
traceable to a chunk. Europe PMC's fullTextXML endpoint returns JATS for open-access
articles; this adapter keeps only articles whose licence is CC BY and records the
licence, DOI, and retrieval date on the document.

Usage:
    .venv/bin/python scripts/ingest_pmc.py --out corpus/docs
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config
from materia.corpus.schema import dump_doc, make_chunk, make_doc, sha256_bytes

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
UA = "materia-corpus/0.1 (+local research build)"

# Curated, not crawled. Each PMCID is a paper whose full text we want in the evidence
# graph: threshold, dose, or safety. Add a paper only when a rule needs it.
PAPERS: dict[str, dict] = {
    "PMC13449291": {
        "topics": ["iron", "ferritin", "anaemia"],
        "analytes": ["ferritin", "transferrin saturation", "haemoglobin", "mcv", "iron"],
        "entities": ["iron"],
    },
    "PMC13634279": {
        "topics": ["b12", "cobalamin", "deficiency"],
        "analytes": ["vitamin b12", "mcv", "homocysteine", "methylmalonic acid"],
        "entities": ["vitamin B12"],
    },
    "PMC13363889": {
        "topics": ["vitamin d", "deficiency"],
        "analytes": ["25-hydroxyvitamin d", "vitamin d"],
        "entities": ["vitamin D"],
    },
    "PMC11404857": {
        "topics": ["liver", "silymarin", "milk thistle"],
        "analytes": ["alt", "ast", "ggt"],
        "entities": ["milk thistle", "silymarin"],
    },
    "PMC12736498": {
        "topics": ["lipids", "turmeric", "curcumin"],
        "analytes": ["ldl", "hdl", "triglycerides", "total cholesterol"],
        "entities": ["turmeric", "curcumin"],
    },
    "PMC13606907": {
        "topics": ["lipids", "berberine", "glucose"],
        "analytes": ["ldl", "hdl", "triglycerides", "glucose", "hba1c"],
        "entities": ["berberine"],
    },
    "PMC13467960": {
        "topics": ["lipids", "omega-3", "fish oil"],
        "analytes": ["triglycerides", "ldl", "hdl"],
        "entities": ["fish oil", "omega-3"],
    },
    "PMC13678706": {
        "topics": ["full blood count", "anaemia"],
        "analytes": ["haemoglobin", "mcv", "platelets", "ferritin"],
        "entities": ["full blood count"],
    },
    "PMC13391447": {
        "topics": ["magnesium", "deficiency", "supplementation"],
        "analytes": ["magnesium"],
        "entities": ["magnesium"],
    },
    "PMC12564107": {
        "topics": ["bleeding", "omega-3", "anticoagulant"],
        "analytes": ["triglycerides"],
        "entities": ["omega-3"],
    },
    "PMC13127095": {
        "topics": ["ppi", "b12", "iron", "magnesium"],
        "analytes": ["vitamin b12", "magnesium", "iron", "ferritin"],
        "entities": ["proton pump inhibitor"],
    },
    "PMC12423746": {
        "topics": ["thiazide", "calcium", "vitamin d"],
        "analytes": ["calcium", "vitamin d"],
        "entities": ["thiazide"],
    },
    "PMC11723399": {
        "topics": ["berberine", "prediabetes", "diabetes", "dyslipidemia"],
        "analytes": ["hba1c", "glucose", "ldl", "triglycerides"],
        "entities": ["berberine"],
    },
    "PMC13115040": {
        "topics": ["critical values", "urgent", "laboratory"],
        "analytes": ["potassium", "sodium", "glucose", "calcium", "haemoglobin"],
        "entities": ["critical values"],
    },
    "PMC13512597": {
        "topics": ["zinc", "deficiency", "anaemia"],
        "analytes": ["zinc", "haemoglobin"],
        "entities": ["zinc"],
    },
    "PMC13401327": {
        "topics": ["homocysteine", "cardiovascular", "b12"],
        "analytes": ["homocysteine", "vitamin b12", "folate"],
        "entities": ["homocysteine"],
    },
    "PMC13525924": {
        "topics": ["kidney", "egfr", "ckd"],
        "analytes": ["egfr", "creatinine"],
        "entities": ["egfr"],
    },
}

# JATS section title -> (section, assertion_type). First match wins.
SECTION_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"abstract", re.I), "evidence", "efficacy"),
    (re.compile(r"dose|dosage|dosing|regimen|administration", re.I), "dosage", "dose"),
    (re.compile(r"contraindicat|adverse|safety|toxicit|risk", re.I), "cautions", "safety"),
    (re.compile(r"interaction", re.I), "interactions", "safety"),
    (re.compile(r"diagnos|threshold|reference|interpret", re.I), "reference_interval", "diagnostic"),
    (re.compile(r"monitor|follow[- ]?up", re.I), "monitoring", "monitoring"),
    (re.compile(r"method", re.I), "methodology", "other"),
    (re.compile(r"result", re.I), "evidence", "efficacy"),
    (re.compile(r"discussion|conclusion|introduction|background|review", re.I), "evidence", "efficacy"),
]

LICENCE = {
    "name": "CC BY 4.0 (Europe PMC open-access full text)",
    "redistributable": True,
    "evidence_url": "https://europepmc.org/RestfulWebService",
    "note": "Only articles whose JATS licence states CC BY are ingested.",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", " ".join(el.itertext())).strip()


def _first(root: ET.Element, path: str) -> ET.Element | None:
    return root.find(path)


def _find_all(root: ET.Element, name: str) -> list[ET.Element]:
    return [e for e in root.iter() if _local(e.tag) == name]


def _license_ok(root: ET.Element) -> bool:
    text = " ".join(_text(e) for e in _find_all(root, "license")).lower()
    if "cc by" in text or "creative commons attribution" in text:
        return True
    # Some JATS use a URI in an attribute rather than text.
    for e in _find_all(root, "license"):
        for k, v in e.attrib.items():
            if "creativecommons.org/licenses/by" in v.lower():
                return True
    return False


def _doi(root: ET.Element) -> str | None:
    for e in _find_all(root, "article-id"):
        if (e.attrib.get("pub-id-type") or "").lower() == "doi":
            return _text(e)
    return None


def _year(root: ET.Element) -> str | None:
    for e in _find_all(root, "pub-date"):
        y = e.find("year")
        if y is not None and _text(y).isdigit():
            return _text(y)
    return None


def _chunks_for(section: str, assertion: str, text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text.split()) < 8:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    buf: list[str] = []
    n = 0
    for s in sentences:
        w = len(s.split())
        if w == 0:
            continue
        if n + w > 120 and buf:
            out.append(" ".join(buf).strip())
            buf, n = [], 0
        buf.append(s)
        n += w
    if buf:
        out.append(" ".join(buf).strip())
    # A "dosage" chunk with no number is a narrative, not a dose.
    if section == "dosage" and not re.search(r"\b\d", " ".join(out)):
        section = "indications"
    return [c for c in out if 8 <= len(c.split()) <= 800]


def _classify(title: str) -> tuple[str, str]:
    for pat, section, assertion in SECTION_RULES:
        if pat.search(title or ""):
            return section, assertion
    return "other", "other"


def _walk_sections(el: ET.Element, depth: int = 0) -> list[tuple[str, str]]:
    """Return [(title, text)] for direct paragraph content, recursively."""
    out: list[tuple[str, str]] = []
    for child in list(el):
        if _local(child.tag) != "sec":
            continue
        title_el = next((c for c in list(child) if _local(c.tag) == "title"), None)
        title = _text(title_el)
        paras = [
            _text(p) for p in list(child)
            if _local(p.tag) in ("p", "list", "statement", "disp-quote")
        ]
        if paras:
            out.append((title, " ".join(paras)))
        out.extend(_walk_sections(child, depth + 1))
    return out


def _table_texts(root: ET.Element) -> list[tuple[str, str]]:
    out = []
    for tw in _find_all(root, "table-wrap"):
        caption = next((c for c in list(tw) if _local(c.tag) == "caption"), None)
        title = _text(caption) or "Table"
        rows = []
        for tr in (e for e in tw.iter() if _local(e.tag) == "tr"):
            cells = [_text(c) for c in list(tr) if _local(c.tag) in ("td", "th")]
            cells = [c for c in cells if c]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            out.append((title, "\n".join(rows)))
    return out


def parse_article(xml: bytes, pmcid: str, *, retrieved_at: str) -> dict | None:
    root = ET.fromstring(xml)
    if not _license_ok(root):
        return None
    title = _text(next(iter(_find_all(root, "article-title")), None)) or "Untitled"
    journal = _text(next(iter(_find_all(root, "journal-title")), None)) or "PMC"
    year = _year(root) or retrieved_at[:4]
    doi = _doi(root)

    raw: list[tuple[str, str]] = []
    abstract = next(iter(_find_all(root, "abstract")), None)
    if abstract is not None:
        body = " ".join(_text(p) for p in list(abstract) if _local(p.tag) in ("p", "sec"))
        raw.append(("Abstract", body or _text(abstract)))
    body_el = next(iter(_find_all(root, "body")), None)
    if body_el is not None:
        raw.extend(_walk_sections(body_el))
    raw.extend(_table_texts(root))

    chunks: list[dict] = []
    for heading, text in raw:
        section, assertion = _classify(heading)
        for piece in _chunks_for(section, assertion, text):
            chunks.append(make_chunk(
                f"pmc-{pmcid.lower()}#{len(chunks) + 1:03d}",
                f"{heading}: {piece}" if heading and heading.lower() != "abstract" else piece,
                section, assertion,
                topics=PAPERS[pmcid]["topics"],
                entities=PAPERS[pmcid]["entities"],
                analytes=PAPERS[pmcid]["analytes"],
            ))
    if not chunks:
        return None
    # Keep documents bounded: the first 80 chunks cover the article body and tables.
    chunks = chunks[:80]
    return make_doc(
        doc_id=f"pmc-{pmcid.lower()}",
        source="Europe PMC (CC-BY full text)",
        tier="primary",
        title=title[:300],
        date_=f"{year}-01-01",
        url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
        identifier={"type": "doi" if doi else "other", "value": doi or pmcid},
        jurisdiction="international",
        language="en",
        licence=LICENCE,
        retrieved_at=retrieved_at,
        checksum=sha256_bytes(xml),
        chunks=chunks,
        entities=PAPERS[pmcid]["entities"],
    )


def fetch(pmcid: str, *, retries: int = 5, timeout: float = 120.0) -> bytes:
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(API.format(pmcid=pmcid), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # transient
            last = e
            time.sleep(4 * (i + 1))
    raise RuntimeError(f"{pmcid}: {last}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(config.CORPUS_DIR / "docs"))
    ap.add_argument("--only", nargs="*", default=[])
    args = ap.parse_args()
    retrieved_at = date.today().isoformat()
    out = Path(args.out)
    built, failed = [], []
    ids = args.only or list(PAPERS)
    for pmcid in ids:
        try:
            xml = fetch(pmcid)
            doc = parse_article(xml, pmcid, retrieved_at=retrieved_at)
            if doc is None:
                raise ValueError("no CC BY licence or no usable chunks")
            dump_doc(doc, out)
            built.append({"pmcid": pmcid, "doc_id": doc["doc_id"], "chunks": len(doc["chunks"]),
                          "title": doc["title"][:90]})
            print(f"{pmcid}: {len(doc['chunks'])} chunks :: {doc['title'][:90]}", flush=True)
        except Exception as e:
            failed.append({"pmcid": pmcid, "error": str(e)})
            print(f"{pmcid}: FAIL {e}", flush=True)
        time.sleep(1.5)
    print(json.dumps({"built": built, "failed": failed}, indent=1))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
