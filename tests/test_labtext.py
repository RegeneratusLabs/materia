"""Text-layer parsing: the deterministic read of a digital lab report.

The fixture is a synthetic report in the layout NPAAC labs print. It carries no patient
data; the real report that exposed the bug stays out of the repo.
"""
from __future__ import annotations

from materia import extract, labtext

# Numbered rows (amino-acid panels) and unnumbered rows (general pathology) both ship.
PAGE = """Page 01 of 03
Lipid Profile
Test Name
Result
Reference
Interval
Units
Cholesterol
5.7 H
<5.6
mmol/L
Triglyceride
0.6 
<2.1
mmol/L
Calculated Free
Testosterone
365 
260 - 740
pmol/L
Tot Chol/HDL
3.5 
<4.6
Comments
TARGET LEVELS:
Total Cholesterol
 <4.0 mmol/L
Reported on 19-Dec-25 15:44
CA
"""


def test_parses_unnumbered_rows_with_units_and_one_sided_intervals():
    rows = labtext.extract_rows(PAGE)
    assert [r["analyte"] for r in rows] == [
        "Cholesterol",
        "Triglyceride",
        "Calculated Free Testosterone",
        "Tot Chol/HDL",
    ]
    cholesterol = rows[0]
    assert cholesterol["value"] == 5.7
    assert cholesterol["lab_flag"] == "H"          # the lab's own marker, kept as printed
    assert (cholesterol["ref_low"], cholesterol["ref_high"]) == (None, 5.6)
    assert cholesterol["unit"] == "mmol/L"
    # A wrapped name is one analyte, not a row called "Testosterone".
    assert rows[2]["value"] == 365.0
    assert rows[2]["unit"] == "pmol/L"
    assert rows[3]["unit"] is None                  # the page prints no unit for it


def test_comment_prose_never_becomes_a_row():
    rows = labtext.extract_rows(PAGE)
    assert not any("Total Cholesterol" == r["analyte"] for r in rows)
    assert len(rows) == 4                           # "CA" (initials) is not a value


def test_limit_result_is_not_turned_into_a_number():
    rows = labtext.extract_rows(
        "Test Name\nResult\nReference\nInterval\nUnits\nActive B12\n>128\n>35\npmol/L\n"
    )
    assert rows[0]["value"] is None
    assert rows[0]["value_text"] == ">128"
    assert rows[0]["ref_low"] == 35.0


def test_page_without_a_table_yields_nothing():
    assert labtext.extract_rows("Homocysteine\nReference interval ( <15 )\nLEGEND\n") == []


def test_umol_is_normalised_to_the_micro_sign():
    rows = labtext.extract_rows(
        "Test Name\nResult\nReference\nInterval\nUnits\nCopper-serum\n8.1 L\n11.0 - 22.0\numol/L\n"
    )
    assert rows[0]["unit"] == "µmol/L"
    record = labtext.to_record(rows[0])
    assert extract.check(record, collected_at="2025-12-19") == []


def test_hba1c_is_plausible_in_both_unit_systems():
    ngsp = labtext.to_record(
        labtext.extract_rows(
            "Test Name\nResult\nReference\nInterval\nUnits\nHbA1c (NGSP)\n5.3\n<6.5\n%\n"
        )[0]
    )
    ifcc = labtext.to_record(
        labtext.extract_rows(
            "Test Name\nResult\nReference\nInterval\nUnits\nHbA1c (IFCC)\n34\n<48\nmmol/mol\n"
        )[0]
    )
    assert extract.check(ngsp, collected_at="2025-12-19") == []
    assert extract.check(ifcc, collected_at="2025-12-19") == []
