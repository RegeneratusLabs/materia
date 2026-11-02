"""Health Canada NNHPD monograph adapter.

182 single-ingredient + 41 multi-ingredient monographs, OGL-Canada, one page each with a
stable structure: Date, Proper names table, Route, Dosage forms, Uses, Doses (with
Subpopulation / Quantity / Directions sub-headings), Duration, Risk Information
(Cautions / Contraindications / Known adverse reactions), References.

Licence: Open Government Licence – Canada permits copy, modify and distribute for
commercial and non-commercial purposes with attribution. Verify per document.
"""
from __future__ import annotations

import html as htmlmod
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

from .schema import dump_doc, make_chunk, make_doc, sha256_bytes
from .text import split_paragraphs, topics

BASE = "https://webprod.hc-sc.gc.ca/nhpid-bdipsn"
INDEX_SINGLE = f"{BASE}/monosReq?monotype=single"
INDEX_PRODUCT = f"{BASE}/monosReq?monotype=product"
MONO = BASE + "/atReq?atid={atid}&lang=eng"

SOURCE = "Health Canada NNHPD"
LICENCE = {
    "name": "Open Government Licence – Canada",
    "redistributable": True,
    "evidence_url": "https://open.canada.ca/en/open-government-licence-canada",
    "note": "Commercial and non-commercial reuse permitted with attribution. Third-party figures excluded.",
}

UA = "materia-corpus/0.1 (+local research build; contact: project owner)"

# h2 heading -> (section, assertion_type). None = do not emit chunks.
SECTION_MAP: dict[str, tuple[str, str] | None] = {
    "date": None,
    "table of contents": None,
    "proper name(s), common name(s), source information": None,
    "proper names, common names and source information": None,
    "route of administration": ("methodology", "other"),
    "dosage form(s)": ("methodology", "other"),
    "dosage forms": ("methodology", "other"),
    "use(s) or purpose(s)": ("indications", "efficacy"),
    "uses or purposes": ("indications", "efficacy"),
    "dose(s)": ("dosage", "dose"),
    "dose": ("dosage", "dose"),
    "duration(s) of use": ("dosage", "dose"),
    "durations of use": ("dosage", "dose"),
    "risk information": ("cautions", "safety"),
    "non-medicinal ingredients": None,
    "storage conditions": None,
    "specifications": None,
    "references cited": None,
    "references reviewed": None,
    "references": None,
    "version history": None,
}

# h3 under Risk Information
H3_MAP: dict[str, tuple[str, str]] = {
    "caution(s) and warning(s)": ("cautions", "safety"),
    "contraindication(s)": ("contraindications", "safety"),
    "known adverse reaction(s)": ("adverse_effects", "safety"),
    "subpopulation(s)": ("dosage", "dose"),
    "quantity(ies)": ("dosage", "dose"),
    "direction(s) for use": ("dosage", "dose"),
    # The multi-vitamin/mineral monograph is numbered and nests its dose tables under
    # h3 headings; these are the sections that carry the actual daily dose ranges.
    "general use or purpose statements": ("indications", "efficacy"),
    "specific use or purpose statements": ("indications", "efficacy"),
    "specific use or purpose statements for vitamins": ("indications", "efficacy"),
    "specific use or purpose statements for minerals": ("indications", "efficacy"),
    "specific use or purpose statements for other medicinal ingredients": ("indications", "efficacy"),
    "background on dose": ("dosage", "dose"),
    "dose information for vitamins": ("dosage", "dose"),
    "dose information for minerals": ("dosage", "dose"),
    "dose information for other medicinal ingredients": ("dosage", "dose"),
    "caution(s) and warning(s)": ("cautions", "safety"),
    "cautions and warnings": ("cautions", "safety"),
    "contraindication(s)": ("contraindications", "safety"),
    "contraindications": ("contraindications", "safety"),
    "known adverse reactions": ("adverse_effects", "safety"),
    "dose information for complementary medicinal ingredients": ("dosage", "dose"),
    "directions for use": ("dosage", "dose"),
}

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july", "august",
         "september", "october", "november", "december"],
        start=1,
    )
}


