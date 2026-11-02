from materia.ocr import extract_lab_rows, parse_otsl

OTSL = (
    "<otsl><fcel>Results μmol/L<lcel><lcel><nl>"
    "<fcel>1. Lysine<fcel>124<fcel>92<fcel>183<fcel>63-220<ecel><nl>"
    "<fcel>2. Methionine<fcel>10<fcel>12<fcel>28<fcel>10-33<ecel><nl>"
    "<fcel>31. Tryptophan/LNAA*<fcel>0.052<fcel>0.061<fcel>0.093<fcel>0.050-0.105<ecel><nl>"
    "</otsl>"
)


def test_parse_otsl_rows_and_cells():
    rows = parse_otsl(OTSL)
    assert len(rows) == 4
    assert rows[1][0] == "1. Lysine"
    assert rows[1][1] == "124"
    assert rows[1][4] == "63-220"


def test_extract_uses_result_not_bar_labels():
    records = extract_lab_rows(parse_otsl(OTSL))
    assert [r["analyte"] for r in records] == ["Lysine", "Methionine", "Tryptophan/LNAA"]
    assert records[0]["value"] == 124.0          # not 92 (the bar minimum)
    assert (records[0]["ref_low"], records[0]["ref_high"]) == (63.0, 220.0)
    assert records[2]["value"] == 0.052
    assert records[2]["unit"] == "ratio"


def test_truncated_otsl_does_not_crash():
    rows = parse_otsl("<otsl><fcel>1. Lysine<fcel>124<fcel>63-")
    assert rows and rows[0][0] == "1. Lysine"


# A Sonic/NPAAC page as MiniCPM-OCR returns it: analytes are not numbered, the interval
# may be one-sided, and the lab's own H/L marker sits beside the result.
UNNUMBERED = (
    "<otsl><fcel>Test Name<fcel>Result<fcel>Reference Interval<fcel>Units<nl>"
    "<fcel>Sodium<fcel>140<fcel>135 - 145<fcel>mmol/L<nl>"
    "<fcel>Potassium<fcel>4.2<fcel>3.5 - 5.5<fcel>mmol/L<nl>"
    "<fcel>eGFR<fcel>88<fcel>&gt;59<ecel><nl>"
    "<fcel>Cholesterol<fcel>5.7 H<fcel>&lt;5.6<fcel>mmol/L<nl>"
    "<fcel>R-U-Creatinine<fcel>2.7<fcel>mmol/L<nl>"
    "<fcel>CA<lcel><lcel><lcel><nl>"
    "<fcel>Reported on 19-Dec-25 15:44<lcel><lcel><lcel><nl></otsl>"
)


def test_decimal_result_is_never_read_as_an_analyte_name():
    """Regression: "4.2" matched the numbering pattern, so a whole report came back as
    rows called "2", "5", "6" with every value missing."""
    records = extract_lab_rows(parse_otsl(UNNUMBERED))
    assert [r["analyte"] for r in records] == [
        "Sodium", "Potassium", "eGFR", "Cholesterol", "R-U-Creatinine",
    ]
    assert records[1]["value"] == 4.2
    assert records[1]["unit"] == "mmol/L"


def test_unnumbered_rows_keep_one_sided_intervals_and_lab_markers():
    records = {r["analyte"]: r for r in extract_lab_rows(parse_otsl(UNNUMBERED))}
    egfr = records["eGFR"]
    assert (egfr["ref_low"], egfr["ref_high"]) == (59.0, None)
    cholesterol = records["Cholesterol"]
    assert cholesterol["lab_flag"] == "H"
    assert (cholesterol["ref_low"], cholesterol["ref_high"]) == (None, 5.6)
    assert records["R-U-Creatinine"]["ref_low"] is None   # no interval printed
    assert "CA" not in records                            # initials are not a value
