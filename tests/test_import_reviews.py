import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_csv_labels_import_with_provenance(tmp_path):
    csv_path = tmp_path / "labels.csv"
    csv_path.write_text(
        "case_id,decision,reason,reviewer\n"
        "iron-with-anaemia,accept,fits,JS\n"
        "b12-deficiency,unsafe,too broad,JS\n"
    )
    out = tmp_path / "reviews.jsonl"
    subprocess.run(
        [sys.executable, "scripts/import_reviews.py", str(csv_path), "--out", str(out)],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(rows) == 2
    assert rows[0]["decision"] == "accept"
    assert rows[1]["decision"] == "unsafe"
    assert all(len(row["rules_hash"]) == 12 for row in rows)
    assert all(row["reviewer"] == "JS" for row in rows)


def test_csv_import_rejects_unknown_case(tmp_path):
    csv_path = tmp_path / "labels.csv"
    csv_path.write_text("case_id,decision\nnot-a-case,accept\n")
    result = subprocess.run(
        [sys.executable, "scripts/import_reviews.py", str(csv_path), "--out", str(tmp_path / "out.jsonl")],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "unknown case_id" in result.stderr
