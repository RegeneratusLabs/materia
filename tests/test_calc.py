import pytest

from materia import calc


def test_unit_conversion_round_trip():
    b12 = calc.to_canonical("vitamin B12", 500, "pg/mL")
    assert b12["unit"] == "pmol/L" and abs(b12["value"] - 368.9) < 0.5
    glucose = calc.to_canonical("glucose", 90, "mg/dL")
    assert abs(glucose["value"] - 5.0) < 0.1
    creat = calc.to_canonical("creatinine", 1.0, "mg/dL")
    assert creat["unit"] == "µmol/L" and abs(creat["value"] - 88.4) < 0.1


def test_unknown_conversion_raises():
    with pytest.raises(ValueError):
        calc.to_canonical("unobtainium", 1, "mg/dL")


def test_tsat():
    assert calc.tsat(15, 60)["value"] == 25.0


def test_corrected_calcium():
    assert calc.corrected_calcium(9.0, 3.0)["value"] == 9.8


def test_anion_gap():
    assert calc.anion_gap(140, 104, 24)["value"] == 12.0


def test_egfr_known_example():
    # 60 year old male, creatinine 1.0 mg/dL -> ~86 mL/min/1.73m2
    out = calc.egfr_ckd_epi_2021(1.0, 60, "male")
    assert 84 <= out["value"] <= 88
    # Sex enters twice: a lower kappa for women AND a 1.012 factor. At the same
    # creatinine/kappa ratio the female result must be the higher one.
    female = calc.egfr_ckd_epi_2021(0.7, 60, "female")
    male = calc.egfr_ckd_epi_2021(0.9, 60, "male")
    assert female["value"] > male["value"]


def test_fib4_known_example():
    out = calc.fib4(60, 30, 40, 200)
    assert abs(out["value"] - 3.18) < 0.02


def test_homa_ir():
    assert calc.homa_ir(5.0, 10.0)["value"] == 2.22


def test_missing_inputs_raise():
    with pytest.raises(ValueError):
        calc.tsat(15, None)
    with pytest.raises(ValueError):
        calc.egfr_ckd_epi_2021(None, 60, "male")
