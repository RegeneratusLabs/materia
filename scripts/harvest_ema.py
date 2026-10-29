#!/usr/bin/env python3
"""Harvest EMA herbal-monograph PDF URLs from the public sitemap.

Concurrent, incremental, resumable. EMA's faceted search is robots-blocked but the sitemap
enumerates every document URL; 164 pages at ~4 workers is a few minutes, not hours.

Usage:
    python scripts/harvest_ema.py            # all pages
    python scripts/harvest_ema.py --pages 5  # smoke test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config  # noqa: E402

UA = "materia-corpus/0.1 (+local research build)"
SITEMAP = "https://www.ema.europa.eu/sitemap.xml"
OUT = config.CORPUS_DIR / "ema_monograph_urls.json"
MONO = re.compile(r"<loc>(https://www\.ema\.europa\.eu/en/documents/herbal-monograph/[^<]+\.pdf)</loc>")
SKIP = re.compile(r"superseded|draft|overview|comments|opinion|assessment|withdrawal|tracked|revision", re.I)

lock = threading.Lock()
found: dict[str, str] = {}


def get(url: str, timeout: float = 90.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def flush() -> None:
    with lock:
        urls = sorted(found)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(urls, indent=1) + "\n")


def fetch_page(page: int) -> tuple[int, int]:
    try:
        xml = get(f"{SITEMAP}?page={page}")
    except Exception as e:
        print(f"  page {page} failed: {e}", flush=True)
        return (page, 0)
    urls = MONO.findall(xml)
    keep = [u for u in urls if not SKIP.search(u.rsplit("/", 1)[-1])]
    with lock:
        for u in keep:
            found[u] = u.rsplit("/", 1)[-1]
    return (page, len(keep))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    index = get(SITEMAP)
    pages = sorted({int(n) for n in re.findall(r"sitemap\.xml\?page=(\d+)", index)})
    if args.pages:
        pages = pages[: args.pages]
    print(f"sitemap pages: {len(pages)}", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, (page, n) in enumerate(ex.map(fetch_page, pages), start=1):
            if i % 10 == 0 or n:
                print(f"  {i}/{len(pages)} page={page} +{n} total={len(found)} "
                      f"({time.time() - t0:.0f}s)", flush=True)
            if i % 10 == 0:
                flush()

    flush()
    print(f"wrote {OUT} with {len(found)} monograph PDFs in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
