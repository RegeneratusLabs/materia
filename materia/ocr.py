"""Document → page image → OCR, with the two-read check.

MiniCPM-OCR returns OTSL for tables (`Table Recognition:`) and plain text for prose
(`Text Recognition:`). OTSL is what makes column-aligned extraction possible: bar labels
and reference ranges stay in their own cells instead of collapsing into one number soup.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import pymupdf

from . import llm
from .extract import normalise_unit

# Capture the whole tag: re.split() includes captured groups as separators, so this
# keeps "<fcel>" (not "fcel"), which fullmatch() can then recognise.
OTSL_TOKEN = re.compile(r"(<(?:fcel|lcel|ecel|ucel|xcel|nl)>)")


def render_page(path: str | Path, page_number: int, out_dir: str | Path, *, dpi: int = 200) -> Path:
    """Render one page. A 16-page report only needs the pages that carry a table."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(path))
    target = out / f"{Path(path).stem}-p{page_number}.png"
    doc[page_number - 1].get_pixmap(dpi=dpi).save(target)
    return target


def pdf_text(path: str | Path) -> str:
    doc = pymupdf.open(str(path))
    return "\n".join(page.get_text() for page in doc)


def pdf_pages(path: str | Path) -> list[str]:
    """The text layer, page by page. A digital report's tables are already here."""
    doc = pymupdf.open(str(path))
    return [page.get_text() for page in doc]


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
        text_part = html.unescape(part.strip())
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
# A numbered row ("1. Lysine") needs whitespace after the dot. Without it, a decimal
# result such as "4.2" matched and the *value* was read as the analyte's name, which
# is how a whole report came back as rows called "2", "5", "6".
NUMBER_PREFIX = re.compile(r"^(\d{1,2})\.\s+(\S.*)$")

CELL_RESULT = re.compile(r"^(\d{1,5}(?:\.\d+)?)\s*([HL])?$")
CELL_LIMIT = re.compile(r"^([<>])\s*(\d{1,5}(?:\.\d+)?)\s*([HL])?$")
CELL_RANGE_LIMIT = re.compile(r"^([<>]=?)\s*(\d{1,5}(?:\.\d+)?)$")

_HEADER_WORDS = {
    "test name", "result", "reference", "interval", "units", "unit", "range",
    "reference interval", "comments",
}


def _unit_from_rows(rows: list[list[str]]) -> str | None:
    """Page-level unit hint, for reports that print the unit once in a banner cell."""
    for row in rows[:40]:
        for cell in row:
            if "reference" in cell.lower() or "result" in cell.lower():
                m = UNIT_RE.search(cell)
                if m:
                    return normalise_unit(m.group(1))
    for row in rows[:40]:
        for cell in row:
            m = UNIT_RE.search(cell)
            if m:
                return normalise_unit(m.group(1))
    return None


def _row_unit(cells: list[str]) -> str | None:
    for cell in cells:
        if UNIT_RE.fullmatch(cell.strip()):
            return normalise_unit(cell.strip())
    return None


def _unnumbered_row(cells: list[str]) -> dict | None:
    """A row from a report that does not number its analytes.

    Sonic/NPAAC reports print ``Sodium | 140 | 135 - 145 | mmol/L``: the name is the
    first cell and the fields follow in printed order. Nothing is inferred — a missing
    result stays missing.
    """
    name = cells[0].strip().strip("*").strip() if cells else ""
    if not name or len(name) > 60 or not re.search(r"[A-Za-z]", name):
        return None
    if name.lower() in _HEADER_WORDS or UNIT_RE.fullmatch(name):
        return None

    value = value_text = lab_flag = None
    ref_low = ref_high = ref_text = None
    for cell in cells[1:]:
        text = cell.strip()
        if not text:
            continue
        if value is None and value_text is None:
            limit = CELL_LIMIT.fullmatch(text)
            plain = CELL_RESULT.fullmatch(text)
            if limit:
                value_text, lab_flag = text, limit.group(3)
                continue
            if plain:
                value, lab_flag = float(plain.group(1)), plain.group(2)
                continue
        if ref_text is None:
            span = RANGE_RE.fullmatch(text)
            one_sided = CELL_RANGE_LIMIT.fullmatch(text)
            if span:
                ref_low, ref_high = float(span.group(1)), float(span.group(2))
                ref_text = text
                continue
            if one_sided:
                op, number = one_sided.group(1), float(one_sided.group(2))
                if op.startswith("<"):
                    ref_high = number
                else:
                    ref_low = number
                ref_text = text
                continue
    if value is None and value_text is None:
        return None
    return {
        "analyte": name,
        "value": value,
        "value_text": value_text,
        "unit": _row_unit(cells) or "",
        "ref_low": ref_low,
        "ref_high": ref_high,
        "ref_text": ref_text,
        "lab_flag": lab_flag,
        "raw_cells": cells,
    }


def extract_lab_rows(rows: list[list[str]], *, unit_hint: str | None = None) -> list[dict]:
    """Deterministic: one record per printed analyte row.

    Two layouts are handled. Numbered rows ("1. Lysine | 124 | ...") carry the unit in a
    banner row, so ``unit_hint`` fills it in. Unnumbered rows carry their own unit and
    interval. Bar labels (the quintile min/max) sit in their own cells, which is why this
    works only on OTSL rather than on flattened text.
    """
    unit = _unit_from_rows(rows) or unit_hint
    records: list[dict] = []
    for row in rows:
        cells = [c.strip() for c in row]
        idx = next((i for i, c in enumerate(cells) if NUMBER_PREFIX.match(c)), None)
        if idx is None:
            candidate = _unnumbered_row(cells)
            if candidate:
                records.append(candidate)
            continue
        m = NUMBER_PREFIX.match(cells[idx])
        analyte = m.group(2).strip().rstrip("*").strip()
        if not analyte or len(analyte) > 60 or not re.search(r"[A-Za-z]", analyte):
            continue
        # value: first numeric cell after the analyte, keeping the lab's own marker
        value = None
        lab_flag = None
        for c in cells[idx + 1 :]:
            plain = CELL_RESULT.fullmatch(c.replace(",", ""))
            if plain:
                value = float(plain.group(1))
                lab_flag = plain.group(2)
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
                "lab_flag": lab_flag,
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
