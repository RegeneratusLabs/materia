"""Shared text helpers for corpus adapters."""
from __future__ import annotations

import re

TOPIC_WORDS = {
    "pregnancy": ("pregnan", "lactat", "breastfeed", "breast-feed"),
    "children": ("child", "paediatric", "pediatric", "infant", "adolescent"),
    "liver": ("liver", "hepat", "jaundice"),
    "anticoagulant": ("anticoag", "warfarin", "bleeding", "platelet", "inr"),
    "surgery": ("surg", "operation", "anaesth", "anesth"),
    "thyroid": ("thyroid", "levothyroxine"),
    "diabetes": ("diabet", "hypoglyc", "blood glucose", "insulin"),
    "sedation": ("sedat", "drows", "driving", "alcohol"),
    "hypertension": ("blood pressure", "hypertens", "diuretic"),
    "immunosuppression": ("immunosupp", "transplant", "cyclosporin"),
    "cancer": ("cancer", "oncolog", "chemotherap", "tumour", "tumor"),
    "renal": ("renal", "kidney"),
    "traditional": ("tradition",),
}


def topics(text: str) -> list[str]:
    low = text.lower()
    return [t for t, keys in TOPIC_WORDS.items() if any(k in low for k in keys)]

def split_paragraphs(text: str, *, target_words: int = 220, max_words: int = 400) -> list[str]:
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    words = 0
    for p in paras:
        pw = len(p.split())
        if pw > max_words:  # split very long paragraphs on sentence boundaries
            sents = re.split(r"(?<=[.!?])\s+", p)
            cur: list[str] = []
            cw = 0
            for s in sents:
                sw = len(s.split())
                if cw + sw > target_words and cur:
                    chunks.append(" ".join(cur))
                    cur, cw = [], 0
                cur.append(s)
                cw += sw
            if cur:
                chunks.append(" ".join(cur))
            continue
        if words + pw > target_words and buf:
            chunks.append("\n".join(buf))
            buf, words = [], 0
        buf.append(p)
        words += pw
    if buf:
        chunks.append("\n".join(buf))
    return chunks




def parse_month_date(text: str) -> str | None:
    """'Updated: May 2025' / 'Last reviewed 12 June 2025' / ISO dates -> ISO date."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return m.group(0)
    months = {m: i for i, m in enumerate(
        ["january","february","march","april","may","june","july","august",
         "september","october","november","december"], start=1)}
    m = re.search(r"(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})", text)
    if m and m.group(2).lower() in months:
        return f"{int(m.group(3)):04d}-{months[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})", text)
    if m and m.group(1).lower() in months:
        return f"{int(m.group(3)):04d}-{months[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    m = re.search(r"([A-Z][a-z]+)\s+(\d{4})", text)
    if m and m.group(1).lower() in months:
        return f"{int(m.group(2)):04d}-{months[m.group(1).lower()]:02d}-01"
    return None
