"""Recommendation graph: citations resolve, doses are supported, safety fires."""
from __future__ import annotations

import json

import pytest

from materia.recommend import (
    load_recommendations,
    open_corpus,
    recommend,
    render_text,
    validate_rule,
)


@pytest.fixture(scope="module")
def conn():
    return open_corpus()


def test_every_rule_resolves_and_every_dose_is_in_its_source(conn):
    problems = {}
    for rule in load_recommendations():
        issues = validate_rule(rule, conn)
        if issues:
            problems[rule["id"]] = issues
    assert problems == {}


def test_iron_case_offers_iron_and_renders(conn):
    rows = [
        {"analyte": "Ferritin", "value": 8, "unit": "ng/mL", "ref_low": 15, "ref_high": 150},
        {"analyte": "Haemoglobin", "value": 105, "unit": "g/L", "ref_low": 120, "ref_high": 160},
    ]
    a = recommend(rows, intake={"age": 42, "sex": "female"}, conn=conn)
    tops = [o.intervention for o in a.options]
    assert tops[0] == "Oral iron"
    assert "Iron absorption and tolerance" in tops
    assert a.options[0].grade == "B"
    assert a.options[0].score > 0.5
    assert "60-120 mg elemental iron" in a.options[0].dose_quote
    assert "Clinical decision support" in render_text(a)


def test_iron_is_withheld_in_iron_overload(conn):
    rows = [{"analyte": "Ferritin", "value": 8, "unit": "ng/mL", "ref_low": 15, "ref_high": 150}]
    a = recommend(rows, intake={"age": 42, "sex": "male", "conditions": ["hemochromatosis"]}, conn=conn)
    assert a.options == []
    assert any("iron overload" in w.reason for w in a.withheld)


def test_b12_dose_is_supported(conn):
    rows = [{"analyte": "Vitamin B12", "value": 150, "unit": "pmol/L",
             "ref_low": 219, "ref_high": 773}]
    a = recommend(rows, intake={"age": 60, "sex": "female"}, conn=conn)
    b12 = next(o for o in a.options if o.intervention == "Oral vitamin B12")
    assert "2 mg/day" in b12.dose_text


def test_milk_thistle_flags_pregnancy_but_stays_available(conn):
    rows = [{"analyte": "ALT", "value": 65, "unit": "U/L", "ref_low": 4, "ref_high": 36}]
    a = recommend(rows, intake={"age": 30, "sex": "female", "contexts": ["pregnancy"]}, conn=conn)
    mt = next(o for o in a.options if o.intervention == "Milk thistle (silymarin)")
    assert "pregnant" in mt.safety_flags
    assert mt.grade == "C"


def test_normal_panel_has_no_options(conn):
    rows = [{"analyte": "Ferritin", "value": 120, "unit": "µg/L", "ref_low": 30, "ref_high": 400}]
    a = recommend(rows, intake={"age": 42, "sex": "female"}, conn=conn)
    assert a.options == []
    assert a.patterns == []


def test_assessment_is_json_serialisable(conn):
    rows = [{"analyte": "Triglycerides", "value": 3.2, "unit": "mmol/L",
             "ref_low": 0.4, "ref_high": 1.7}]
    a = recommend(rows, intake={"age": 45, "sex": "male"}, conn=conn)
    payload = json.loads(json.dumps(a.as_dict()))
    assert payload["recommendations"][0]["intervention"] == "Diet, exercise and weight"
    assert any(r["intervention"].startswith("Omega-3") for r in payload["recommendations"])
    assert payload["recommendations"][0]["evidence"]


def test_lifestyle_option_has_no_dose_but_keeps_evidence(conn):
    rows = [{"analyte": "Ferritin", "value": 8, "unit": "ng/mL", "ref_low": 15, "ref_high": 150}]
    a = recommend(rows, intake={"age": 42, "sex": "female"}, conn=conn)
    lifestyle = next(o for o in a.options if o.id == "iron-absorption")
    assert lifestyle.dose_text is None
    assert lifestyle.evidence
    payload = a.as_dict()
    row = next(r for r in payload["recommendations"] if r["id"] == "iron-absorption")
    assert row["dose"] is None


def test_magnesium_rule_quotes_the_regulatory_row(conn):
    rows = [{"analyte": "Magnesium", "value": 0.62, "unit": "mmol/L",
             "ref_low": 0.70, "ref_high": 0.91}]
    a = recommend(rows, intake={"age": 38, "sex": "female"}, conn=conn)
    mg = next(o for o in a.options if o.id == "magnesium-oral")
    assert mg.dose_text == "300–350 mg/day elemental magnesium"
    assert "pmc-pmc13391447#026" in mg.dose_chunk
    assert "pmc-pmc13391447#012" in mg.dose_chunk


