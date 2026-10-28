#!/usr/bin/env python3
"""Deterministic 'photo' stand-in: rotate, downscale and JPEG-crush a clean page.

This is a synthetic degradation, not a real phone photograph. It is labelled as such
everywhere it is used (Gate 0 report, provenance file).
"""
import sys
from pathlib import Path

from PIL import Image

src = Path(sys.argv[1] if len(sys.argv) > 1 else "samples/pages/nutripath-p2.png")
dst = Path(sys.argv[2] if len(sys.argv) > 2 else "samples/pages/nutripath-p2-degraded.jpg")
img = Image.open(src).convert("RGB")
w, h = img.size
img = img.resize((int(w * 0.6), int(h * 0.6)), Image.LANCZOS)
img = img.rotate(4, resample=Image.BICUBIC, expand=True, fillcolor="white")
img.save(dst, "JPEG", quality=40)
print(dst, img.size)
