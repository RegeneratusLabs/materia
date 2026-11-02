"""The synthetic contract set must keep passing as the engine changes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from materia.recommend import open_corpus, recommend


@pytest.fixture(scope="module")
def conn():
    return open_corpus()


def test_all_contract_vignettes(conn):
    data = json.loads(Path("data/clinical_vignettes.json").read_text())
    failures = []
    for case in data["cases"]:
        a = recommend(case["rows"], intake=case.get("intake") or {}, conn=conn)
        actual_patterns = {p.id for p in a.patterns}
        top = a.options[0].id if a.options else None
        withheld = {w.id for w in a.withheld}
        if not set(case.get("expect_patterns") or []) <= actual_patterns:
            failures.append((case["id"], "pattern", sorted(actual_patterns)))
        if top != case.get("expect_top"):
            failures.append((case["id"], "top", top))
        if not set(case.get("expect_withheld") or []) <= withheld:
            failures.append((case["id"], "withheld", sorted(withheld)))
        if case.get("expect_gap") and not any(g["pattern"] == case["expect_gap"] for g in a.gaps):
            failures.append((case["id"], "gap", [g["pattern"] for g in a.gaps]))
        for oid, wanted in (case.get("expect_flags") or {}).items():
            option = next((o for o in a.options if o.id == oid), None)
            if option is None or not set(wanted) <= set(option.safety_flags):
                failures.append((case["id"], "flags", option.safety_flags if option else None))
    assert failures == []
