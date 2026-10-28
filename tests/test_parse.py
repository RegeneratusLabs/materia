from materia.parse import is_no_evidence, parse_letter, parse_sources


def test_explicit_answer_markers():
    assert parse_letter("Answer: C") == "C"
    assert parse_letter("**Answer: C**") == "C"
    assert parse_letter("The answer is (B).") == "B"
    assert parse_letter("answer is D") == "D"
    assert parse_letter("Option C is best") == "C"


def test_standalone_uppercase_letter():
    assert parse_letter("C") == "C"
    assert parse_letter("C\n") == "C"
    assert parse_letter("  **C**") == "C"


def test_lowercase_article_is_not_an_answer():
    # The E31 bug: "answer: a" must never return 'A'.
    assert parse_letter("answer: a") is None
    assert parse_letter("a") is None
    assert parse_letter("As the evidence shows, a reasonable choice is unclear") is None


def test_no_answer_returns_none():
    assert parse_letter("") is None
    assert parse_letter("I cannot determine this from the options given.") is None


def test_reasoning_tail_is_used():
    assert parse_letter("", "We compare A and B. The best fit is D.") == "D"


def test_parse_sources():
    assert parse_sources("ANSWER: C. SOURCE: S2, S5") == ["S2", "S5"]
    assert parse_sources("no citations here") == []
    assert parse_sources("S3 and S3") == ["S3"]


def test_no_evidence():
    assert is_no_evidence("NO_EVIDENCE")
    assert not is_no_evidence("ANSWER: A")
