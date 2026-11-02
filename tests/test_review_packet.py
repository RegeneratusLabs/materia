import json
from pathlib import Path


def test_review_packet_header_matches_the_review_subset():
    data = json.loads(Path("data/clinical_vignettes.json").read_text())
    review_cases = [c for c in data["cases"] if c.get("review", True)]
    text = Path("docs/practitioner-review.md").read_text()
    assert f"**Cases:** {len(review_cases)}." in text
    assert "**Reviewer:**" in text
    assert "  - evidence:" in text
    assert "  - monitor:" in text
