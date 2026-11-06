import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_blank_review_csv_matches_review_subset(tmp_path):
    out = tmp_path / "labels.csv"
    subprocess.run(
        [sys.executable, "scripts/make_review_csv.py", "--out", str(out)],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    with out.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    import json
    data = json.loads((ROOT / "data/clinical_vignettes.json").read_text())
    review = [c for c in data["cases"] if c.get("review", True)]
    assert len(rows) == len(review)
    assert all(row["decision"] == "" for row in rows)
    assert len({row["case_id"] for row in rows}) == len(review)
