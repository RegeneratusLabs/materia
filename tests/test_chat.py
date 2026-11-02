"""The chat layer may only answer from the assessment object."""
from __future__ import annotations

from materia.chat import answer
from materia.recommend import recommend


def assessment():
    rows = [
        {"analyte": "Ferritin", "value": 8, "unit": "ng/mL", "ref_low": 15, "ref_high": 150},
        {"analyte": "Haemoglobin", "value": 105, "unit": "g/L", "ref_low": 120, "ref_high": 160},
    ]
    return recommend(rows, intake={"age": 42, "sex": "female"}).as_dict()


def test_deterministic_answer_quotes_the_dose():
    result = answer("What dose of iron?", assessment(), use_model=False)
    assert result["grounded"] is True
    assert "60–120 mg" in result["answer"]
    assert "pmc-pmc13449291#030" in result["citations"]


def test_missing_context_is_named_not_guessed():
    result = answer("Is it safe in pregnancy?", assessment(), use_model=False)
    assert "did not record pregnancy" in result["answer"]


def test_model_answer_with_invented_dose_is_rejected(monkeypatch):
    import materia.chat as chat

    monkeypatch.setattr(chat, "_call_model", lambda *a, **k: "Take 500 mg of iron daily.")
    result = answer("What dose of iron?", assessment(), use_model=True)
    assert result["mode"] == "rejected-model"
    assert "500 mg" not in result["answer"]
    assert "60–120 mg" in result["answer"]


def test_model_answer_with_unknown_citation_is_rejected(monkeypatch):
    import materia.chat as chat

    monkeypatch.setattr(chat, "_call_model", lambda *a, **k: "Take iron [madeup-123#001].")
    result = answer("What dose of iron?", assessment(), use_model=True)
    assert result["mode"] == "rejected-model"


def test_valid_model_answer_is_used(monkeypatch):
    import materia.chat as chat

    monkeypatch.setattr(
        chat, "_call_model",
        lambda *a, **k: "The assessment suggests oral iron 60–120 mg on alternate days [pmc-pmc13449291#030].",
    )
    result = answer("What dose of iron?", assessment(), use_model=True)
    assert result["mode"] == "model"
    assert result["grounded"] is True


def test_model_answer_without_a_chunk_citation_is_rejected(monkeypatch):
    import materia.chat as chat

    monkeypatch.setattr(chat, "_call_model", lambda *a, **k: "Consider 60–120 mg of iron on alternate days.")
    result = answer("What dose of iron?", assessment(), use_model=True)
    assert result["mode"] == "rejected-model"
    assert "60–120 mg" in result["answer"]  # deterministic fallback


def test_critical_value_takes_precedence_over_a_dose_question():
    from materia.recommend import recommend

    rows = [{"analyte": "Potassium", "value": 6.5, "unit": "mmol/L",
             "ref_low": 3.7, "ref_high": 5.2}]
    a = recommend(rows, intake={"age": 60, "sex": "male"}).as_dict()
    result = answer("What supplement should I take?", a, use_model=False)
    assert result["answer"].startswith("Critical values need attention first")
    assert "Potassium" in result["answer"]
    assert result["citations"]


def test_critical_value_is_prepended_to_a_model_answer(monkeypatch):
    import materia.chat as chat
    from materia.recommend import recommend

    rows = [{"analyte": "Potassium", "value": 6.5, "unit": "mmol/L",
             "ref_low": 3.7, "ref_high": 5.2}]
    a = recommend(rows, intake={"age": 60, "sex": "male"}).as_dict()
    monkeypatch.setattr(chat, "_call_model", lambda *x, **k: "The assessment does not cover that [pmc-pmc13115040#052].")
    result = answer("What supplement should I take?", a, use_model=True)
    assert result["answer"].startswith("Critical values need attention first")


def test_ranking_question_explains_the_score_components():
    from materia.recommend import recommend

    rows = [{"analyte": "LDL", "value": 3.8, "unit": "mmol/L", "ref_low": 0, "ref_high": 2.6}]
    a = recommend(rows, intake={"age": 55, "sex": "male"}).as_dict()
    result = answer("Why is the cardiovascular review ranked first?", a, use_model=False)
    assert "Ranking:" in result["answer"]
    assert "match" in result["answer"] and "evidence" in result["answer"]


def test_dose_question_without_a_dose_is_rejected(monkeypatch):
    import materia.chat as chat

    monkeypatch.setattr(chat, "_call_model", lambda *a, **k: "Consider oral iron [pmc-pmc13449291#030].")
    result = answer("What dose of iron?", assessment(), use_model=True)
    assert result["mode"] == "rejected-model"
    assert "60–120 mg" in result["answer"]


def test_model_receives_a_bounded_conversation_history(monkeypatch):
    import materia.chat as chat

    captured = {}

    def fake(messages, **kwargs):
        captured["messages"] = messages
        return "The dose is 60–120 mg on alternate days [pmc-pmc13449291#030]."

    monkeypatch.setattr(chat, "_call_model", fake)
    result = answer(
        "And the dose?", assessment(), use_model=True,
        history=[{"role": "user", "text": "What should I take?"},
                 {"role": "bot", "text": "Oral iron is suggested."}],
    )
    joined = " ".join(m["content"] for m in captured["messages"])
    assert "What should I take?" in joined
    assert "Oral iron is suggested." in joined
    assert result["mode"] == "model"


def test_default_answer_mentions_withheld_items():
    from materia.recommend import recommend

    rows = [
        {"analyte": "Magnesium", "value": 0.60, "unit": "mmol/L", "ref_low": 0.70, "ref_high": 0.91},
        {"analyte": "eGFR", "value": 25, "unit": "mL/min/1.73m2", "ref_low": 90, "ref_high": 200},
    ]
    a = recommend(rows, intake={"age": 65, "sex": "male"}).as_dict()
    result = answer("What should I take?", a, use_model=False)
    assert "withheld" in result["answer"].lower()
    assert "magnesium" in result["answer"].lower()


def test_explain_more_returns_goal_monitoring_and_evidence():
    result = answer("Tell me more", assessment(), use_model=False)
    assert "Goal:" in result["answer"]
    assert "Monitor:" in result["answer"]
    assert "Evidence:" in result["answer"]
    assert result["citations"]


def test_malformed_history_is_ignored_without_crashing(monkeypatch):
    import materia.chat as chat

    monkeypatch.setattr(
        chat, "_call_model",
        lambda messages, **kwargs: "The dose is 60–120 mg on alternate days [pmc-pmc13449291#030].",
    )
    result = answer(
        "And the dose?", assessment(), use_model=True,
        history=["not a dict", 42, None, {"role": "user", "text": None}],
    )
    assert result["mode"] == "model"
    assert "60–120 mg" in result["answer"]
