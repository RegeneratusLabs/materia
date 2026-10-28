#!/usr/bin/env python3
"""Harvest EMA herbal-monograph PDF URLs from the public sitemap.

EMA's faceted search is robots-blocked (403) and rate-limits, but the sitemap is open.
This only collects URLs; the documents themselves are fetched by materia.corpus.ema.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

UA = "materia-corpus/0.1 (+local research build)"
SITEMAP = "https://www.ema.europa.eu/sitemap.xml"
OUT = Path("corpus/ema_monograph_urls.json")


def get(url: str, timeout: float = 60.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def main() -> int:
    index = get(SITEMAP)
    pages = sorted({int(n) for n in re.findall(r"sitemap\.xml\?page=(\d+)", index)})
    print(f"sitemap pages: {len(pages)}", flush=True)

    found: dict[str, str] = {}
    for p in pages:
        try:
            xml = get(f"{SITEMAP}?page={p}")
        except Exception as e:
            print(f"page {p} failed: {e}", flush=True)
            continue
        urls = re.findall(r"<loc>(https://www\.ema\.europa\.eu/en/documents/herbal-monograph/[^<]+\.pdf)</loc>", xml)
        for u in urls:
            found[u] = u.rsplit("/", 1)[-1]
        print(f"page {p}: +{len(urls)} (total {len(found)})", flush=True)
        time.sleep(0.5)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(sorted(found), indent=1) + "\n")
    print(f"wrote {OUT} with {len(found)} monograph PDFs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
