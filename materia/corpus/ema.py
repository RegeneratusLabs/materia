"""EMA European Union herbal monograph adapter (PDF).

EMA's search endpoint is robots-blocked but the documents themselves are open, and the
sitemap enumerates them (scripts/harvest_ema.py). Each monograph has a fixed numbered
structure, which is what makes section-level citation possible:

    4.1 Therapeutic indications      4.5 Interactions
    4.2 Posology and method          4.6 Pregnancy and lactation
    4.3 Contraindications            4.8 Undesirable effects
    4.4 Special warnings             5.1/5.2 Pharmacology

Licence: EMA legal notice permits reproduction and distribution, commercial and
non-commercial, provided EMA is acknowledged as the source in each copy. Third-party
content is excluded.
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

import pymupdf

from .schema import dump_doc, make_chunk, make_doc, sha256_bytes
from .text import parse_month_date, split_paragraphs, topics

UA = "materia-corpus/0.1 (+local research build; contact: project owner)"
LICENCE = {
    "name": "EMA legal notice — reproduction authorised with acknowledgement",
    "redistributable": True,
    "evidence_url": "https://www.ema.europa.eu/en/legal-notice",
    "note": "Commercial and non-commercial reuse permitted with EMA acknowledged in each copy. Third-party content excluded.",
}

SECTION_MAP: list[tuple[str, str, str]] = [
    (r"4\.3\s+contraindication", "contraindications", "safety"),
    (r"4\.4\s+special warning|special precautions", "cautions", "safety"),
    (r"4\.5\s+interaction", "interactions", "safety"),
    (r"4\.6\s+pregnan|fertility", "cautions", "safety"),
    (r"4\.7\s+effects on ability", "cautions", "safety"),
    (r"4\.8\s+undesirable", "adverse_effects", "safety"),
    (r"4\.9\s+overdose", "adverse_effects", "safety"),
    (r"4\.1\s+therapeutic indication", "indications", "efficacy"),
    (r"4\.2\s+posology", "dosage", "dose"),
    (r"5\.1\s+pharmacodynamic", "pharmacology", "other"),
    (r"5\.2\s+pharmacokinetic", "pharmacology", "other"),
    (r"2\.\s+qualitative|3\.\s+pharmaceutical form", "methodology", "other"),
]

SKIP = (
    "superseded", "draft", "overview", "comments", "opinion", "assessment",
    "withdrawal", "list-entry", "call-", "revision-", "tracked",
)


def fetch(url: str, *, retries: int = 4, timeout: float = 90.0) -> bytes:
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(2.0 * (i + 1))  # EMA rate-limits; back off politely
    raise RuntimeError(f"fetch failed: {url}: {last}")


def slug_from_url(url: str) -> str:
    name = url.rsplit("/", 1)[-1].removesuffix(".pdf").removesuffix("_en")
    for prefix in (
        "final-community-herbal-monograph-",
        "community-herbal-monograph-",
        "final-european-union-herbal-monograph-",
        "european-union-herbal-monograph-",
        "final-",
    ):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_pdf(raw: bytes) -> tuple[str, int]:
    doc = pymupdf.open(stream=io.BytesIO(raw), filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    return text, len(doc)


def split_numbered(text: str) -> list[tuple[str, str]]:
    """Split on numbered headings such as '4.3 Contraindications'."""
    marks = list(re.finditer(r"^\s*(\d{1,2}(?:\.\d{1,2})?)\.?\s+([A-Z][^\n]{2,90})$", text, re.M))
    out: list[tuple[str, str]] = []
    for i, m in enumerate(marks):
        body_start = m.end()
        body_end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        heading = f"{m.group(1)} {m.group(2).strip()}"
        body = text[body_start:body_end].strip()
        if body:
            out.append((heading, body))
    return out


def classify(heading: str) -> tuple[str, str] | None:
    for pattern, section, assertion in SECTION_MAP:
        if re.search(pattern, heading, re.I):
            return section, assertion
    return None


def parse_monograph(text: str, url: str, pages: int, *, retrieved_at: str, raw: bytes) -> dict:
    slug = slug_from_url(url)
    doc_id = f"ema-{slug}"

    # title: the "European Union herbal monograph on ..." line
    title = ""
    m = re.search(r"(European Union herbal monograph on[^\n]{5,200})", text, re.I)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
    if not title:
        title = slug.replace("-", " ")

    # date of revision, else adoption/first authorisation
    revised = None
    for pattern in (
        r"date of revision of the text\s*:?\s*([^\n]{4,40})",
        r"date of first authorisation[^\n]{0,40}?(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})",
        r"adopted on\s*([^\n]{4,40})",
    ):
        m = re.search(pattern, text, re.I)
        if m:
            revised = parse_month_date(" ".join(m.group(1).split()))
            if revised:
                break
    if not revised:
        m = re.search(r"(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})", text)
        revised = parse_month_date(m.group(1)) if m else None

    ident = re.search(r"(EMA/HMPC/\d+/\d{3,})", text)
    herbs = re.findall(r"([A-Z][a-z]{2,}\s+[a-z]{3,}(?:\s+[a-z.]{2,})?)", title)
    entities = list(dict.fromkeys(herbs))[:3] or [slug.replace("-", " ")]

    chunks = []
    for heading, body in split_numbered(text):
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
                    topics=topics(txt),
                    entities=entities,
                    page=None,
                )
            )

    return make_doc(
        doc_id=doc_id,
        source="EMA (HMPC)",
        tier="regulatory",
        title=title,
        date_=revised,
        url=url,
        identifier={"type": "ema", "value": ident.group(1) if ident else url},
        jurisdiction="eu",
        language="en",
        licence=LICENCE,
        retrieved_at=retrieved_at,
        checksum=sha256_bytes(raw),
        chunks=chunks,
        entities=entities,
    )


def build(
    urls: list[str],
    out_dir: Path,
    *,
    limit: int = 0,
    sleep: float = 1.0,
    raw_dir: Path | None = None,
) -> dict:
    retrieved_at = date.today().isoformat()
    targets = [u for u in urls if not any(s in u.lower() for s in SKIP)]
    if limit:
        targets = targets[:limit]
    built, skipped, failed = [], [], []
    for n, url in enumerate(targets, start=1):
        try:
            raw = fetch(url)
            text, pages = parse_pdf(raw)
            doc = parse_monograph(text, url, pages, retrieved_at=retrieved_at, raw=raw)
        except Exception as e:
            failed.append({"url": url, "error": str(e)})
            print(f"[{n}/{len(targets)}] FAIL {url.rsplit('/', 1)[-1]}: {e}", flush=True)
            continue
        if raw_dir is not None:
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / url.rsplit("/", 1)[-1]).write_bytes(raw)
        if not doc["date"] or len(doc["chunks"]) < 3:
            skipped.append({"url": url, "reason": "no date or too few sections",
                            "date": doc["date"], "chunks": len(doc["chunks"])})
            print(f"[{n}/{len(targets)}] SKIP {doc['doc_id']} date={doc['date']} chunks={len(doc['chunks'])}", flush=True)
            continue
        dump_doc(doc, out_dir)
        built.append({"doc_id": doc["doc_id"], "url": url, "chunks": len(doc["chunks"]),
                      "date": doc["date"], "checksum": doc["checksum"]})
        print(f"[{n}/{len(targets)}] {doc['doc_id']} chunks={len(doc['chunks'])} date={doc['date']}", flush=True)
        time.sleep(sleep)
    return {"source": "ema", "built": built, "skipped": skipped, "failed": failed}


def _main() -> int:
    import argparse

    from .. import config

    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", default=str(config.CORPUS_DIR / "ema_monograph_urls.json"))
    ap.add_argument("--out", default=str(config.CORPUS_DIR / "docs"))
    ap.add_argument("--raw", default=str(config.CORPUS_DIR / "raw" / "ema"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    urls = json.loads(Path(args.urls).read_text())
    report = build(urls, Path(args.out), limit=args.limit, raw_dir=Path(args.raw))
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
