"""Smoke tests for the local web app. No model is required."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from materia.webapp import server


@pytest.fixture()
def live_server(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "FEEDBACK", tmp_path / "feedback.jsonl")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def get(url: str) -> tuple[int, bytes, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("Content-Type", "")


def post(url: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_sample_payload_has_rows_and_lab_flags():
    payload = server._sample_payload()
    assert payload["session"] == "sample"
    assert payload["doc"]["sample"] is True
    assert len(payload["rows"]) == 12
    flags = [row for row in payload["rows"] if row["flag"]]
    assert {row["analyte"] for row in flags} == {"Methionine", "Tryptophan", "Phenylalanine"}
    assert all(row["conf"] is None for row in payload["rows"])
    assert all(row["status"] == "review" for row in flags)


def test_public_row_derives_range_flag_and_review():
    row = server._public_row(
        {"analyte": "Ferritin", "value": 4, "unit": "µg/L", "ref_low": 15, "ref_high": 150},
        "2026-01-01",
    )
    assert row["flag"] == "L"
    assert row["status"] == "review"
    assert row["issues"] == []

    clean = server._public_row(
        {"analyte": "Ferritin", "value": 80, "unit": "µg/L", "ref_low": 15, "ref_high": 150},
        "2026-01-01",
    )
    assert clean["flag"] is None
    assert clean["status"] == "ready"


def test_date_only_when_printed():
    assert server._iso_date("Date Collected: 01/15/2012") == "2012-01-15"
    assert server._iso_date("no date here") is None


def test_day_first_date_is_read_day_first():
    """An Australian report prints 19/12/2025. Read month-first that is month 19: the
    date came back None and every row was flagged "no collection date"."""
    assert server._iso_date("Collected 19/12/2025 08:02") == "2025-12-19"
    assert server._iso_date("Collected\n19 Dec 2025 08:02") is None      # not the numeric form


def test_ambiguous_date_is_not_guessed():
    # 03/04/2025 could be either order; a wrong collection date is a wrong result.
    assert server._iso_date("Collected 03/04/2025") is None
    # Once the page itself shows a day above 12, the order is settled for every date.
    assert server._iso_date("Collected 03/04/2025\nReceived 19/04/2025") == "2025-04-03"


def test_collection_date_outranks_a_stray_date_in_the_text():
    # A month-first collection date, with a day-first date in the comment prose below it.
    assert server._iso_date("Collected 12/19/2025\nComment: since 15/09/2025") == "2025-12-19"


def test_page_label_describes_what_was_read():
    assert server._page_label([1], 16) == "Page 1 of 16"
    assert server._page_label([1, 2, 3], 3) == "All 3 pages"
    assert server._page_label([1, 2, 3], 16) == "Pages 1–3 of 16"
    assert server._page_label([], None) == "Page 1"


def test_merge_keeps_one_row_per_printed_value():
    pages = [
        (2, [{"analyte": "Cholesterol", "value": 5.7, "unit": "mmol/L", "ref_low": None,
              "ref_high": 5.6, "ref_text": "<5.6", "lab_flag": "H"}]),
        (5, [{"analyte": "Cholesterol", "value": 5.7, "unit": "mmol/L", "ref_low": None,
              "ref_high": 5.6, "ref_text": "<5.6", "lab_flag": "H"},
             {"analyte": "HDL", "value": 1.63, "unit": "mmol/L", "ref_low": 0.89,
              "ref_high": None, "ref_text": ">0.89", "lab_flag": None}]),
    ]
    merged = server._merge_pages(pages)
    assert [r["analyte"] for r in merged] == ["Cholesterol", "HDL"]
    assert merged[0]["page"] == 2       # the page it was first read from
    assert merged[1]["page"] == 5


def test_multi_page_report_is_read_from_the_text_layer(tmp_path, monkeypatch):
    """The whole upload path, with no model, on a digital 2-page report."""
    import pymupdf

    def raise_if_called(image):  # the text layer must be enough
        raise AssertionError(f"OCR was called for {image}")

    monkeypatch.setattr(server, "_run_ocr", raise_if_called)

    header = [
        "Synthetic Pathology Report", "Lab ID 000000000",
        "Collected 19/12/2025 08:02", "These results may be an incomplete extract.",
        "Accredited for compliance with NPAAC standards and ISO 15189",
    ]
    table = ["Test Name", "Result", "Reference", "Interval", "Units"]
    page_two = header + ["Biochemistry"] + table + [
        "Sodium", "140", "135 - 145", "mmol/L",
        "Cholesterol", "5.7 H", "<5.6", "mmol/L",
    ]
    page_five = header + ["Lipid Profile"] + table + [
        "HDL", "1.63", ">0.89", "mmol/L",
    ]
    path = tmp_path / "report.pdf"
    doc = pymupdf.open()
    for lines in (page_two, page_five):
        page = doc.new_page()
        y = 72
        for line in lines:
            page.insert_text((72, y), line, fontsize=11)
            y += 16
    doc.save(str(path))
    doc.close()

    payload = server._extract_upload("report.pdf", path.read_bytes(), "application/pdf")
    doc_info = payload["doc"]
    assert doc_info["provenance"] == "Text layer read"
    assert doc_info["collected"] == "2025-12-19"
    assert doc_info["page_count"] == 2
    assert doc_info["pages"] == [1, 2]

    rows = {row["analyte"]: row for row in payload["rows"]}
    assert set(rows) == {"Sodium", "Cholesterol", "HDL"}
    assert rows["Sodium"]["value"] == 140.0
    assert rows["Sodium"]["page"] == 1
    assert rows["HDL"]["page"] == 2
    assert rows["HDL"]["ref_low"] == 0.89 and rows["HDL"]["ref_high"] is None
    assert rows["Cholesterol"]["flag"] == "H"
    assert rows["Cholesterol"]["flag_kind"] == "lab"
    assert rows["Cholesterol"]["status"] == "review"   # the lab flagged it
    assert rows["Sodium"]["status"] == "ready"
    assert rows["HDL"]["status"] == "ready"


def test_index_and_assets(live_server):
    status, body, ctype = get(live_server + "/")
    assert status == 200 and b"materia" in body and "text/html" in ctype
    status, body, ctype = get(live_server + "/app.js")
    assert status == 200 and b"loadSample" in body
    assert "javascript" in ctype


def test_sample_endpoint(live_server):
    status, body, _ = get(live_server + "/api/lab/sample")
    assert status == 200
    payload = json.loads(body)
    assert payload["sample"] is True
    assert len(payload["rows"]) == 12


def test_feedback_writes_jsonl(live_server, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "FEEDBACK", tmp_path / "feedback.jsonl")
    status, payload = post(live_server + "/api/feedback", {"message": "Clear and calm."})
    assert status == 200 and payload["ok"] is True
    lines = (tmp_path / "feedback.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["message"] == "Clear and calm."


def test_static_traversal_is_blocked(live_server):
    status, _, _ = get(live_server + "/../HANDOVER.md")
    assert status == 404


def test_recommend_endpoint_returns_cited_assessment(live_server):
    status, payload = post(f"{live_server}/api/recommend", {
        "intake": {"age": 42, "sex": "female"},
        "rows": [
            {"analyte": "Ferritin", "value": 8, "unit": "ng/mL", "ref_low": 15, "ref_high": 150},
            {"analyte": "Haemoglobin", "value": 105, "unit": "g/L", "ref_low": 120, "ref_high": 160},
        ],
    })
    assert status == 200
    assert payload["patterns"][0]["id"] == "iron_deficiency"
    assert payload["recommendations"][0]["intervention"] == "Oral iron"
    assert payload["recommendations"][0]["evidence"][0]["chunk_id"]
    assert payload["recommendations"][0]["dose"]["chunk_id"] == "pmc-pmc13449291#030"


def test_recommend_endpoint_rejects_empty_rows(live_server):
    status, payload = post(f"{live_server}/api/recommend", {"rows": []})
    assert status == 422
    assert "No lab rows" in payload["error"]


def test_chat_endpoint_is_grounded_in_the_assessment(live_server):
    assessment = {
        "intake": {"age": 42, "sex": "female", "contexts": []},
        "patterns": [{"label": "Iron deficiency pattern", "status": "likely", "confidence": 0.82,
                      "citations": ["pmc-pmc13449291#025"]}],
        "recommendations": [{
            "id": "oral-iron-alternate-day", "intervention": "Oral iron", "grade": "B",
            "goal": "Restore iron stores.",
            "dose": {"text": "60–120 mg elemental iron on alternate days",
                     "chunk_id": "pmc-pmc13449291#030"},
            "evidence": [{"chunk_id": "pmc-pmc13449291#030",
                          "text": "Morning dosing with 60-120 mg elemental iron on alternate days."}],
            "monitoring": {"text": "Recheck ferritin at 8–12 weeks.", "chunk_id": "pmc-pmc13449291#035"},
            "safety": {"flags": [], "notes": []}, "notes": [],
        }],
        "withheld": [], "gaps": [],
    }
    status, payload = post(f"{live_server}/api/chat", {
        "message": "What dose of iron?", "assessment": assessment, "use_model": False,
    })
    assert status == 200
    assert "60–120 mg" in payload["answer"]
    assert payload["grounded"] is True


def test_review_endpoint_writes_a_local_label(live_server, tmp_path, monkeypatch):
    path = tmp_path / "reviews.jsonl"
    monkeypatch.setattr(server, "REVIEWS", path)
    status, payload = post(f"{live_server}/api/review", {
        "session": "sample", "option_id": "oral-iron-alternate-day",
        "decision": "accept", "reason": "Fits the iron pattern.",
    })
    assert status == 200
    assert payload["ok"] is True
    entry = json.loads(path.read_text().strip())
    assert entry["option_id"] == "oral-iron-alternate-day"
    assert entry["decision"] == "accept"
    assert entry["engine_version"]
    assert len(entry["rules_hash"]) == 12

    status, body, _ctype = get(f"{live_server}/api/review/export")
    assert status == 200
    assert b"oral-iron-alternate-day" in body


def test_review_endpoint_rejects_unknown_decision(live_server):
    status, payload = post(f"{live_server}/api/review", {
        "option_id": "x", "decision": "maybe",
    })
    assert status == 422


def test_review_cases_endpoint_returns_assessments(live_server):
    status, body, _ctype = get(f"{live_server}/api/review/cases")
    payload = json.loads(body)
    assert status == 200
    assert len(payload["cases"]) >= 30
    first = payload["cases"][0]
    assert first["id"]
    assert first["assessment"]["patterns"] is not None
    assert "recommendations" in first["assessment"]
    assert "labels" in payload
