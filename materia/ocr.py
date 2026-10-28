"""Document → page image → OCR, with the two-read check.

MiniCPM-OCR returns OTSL for tables (`Table Recognition:`) and plain text for prose
(`Text Recognition:`). OTSL is what makes column-aligned extraction possible: bar labels
and reference ranges stay in their own cells instead of collapsing into one number soup.
"""
from __future__ import annotations

import re
from pathlib import Path

import pymupdf

from . import llm

# Capture the whole tag: re.split() includes captured groups as separators, so this
# keeps "<fcel>" (not "fcel"), which fullmatch() can then recognise.
OTSL_TOKEN = re.compile(r"(<(?:fcel|lcel|ecel|ucel|xcel|nl)>)")


def render_pdf(path: str | Path, out_dir: str | Path, *, dpi: int = 200) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(path))
    pages: list[Path] = []
    for i, page in enumerate(doc, start=1):
        p = out / f"{Path(path).stem}-p{i}.png"
        page.get_pixmap(dpi=dpi).save(p)
        pages.append(p)
    return pages


def pdf_text(path: str | Path) -> str:
    doc = pymupdf.open(str(path))
    return "\n".join(page.get_text() for page in doc)


def ocr_page(image: str | Path, *, mode: str = "table", max_tokens: int = 3000) -> dict:
    """Full result: text, finish reason, token count. Truncation must be explicit."""
    prompt = "Table Recognition:" if mode == "table" else "Text Recognition:"
    r = llm.chat_image(image, prompt, max_tokens=max_tokens, timeout=1800)
    text = r["text"]
    r["truncated"] = r.get("finish") == "length" or (
        mode == "table" and "<otsl>" in text and "</otsl>" not in text
    )
    return r


def ocr_image(image: str | Path, *, mode: str = "table", max_tokens: int = 3000) -> str:
    return ocr_page(image, mode=mode, max_tokens=max_tokens)["text"]


def parse_otsl(text: str) -> list[list[str]]:
    """OTS L -> rows of cell strings. lcel/ecel/ucel become empty cells (no invention)."""
    m = re.search(r"<otsl>(.*?)(</otsl>|$)", text, re.S)
    body = m.group(1) if m else text
    parts = OTSL_TOKEN.split(body)
    rows: list[list[str]] = []
    row: list[str] = []
    pending_cell = False
    for part in parts:
        if not part:
            continue
        if OTSL_TOKEN.fullmatch(part):
            if part == "<nl>":
                if any(c.strip() for c in row):
                    rows.append(row)
                row = []
            else:
                row.append("")
                pending_cell = True
            continue
        text_part = part.strip()
        if pending_cell and row:
            row[-1] = (row[-1] + " " + text_part).strip() if row[-1] else text_part
            pending_cell = False
        elif row:
            row[-1] = (row[-1] + " " + text_part).strip()
    if any(c.strip() for c in row):
        rows.append(row)
    return rows


UNIT_RE = re.compile(
    r"(µmol/L|μmol/L|mmol/L|pmol/L|nmol/L|mg/dL|mg/L|ng/mL|pg/mL|ng/dL|"
    r"mIU/L|µIU/mL|μIU/mL|IU/L|U/L|g/L|g/dL|%|mL/min/1\.73m2|ratio)",
    re.I,
)
RANGE_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)$")
NUMBER_PREFIX = re.compile(r"^(\d{1,3})\.\s*(.+)$")


def _unit_from_rows(rows: list[list[str]]) -> str | None:
    for row in rows[:40]:
        for cell in row:
            if "reference" in cell.lower() or "result" in cell.lower():
                m = UNIT_RE.search(cell)
                if m:
                    return m.group(1)
    for row in rows[:40]:
        for cell in row:
            m = UNIT_RE.search(cell)
            if m:
                return m.group(1)
    return None


def extract_lab_rows(rows: list[list[str]], *, unit_hint: str | None = None) -> list[dict]:
    """Deterministic: numbered analyte → next cell is the result, last range-like cell is the interval.

    Bar labels (the quintile min/max) sit in their own cells, which is why this works
    only on OTSL rather than on flattened text.
    """
    unit = _unit_from_rows(rows) or unit_hint
    records: list[dict] = []
    for row in rows:
        cells = [c.strip() for c in row]
        idx = next((i for i, c in enumerate(cells) if NUMBER_PREFIX.match(c)), None)
        if idx is None:
            continue
        m = NUMBER_PREFIX.match(cells[idx])
        analyte = m.group(2).strip().rstrip("*").strip()
        if not analyte or len(analyte) > 60:
            continue
        # value: first numeric cell after the analyte
        value = None
        for c in cells[idx + 1 :]:
            if re.fullmatch(r"-?\d+(?:\.\d+)?", c.replace(",", "")):
                value = float(c.replace(",", ""))
                break
        ref_text = next((c for c in reversed(cells) if RANGE_RE.match(c.replace(",", ""))), None)
        ref_low = ref_high = None
        if ref_text:
            rm = RANGE_RE.match(ref_text.replace(",", ""))
            ref_low, ref_high = float(rm.group(1)), float(rm.group(2))
        row_unit = unit
        if re.search(r"ratio|/lnaa|/", analyte, re.I) and not re.search(r"\d", analyte):
            row_unit = "ratio"
        records.append(
            {
                "analyte": analyte,
                "value": value,
                "unit": row_unit,
                "ref_low": ref_low,
                "ref_high": ref_high,
                "ref_text": ref_text,
                "raw_cells": cells,
            }
        )
    return records


def numbers_in(text: str) -> set[str]:
    """Number tokens for the two-read completeness check.

    The lookbehind matters: in "63-220" the hyphen is a range separator, not a minus
    sign, and treating it as one silently loses every upper interval bound.
    """
    return {t.replace(",", "") for t in re.findall(r"(?<![\d.])-?\d+(?:\.\d+)?", text)}
