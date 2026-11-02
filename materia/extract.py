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
# second failure is the one that hurts. Canon may be a tuple for analytes the lab
# prints in two unit systems, or None where the report prints no unit at all.
PLAUSIBLE: dict[str, tuple[float, float, str | tuple[str, ...] | None]] = {
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
    # ---- general pathology panel (NPAAC-style reports print SI units) ----
    "sodium": (110, 190, "mmol/L"),
    "potassium": (1.5, 10, "mmol/L"),
    "chloride": (60, 140, "mmol/L"),
    "bicarbonate": (5, 50, "mmol/L"),
    "anion gap": (0, 60, "mmol/L"),
    "urea": (0.5, 100, "mmol/L"),
    "egfr": (1, 200, "mL/min/1.73m2"),
    "glucose fasting": (0.5, 60, "mmol/L"),
    "total protein": (20, 130, "g/L"),
    "albumin": (5, 80, "g/L"),
    "globulin": (5, 100, "g/L"),
    "bilirubin": (0.5, 800, "µmol/L"),
    "alp": (5, 3000, "U/L"),
    "haemolysis index": (0, 1000, None),
    "triglyceride": (0.1, 60, "mmol/L"),
    "non hdlc": (0.2, 25, "mmol/L"),
    "tot chol/hdl": (0.5, 30, "ratio"),
    "haematocrit": (0.05, 0.8, None),
    "red cell count": (0.3, 10, "10^12/L"),
    "mcv": (40, 140, "fL"),
    "white cell count": (0.2, 200, "10^9/L"),
    "neutrophils": (0, 150, "10^9/L"),
    "lymphocytes": (0, 150, "10^9/L"),
    "monocytes": (0, 60, "10^9/L"),
    "eosinophils": (0, 60, "10^9/L"),
    "basophils": (0, 30, "10^9/L"),
    "platelets": (1, 1500, "10^9/L"),
    "testosterone": (0.1, 100, "nmol/L"),
    "shbg": (1, 300, "nmol/L"),
    "calculated free testosterone": (10, 5000, "pmol/L"),
    "thyroid peroxidase ab": (0, 10000, "IU/mL"),
    "thyroglobulin ab": (0, 10000, "IU/mL"),
    "iron": (1, 100, "µmol/L"),
    "transferrin": (0.2, 10, "g/L"),
    "tibc": (5, 150, "µmol/L"),
    "saturation": (1, 100, "%"),
    "active b12": (10, 5000, "pmol/L"),
    "copper": (1, 60, "µmol/L"),
    "copper-serum": (1, 60, "µmol/L"),
    "zinc": (1, 100, "µmol/L"),
    "zinc-plasma": (1, 100, "µmol/L"),
    "r-u-creatinine": (0.1, 50, "mmol/L"),
    "urine iodine": (1, 20000, "µg/L"),
    "creat corr. iodine": (1, 20000, "µg/L"),
    "s-insulin": (0, 500, "mU/L"),
    "insulin": (0, 500, "mU/L"),
    "hba1c": (2, 20, ("%", "mmol/mol")),
    "fsh": (0.1, 300, "IU/L"),
    "lh": (0.1, 300, "IU/L"),
    "oestradiol": (1, 20000, "pmol/L"),
    "progesterone": (0.1, 1000, "nmol/L"),
    "dheas": (0.1, 100, "µmol/L"),
    "cortisol am": (10, 5000, "nmol/L"),
    "cortisol": (10, 5000, "nmol/L"),
}

# A few analytes are printed in two unit systems, so one (min, max) cannot cover both.
# Keyed by (analyte, unit); takes precedence over PLAUSIBLE for that unit.
UNIT_BOUNDS: dict[tuple[str, str], tuple[float, float]] = {
    ("hba1c", "%"): (2, 20),
    ("hba1c", "mmol/mol"): (10, 200),
}

KNOWN_UNITS = {
    "µmol/L", "μmol/L", "mmol/L", "pmol/L", "nmol/L", "mg/dL", "mg/L", "µg/L", "ug/L",
    "ng/mL", "pg/mL", "ng/dL", "mIU/L", "mU/L", "µIU/mL", "μIU/mL", "IU/mL", "IU/L",
    "U/L", "g/L", "g/dL", "%", "ratio", "mL/min/1.73m2", "mmol/mol", "10^12/L",
    "10^9/L", "fL", "mEq/L", "sec", "mm/hr",
}

# Labs print "umol/L" and "ug/L"; the record uses µ. Normalise, never guess.
_UNIT_ALIASES = {
    "umol/l": "µmol/L", "μmol/l": "µmol/L", "µmol/l": "µmol/L",
    "ug/l": "µg/L", "μg/l": "µg/L", "µg/l": "µg/L",
    "mmol/l": "mmol/L", "nmol/l": "nmol/L", "pmol/l": "pmol/L",
    "mg/l": "mg/L", "mg/dl": "mg/dL", "g/l": "g/L", "g/dl": "g/dL",
    "ng/ml": "ng/mL", "pg/ml": "pg/mL", "ng/dl": "ng/dL",
    "miu/l": "mIU/L", "mu/l": "mU/L", "iu/l": "IU/L", "u/l": "U/L",
    "iu/ml": "IU/mL", "µiu/ml": "µIU/mL", "μiu/ml": "µIU/mL",
    "ml/min/1.73m2": "mL/min/1.73m2", "mmol/mol": "mmol/mol", "meq/l": "mEq/L",
    "fl": "fL", "10^12/l": "10^12/L", "10^9/l": "10^9/L",
    "%": "%", "ratio": "ratio", "sec": "sec", "mm/hr": "mm/hr",
}


def normalise_unit(unit: str) -> str:
    text = (unit or "").strip()
    return _UNIT_ALIASES.get(text.lower(), text)


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
    value_text = record.get("value_text")
    unit = (record.get("unit") or "").strip()
    low, high = record.get("ref_low"), record.get("ref_high")

    if not analyte:
        issues.append("no analyte name")
    if value is None and not value_text:
        issues.append("no numeric value")
    elif value is None and value_text:
        # ">128" is a limit of quantitation, not a measurement. Say so; never round it.
        issues.append(f"result printed as {value_text}, a limit rather than a single number")
    if not unit:
        issues.append("no unit")
    elif unit not in KNOWN_UNITS and unit.replace("μ", "µ") not in KNOWN_UNITS:
        issues.append(f"unrecognised unit {unit!r}")
    if low is None and high is None:
        issues.append("no reference interval")
    elif low is not None and high is not None and low > high:
        issues.append("reference interval inverted")
    if not collected_at:
        issues.append("no collection date")

    key = _key(analyte)
    bound = PLAUSIBLE.get(key)
    unit_bound = UNIT_BOUNDS.get((key, unit.replace("μ", "µ")))
    if unit_bound and value is not None:
        lo, hi = unit_bound
        if not (lo <= value <= hi):
            issues.append(f"value {value} outside plausible range {lo}-{hi} {unit}")
    elif bound and value is not None:
        lo, hi, canon = bound
        if not (lo <= value <= hi):
            issues.append(f"value {value} outside plausible range {lo}-{hi} {canon}")
        if unit and canon:
            allowed = (canon,) if isinstance(canon, str) else canon
            if unit.replace("μ", "µ") not in {u.replace("μ", "µ") for u in allowed}:
                issues.append(f"unit {unit!r} differs from expected {'/'.join(allowed)!r}")
        if low is not None and high is not None and high > 0:
            if value > high * 100 or value < low / 100:
                issues.append("value more than 100x outside the lab interval")
    elif value is not None:
        issues.append("analyte not in plausibility table")
    return issues