def test_inflammation_flags_iron_interpretation(conn):
    rows = [
        {"analyte": "Ferritin", "value": 25, "unit": "ng/mL", "ref_low": 15, "ref_high": 150},
        {"analyte": "CRP", "value": 18, "unit": "mg/L", "ref_low": 0, "ref_high": 5},
    ]
    a = recommend(rows, intake={"age": 42, "sex": "female"}, conn=conn)
    iron = next(o for o in a.options if o.id == "oral-iron-alternate-day")
    assert any("inflammation" in flag for flag in iron.safety_flags)


def test_medication_contexts_flag_the_relevant_option(conn):
    iron = recommend(
        [{"analyte": "Ferritin", "value": 8, "unit": "ng/mL", "ref_low": 15, "ref_high": 150}],
        intake={"age": 50, "sex": "female", "medications": ["omeprazole"]}, conn=conn,
    )
    row = next(o for o in iron.options if o.id == "oral-iron-alternate-day")
    assert "taking a proton-pump inhibitor" in row.safety_flags

    vitd = recommend(
        [{"analyte": "25-hydroxyvitamin D", "value": 35, "unit": "nmol/L",
          "ref_low": 75, "ref_high": 250}],
        intake={"age": 60, "sex": "female", "medications": ["hydrochlorothiazide"]}, conn=conn,
    )
    row = next(o for o in vitd.options if o.id == "vitamin-d3")
    assert "taking a thiazide diuretic" in row.safety_flags

    fish = recommend(
        [{"analyte": "Triglycerides", "value": 3.2, "unit": "mmol/L",
          "ref_low": 0.4, "ref_high": 1.7}],
        intake={"age": 55, "sex": "male", "medications": ["clopidogrel"]}, conn=conn,
    )
    row = next(o for o in fish.options if o.id == "fish-oil-triglycerides")
    assert "taking an antiplatelet" in row.safety_flags


def test_curcumin_is_an_adjunct_after_the_ldl_referral(conn):
    rows = [{"analyte": "LDL", "value": 3.8, "unit": "mmol/L", "ref_low": 0, "ref_high": 2.6}]
    a = recommend(rows, intake={"age": 55, "sex": "male"}, conn=conn)
    assert a.options[0].id == "ldl-review"
    curcumin = next(o for o in a.options if o.id == "curcumin-ldl")
    assert curcumin.dose_text == "1,500 mg/day curcuminoids"
    assert curcumin.grade == "C"


def test_curcumin_flags_liver_and_anticoagulant_context(conn):
    rows = [{"analyte": "LDL", "value": 3.8, "unit": "mmol/L", "ref_low": 0, "ref_high": 2.6}]
    a = recommend(rows, intake={"age": 55, "sex": "male", "medications": ["warfarin"],
                                "conditions": ["liver disease"]}, conn=conn)
    curcumin = next(o for o in a.options if o.id == "curcumin-ldl")
    assert "taking an anticoagulant" in curcumin.safety_flags
    assert "liver disease" in curcumin.safety_flags


def test_berberine_is_an_adjunct_for_dysglycaemia(conn):
    rows = [{"analyte": "HbA1c", "value": 5.9, "unit": "%", "ref_low": 4.0, "ref_high": 5.6}]
    a = recommend(rows, intake={"age": 52, "sex": "male"}, conn=conn)
    assert a.options[0].id == "dysglycaemia-review"
    berberine = next(o for o in a.options if o.id == "berberine-dysglycaemia")
    assert berberine.dose_text == "1 g/day berberine"
    assert berberine.grade == "C"


def test_berberine_flags_anticoagulant_context(conn):
    rows = [{"analyte": "HbA1c", "value": 5.9, "unit": "%", "ref_low": 4.0, "ref_high": 5.6}]
    a = recommend(rows, intake={"age": 52, "sex": "male", "medications": ["warfarin"]}, conn=conn)
    berberine = next(o for o in a.options if o.id == "berberine-dysglycaemia")
    assert "taking an anticoagulant" in berberine.safety_flags


def test_critical_value_withholds_supplement_options(conn):
    rows = [{"analyte": "Triglycerides", "value": 7.0, "unit": "mmol/L",
             "ref_low": 0.4, "ref_high": 1.7}]
    a = recommend(rows, intake={"age": 45, "sex": "male"}, conn=conn)
    assert [x["canonical"] for x in a.critical_alerts] == ["triglycerides"]
    assert {o.kind for o in a.options} <= {"lifestyle", "referral"}
    assert any(w.id == "fish-oil-triglycerides" and "critical value" in w.reason for w in a.withheld)


