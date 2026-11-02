"""Deterministic clinical layer: units, findings, pattern matching."""
from __future__ import annotations

from materia.clinical import (
    canonicalize,
    convert,
    findings_from_rows,
    parse_intake,
    assess,
)


def test_alias_and_unit_normalisation():
    a = canonicalize("Serum Ferritin")
    assert a and a.id == "ferritin"
    # ng/mL and ug/L are the same for ferritin
    assert convert(8, "ng/mL", "µg/L", a) == 8
    b = canonicalize("B12")
    assert b and b.id == "vitamin_b12"
    assert round(convert(300, "pg/mL", "pmol/L", b), 1) == 221.3
    d = canonicalize("25-OH Vitamin D")
    assert d and d.id == "vitamin_d"
    assert round(convert(30, "ng/mL", "nmol/L", d), 1) == 74.9


def test_finding_uses_lab_interval_and_converts_units():
    intake = parse_intake(data={"age": 42, "sex": "female"})
    rows = [{"analyte": "Ferritin", "value": 8, "unit": "ng/mL",
             "ref_low": 15, "ref_high": 150}]
    f = findings_from_rows(rows, intake)[0]
    assert f.canonical == "ferritin"
    assert f.value == 8 and f.unit == "µg/L"
    assert f.direction == "low"
    assert f.ref_low == 15


def test_iron_pattern_with_anaemia_is_likely_and_high():
    intake = parse_intake(data={"age": 42, "sex": "female"})
    rows = [
        {"analyte": "Ferritin", "value": 8, "unit": "ng/mL", "ref_low": 15, "ref_high": 150},
        {"analyte": "Haemoglobin", "value": 105, "unit": "g/L", "ref_low": 120, "ref_high": 160},
        {"analyte": "MCV", "value": 76, "unit": "fL", "ref_low": 80, "ref_high": 100},
    ]
    patterns = assess(findings_from_rows(rows, intake), intake)
    iron = next(p for p in patterns if p.id == "iron_deficiency")
    assert iron.status == "likely"
    assert iron.severity == "high"
    assert iron.citations


def test_normal_panel_has_no_pattern():
    intake = parse_intake(data={"age": 30, "sex": "male"})
    rows = [
        {"analyte": "Ferritin", "value": 120, "unit": "µg/L", "ref_low": 30, "ref_high": 400},
        {"analyte": "Vitamin B12", "value": 500, "unit": "pmol/L", "ref_low": 219, "ref_high": 773},
        {"analyte": "ALT", "value": 20, "unit": "U/L", "ref_low": 4, "ref_high": 36},
        {"analyte": "Triglycerides", "value": 1.0, "unit": "mmol/L", "ref_low": 0.4, "ref_high": 1.7},
    ]
    assert assess(findings_from_rows(rows, intake), intake) == []


def test_b12_and_liver_patterns():
    intake = parse_intake(data={"age": 60, "sex": "female"})
    rows = [
        {"analyte": "Vitamin B12", "value": 150, "unit": "pmol/L", "ref_low": 219, "ref_high": 773},
        {"analyte": "MCV", "value": 102, "unit": "fL", "ref_low": 80, "ref_high": 100},
    ]
    ids = {p.id for p in assess(findings_from_rows(rows, intake), intake)}
    assert "b12_deficiency" in ids

    rows = [{"analyte": "ALT", "value": 65, "unit": "U/L", "ref_low": 4, "ref_high": 36}]
    ids = {p.id for p in assess(findings_from_rows(rows, intake), intake)}
    assert "liver_enzyme_elevation" in ids


def test_every_pattern_citation_and_option_pattern_resolves():
    from materia.clinical import load_patterns
    from materia.recommend import load_recommendations, open_corpus

    conn = open_corpus()
    for pattern in load_patterns():
        for cid in pattern.get("citations") or []:
            assert conn.execute("SELECT 1 FROM chunks WHERE chunk_id = ?", (cid,)).fetchone(), cid
    pattern_ids = {p["id"] for p in load_patterns()}
    for rule in load_recommendations():
        assert rule["pattern"] in pattern_ids, rule["id"]


def test_b12_reported_in_pg_ml_is_converted_before_matching():
    intake = parse_intake(data={"age": 60, "sex": "female"})
    rows = [{"analyte": "Vitamin B12", "value": 180, "unit": "pg/mL",
             "ref_low": 299, "ref_high": 1054}]
    f = findings_from_rows(rows, intake)[0]
    assert round(f.value, 1) == 132.8
    assert f.unit == "pmol/L"
    patterns = {p.id for p in assess([f], intake)}
    assert "b12_deficiency" in patterns


def test_magnesium_and_thyroid_patterns():
    intake = parse_intake(data={"age": 45, "sex": "female"})
    rows = [{"analyte": "Magnesium", "value": 0.62, "unit": "mmol/L",
             "ref_low": 0.70, "ref_high": 0.91}]
    ids = {p.id for p in assess(findings_from_rows(rows, intake), intake)}
    assert "magnesium_low" in ids

    rows = [
        {"analyte": "TSH", "value": 8.2, "unit": "mIU/L", "ref_low": 0.4, "ref_high": 4.8},
        {"analyte": "Free T4", "value": 8.0, "unit": "pmol/L", "ref_low": 9, "ref_high": 19},
    ]
    patterns = assess(findings_from_rows(rows, intake), intake)
    thyroid = next(p for p in patterns if p.id == "thyroid_underactive")
    assert thyroid.severity == "high"
