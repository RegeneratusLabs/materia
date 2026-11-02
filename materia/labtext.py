"""Deterministic read of a digital lab report's text layer.

Why this module exists: a PDF that carries a text layer is already a machine-readable
table. Running a vision model over it is slower, lossier and cannot be checked by
inspection. HANDOVER §"two independent reads" asks for the text layer *and* OCR on the
same page, compared; this module is the deterministic half. The server decides when the
OCR half runs (it is ~45 s per page on CPU, the text layer is milliseconds).

The layouts this reads are the ones NPAAC-accredited Australian labs print::

    Test Name          _or_   1. Lysine
    Result                    124
    Reference                 63-220
    Interval
    Units
    Sodium
    140 L
    <16
    mmol/L

A row is name, result, optional interval, optional unit. The result may carry the lab's
own H/L marker, and both the result and the interval may be one-sided ("<5.6", ">100").
Nothing is inferred: a field that is not printed stays None.
"""
from __future__ import annotations

import re

from .extract import normalise_unit

# A column header block. Some reports break "Reference Interval" over two lines.
_HEADER = re.compile(r"^test\s*name$", re.I)
_HEADER_PARTS = {"result", "reference", "interval", "units", "unit", "range"}

# A plain result, with the lab's optional marker: "140", "5.7 H", "34 L".
_RESULT = re.compile(r"^(\d{1,5}(?:\.\d+)?)\s*([HL])?$")
# A result the lab reports as a limit: ">128". Not a single number, so not a number.
_RESULT_LIMIT = re.compile(r"^([<>])\s*(\d{1,5}(?:\.\d+)?)\s*([HL])?$")
# A two-sided interval: "135 - 145" (hyphen or en dash).
_INTERVAL = re.compile(r"^(\d{1,5}(?:\.\d+)?)\s*[-\u2013\u2014]\s*(\d{1,5}(?:\.\d+)?)$")
# A one-sided interval: "<5.6", ">59", ">=1.00", "<=16".
_INTERVAL_LIMIT = re.compile(r"^([<>]=?)\s*(\d{1,5}(?:\.\d+)?)$")

# Units, spelled as labs print them. Whitelisted on purpose: a bare "Tot Chol/HDL"
# is an analyte name that contains a slash and must not be mistaken for a unit.
_UNIT = re.compile(
    r"^(?:"
    r"10\^\d+/L|10\*\d+/L|fL|%|mmol/mol|mL/min/1\.73m2|ratio|sec|mm/hr|/hpf"
    r"|[kmunp\u00b5\u03bc]?(?:mol|g|IU|U|Eq)/L"
    r"|IU/mL|\u00b5IU/mL|mIU/L|mU/L|IU/L|U/L"
    r"|mg/dL|mg/L|g/dL|g/L|\u00b5g/L|ug/L|ng/mL|pg/mL|ng/dL"
    r")$",
    re.I,
)

# A table stops at the first of these; comment prose must never become a row.
_TABLE_END = re.compile(r"^(?:comments?|legend)$", re.I)
_TABLE_END_PREFIX = ("sullivan", "reported on", "page ", "accredited", "document created")

_NAME_MAX = 60


def _is_name(text: str) -> bool:
    """A cell that could be an analyte name: text, not a header, not a field."""
    if not text or len(text) > _NAME_MAX:
        return False
    if not re.search(r"[A-Za-z]", text):
        return False
    return not _HEADER.match(text) and text.lower().strip(" :") not in _HEADER_PARTS


def _blank(analyte: str, section: str | None = None) -> dict:
    """Every row has the same shape, so a missing field is None and never a KeyError."""
    return {
        "analyte": analyte,
        "section": section,
        "value": None,
        "value_text": None,
        "limit": None,
        "lab_flag": None,
        "unit": None,
        "ref_low": None,
        "ref_high": None,
        "ref_text": None,
    }


def _finish(table: list[dict], row: dict | None) -> None:
    """A name with no result is not a value: scientist initials ("CA", "EA") and stray
    headings end pages, and they must not become rows with an invented number."""
    if row and row.get("analyte") and (row.get("value") is not None or row.get("value_text")):
        table.append(row)