def test_potassium_critical_value_is_the_output_with_no_option(conn):
    rows = [{"analyte": "Potassium", "value": 6.5, "unit": "mmol/L",
             "ref_low": 3.7, "ref_high": 5.2}]
    a = recommend(rows, intake={"age": 60, "sex": "male"}, conn=conn)
    assert a.critical_alerts[0]["analyte"] == "Potassium"
    assert a.options == []
    assert "critical value" not in render_text(a).lower() or "URGENT" in render_text(a)


def test_zinc_option_is_cited_and_copper_monitored(conn):
    rows = [{"analyte": "Zinc", "value": 8.0, "unit": "µmol/L", "ref_low": 10, "ref_high": 18}]
    a = recommend(rows, intake={"age": 45, "sex": "female"}, conn=conn)
    zinc = next(o for o in a.options if o.id == "zinc-oral")
    assert zinc.dose_text == "50 mg/day elemental zinc"
    assert zinc.grade == "C"
    assert any("copper" in n.text.lower() for n in zinc.safety_notes)


def test_inr_critical_value(conn):
    rows = [{"analyte": "INR", "value": 5.5, "unit": "ratio", "ref_low": 0.8, "ref_high": 1.2}]
    a = recommend(rows, intake={"age": 65, "sex": "male"}, conn=conn)
    assert a.critical_alerts[0]["canonical"] == "inr"
    assert a.options == []


def test_bicarbonate_critical_value(conn):
    rows = [{"analyte": "Bicarbonate", "value": 8, "unit": "mmol/L",
             "ref_low": 22, "ref_high": 29}]
    a = recommend(rows, intake={"age": 60, "sex": "male"}, conn=conn)
    assert a.critical_alerts[0]["canonical"] == "bicarbonate"
    assert a.options == []


def test_low_hdl_is_lifestyle_first(conn):
    rows = [{"analyte": "HDL", "value": 0.8, "unit": "mmol/L", "ref_low": 1.0, "ref_high": 3.0}]
    a = recommend(rows, intake={"age": 45, "sex": "male"}, conn=conn)
    assert a.options[0].id == "hdl-lifestyle"
    assert a.options[0].dose_text is None


def test_platelet_critical_value(conn):
    rows = [{"analyte": "Platelets", "value": 8, "unit": "10^9/L",
             "ref_low": 150, "ref_high": 400}]
    a = recommend(rows, intake={"age": 60, "sex": "male"}, conn=conn)
    assert a.critical_alerts[0]["canonical"] == "platelets"
    assert all(o.kind == "referral" for o in a.options)
    assert a.options[0].id == "thrombocytopenia-review"


def test_homocysteine_is_a_referral_not_a_blind_supplement(conn):
    rows = [{"analyte": "Homocysteine", "value": 18, "unit": "µmol/L",
             "ref_low": 5, "ref_high": 15}]
    a = recommend(rows, intake={"age": 45, "sex": "female"}, conn=conn)
    assert a.options[0].id == "homocysteine-review"
    assert a.options[0].kind == "referral"
    assert a.options[0].dose_text is None


def test_b12_pattern_catches_high_mma_with_normal_b12(conn):
    rows = [
        {"analyte": "Vitamin B12", "value": 350, "unit": "pmol/L", "ref_low": 219, "ref_high": 773},
        {"analyte": "Methylmalonic acid", "value": 400, "unit": "nmol/L", "ref_low": 0, "ref_high": 270},
    ]
    a = recommend(rows, intake={"age": 60, "sex": "female"}, conn=conn)
    assert a.options[0].id == "oral-b12"


def test_score_parts_are_exposed_and_rank_the_referral_first(conn):
    rows = [{"analyte": "LDL", "value": 3.8, "unit": "mmol/L", "ref_low": 0, "ref_high": 2.6}]
    a = recommend(rows, intake={"age": 55, "sex": "male"}, conn=conn)
    assert a.options[0].id == "ldl-review"
    curcumin = next(o for o in a.options if o.id == "curcumin-ldl")
    assert a.options[0].score > curcumin.score
    for option in a.options:
        assert {"match", "evidence", "severity", "rank_hint"} <= set(option.score_parts)
        assert 0 <= option.score_parts["match"] <= 1


