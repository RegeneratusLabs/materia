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
