"""MedlinePlus symptom articles -> referral red-flag evidence.

The referral branch had no corpus at all. These pages carry a "When to Contact a Medical
Professional" section, which is exactly the cited red-flag guidance the deterministic gate
should be able to point at. Public domain (NLM).
"""
from __future__ import annotations

import re
import string
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
INDEX = "https://medlineplus.gov/ency/encyclopedia_{letter}.htm"

LICENCE = {
    "name": "US federal work — public domain (NLM MedlinePlus)",
    "redistributable": True,
    "evidence_url": "https://medlineplus.gov/copyright.html",
    "note": "Most MedlinePlus health topic and encyclopedia content is free of copyright restrictions.",
}

# Titles worth ingesting for referral. Deliberately narrow: no poisonings, no diets.
TITLE_PATTERNS = re.compile(
    r"^(abdominal pain|chest pain|headache|back pain|cough|fever|dizziness|fainting|"
    r"shortness of breath|breathing problems|nausea and vomiting|blood in the stool|"
    r"vomiting blood|weight loss|fatigue|confusion|seizures?|night sweats|"
    r"swelling|leg pain|calf pain|vision problems|blurred vision|"
    r"painful urination|urinary tract infection)\b",
    re.I,
)

HEADING_MAP: list[tuple[str, str, str]] = [
    (r"when to contact|when to call|seek (immediate|urgent)|call (your|the) (doctor|provider)|"
     r"contact a medical professional", "red_flags", "diagnostic"),
    (r"what (abnormal|the results) mean|tests? and results?", "reference_interval", "diagnostic"),
    (r"causes|symptoms|overview", "evidence", "diagnostic"),
    (r"prevention|outlook|references|alternative names|images|related", None, None),
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


def discover(limit: int = 24) -> dict[str, str]:
    found: dict[str, str] = {}
    for letter in string.ascii_uppercase:
        try:
            html = fetch(INDEX.format(letter=letter))
        except Exception:
            continue
        for m in re.finditer(r'href="article/(\d+)\.htm"[^>]*>([^<]{3,120})</a>', html):
            title = re.sub(r"\s+", " ", m.group(2)).strip()
            if TITLE_PATTERNS.match(title):
                found.setdefault(m.group(1), title)
        if len(found) >= limit:
            break
    return dict(list(found.items())[:limit])


def classify(heading: str):
    for pattern, section, assertion in HEADING_MAP:
        if re.search(pattern, heading, re.I):
            return None if section is None else (section, assertion)
    return None


def parse(html: str, aid: str, title: str, *, retrieved_at: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    page_title = h1.get_text(" ", strip=True) if h1 else title

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
    text = re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", main.get_text("\n"))).strip()

    doc_id = f"medlineplus-sym-{aid}"
    chunks = []
    for part in re.split(r"@@HEAD@@[ ]*", text)[1:]:
        lines = part.split("\n", 1)
        heading = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        if not body:
            continue
        mapped = classify(heading)
        if mapped is None:
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
                    topics=list(dict.fromkeys(["referral"] + topics(txt))),
                    entities=[page_title],
                )
            )
    if not chunks:
        return None
    return make_doc(
        doc_id=doc_id,
        source="MedlinePlus (NLM)",
        tier="compendium",
        title=page_title,
        date_=published,
        url=BASE.format(aid=aid),
        identifier={"type": "web", "value": BASE.format(aid=aid)},
        jurisdiction="us",
        language="en",
        licence=LICENCE,
        retrieved_at=retrieved_at,
        checksum=sha256_bytes(html.encode("utf-8", "replace")),
        chunks=chunks,
        entities=[page_title],
    )


def build(out_dir: Path, *, sleep: float = 0.6, limit: int = 24) -> dict:
    retrieved_at = date.today().isoformat()
    targets = discover(limit)
    built, failed = [], []
    print(f"discovered {len(targets)} symptom articles")
    for n, (aid, title) in enumerate(targets.items(), start=1):
        try:
            doc = parse(fetch(BASE.format(aid=aid)), aid, title, retrieved_at=retrieved_at)
        except Exception as e:
            failed.append({"id": aid, "error": str(e)})
            print(f"[{n}/{len(targets)}] FAIL {aid}: {e}", flush=True)
            continue
        if doc is None:
            print(f"[{n}/{len(targets)}] SKIP {aid} {title}", flush=True)
            continue
        dump_doc(doc, out_dir)
        built.append({"doc_id": doc["doc_id"], "title": title, "chunks": len(doc["chunks"])})
        print(f"[{n}/{len(targets)}] {doc['doc_id']} chunks={len(doc['chunks'])} :: {title}", flush=True)
        time.sleep(sleep)
    return {"source": "medlineplus-symptoms", "built": built, "failed": failed}


def _main() -> int:
    import argparse

    from .. import config

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(config.CORPUS_DIR / "docs"))
    ap.add_argument("--limit", type=int, default=24)
    args = ap.parse_args()
    report = build(Path(args.out), limit=args.limit)
    print({"built": len(report["built"]), "failed": len(report["failed"])})
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