def test_newborn_critical_limits_are_age_specific(conn):
    high = recommend(
        [{"analyte": "Potassium", "value": 7.2, "unit": "mmol/L",
          "ref_low": 3.7, "ref_high": 5.2}],
        intake={"age": 0, "sex": "male"}, conn=conn,
    )
    assert high.critical_alerts[0]["age_group"] == "newborn"
    assert high.critical_alerts[0]["limit"] == 7.1

    not_adult_critical = recommend(
        [{"analyte": "Potassium", "value": 6.5, "unit": "mmol/L",
          "ref_low": 3.7, "ref_high": 5.2}],
        intake={"age": 0, "sex": "male"}, conn=conn,
    )
    assert not_adult_critical.critical_alerts == []


def test_vitamin_d_lifestyle_option_is_offered_after_d3(conn):
    rows = [{"analyte": "25-hydroxyvitamin D", "value": 35, "unit": "nmol/L",
             "ref_low": 75, "ref_high": 250}]
    a = recommend(rows, intake={"age": 35, "sex": "female"}, conn=conn)
    assert a.options[0].id == "vitamin-d3"
    assert any(o.id == "vitamin-d-lifestyle" and o.kind == "lifestyle" for o in a.options)


def test_child_critical_alert_is_labelled_as_adult_limits(conn):
    rows = [{"analyte": "Potassium", "value": 6.5, "unit": "mmol/L",
             "ref_low": 3.7, "ref_high": 5.2}]
    a = recommend(rows, intake={"age": 8, "sex": "male"}, conn=conn)
    assert a.critical_alerts[0]["age_group"] == "child"
    assert "paediatric" in a.critical_alerts[0]["age_note"].lower()


def test_rules_fingerprint_is_stable_and_short():
    from materia.recommend import rules_fingerprint

    first = rules_fingerprint()
    assert len(first) == 12
    assert first == rules_fingerprint()


def test_reduced_egfr_is_a_referral(conn):
    rows = [{"analyte": "eGFR", "value": 45, "unit": "mL/min/1.73m2",
             "ref_low": 90, "ref_high": 200}]
    a = recommend(rows, intake={"age": 65, "sex": "male"}, conn=conn)
    assert a.options[0].id == "renal-review"
    assert a.options[0].kind == "referral"


def test_reduced_egfr_flags_magnesium_and_vetoes_below_30(conn):
    rows = [
        {"analyte": "Magnesium", "value": 0.60, "unit": "mmol/L", "ref_low": 0.70, "ref_high": 0.91},
        {"analyte": "eGFR", "value": 45, "unit": "mL/min/1.73m2", "ref_low": 90, "ref_high": 200},
    ]
    a = recommend(rows, intake={"age": 65, "sex": "male"}, conn=conn)
    mg = next(o for o in a.options if o.id == "magnesium-oral")
    assert "reduced eGFR" in mg.safety_flags

    rows[1]["value"] = 25
    a = recommend(rows, intake={"age": 65, "sex": "male"}, conn=conn)
    assert all(o.id != "magnesium-oral" for o in a.options)
    assert any(w.id == "magnesium-oral" for w in a.withheld)


def test_curcumin_flags_raised_liver_enzymes(conn):
    rows = [{"analyte": "LDL", "value": 3.8, "unit": "mmol/L", "ref_low": 0, "ref_high": 2.6},
            {"analyte": "ALT", "value": 65, "unit": "U/L", "ref_low": 4, "ref_high": 36}]
    a = recommend(rows, intake={"age": 55, "sex": "male"}, conn=conn)
    curcumin = next(o for o in a.options if o.id == "curcumin-ldl")
    assert "raised ALT" in curcumin.safety_flags


def test_berberine_flags_raised_liver_enzymes(conn):
    rows = [{"analyte": "HbA1c", "value": 5.9, "unit": "%", "ref_low": 4.0, "ref_high": 5.6},
            {"analyte": "ALT", "value": 65, "unit": "U/L", "ref_low": 4, "ref_high": 36}]
    a = recommend(rows, intake={"age": 52, "sex": "male"}, conn=conn)
    berberine = next(o for o in a.options if o.id == "berberine-dysglycaemia")
    assert "raised ALT" in berberine.safety_flags


