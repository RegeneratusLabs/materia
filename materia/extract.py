"""Plausibility gate for extracted lab values.

This is the second gate, and it answers a different question from OCR confidence
(HANDOVER §2): not "did we read the glyphs" but "is this value physically possible for
this analyte, in a unit we recognise, with an interval and a date".

The bounds here are wide physiological *plausibility* bounds, NOT reference intervals.
A value inside them is not "normal"; it is merely not impossible. Reference intervals
come from the lab's own report, and from the corpus when the report gives none.
"""
from __future__ import annotations

# analyte -> (min, max, canonical unit). Deliberately wide: a false "impossible"
# sends a real number to review, a false "possible" lets a typo through, and the
# second failure is the one that hurts.
PLAUSIBLE: dict[str, tuple[float, float, str]] = {
    # amino acids (µmol/L)
    "lysine": (20, 400, "µmol/L"),
    "methionine": (3, 200, "µmol/L"),
    "tryptophan": (5, 200, "µmol/L"),
    "isoleucine": (5, 400, "µmol/L"),
    "leucine": (10, 600, "µmol/L"),
    "valine": (20, 700, "µmol/L"),
    "phenylalanine": (5, 300, "µmol/L"),
    "histidine": (5, 300, "µmol/L"),
    "threonine": (10, 400, "µmol/L"),
    "arginine": (5, 400, "µmol/L"),
    "taurine": (10, 600, "µmol/L"),
    # common panel analytes
    "ferritin": (0.5, 5000, "µg/L"),
    "vitamin b12": (20, 3000, "pmol/L"),
    "b12": (20, 3000, "pmol/L"),
    "folate": (1, 100, "nmol/L"),
    "tsh": (0.001, 200, "mIU/L"),
    "free t4": (1, 100, "pmol/L"),
    "ft4": (1, 100, "pmol/L"),
    "free t3": (0.5, 50, "pmol/L"),
    "crp": (0, 500, "mg/L"),
    "hs-crp": (0, 500, "mg/L"),
    "glucose": (1, 60, "mmol/L"),
    "hba1c": (2, 20, "%"),
    "haemoglobin": (30, 250, "g/L"),
    "hemoglobin": (30, 250, "g/L"),
    "creatinine": (10, 2000, "µmol/L"),
    "alt": (0, 10000, "U/L"),
    "ast": (0, 10000, "U/L"),
    "ggt": (0, 5000, "U/L"),
    "cholesterol": (0.5, 30, "mmol/L"),
    "ldl": (0.2, 25, "mmol/L"),
    "hdl": (0.1, 10, "mmol/L"),
    "triglycerides": (0.1, 60, "mmol/L"),
    "homocysteine": (1, 300, "µmol/L"),
    "transferrin saturation": (1, 100, "%"),
    "tryptophan/lnaa": (0.001, 1.0, "ratio"),
}

KNOWN_UNITS = {
    "µmol/L", "μmol/L", "mmol/L", "pmol/L", "nmol/L", "mg/dL", "mg/L", "µg/L", "ug/L",
    "ng/mL", "pg/mL", "ng/dL", "mIU/L", "µIU/mL", "μIU/mL", "IU/L", "U/L", "g/L",
    "g/dL", "%", "ratio", "mL/min/1.73m2",
}


def _key(analyte: str) -> str:
    a = analyte.lower().strip()
    a = a.replace("µ", "u").replace("μ", "u")
    a = a.split("(")[0].strip()
    return a


def check(record: dict, *, collected_at: str | None = None) -> list[str]:
    """Return review issues. Empty list = safe to auto-accept (still human-visible)."""
    issues: list[str] = []
    analyte = record.get("analyte") or ""
    value = record.get("value")
    unit = (record.get("unit") or "").strip()
    low, high = record.get("ref_low"), record.get("ref_high")

    if not analyte:
        issues.append("no analyte name")
    if value is None:
        issues.append("no numeric value")
    if not unit:
        issues.append("no unit")
    elif unit not in KNOWN_UNITS and unit.replace("μ", "µ") not in KNOWN_UNITS:
        issues.append(f"unrecognised unit {unit!r}")
    if low is None or high is None:
        issues.append("no reference interval")
    elif low > high:
        issues.append("reference interval inverted")
    if not collected_at:
        issues.append("no collection date")

    key = _key(analyte)
    bound = PLAUSIBLE.get(key)
    if bound and value is not None:
        lo, hi, canon = bound
        if not (lo <= value <= hi):
            issues.append(f"value {value} outside plausible range {lo}-{hi} {canon}")
        if unit and unit.replace("μ", "µ") != canon.replace("μ", "µ"):
            issues.append(f"unit {unit!r} differs from expected {canon!r}")
        if low is not None and high is not None and (high or 1) > 0:
            if value > high * 100 or value < low / 100:
                issues.append("value more than 100x outside the lab interval")
    elif value is not None:
        issues.append("analyte not in plausibility table")
    return issues