def fetch(url: str, *, retries: int = 3, timeout: float = 40.0) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # transient 429/5xx
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")


def _clean(fragment: str) -> str:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment, flags=re.S | re.I)
    s = re.sub(r"<img[^>]*>", " ", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</t[dh]>", " | ", s, flags=re.I)
    s = re.sub(r"</tr>", "\n", s, flags=re.I)
    s = re.sub(r"</(p|li|div|h[1-6])>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmlmod.unescape(s)
    s = s.replace("\u00a0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip(" |") for ln in s.split("\n")]
    return "\n".join(ln for ln in lines if ln.strip())


def split_sections(html: str) -> tuple[str, list[tuple[str, str, str]]]:
    """Return (page title, [(h2, h3, text), ...])."""
    title = ""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    if m:
        title = _clean(m.group(1)).strip()

    start = re.search(r"<h2[^>]*>\s*Date\s*</h2>", html, re.I)
    end = re.search(r"<h2[^>]*>\s*(References Cited|About government)", html, re.I)
    region = html[start.start() if start else 0 : end.start() if end else len(html)]

    marks = list(re.finditer(r"<(h2|h3)[^>]*>(.*?)</\1>", region, re.S | re.I))
    out: list[tuple[str, str, str]] = []
    for i, mk in enumerate(marks):
        level = mk.group(1).lower()
        heading = _clean(mk.group(2)).strip()
        body_start = mk.end()
        body_end = marks[i + 1].start() if i + 1 < len(marks) else len(region)
        body = _clean(region[body_start:body_end])
        if not body:
            continue
        out.append((level, heading, body))
    return title, out


def _parse_date(text: str) -> str | None:
    m = re.search(r"([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})", text)
    if m and m.group(1).lower() in _MONTHS:
        return date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2))).isoformat()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    return m.group(0) if m else None


def _heading_key(heading: str) -> str:
    """Normalise '5.3 Dose information for vitamins' to 'dose information for vitamins'."""
    text = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", (heading or "").strip())
    return text.lower().rstrip(":")


def parse_monograph(html: str, atid: str, url: str, *, retrieved_at: str) -> dict:
    title, sections = split_sections(html)
    published: str | None = None
    proper: list[str] = []
    body_chunks: list[tuple[str, str, str]] = []  # (text, section, assertion)

    for level, heading, body in sections:
        key = _heading_key(heading)
        if level == "h2" and key == "date":
            published = _parse_date(body)
            continue
        if level == "h2" and key.startswith("proper name"):
            for line in body.split("\n"):
                for cell in (c.strip(" |") for c in line.split(" | ")):
                    low = cell.lower()
                    if not cell or low.endswith(("name", "name(s)", "information", "material")):
                        continue
                    if low in ("part(s)", "source", "proper name", "common name"):
                        continue
                    proper.append(cell)
            continue
        if level == "h3":
            mapped = H3_MAP.get(key)
            if not mapped:
                continue
            for chunk in split_paragraphs(body):
                body_chunks.append((f"{heading}: {chunk}", mapped[0], mapped[1]))
            continue
        mapped = SECTION_MAP.get(key)
        if mapped is None:
            continue
        # Route + dosage form are tiny; keep them as one methodology chunk each.
        for chunk in split_paragraphs(body):
            body_chunks.append((f"{heading}: {chunk}", mapped[0], mapped[1]))

    if not published:
        published = retrieved_at  # never silently undated; flagged in the manifest instead
    doc_id = "hc-nhpid-" + re.sub(r"[^a-z0-9]+", "-", atid.lower()).strip("-")

    # Entities: the common name from the title, plus the Latin binomial when the
    # title carries one ("ST. JOHN'S WORT - HYPERICUM PERFORATUM - Oral"). Table cells
    # also contain column headers ("Proper name", "Herb top"), so a stoplist is needed.
    def _pretty(x: str) -> str:
        return re.sub(r"'(\w)", lambda m: "'" + m.group(1).lower(), x.title()).strip()

    generic = {
        "proper name", "common name", "source information", "source material",
        "herb top", "part s", "source", "dry", "fresh", "oral", "topical",
    }
    parts = [p.strip() for p in re.split(r"\s+[-–—]\s+", title or "") if p.strip()]
    common = _pretty(parts[0]) if parts else atid
    binomial = None
    for cand in parts[1:]:
        words = cand.split()
        if (
            len(words) == 2
            and all(w.isalpha() and len(w) >= 3 for w in words)
            and cand.lower() not in generic
        ):
            binomial = f"{words[0].capitalize()} {words[1].lower()}"
            break
    if not binomial:
        for cand in re.findall(r"\b([A-Z][a-z]{2,}\s+[a-z]{3,}(?:\s+[a-z]{3,})?)\b", " ".join(proper)):
            if cand.lower() not in generic:
                binomial = cand
                break
    entities = [common] + ([binomial] if binomial else [])

    display_title = common if not binomial else f"{common} ({binomial})"
    chunks = []
    for i, (text, section, assertion) in enumerate(body_chunks, start=1):
        text = text.strip()
        if len(text.split()) < 8:
            continue
        chunks.append(
            make_chunk(
                f"{doc_id}#{len(chunks) + 1:03d}",
                text,
                section,
                assertion,
                topics=topics(text),
                entities=entities,
            )
        )

    return make_doc(
        doc_id=doc_id,
        source=SOURCE,
        tier="regulatory",
        title=display_title or atid,
        date_=published,
        url=url,
        identifier={"type": "nhpid", "value": atid},
        jurisdiction="ca",
        language="en",
        licence=LICENCE,
        retrieved_at=retrieved_at,
        checksum=sha256_bytes(html.encode("utf-8", "replace")),
        chunks=chunks,
        entities=entities,
    )


