from materia.prompt import build_prompt, build_prompt_retrieval, evidence_header

ITEM = {
    "id": "H01",
    "cat": "herb-drug",
    "q": "A patient on a combined oral contraceptive starts St John's Wort. What happens?",
    "o": {"B": "Nothing", "A": "More oestrogen", "D": "Less effect", "C": "Reduced efficacy via induction"},
    "a": "C",
}


def test_closed_prompt_shape():
    p = build_prompt(ITEM)
    assert "at most 60 words" in p
    assert ITEM["q"] in p
    # options are sorted A,B,C,D regardless of dict order (match the block exactly:
    # the rule itself contains "C or D).", so naive index() is a trap)
    block = "\n".join(f"{k}) {ITEM['o'][k]}" for k in sorted(ITEM["o"]))
    assert block in p
    assert p.rstrip().endswith("Answer:")


def test_retrieval_prompt_carries_labels_and_obligation():
    chunks = [
        {
            "chunk_id": "ema-sjw-2024#003",
            "source": "EMA",
            "tier": "regulatory",
            "jurisdiction": "eu",
            "date": "2024-03-01",
            "section": "interactions",
            "text": "St John's wort induces CYP3A4 and reduces contraceptive efficacy.",
        }
    ]
    p = build_prompt_retrieval(ITEM, chunks)
    assert "SOURCE:" in p
    assert "NO_EVIDENCE" in p
    assert "[S1]" in p
    assert "ema-sjw-2024#003" in p
    assert "section=interactions" in p
    assert "at most 60 words" in p
    # no prior-distrust instructions
    assert "distrust" not in p.lower()
    assert "reinterpret" not in p.lower()


def test_evidence_header():
    h = evidence_header(2, {"chunk_id": "x#1", "source": "NICE", "tier": "regulatory", "jurisdiction": "uk"})
    assert h.startswith("[S2]") and "NICE" in h and "uk" in h
