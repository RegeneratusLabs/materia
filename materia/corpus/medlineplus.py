"""MedlinePlus (NLM) encyclopedia adapter — lab test interpretation.

Public-domain US federal content, with the one thing the lab branch was missing: the
"Normal Results" and "What Abnormal Results Mean" sections, i.e. reference intervals and
their interpretation, from a citable source.

Article IDs were discovered from the encyclopedia A-Z index and selected by title; the
list is curated rather than crawled, so poisoning/overdose pages cannot leak in.
"""
from __future__ import annotations

import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

from .schema import dump_doc, make_chunk, make_doc, sha256_bytes
from .text import split_paragraphs, topics

UA = "materia-corpus/0.1 (+local research build)"
BASE = "https://medlineplus.gov/ency/article/{aid}.htm"

LICENCE = {
    "name": "US federal work — public domain (NLM MedlinePlus)",
    "redistributable": True,
    "evidence_url": "https://medlineplus.gov/copyright.html",
    "note": "Most MedlinePlus health topic and encyclopedia content is free of copyright restrictions.",
}

# article id -> (entity label, topic tags)
ARTICLES: dict[str, tuple[str, list[str]]] = {
    "003490": ("Ferritin blood test", ["ferritin", "iron"]),
    "003488": ("Serum iron test", ["iron", "ferritin"]),
    "003489": ("Total iron binding capacity", ["iron", "transferrin", "ferritin"]),
    "003705": ("Vitamin B12 level", ["b12", "folate"]),
    "003684": ("TSH test", ["thyroid", "tsh"]),
    "003517": ("Free T4 test", ["thyroid", "ft4"]),
    "003687": ("T3 test", ["thyroid", "t3"]),
    "003473": ("Alanine transaminase (ALT) blood test", ["alt", "liver"]),
    "003472": ("Aspartate aminotransferase (AST) blood test", ["ast", "liver"]),
    "003458": ("Gamma-glutamyl transferase (GGT) blood test", ["ggt", "liver"]),
    "003356": ("C-reactive protein", ["crp"]),
    "003642": ("CBC blood test", ["haemoglobin", "anaemia"]),
    "003640": ("A1C test", ["hba1c", "glucose"]),
    "003638": ("ESR", ["crp", "inflammation"]),
    "003475": ("Creatinine blood test", ["creatinine", "renal"]),
    "003477": ("Calcium blood test", ["calcium"]),
    "003487": ("Magnesium blood test", ["magnesium"]),
    "007813": ("Total cholesterol", ["cholesterol"]),
    "007810": ("HDL test", ["hdl", "cholesterol"]),
    "007811": ("LDL test", ["ldl", "cholesterol"]),
    "007812": ("Lipid profile test", ["cholesterol", "ldl", "hdl", "triglycerides"]),
    "003493": ("Triglyceride level", ["triglycerides"]),
    "003480": ("Albumin blood (serum) test", ["albumin", "liver"]),
    "003479": ("Bilirubin blood test", ["bilirubin", "liver"]),
    "003484": ("Potassium test", ["potassium"]),
    "003481": ("Sodium blood test", ["sodium"]),
    "003476": ("Uric acid - blood", ["uric acid"]),
    "003686": ("Folic acid - test", ["folate"]),
    "000354": ("Folate deficiency", ["folate"]),
    "002405": ("Vitamin D", ["vitamin d"]),
    "000315": ("Magnesium deficiency", ["magnesium"]),
}

SECTION_MAP: list[tuple[str, str, str]] = [
    (r"normal result", "reference_interval", "diagnostic"),
    (r"abnormal result", "reference_interval", "diagnostic"),
    (r"why the test", "evidence", "diagnostic"),
    (r"how the test is performed|how to prepare|how the test will feel", "methodology", "other"),
    # Encyclopedia pages for deficiencies carry the clinical context a lab test page
    # does not: what causes the abnormality, how it is confirmed, and what treatment
    # looks like. They are tagged so the recommendation engine can retrieve them.
    (r"exams and tests", "reference_interval", "diagnostic"),
    (r"causes", "differential", "diagnostic"),
    (r"symptoms", "differential", "diagnostic"),
    (r"treatment", "indications", "efficacy"),
    (r"prevention", "indications", "efficacy"),
    (r"recommendations", "reference_interval", "diagnostic"),
    (r"food sources", "indications", "efficacy"),
    (r"side effects", "cautions", "safety"),
    (r"possible complications", "cautions", "safety"),
    (r"when to contact", "red_flags", "safety"),
]