def index_atids(html: str) -> list[str]:
    seen: list[str] = []
    for m in re.finditer(r"atReq\.do\?atid=([A-Za-z0-9._-]+)", html):
        atid = m.group(1)
        if atid not in seen:
            seen.append(atid)
    return seen


def build(
    out_dir: Path,
    *,
    limit: int = 0,
    only: list[str] | None = None,
    kind: str = "single",
    sleep: float = 0.4,
) -> dict:
    index_url = INDEX_SINGLE if kind == "single" else INDEX_PRODUCT
    index_html = fetch(index_url).decode("utf-8", "replace")
    atids = index_atids(index_html)
    if only:
        atids = [a for a in atids if a in set(only)]
    if limit:
        atids = atids[:limit]

    retrieved_at = date.today().isoformat()
    built, failed = [], []
    for n, atid in enumerate(atids, start=1):
        url = MONO.format(atid=atid)
        try:
            raw = fetch(url)
            doc = parse_monograph(raw.decode("utf-8", "replace"), atid, url, retrieved_at=retrieved_at)
        except Exception as e:
            failed.append({"atid": atid, "error": str(e)})
            print(f"[{n}/{len(atids)}] FAIL {atid}: {e}", flush=True)
            continue
        if not doc["chunks"]:
            failed.append({"atid": atid, "error": "no parsable sections (0 chunks)"})
            print(f"[{n}/{len(atids)}] SKIP {atid}: no parsable sections", flush=True)
            continue
        dump_doc(doc, out_dir)
        built.append({"doc_id": doc["doc_id"], "atid": atid, "chunks": len(doc["chunks"]),
                      "date": doc["date"], "url": url, "checksum": doc["checksum"]})
        print(f"[{n}/{len(atids)}] {doc['doc_id']} chunks={len(doc['chunks'])} date={doc['date']}", flush=True)
        time.sleep(sleep)
    return {"kind": kind, "built": built, "failed": failed, "index": index_url}


def _main() -> int:
    import argparse

    from .. import config

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(config.CORPUS_DIR / "docs"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--kind", choices=["single", "product"], default="single")
    args = ap.parse_args()
    report = build(
        Path(args.out),
        limit=args.limit,
        only=[s.strip() for s in args.only.split(",") if s.strip()] or None,
        kind=args.kind,
    )
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}, indent=1))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(_main())
