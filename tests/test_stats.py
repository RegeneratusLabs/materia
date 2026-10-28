from materia.stats import wilson, wilson_str


def test_wilson_matches_published_intervals():
    lo, hi = wilson(99, 104)
    assert round(lo, 1) == 89.2 and round(hi, 1) == 97.9
    lo, hi = wilson(46, 46)
    assert round(lo, 1) == 92.3 and round(hi, 1) == 100.0
    lo, hi = wilson(33, 46)
    assert round(lo, 1) == 57.5 and round(hi, 1) == 82.7


def test_wilson_degenerate():
    assert wilson(0, 0) == (0.0, 0.0)
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and 0 < hi < 30


def test_wilson_str():
    assert wilson_str(99, 104).startswith("99/104 = 95.2% [89.2, 97.9]")
