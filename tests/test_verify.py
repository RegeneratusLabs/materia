from materia import verify


def test_dose_supported_with_unit_spelling():
    assert verify.dose_supported(("1200", "mg"), "Do not exceed 1200 milligrams curcumin per day")
    assert verify.dose_supported(("300", "mg"), "valerian 300-600 mg at night")
    assert verify.dose_supported(("600", "mg"), "valerian 300-600 mg at night")
    assert not verify.dose_supported(("140", "mg"), "valerian 300 mg at night")


def test_dose_comma_normalisation():
    assert verify.dose_supported(("1200", "mg"), "up to 1,200 mg daily")


def test_claim_support_floor():
    evidence = "St John's wort induces CYP3A4 and reduces contraceptive efficacy, with breakthrough bleeding."
    claim = "Reduces contraceptive efficacy through CYP3A4 induction."
    assert verify.claim_support(claim, evidence) >= 0.35
    assert verify.claim_support("Increases blood pressure in pregnancy", evidence) < 0.35


def test_verify_line_requires_citation():
    out = verify.verify_line("Ginkgo increases bleeding risk.", {})
    assert not out["supported"] and out["reason"] == "no citation"


def test_verify_line_rejects_unmatched_dose():
    chunks = {1: {"text": "Ginkgo may increase bleeding risk in anticoagulated patients."}}
    out = verify.verify_line("- Ginkgo — bleeding risk — 240 mg daily [S1]", chunks)
    assert not out["supported"] and "dose" in out["reason"]


def test_verify_options_block_counts():
    sheet = (
        "OPTIONS\n"
        "- Ginkgo — may increase bleeding risk [S1]\n"
        "- Ginkgo — 240 mg daily [S1]\n"
        "SAFETY SCREEN\n"
    )
    chunks = [{"text": "Ginkgo may increase bleeding risk in anticoagulated patients."}]
    out = verify.verify_options_block(sheet, chunks)
    assert out["total"] == 2 and out["supported"] == 1


def test_drop_unsupported_removes_miscited_claim():
    sheet = (
        "OPTIONS\n"
        "- Peppermint oil — NCCIH notes peppermint oil for GI ailments [S1]\n"
        "- Acupuncture — improved fatigue in cancer patients [S2]\n"
        "SAFETY SCREEN\nnone\n"
    )
    chunks = [
        {"text": "NCCIH Clearinghouse provides information on NCCIH and complementary approaches."},
        {"text": "Several RCTs studied acupuncture in reducing cancer-related fatigue."},
    ]
    out, removed = verify.drop_unsupported(sheet, chunks, threshold=0.2)
    assert len(removed) == 1 and "Peppermint" in removed[0]["line"]
    assert "Peppermint" not in out
    assert "Acupuncture" in out
    assert "claimed option" in out.lower()