def _parse_table(lines: list[str], start: int, section: str | None = None) -> tuple[list[dict], int]:
    """Read one table beginning at ``start`` (the "Test Name" line)."""
    rows: list[dict] = []
    i = start + 1
    while i < len(lines) and lines[i].strip().lower().strip(":") in _HEADER_PARTS:
        i += 1

    current: dict | None = None
    while i < len(lines):
        text = lines[i].strip()
        i += 1
        if not text:
            continue
        lowered = text.lower()
        if _TABLE_END.match(text) or lowered.startswith(_TABLE_END_PREFIX):
            break
        if _HEADER.match(text):
            # A second table on the same page: close this one and let the caller re-enter.
            _finish(rows, current)
            return rows, i - 1

        if _UNIT.match(text):
            # Only meaningful once a result exists; a unit before it is a stray.
            if current and not current.get("unit") and (
                current.get("value") is not None or current.get("value_text")
            ):
                current["unit"] = normalise_unit(text)
            continue

        limit = _RESULT_LIMIT.match(text)
        plain = _RESULT.match(text)
        interval = _INTERVAL.match(text)
        one_sided = _INTERVAL_LIMIT.match(text)

        if current and current.get("value") is None and not current.get("value_text"):
            if limit:
                current["value_text"] = text
                current["limit"] = limit.group(1)
                current["lab_flag"] = limit.group(3)
                continue
            if plain:
                current["value"] = float(plain.group(1))
                current["lab_flag"] = plain.group(2)
                continue
        elif current and current.get("ref_text") is None:
            if interval:
                current["ref_low"] = float(interval.group(1))
                current["ref_high"] = float(interval.group(2))
                current["ref_text"] = f"{interval.group(1)} - {interval.group(2)}"
                continue
            if one_sided:
                op, number = one_sided.group(1), float(one_sided.group(2))
                if op.startswith("<"):
                    current["ref_high"] = number
                else:
                    current["ref_low"] = number
                current["ref_text"] = text
                continue

        # Anything else is a name: either a new row, or a wrapped continuation.
        if current and current.get("value") is None and not current.get("value_text"):
            current["analyte"] = f"{current['analyte']} {text}".strip()
            continue
        if current and (current.get("ref_text") is None) and _is_name(text):
            # Name after a value but before an interval means the interval is absent.
            _finish(rows, current)
            current = _blank(text.strip("*").strip(), section)
            continue
        if not _is_name(text):
            if current:
                _finish(rows, current)
                current = None
            continue
        _finish(rows, current)
        current = _blank(text.strip("*").strip(), section)

    _finish(rows, current)
    return rows, i


def _section_before(lines: list[str], index: int) -> str | None:
    """The heading a lab prints above its column header ("Lipid Profile", "Haematinics")."""
    for back in range(index - 1, max(index - 4, -1), -1):
        text = lines[back].strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in _HEADER_PARTS or lowered.startswith(_TABLE_END_PREFIX):
            continue
        if re.match(r"^page\s", lowered) or not re.search(r"[A-Za-z]", text):
            return None
        return text if len(text) <= 40 else None
    return None


def extract_rows(text: str) -> list[dict]:
    """Every lab row in a page's text layer, in printed order. Empty list = no table."""
    lines = text.splitlines()
    rows: list[dict] = []
    i = 0
    while i < len(lines):
        if _HEADER.match(lines[i].strip()):
            table, i = _parse_table(lines, i, _section_before(lines, i))
            rows.extend(table)
            continue
        i += 1
    return rows


def to_record(row: dict) -> dict:
    """Shape a parsed row for the plausibility gate."""
    return {
        "analyte": row.get("analyte", ""),
        "section": row.get("section"),
        "value": row.get("value"),
        "value_text": row.get("value_text"),
        "limit": row.get("limit"),
        "unit": row.get("unit") or "",
        "ref_low": row.get("ref_low"),
        "ref_high": row.get("ref_high"),
        "ref_text": row.get("ref_text"),
        "lab_flag": row.get("lab_flag"),
    }
