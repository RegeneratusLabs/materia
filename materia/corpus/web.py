"""HTML source adapter: NCCIH herb pages and NCI PDQ summaries.

Both are US federal works (public domain, credit the agency), both are dated on the page,
and both are reachable from this host. NICE CKS geo-blocks non-UK traffic, ODS sits behind
Cloudflare and Bookshelf serves a reCAPTCHA, so those sources need manual downloads rather
than a crawler — recorded in docs/corpus.md rather than worked around.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

from .schema import dump_doc, make_chunk, make_doc, sha256_bytes
from .text import parse_month_date, split_paragraphs, topics

UA = "materia-corpus/0.1 (+local research build; contact: project owner)"

SOURCES: dict[str, dict] = {
    "nccih": {
        "source": "NCCIH (NIH)",
        "tier": "compendium",
        "jurisdiction": "us",
        "prefix": "nccih",
        "licence": {
            "name": "US federal work — public domain",
            "redistributable": True,
            "evidence_url": "https://www.nih.gov/web-policies-notices",
            "note": "Credit NCCIH. Third-party images and quoted material excluded.",
        },
        "discover": ("https://www.nccih.nih.gov/health/herbsataglance", r'href="(/health/[a-z0-9-]+)"'),
        "skip": {"atoz", "espanol", "herblist-app", "herbsataglance", "safety",
                 "know-science", "health-info", "topics", "news",
                 "complementary-alternative-or-integrative-health-whats-in-a-name"},
    },
    "nci": {
        "source": "NCI PDQ",
        "tier": "primary",
        "jurisdiction": "us",
        "prefix": "nci-pdq",
        "licence": {
            "name": "US federal work — public domain",
            "redistributable": True,
            "evidence_url": "https://www.cancer.gov/policies/copyright-reuse",
            "note": "NCI PDQ evidence summaries. Text is copyright-free; credit NCI.",
        },
        "discover": ("https://www.cancer.gov/about-cancer/treatment/cam/hp",
                     r'href="(/about-cancer/treatment/cam/hp/[a-z0-9-]+)"'),
        "skip": set(),
    },
}

# headings that are not clinical content at all
SKIP_HEADINGS = re.compile(
    r"^(key )?references?\b|references cited|for more information|where to find|"
    r"share this|related topics|acknowledg|disclaimer|about us",
    re.I,
)

# heading regex -> (section, assertion_type)
HEADING_MAP: list[tuple[str, str, str]] = [
    (r"contraindicat|who should not|do not use", "contraindications", "safety"),
    (r"side effect|adverse|safety|risk|harm", "adverse_effects", "safety"),
    (r"interaction", "interactions", "safety"),
    (r"pregnan|lactat|breastfeed", "cautions", "safety"),
    (r"caution|warning", "cautions", "safety"),
    (r"dos(e|age)|how much|supplement form|prepar", "dosage", "dose"),
    (r"monitor", "monitoring", "monitoring"),
    (r"red flag|when to (see|seek|contact)|referral\b", "red_flags", "diagnostic"),
    (r"how (it|does it) work|mechanism|pharmacolog|what (it|is) it", "pharmacology", "other"),
    (r"evidence|research|clinical trial|effective|benefit|study", "evidence", "efficacy"),
    (r"use|indication|purpose|treatment", "indications", "efficacy"),
    (r"reference|interval", "reference_interval", "other"),
]


def fetch(url: str, *, retries: int = 3, timeout: float = 45.0) -> bytes:
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(1.0 * (i + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")


def classify(heading: str) -> tuple[str, str] | None:
    if SKIP_HEADINGS.search(heading):
        return None
    low = heading.lower()
    for pattern, section, assertion in HEADING_MAP:
        if re.search(pattern, low):
            return section, assertion
    return "other", "other"


def extract_page(html: str) -> dict:
    # The date usually lives outside <main> (meta strip / page footer), so read it from
    # the whole document before any tags are decomposed.
    plain_all = re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text(" "))
    date_m = re.search(
        r"(?:last\s+)?(?:updated|reviewed|revised)\s*:?\s*"
        r"(\d{4}-\d{2}-\d{2}|[A-Za-z]+\s+\d{1,2},?\s+\d{4}"
        r"|[A-Za-z]+\s+\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})",
        plain_all,
        re.I,
    )
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "nav", "aside", "footer", "form", "button", "noscript"]):
        tag.decompose()

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)

    main = soup.find("main") or soup.find("article") or soup.body or soup
    # mark headings, then drop them so their text is not duplicated in the body
    for h in main.find_all(["h2", "h3"]):
        h.insert_before(NavigableString(f"\n@@HEAD@@ {h.get_text(' ', strip=True)}\n"))
        h.decompose()
    for tag in main.find_all(["table", "ul", "ol"]):
        tag.insert_before(NavigableString("\n"))
        tag.insert_after(NavigableString("\n"))

    text = main.get_text("\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()

    sections: list[tuple[str, str]] = []
    parts = re.split(r"@@HEAD@@[ ]*", text)
    if parts[0].strip():
        sections.append(("", parts[0].strip()))
    for part in parts[1:]:
        lines = part.split("\n", 1)
        heading = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        if body:
            sections.append((heading, body))

    date_iso = parse_month_date(date_m.group(1)) if date_m else None
    if not date_iso:
        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag and re.match(r"\d{4}-\d{2}-\d{2}", time_tag["datetime"]):
            date_iso = time_tag["datetime"][:10]
    return {"title": title, "date": date_iso, "sections": sections, "text": text}


def build_doc(html: str, url: str, cfg: dict, retrieved_at: str) -> dict:
    page = extract_page(html)
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    doc_id = f"{cfg['prefix']}-{slug}"
    title = re.sub(r"\s*\(PDQ®?\)\s*", "", page["title"]).strip() or slug.replace("-", " ").title()

    chunks = []
    for heading, body in page["sections"]:
        mapped = classify(heading)
        if mapped is None:
            continue
        section, assertion = mapped
        for piece in split_paragraphs(body):
            text = f"{heading}: {piece}" if heading else piece
            if len(text.split()) < 8:
                continue
            chunks.append(
                make_chunk(
                    f"{doc_id}#{len(chunks) + 1:03d}",
                    text,
                    section,
                    assertion,
                    topics=topics(text),
                    entities=[title],
                )
            )

    return make_doc(
        doc_id=doc_id,
        source=cfg["source"],
        tier=cfg["tier"],
        title=title,
        date_=page["date"],
        url=url,
        identifier={"type": "web", "value": url},
        jurisdiction=cfg["jurisdiction"],
        language="en",
        licence=cfg["licence"],
        retrieved_at=retrieved_at,
        checksum=sha256_bytes(html.encode("utf-8", "replace")),
        chunks=chunks,
        entities=[title],
    )


def discover(cfg: dict) -> list[str]:
    index_url, pattern = cfg["discover"]
    html = fetch(index_url).decode("utf-8", "replace")
    seen: list[str] = []
    base = "https://www.nccih.nih.gov" if "nccih" in cfg["prefix"] else "https://www.cancer.gov"
    # keep only the A-Z herb list region; nav/footer links share the same prefix
    if "nccih" in cfg["prefix"]:
        start = html.find('id="herbs"')
        if start == -1:
            start = html.find("Herbs at a Glance")
        region = html[start:] if start != -1 else html
    else:
        region = html
    for href in re.findall(pattern, region):
        slug = href.rstrip("/").rsplit("/", 1)[-1]
        if slug in cfg.get("skip", set()):
            continue
        full = base + href if href.startswith("/") else href
        if full not in seen:
            seen.append(full)
    return seen


def build(
    source: str,
    out_dir: Path,
    *,
    limit: int = 0,
    urls: list[str] | None = None,
    sleep: float = 0.5,
) -> dict:
    cfg = SOURCES[source]
    targets = urls or discover(cfg)
    if limit:
        targets = targets[:limit]
    retrieved_at = date.today().isoformat()
    built, skipped, failed = [], [], []

    for n, url in enumerate(targets, start=1):
        try:
            html = fetch(url).decode("utf-8", "replace")
            doc = build_doc(html, url, cfg, retrieved_at)
        except Exception as e:
            failed.append({"url": url, "error": str(e)})
            print(f"[{n}/{len(targets)}] FAIL {url}: {e}", flush=True)
            continue
        if not doc["date"]:
            skipped.append({"url": url, "reason": "no publication/review date on page"})
            print(f"[{n}/{len(targets)}] SKIP (no date) {doc['doc_id']}", flush=True)
            continue
        if len(doc["chunks"]) < 3:
            skipped.append({"url": url, "reason": f"thin page ({len(doc['chunks'])} chunks)"})
            print(f"[{n}/{len(targets)}] SKIP (thin) {doc['doc_id']}", flush=True)
            continue
        dump_doc(doc, out_dir)
        built.append({"doc_id": doc["doc_id"], "url": url, "chunks": len(doc["chunks"]),
                      "date": doc["date"], "checksum": doc["checksum"]})
        print(f"[{n}/{len(targets)}] {doc['doc_id']} chunks={len(doc['chunks'])} date={doc['date']}", flush=True)
        time.sleep(sleep)
    return {"source": source, "built": built, "skipped": skipped, "failed": failed}


def _main() -> int:
    import argparse

    from .. import config

    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=sorted(SOURCES), required=True)
    ap.add_argument("--out", default=str(config.CORPUS_DIR / "docs"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--url", action="append", default=[])
    args = ap.parse_args()
    report = build(args.source, Path(args.out), limit=args.limit, urls=args.url or None)
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
