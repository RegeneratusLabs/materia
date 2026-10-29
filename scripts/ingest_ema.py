#!/usr/bin/env python3
"""Ingest EMA monographs for panel-relevant herbs from the harvested sitemap URL list."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materia import config
from materia.corpus import ema

# Panel herbs present in the EMA monograph set (filename fragments).
KEYWORDS = [
    "hypericum", "ginkgo", "echinacea", "panax", "withania", "curcuma", "allium",
    "silybum", "valeriana", "piperis-methystici", "serenoa", "cimicifuga", "rhodiola",
    "berberis", "camellia", "glycyrrhiza", "matricaria", "chamaemelum", "lavandula",
    "passiflora", "melissa", "tanacetum", "zingiber", "boswellia", "commiphora",
    "ocimum", "sambucus", "astragalus", "lepidium", "humulus", "avena",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", default=str(config.CORPUS_DIR / "ema_monograph_urls.json"))
    ap.add_argument("--out", default=str(config.CORPUS_DIR / "docs"))
    ap.add_argument("--raw", default=str(config.CORPUS_DIR / "raw" / "ema"))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    urls = json.loads(Path(args.urls).read_text())
    if not args.all:
        urls = [u for u in urls if any(k in u.lower() for k in KEYWORDS)]
    if args.limit:
        urls = urls[: args.limit]
    print(f"targets: {len(urls)}")
    report = ema.build(urls, Path(args.out), raw_dir=Path(args.raw), sleep=0.8)
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}, indent=1))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
