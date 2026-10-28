"""Deterministic lab arithmetic.

Every function here is code with a citation, never model intuition. If an input is
missing the function raises rather than guessing, and the caller must report that it could
not compute the value.
"""
from __future__ import annotations

import math

# (analyte, unit) -> (factor, canonical unit). Multiply to convert to the canonical unit.
# Sources: standard SI/conventional conversion tables; factors rounded as published.
UNIT_FACTORS: dict[tuple[str, str], tuple[float, str]] = {
    ("vitamin b12", "pg/mL"): (0.7378, "pmol/L"),
    ("vitamin b12", "pmol/L"): (1.0, "pmol/L"),
    ("glucose", "mg/dL"): (0.0555, "mmol/L"),
    ("glucose", "mmol/L"): (1.0, "mmol/L"),
    ("cholesterol", "mg/dL"): (0.02586, "mmol/L"),
    ("ldl", "mg/dL"): (0.02586, "mmol/L"),
    ("hdl", "mg/dL"): (0.02586, "mmol/L"),
    ("triglycerides", "mg/dL"): (0.01129, "mmol/L"),
    ("creatinine", "mg/dL"): (88.4, "µmol/L"),
    ("creatinine", "µmol/L"): (1.0, "µmol/L"),
    ("ferritin", "ng/mL"): (1.0, "µg/L"),
    ("ferritin", "µg/L"): (1.0, "µg/L"),
    ("free t4", "ng/dL"): (12.87, "pmol/L"),
    ("free t4", "pmol/L"): (1.0, "pmol/L"),
    ("free t3", "ng/dL"): (0.0154, "nmol/L"),
    ("free t3", "nmol/L"): (1.0, "nmol/L"),
    ("haemoglobin", "g/dL"): (10.0, "g/L"),
    ("haemoglobin", "g/L"): (1.0, "g/L"),
}

CALC_CITATIONS = {
    "egfr": "CKD-EPI 2021 creatinine equation (Inker et al., NEJM 2021)",
    "fib4": "FIB-4 index (Sterling et al., Hepatology 2006)",
    "tsat": "Transferrin saturation = iron / TIBC x 100",
    "corrected_calcium": "Corrected calcium = Ca + 0.8 x (4.0 - albumin g/dL)",
    "anion_gap": "Anion gap = Na - (Cl + HCO3)",
    "homa_ir": "HOMA-IR = fasting glucose (mmol/L) x insulin (uU/mL) / 22.5",
}


def _require(**kwargs) -> None:
    missing = [k for k, v in kwargs.items() if v is None]
    if missing:
        raise ValueError(f"missing inputs: {', '.join(missing)}")


def to_canonical(analyte: str, value: float, unit: str) -> dict:
    key = (analyte.lower().strip(), unit.strip())
    if key not in UNIT_FACTORS:
        raise ValueError(f"no conversion for {analyte!r} from {unit!r}")
    factor, canonical = UNIT_FACTORS[key]
    return {"value": round(value * factor, 4), "unit": canonical, "factor": factor}


def tsat(iron_umol_l: float, tibc_umol_l: float) -> dict:
    _require(iron=iron_umol_l, tibc=tibc_umol_l)
    if tibc_umol_l <= 0:
        raise ValueError("TIBC must be positive")
    return {
        "value": round(100 * iron_umol_l / tibc_umol_l, 1),
        "unit": "%",
        "citation": CALC_CITATIONS["tsat"],
    }


def corrected_calcium(ca_mg_dl: float, albumin_g_dl: float) -> dict:
    _require(calcium=ca_mg_dl, albumin=albumin_g_dl)
    return {
        "value": round(ca_mg_dl + 0.8 * (4.0 - albumin_g_dl), 2),
        "unit": "mg/dL",
        "citation": CALC_CITATIONS["corrected_calcium"],
    }


def anion_gap(na: float, cl: float, hco3: float) -> dict:
    _require(sodium=na, chloride=cl, bicarbonate=hco3)
    return {"value": round(na - (cl + hco3), 1), "unit": "mmol/L", "citation": CALC_CITATIONS["anion_gap"]}


def egfr_ckd_epi_2021(creatinine_mg_dl: float, age: int, sex: str) -> dict:
    """CKD-EPI 2021, creatinine only. sex: 'female' or 'male'."""
    _require(creatinine=creatinine_mg_dl, age=age, sex=sex)
    female = sex.lower().startswith("f")
    kappa = 0.7 if female else 0.9
    ratio = creatinine_mg_dl / kappa
    egfr = (
        142
        * min(ratio, 1) ** -0.302
        * max(ratio, 1) ** -1.2
        * 0.9938**age
        * (1.012 if female else 1.0)
    )
    return {"value": round(egfr, 1), "unit": "mL/min/1.73m2", "citation": CALC_CITATIONS["egfr"]}


def fib4(age: int, ast: float, alt: float, platelets_10e9_l: float) -> dict:
    _require(age=age, ast=ast, alt=alt, platelets=platelets_10e9_l)
    if alt <= 0 or platelets_10e9_l <= 0:
        raise ValueError("ALT and platelets must be positive")
    value = (age * ast) / (alt * math.sqrt(platelets_10e9_l))
    return {"value": round(value, 2), "unit": "index", "citation": CALC_CITATIONS["fib4"]}


def homa_ir(glucose_mmol_l: float, insulin_uU_ml: float) -> dict:
    _require(glucose=glucose_mmol_l, insulin=insulin_uU_ml)
    return {
        "value": round(glucose_mmol_l * insulin_uU_ml / 22.5, 2),
        "unit": "index",
        "citation": CALC_CITATIONS["homa_ir"],
    }