def test_raised_inr_flags_bleeding_risk_options(conn):
    base = {"analyte": "INR", "value": 3.5, "unit": "ratio", "ref_low": 0.8, "ref_high": 1.2}
    ldl = recommend(
        [{"analyte": "LDL", "value": 3.8, "unit": "mmol/L", "ref_low": 0, "ref_high": 2.6}, base],
        intake={"age": 55, "sex": "male"}, conn=conn,
    )
    assert "raised INR" in next(o for o in ldl.options if o.id == "curcumin-ldl").safety_flags

    tg = recommend(
        [{"analyte": "Triglycerides", "value": 3.2, "unit": "mmol/L",
          "ref_low": 0.4, "ref_high": 1.7}, base],
        intake={"age": 55, "sex": "male"}, conn=conn,
    )
    assert "raised INR" in next(o for o in tg.options if o.id == "fish-oil-triglycerides").safety_flags


def test_low_platelets_flag_bleeding_risk_options(conn):
    rows = [
        {"analyte": "LDL", "value": 3.8, "unit": "mmol/L", "ref_low": 0, "ref_high": 2.6},
        {"analyte": "Platelets", "value": 80, "unit": "10^9/L", "ref_low": 150, "ref_high": 400},
    ]
    a = recommend(rows, intake={"age": 55, "sex": "male"}, conn=conn)
    assert "low platelets" in next(o for o in a.options if o.id == "curcumin-ldl").safety_flags


def test_high_uric_acid_is_lifestyle_first(conn):
    rows = [{"analyte": "Uric acid", "value": 550, "unit": "µmol/L",
             "ref_low": 238, "ref_high": 511}]
    a = recommend(rows, intake={"age": 50, "sex": "male"}, conn=conn)
    assert a.options[0].id == "urate-lifestyle"
    assert a.options[0].dose_text is None


def test_raised_bilirubin_is_a_referral(conn):
    rows = [{"analyte": "Bilirubin", "value": 35, "unit": "µmol/L",
             "ref_low": 3, "ref_high": 20}]
    a = recommend(rows, intake={"age": 50, "sex": "male"}, conn=conn)
    assert a.options[0].id == "bilirubin-review"
    assert a.options[0].kind == "referral"


def test_low_albumin_is_a_referral(conn):
    rows = [{"analyte": "Albumin", "value": 30, "unit": "g/L",
             "ref_low": 34, "ref_high": 54}]
    a = recommend(rows, intake={"age": 55, "sex": "male"}, conn=conn)
    assert a.options[0].id == "albumin-review"
    assert a.options[0].kind == "referral"


def test_high_platelets_is_a_referral(conn):
    rows = [{"analyte": "Platelets", "value": 600, "unit": "10^9/L",
             "ref_low": 150, "ref_high": 400}]
    a = recommend(rows, intake={"age": 50, "sex": "female"}, conn=conn)
    assert a.options[0].id == "platelet-review"
    assert a.options[0].kind == "referral"


import pytest


@pytest.mark.parametrize("analyte,value,unit,ref_low,ref_high", [
    ("Glucose", 11.5, "mmol/L", 3.9, 5.5),
    ("Calcium", 1.70, "mmol/L", 2.15, 2.55),
    ("Sodium", 128, "mmol/L", 135, 145),
    ("Haemoglobin", 95, "g/L", 120, 160),
    ("INR", 4.5, "ratio", 0.8, 1.2),
])
def test_newborn_limits_are_applied_to_all_supported_analytes(
    conn, analyte, value, unit, ref_low, ref_high
):
    rows = [{"analyte": analyte, "value": value, "unit": unit,
             "ref_low": ref_low, "ref_high": ref_high}]
    newborn = recommend(rows, intake={"age": 0, "sex": "male"}, conn=conn)
    adult = recommend(rows, intake={"age": 30, "sex": "male"}, conn=conn)
    assert newborn.critical_alerts, f"{analyte} should be critical in a newborn"
    assert not adult.critical_alerts, f"{analyte} should not be adult-critical at this value"


def test_low_platelets_is_a_referral_when_not_critical(conn):
    rows = [{"analyte": "Platelets", "value": 80, "unit": "10^9/L",
             "ref_low": 150, "ref_high": 400}]
    a = recommend(rows, intake={"age": 50, "sex": "female"}, conn=conn)
    assert a.options[0].id == "thrombocytopenia-review"
    assert a.options[0].kind == "referral"
    assert a.critical_alerts == []


def test_high_free_t4_is_a_referral(conn):
    rows = [
        {"analyte": "Free T4", "value": 30, "unit": "pmol/L", "ref_low": 12, "ref_high": 22},
        {"analyte": "TSH", "value": 0.02, "unit": "mIU/L", "ref_low": 0.4, "ref_high": 4.8},
    ]
    a = recommend(rows, intake={"age": 40, "sex": "female"}, conn=conn)
    assert a.options[0].id == "hyperthyroid-review"
    assert a.options[0].kind == "referral"
