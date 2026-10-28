import json
from pathlib import Path

import pytest

from materia import config, symptom

VIGNETTES = json.loads((config.DATA_DIR / "symptom_vignettes.json").read_text())["vignettes"]


@pytest.fixture(scope="module")
def rules():
    return symptom.load_rules()


def test_red_flag_exact_matches(rules):
    by_id = {v["id"]: v for v in VIGNETTES}
    for vid, expected in [
        ("RF01", "rf-chest-pain"),
        ("RF02", "rf-stroke"),
        ("RF03", "rf-thunderclap"),
        ("RF04", "rf-gi-bleed"),
        ("RF05", "rf-suicidal"),
        ("RF06", "rf-infant-fever"),
        ("RF07", "rf-weight-loss"),
        ("RF08", "rf-dvt"),
    ]:
        hits = symptom.red_flag_check(by_id[vid]["text"], rules["red_flags"])
        assert expected in [h["id"] for h in hits], (vid, hits)


def test_red_flag_recall_on_red_flag_set(rules):
    rf = [v for v in VIGNETTES if v["kind"] == "red_flag"]
    missed = []
    for v in rf:
        hits = [h["id"] for h in symptom.red_flag_check(v["text"], rules["red_flags"])]
        if not hits:
            missed.append(v["id"])
    assert missed == [], f"red flags missed: {missed}"


def test_common_presentations_do_not_trip_emergency(rules):
    for v in VIGNETTES:
        if v["kind"] != "common":
            continue
        hits = symptom.red_flag_check(v["text"], rules["red_flags"])
        assert not [h for h in hits if h["urgency"] == "emergency"], (v["id"], hits)


def test_intake_parses_contexts():
    intake = symptom.parse_intake("I'm a 30 year old woman, 12 weeks pregnant, on sertraline")
    assert intake.age == 30
    assert "pregnancy" in intake.contexts
    assert "ssri" in intake.contexts


def test_intake_reports_missing_slots():
    intake = symptom.parse_intake("I feel tired and want a supplement")
    assert "age" in intake.missing
    assert "duration" in intake.missing


@pytest.fixture(scope="module")
def conn():
    idx = config.CORPUS_DIR / "index.sqlite"
    if not idx.exists():
        pytest.skip("corpus index not built")
    from materia.corpus.index import open_index

    return open_index(idx)


def test_safety_screen_vetoes_ginkgo_on_warfarin(conn, rules):
    intake = symptom.parse_intake("68 year old on warfarin, can I take ginkgo?")
    findings = symptom.safety_screen(intake, ["ginkgo", "turmeric"], conn, rules["safety"])
    vetoed = {f["intervention"] for f in findings if f["severity"] == "veto"}
    assert "ginkgo" in vetoed
    for f in findings:
        assert f["chunk_id"], "every finding must carry a citation"


def test_safety_screen_vetoes_sjw_on_ssri(conn, rules):
    intake = symptom.parse_intake("44 year old woman on sertraline, wants St John's wort")
    findings = symptom.safety_screen(intake, ["st john's wort"], conn, rules["safety"])
    assert any(f["severity"] == "veto" and "st john" in f["intervention"] for f in findings)


def _sheet(options="1. Valerian root — dose 300-600 mg at night [S1]"):
    return (
        "WHAT YOU DESCRIBED\ninsomnia, 6 weeks, mild\n\n"
        "CHECK FIRST\nNo red flags identified from what you have described. This is not a diagnosis.\n\n"
        f"OPTIONS\n{options}\n\n"
        "SAFETY SCREEN\nno vetoes\n\n"
        "MONITOR\nsleep diary\n\n"
        "EVIDENCE GAPS\nconflicting trial results\n"
    )


def test_contract_accepts_a_clean_sheet():
    chunks = [{"chunk_id": "x#1", "text": "valerian 300-600 mg at night"}]
    assert symptom.contract_check(_sheet(), chunks, []) == []


def test_contract_flags_uncited_option():
    issues = symptom.contract_check(_sheet("Valerian root at night"), [{"text": ""}], [])
    assert any("uncited option" in i for i in issues)


def test_contract_flags_dose_not_in_evidence():
    chunks = [{"chunk_id": "x#1", "text": "valerian is traditionally used"}]
    issues = symptom.contract_check(_sheet(), chunks, [])
    assert any("dose not found" in i for i in issues)


def test_contract_flags_diagnosis_language():
    sheet = _sheet().replace("This is not a diagnosis.", "You have chronic insomnia.")
    issues = symptom.contract_check(sheet, [{"text": "valerian 300-600 mg at night"}], [])
    assert any("diagnosis language" in i for i in issues)


def test_contract_flags_vetoed_intervention():
    findings = [{"intervention": "valerian", "severity": "veto", "context": "pregnancy"}]
    issues = symptom.contract_check(_sheet(), [{"text": "valerian 300-600 mg at night"}], findings)
    assert any("vetoed intervention" in i for i in issues)
