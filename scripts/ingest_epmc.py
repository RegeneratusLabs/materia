#!/usr/bin/env python3
"""Ingest CC-BY primary literature from Europe PMC for uncovered topics.

Licence filter is explicit: OPEN_ACCESS:y AND LICENSE:"cc by". Anything else is skipped,
because the corpus must remain redistributable.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config
from materia.corpus.schema import dump_doc, make_chunk, make_doc, sha256_bytes

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
UA = "materia-corpus/0.1 (+local research build)"

# query -> (section, assertion_type, topic)
QUERIES: dict[str, tuple[str, str, str]] = {
    "ferritin interpretation iron deficiency": ("reference_interval", "diagnostic", "ferritin"),
    "transferrin saturation iron deficiency diagnosis": ("reference_interval", "diagnostic", "iron"),
    "vitamin B12 deficiency diagnosis methylmalonic acid": ("reference_interval", "diagnostic", "b12"),
    "folate deficiency homocysteine": ("reference_interval", "diagnostic", "folate"),
    "thyroid function tests interpretation TSH free T4": ("reference_interval", "diagnostic", "thyroid"),
    "hs-CRP cardiovascular risk interpretation": ("reference_interval", "diagnostic", "crp"),
    "herbal hepatotoxicity liver injury": ("cautions", "safety", "liver"),
    "St John's wort drug interactions CYP3A4": ("interactions", "safety", "anticoagulant"),
    "ginkgo bleeding risk anticoagulant": ("interactions", "safety", "anticoagulant"),
    "vitamin K warfarin interaction": ("interactions", "safety", "anticoagulant"),
    "iron absorption proton pump inhibitor": ("interactions", "safety", "iron"),
    "vitamin B12 metformin deficiency": ("interactions", "safety", "b12"),
    "folate methotrexate interaction": ("interactions", "safety", "folate"),
    "calcium drug interactions absorption": ("interactions", "safety", "calcium"),
    "magnesium drug interactions": ("interactions", "safety", "magnesium"),
    "zinc absorption interactions": ("interactions", "safety", "zinc"),
    "red flags serious illness primary care referral": ("red_flags", "diagnostic", "referral"),
    "unexplained weight loss investigation primary care": ("red_flags", "diagnostic", "referral"),
}

LICENCE = {
    "name": "CC BY (Europe PMC open-access subset)",
    "redistributable": True,
    "evidence_url": "https://europepmc.org/RestfulWebService",
    "note": "Filtered at query time to OPEN_ACCESS:y and LICENSE:\"cc by\".",
}


def fetch(query: str, page_size: int = 2) -> list[dict]:
    q = f'({query}) AND OPEN_ACCESS:y AND LICENSE:"cc by"'
    params = urllib.parse.urlencode({
        "query": q, "format": "json", "pageSize": page_size, "resultType": "core",
    })
    req = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    return data.get("resultList", {}).get("result", [])


def split_sentences(text: str, target: int = 110) -> list[str]:
    sents = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    chunks, buf, n = [], [], 0
    for s in sents:
        w = len(s.split())
        if n + w > target and buf:
            chunks.append(" ".join(buf))
            buf, n = [], 0
        buf.append(s)
        n += w
    if buf:
        chunks.append(" ".join(buf))
    return chunks


STOP = set("the a an of in on for with to from by is are and or effects effect study review "
           "clinical trial patients risk due role use".split())


def relevant(query: str, title: str, abstract: str) -> bool:
    """Cheap relevance gate: the paper must actually mention the query's key terms."""
    text = f"{title} {abstract}".lower()
    terms = {w for w in re.split(r"\W+", query.lower()) if len(w) > 3 and w not in STOP}
    hits = {t for t in terms if t in text}
    return len(hits) >= max(2, min(3, len(terms) - 1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(config.CORPUS_DIR / "docs"))
    ap.add_argument("--per-query", type=int, default=2)
    ap.add_argument("--sleep", type=float, default=0.5)
    args = ap.parse_args()

    retrieved_at = date.today().isoformat()
    seen: set[str] = set()
    built, skipped, failed = [], [], []

    for query, (section, assertion, topic) in QUERIES.items():
        try:
            results = fetch(query, args.per_query)
        except Exception as e:
            failed.append({"query": query, "error": str(e)})
            print(f"FAIL {query}: {e}", flush=True)
            continue
        for r in results:
            pmid = str(r.get("pmid") or "")
            doi = r.get("doi") or ""
            key = pmid or doi
            if not key or key in seen:
                continue
            seen.add(key)
            abstract = re.sub(r"<[^>]+>", " ", r.get("abstractText") or "").strip()
            title = r.get("title") or ""
            if not relevant(query, title, abstract):
                skipped.append({"pmid": pmid, "reason": "off-topic for query"})
                continue
            if len(abstract) < 400:
                skipped.append({"pmid": pmid, "reason": "abstract too short or missing"})
                continue
            year = str(r.get("pubYear") or "")[:4]
            if not year.isdigit():
                skipped.append({"pmid": pmid, "reason": "no publication year"})
                continue
            doc_id = f"epmc-{pmid}" if pmid else "epmc-" + re.sub(r"\W+", "-", doi.lower())
            entities = [r.get("title", "")[:80]] if r.get("title") else []
            chunks = []
            for piece in split_sentences(abstract):
                if len(piece.split()) < 12:
                    continue
                chunks.append(make_chunk(
                    f"{doc_id}#{len(chunks)+1:03d}", piece, section, assertion,
                    topics=[topic], entities=entities,
                ))
            if not chunks:
                skipped.append({"pmid": pmid, "reason": "no usable chunks"})
                continue
            doc = make_doc(
                doc_id=doc_id,
                source="Europe PMC (CC-BY)",
                tier="primary",
                title=(r.get("title") or "Untitled")[:300],
                date_=f"{year}-01-01",
                url=f"https://europepmc.org/article/MED/{pmid}" if pmid else f"https://doi.org/{doi}",
                identifier={"type": "pmid" if pmid else "doi", "value": pmid or doi},
                jurisdiction="international",
                language=r.get("language", "eng")[:2].lower() or "en",
                licence=LICENCE,
                retrieved_at=retrieved_at,
                checksum=sha256_bytes(json.dumps(r, sort_keys=True).encode()),
                chunks=chunks,
                entities=entities,
            )
            doc["date_precision"] = "year"
            dump_doc(doc, Path(args.out))
            built.append({"doc_id": doc_id, "query": query, "chunks": len(chunks)})
            print(f"  {doc_id} [{section}/{assertion}] {len(chunks)} chunks :: {doc['title'][:70]}", flush=True)
        time.sleep(args.sleep)

    print(json.dumps({"built": len(built), "skipped": len(skipped), "failed": len(failed)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