def fetch(url: str, *, retries: int = 3, timeout: float = 40.0) -> str:
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(1.0 * (i + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")


def classify(heading: str) -> tuple[str, str] | None:
    for pattern, section, assertion in SECTION_MAP:
        if re.search(pattern, heading, re.I):
            return section, assertion
    return None


def parse(html: str, aid: str, *, retrieved_at: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else ARTICLES[aid][0]

    m = re.search(r"Review Date\s+(\d{1,2})/(\d{1,2})/(\d{4})", soup.get_text(" "), re.I)
    if not m:
        return None
    published = f"{int(m.group(3)):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"

    main = soup.find("main") or soup.find("article") or soup.body or soup
    for tag in main.find_all(["script", "style", "nav", "aside", "footer", "form", "button"]):
        tag.decompose()
    for h in main.find_all(["h2", "h3"]):
        h.insert_before(NavigableString(f"\n@@HEAD@@ {h.get_text(' ', strip=True)}\n"))
        h.decompose()
    text = re.sub(r"[ \t]+", " ", main.get_text("\n"))
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()

    sections: list[tuple[str, str]] = []
    parts = re.split(r"@@HEAD@@[ ]*", text)
    for part in parts[1:]:
        lines = part.split("\n", 1)
        heading = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        if body:
            sections.append((heading, body))

    doc_id = f"medlineplus-{aid}"
    entity, topic_tags = ARTICLES[aid]
    chunks = []
    for heading, body in sections:
        mapped = classify(heading)
        if not mapped:
            continue
        for piece in split_paragraphs(body):
            txt = f"{heading}: {piece}"
            if len(txt.split()) < 8:
                continue
            chunks.append(
                make_chunk(
                    f"{doc_id}#{len(chunks) + 1:03d}",
                    txt,
                    mapped[0],
                    mapped[1],
                    topics=list(dict.fromkeys(topic_tags + topics(txt))),
                    entities=[entity],
                )
            )
    if not chunks:
        return None
    return make_doc(
        doc_id=doc_id,
        source="MedlinePlus (NLM)",
        tier="compendium",
        title=title,
        date_=published,
        url=BASE.format(aid=aid),
        identifier={"type": "web", "value": BASE.format(aid=aid)},
        jurisdiction="us",
        language="en",
        licence=LICENCE,
        retrieved_at=retrieved_at,
        checksum=sha256_bytes(html.encode("utf-8", "replace")),
        chunks=chunks,
        entities=[entity],
    )


def build(out_dir: Path, *, sleep: float = 0.6, limit: int = 0) -> dict:
    retrieved_at = date.today().isoformat()
    ids = list(ARTICLES)[: limit or None]
    built, skipped, failed = [], [], []
    for n, aid in enumerate(ids, start=1):
        try:
            doc = parse(fetch(BASE.format(aid=aid)), aid, retrieved_at=retrieved_at)
        except Exception as e:
            failed.append({"id": aid, "error": str(e)})
            print(f"[{n}/{len(ids)}] FAIL {aid}: {e}", flush=True)
            continue
        if doc is None:
            skipped.append({"id": aid, "reason": "no review date or no mapped sections"})
            print(f"[{n}/{len(ids)}] SKIP {aid}", flush=True)
            continue
        dump_doc(doc, out_dir)
        built.append({"doc_id": doc["doc_id"], "chunks": len(doc["chunks"]), "date": doc["date"]})
        print(f"[{n}/{len(ids)}] {doc['doc_id']} chunks={len(doc['chunks'])} date={doc['date']}", flush=True)
        time.sleep(sleep)
    return {"source": "medlineplus", "built": built, "skipped": skipped, "failed": failed}


def _main() -> int:
    import argparse

    from .. import config

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(config.CORPUS_DIR / "docs"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    report = build(Path(args.out), limit=args.limit)
    print({"built": len(report["built"]), "skipped": len(report["skipped"]), "failed": len(report["failed"])})
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(_main())
