"""Local web app: the Figtree Bench review surface plus the engine API.

Run:
    materia serve --port 8765

Design constraints:
* local-only by default; no cloud calls, no auth, no telemetry
* the sample case works without any model running
* uploads need the OCR model; the server will not pretend OCR succeeded
* confirmed values are session state, not a medical record
* uploaded files live in a temporary directory and are removed on exit
"""
from __future__ import annotations

import atexit
import json
import mimetypes
import os
import re
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .. import __version__, config, extract, labtext, llm, ocr
from ..recommend import recommend as build_recommendation, rules_fingerprint
from ..chat import answer as answer_question
from ..corpus.index import stats as corpus_stats

STATIC = Path(__file__).resolve().parent / "static"
SAMPLE_IMAGE = STATIC / "assets" / "nutripath-p2.png"
SAMPLE_TRUTH = STATIC / "assets" / "sample-truth.json"
VIGNETTES = config.ROOT / "data" / "clinical_vignettes.json"
APP_DATA = Path(os.environ.get("MATERIA_APP_DATA", Path.home() / ".materia")).expanduser()
FEEDBACK = APP_DATA / "feedback.jsonl"
REVIEWS = APP_DATA / "reviews.jsonl"
MAX_UPLOAD = 25 * 1024 * 1024
# A digital report is read from its text layer in milliseconds. Only pages whose text
# layer is empty (a scan, a photo) go to the OCR model, and never more than this many:
# an OCR page costs ~45 s on CPU, so an unbounded scan would look like a hung tab.
MAX_OCR_PAGES = int(os.environ.get("MATERIA_MAX_OCR_PAGES", "12"))
MIN_TEXT_CHARS = 200
UPLOAD_ROOT = Path(tempfile.mkdtemp(prefix="materia-uploads-"))
SESSIONS: dict[str, dict] = {}
OCR_LOCK = threading.Lock()

# The sample is a fixed public report. These are its printed bars, so the UI can
# point at a value. For uploads there is no bbox, so no band is drawn.
SAMPLE_Y = {
    "lysine": 47.7, "methionine": 50.6, "tryptophan": 53.4, "isoleucine": 58.4,
    "leucine": 61.3, "valine": 64.1, "phenylalanine": 69.0, "histidine": 71.9,
    "threonine": 74.8, "arginine": 79.7, "taurine": 82.6, "tryptophan/lnaa": 87.4,
}
SAMPLE_FLAGS = {"methionine": "L", "tryptophan": "L", "phenylalanine": "L"}


def _cleanup_uploads() -> None:
    shutil.rmtree(UPLOAD_ROOT, ignore_errors=True)


atexit.register(_cleanup_uploads)


_DATE_RE = re.compile(
    r"(?:date\s+collected|collected|collection\s+date)\s*:?\s*(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})",
    re.I,
)
# Any printed numeric date, used only as evidence of the page's own day/month order
# (the date of birth, the report timestamp, a comment). Never used as the result.
_ANY_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})(?!\d)")


def _iso_date(raw: str) -> str | None:
    """Best-effort date from a report's text; never guess if no date is printed.

    Day and month order is taken from the document itself: a value above 12 in one
    position settles which is which. If every printed date could be read either way
    (03/04/2025), the date is left unread rather than guessed — a wrong collection date
    on a lab report is a wrong result.
    """
    matches = list(_DATE_RE.finditer(raw))
    if not matches:
        return None

    def order_of(pairs: list[tuple[int, int]]) -> str | None:
        for first, second in pairs:
            if first > 12 and second <= 12:
                return "DM"
            if second > 12 and first <= 12:
                return "MD"
        return None

    # The collection date is its own best evidence; other printed dates (a date of
    # birth, a comment) only settle the question when the collection date cannot.
    order = order_of([(int(m.group(1)), int(m.group(2))) for m in matches])
    if order is None:
        order = order_of(
            [(int(m.group(1)), int(m.group(2))) for m in _ANY_DATE_RE.finditer(raw)]
        )
    if order is None:
        return None
    for m in matches:
        first, second, year = (int(part) for part in m.groups())
        if year < 100:
            year += 2000
        day, month = (first, second) if order == "DM" else (second, first)
        try:
            return datetime(year, month, day).date().isoformat()
        except ValueError:
            continue
    return None


def _row_id(analyte: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (analyte or "").lower()).strip("-")


def _sample_payload() -> dict:
    if "sample" in SESSIONS:
        return {"session": "sample", "sample": True, "doc": SESSIONS["sample"]["doc"],
                "rows": SESSIONS["sample"]["rows"]}
    truth = json.loads(SAMPLE_TRUTH.read_text())
    rows = []
    for item in truth["rows"]:
        key = item["analyte"].lower()
        flag = SAMPLE_FLAGS.get(key)
        rows.append(
            {
                "id": _row_id(item["analyte"]),
                "analyte": item["analyte"],
                "value": item["value"],
                "unit": item.get("unit", truth.get("unit", "µmol/L")),
                "ref_low": item["ref_low"],
                "ref_high": item["ref_high"],
                "flag": flag,
                "flag_kind": "lab" if flag else None,
                "status": "review" if flag else "ready",
                "issues": [],
                "review_reason": "The lab marked this L. Check it against the page." if flag else None,
                "conf": None,
                "y": SAMPLE_Y.get(key),
            }
        )
    doc = {
        "title": "0013 Bloodspot Amino Acids 11 Profile",
        "lab": "Genova Diagnostics",
        "page_label": "Page 2 of 3",
        "page_number": 2,
        "collected": truth.get("collected_at"),
        "reported": truth.get("reported_at"),
        "unit": truth.get("unit", "µmol/L"),
        "image": "/api/lab/sample/page",
        "source_url": truth.get("source_url"),
        "provenance": "Sample values from the printed report",
        "sample": True,
    }
    SESSIONS["sample"] = {"doc": doc, "rows": rows, "dir": None}
    return {"session": "sample", "sample": True, "doc": doc, "rows": rows}


def _public_row(record: dict, collected: str | None, *, flag_kind: str = "range") -> dict:
    issues = extract.check(record, collected_at=collected)
    value = record.get("value")
    low, high = record.get("ref_low"), record.get("ref_high")
    lab_flag = (record.get("lab_flag") or "").strip().upper() or None
    derived = None
    if value is not None:
        if low is not None and value < low:
            derived = "L"
        elif high is not None and value > high:
            derived = "H"
    # The lab's own marker wins: it is what the report says, not what we computed.
    flag = lab_flag or derived
    kind = "lab" if lab_flag else ("range" if derived else None)
    flagged = bool(flag)
    review = bool(issues) or flagged
    reason = issues[0] if issues else ("Outside the lab's range." if flagged else None)
    return {
        "id": _row_id(record.get("analyte", "")),
        "analyte": (record.get("analyte") or "").strip(),
        "section": record.get("section"),
        "value": value,
        "value_text": record.get("value_text"),
        "unit": extract.normalise_unit(record.get("unit") or ""),
        "ref_low": low,
        "ref_high": high,
        "ref_text": record.get("ref_text"),
        "flag": flag,
        "flag_kind": kind,
        "status": "review" if review else "ready",
        "issues": issues,
        "review_reason": reason,
        "conf": None,
        "y": None,
        "page": record.get("page"),
    }


def _run_ocr(image: Path) -> dict:
    if not llm.health(config.OCR_PORT):
        llm.load_phase("ocr")
    return ocr.ocr_page(image, mode="table", max_tokens=3000)


def _two_read_label(reads: set[str]) -> str:
    if reads == {"text"}:
        return "Text layer read"
    if reads == {"ocr"}:
        return "OCR read"
    return "Text layer + OCR read"


def _page_label(pages: list[int], total: int | None) -> str:
    pages = sorted(set(pages))
    if not pages:
        return "Page 1"
    if len(pages) == 1:
        return f"Page {pages[0]}" if not total or total == 1 else f"Page {pages[0]} of {total}"
    if total and pages == list(range(1, total + 1)):
        return f"All {total} pages"
    if total and pages == list(range(pages[0], pages[-1] + 1)):
        return f"Pages {pages[0]}–{pages[-1]} of {total}"
    return f"{len(pages)} pages of {total}" if total else f"{len(pages)} pages"


def _merge_pages(found: list[tuple[int, list[dict]]]) -> list[dict]:
    """One record per distinct printed value, keeping the page it was read from.

    A report repeats a panel across pages (cholesterol on the chemistry page and again
    in the lipid profile). The same analyte, value and interval is one row; the first
    page it appears on is the one the UI points at.
    """
    merged: list[dict] = []
    seen: dict[tuple, dict] = {}
    for page, rows in sorted(found, key=lambda item: item[0]):
        for row in rows:
            record = labtext.to_record(row)
            record["page"] = page
            key = (
                record["analyte"].strip().lower(),
                record.get("value"),
                record.get("value_text"),
                record.get("ref_low"),
                record.get("ref_high"),
            )
            if key in seen:
                # Same value printed twice: keep the first page, but a heading printed
                # with the second copy is still the panel this analyte belongs to.
                if not seen[key].get("section") and record.get("section"):
                    seen[key]["section"] = record["section"]
                continue
            seen[key] = record
            merged.append(record)
    return merged


def _extract_upload(filename: str, data: bytes, content_type: str) -> dict:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise ValueError("Use a PDF, PNG, JPG, or JPEG lab report.")
    if not data:
        raise ValueError("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD:
        raise ValueError("The file is larger than 25 MB.")

    session = uuid.uuid4().hex
    work = Path(tempfile.mkdtemp(prefix=f"materia-{session[:8]}-", dir=UPLOAD_ROOT))
    source = work / ("report" + suffix)
    source.write_bytes(data)

    page_texts: list[str] = []
    found: list[tuple[int, list[dict]]] = []
    reads: set[str] = set()
    images: dict[int, Path] = {}
    total_pages: int | None = None

    with OCR_LOCK:
        if suffix == ".pdf":
            # The text layer is the first read: deterministic, exact, and free. OCR is
            # only spent on pages that carry no text (a scan or a photo inside the PDF).
            page_texts = ocr.pdf_pages(source)
            total_pages = len(page_texts)
            budget = MAX_OCR_PAGES
            for index, text in enumerate(page_texts, start=1):
                rows = labtext.extract_rows(text)
                if rows:
                    found.append((index, rows))
                    reads.add("text")
                    continue
                if len(text.strip()) >= MIN_TEXT_CHARS or budget <= 0:
                    continue
                budget -= 1
                image = ocr.render_page(source, index, work / "pages")
                page = _run_ocr(image)
                if page.get("truncated"):
                    continue
                parsed = ocr.extract_lab_rows(ocr.parse_otsl(page.get("text", "")))
                if parsed:
                    found.append((index, parsed))
                    reads.add("ocr")
                    images[index] = image
            if budget <= 0 and len(page_texts) > MAX_OCR_PAGES:
                print(f"[web] OCR stopped after {MAX_OCR_PAGES} unreadable pages")
        else:
            image = source
            page = _run_ocr(image)
            page_texts = [page.get("text", "")]
            total_pages = 1
            parsed = ocr.extract_lab_rows(ocr.parse_otsl(page.get("text", "")))
            if parsed:
                found.append((1, parsed))
                reads.add("ocr")
            images[1] = image

        if not found:
            raise ValueError(
                "No lab table was found in this report. Try a clearer page or a single-page image."
            )
        for index, _rows in found:
            if index not in images:
                images[index] = ocr.render_page(source, index, work / "pages")

    rows = _merge_pages(found)
    collected = _iso_date("\n".join(page_texts))
    clean_rows = [_public_row(record, collected) for record in rows if record.get("analyte")]
    if not clean_rows:
        raise ValueError("The table was read, but no analyte rows could be extracted.")

    pages = sorted({row["page"] for row in clean_rows if row.get("page") is not None})
    doc = {
        "title": Path(filename).stem.replace("_", " ").replace("-", " ").strip() or "Uploaded report",
        "lab": "Uploaded report",
        "page_label": _page_label(pages, total_pages),
        "page_number": pages[0] if pages else 1,
        "page_count": total_pages,
        "pages": pages,
        "collected": collected,
        "reported": None,
        "unit": clean_rows[0].get("unit") or "",
        "image": f"/api/lab/session/{session}/page",
        "source_url": None,
        "provenance": _two_read_label(reads),
        "sample": False,
    }
    SESSIONS[session] = {
        "doc": doc,
        "rows": clean_rows,
        "dir": work,
        "images": images,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return {"session": session, "sample": False, "doc": doc, "rows": clean_rows}


def _status_payload() -> dict:
    status = llm.status()
    corpus = {}
    index = config.CORPUS_DIR / "index.sqlite"
    if index.exists():
        try:
            corpus = corpus_stats(index)
        except Exception:
            corpus = {}
    return {
        "version": __version__,
        "reason": {"healthy": status["reason"]["healthy"], "port": config.REASON_PORT},
        "ocr": {
            "healthy": status["ocr"]["healthy"],
            "port": config.OCR_PORT,
            "weights_present": status["ocr"].get("weights_present", False),
        },
        "corpus": {"docs": corpus.get("docs"), "chunks": corpus.get("chunks")},
        "sample_case": SAMPLE_TRUTH.exists(),
        "feedback_path": str(FEEDBACK),
        "reviews_path": str(REVIEWS),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = f"materia/{__version__}"

    def log_message(self, fmt, *args):  # keep the console readable
        print(f"[web] {self.address_string()} {fmt % args}")

    def _start(self, status=HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'",
        )

    def send_json(self, payload: dict, status=HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        try:
            self._start(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # The browser closed the tab while OCR was still running.
            pass

    def send_error_json(self, message: str, status=HTTPStatus.BAD_REQUEST) -> None:
        self.send_json({"error": message}, status)

    def send_file(self, path: Path, *, cache: bool = False) -> None:
        if not path.exists() or not path.is_file():
            self.send_error_json("Not found.", HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        try:
            self._start()
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=3600" if cache else "no-store")
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _static(self, path: str) -> None:
        clean = unquote(path)
        if clean in ("", "/"):
            clean = "/index.html"
        target = (STATIC / clean.lstrip("/")).resolve()
        try:
            target.relative_to(STATIC.resolve())
        except ValueError:
            self.send_error_json("Not found.", HTTPStatus.NOT_FOUND)
            return
        if target.is_dir():
            target = target / "index.html"
        self.send_file(target, cache=not target.name.endswith((".html", ".js")))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/status":
                self.send_json(_status_payload())
                return
            if path == "/api/review/export":
                data = REVIEWS.read_bytes() if REVIEWS.exists() else b""
                try:
                    self._start()
                    self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                    self.send_header("Content-Disposition", 'attachment; filename="materia-reviews.jsonl"')
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            if path == "/api/review/cases":
                if not VIGNETTES.exists():
                    self.send_error_json("Review vignettes are not installed.", HTTPStatus.NOT_FOUND)
                    return
                data = json.loads(VIGNETTES.read_text())
                cases = []
                for case in data.get("cases") or []:
                    if not case.get("review", True):
                        continue
                    assessment = build_recommendation(
                        case["rows"], intake=case.get("intake") or {}
                    )
                    cases.append({
                        "id": case["id"],
                        "intake": case.get("intake") or {},
                        "assessment": assessment.as_dict(),
                    })
                labels = {}
                if REVIEWS.exists():
                    for line in REVIEWS.read_text().splitlines():
                        if not line.strip():
                            continue
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        cid = row.get("case_id")
                        if cid:
                            labels[cid] = row.get("decision")
                self.send_json({"cases": cases, "labels": labels})
                return
            if path == "/api/lab/sample":
                self.send_json(_sample_payload())
                return
            if path == "/api/lab/sample/page":
                self.send_file(SAMPLE_IMAGE, cache=True)
                return
            if path.startswith("/api/lab/session/"):
                parts = path.strip("/").split("/")
                if len(parts) == 5 and parts[4] == "page":
                    session = SESSIONS.get(parts[3])
                    images = (session or {}).get("images") or {}
                    if not session or not images:
                        self.send_error_json("Session not found.", HTTPStatus.NOT_FOUND)
                        return
                    wanted = parse_qs(parsed.query).get("page", [None])[0]
                    try:
                        number = int(wanted) if wanted else session["doc"].get("page_number", 1)
                    except (TypeError, ValueError):
                        number = session["doc"].get("page_number", 1)
                    target = images.get(number) or images[sorted(images)[0]]
                    self.send_file(Path(target))
                    return
            if path.startswith("/api/"):
                self.send_error_json("Unknown API route.", HTTPStatus.NOT_FOUND)
                return
            self._static(path)
        except Exception as exc:  # noqa: BLE001 - always answer the browser
            print(f"[web] GET {path} failed: {exc!r}")
            self.send_error_json("The local engine hit an unexpected error.", HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_UPLOAD:
                self.send_error_json("The request is larger than 25 MB.", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                return
            body = self.rfile.read(length)
            if path == "/api/lab/upload":
                filename = unquote(self.headers.get("X-Filename") or "report")
                try:
                    payload = _extract_upload(filename, body, self.headers.get("Content-Type") or "")
                except ValueError as exc:
                    self.send_error_json(str(exc), HTTPStatus.UNPROCESSABLE_ENTITY)
                    return
                self.send_json(payload)
                return
            if path == "/api/lab/confirm":
                data = json.loads(body or b"{}")
                session_id = data.get("session")
                analyte = data.get("analyte")
                session = SESSIONS.get(session_id)
                if not session:
                    self.send_error_json("Session not found.", HTTPStatus.NOT_FOUND)
                    return
                for row in session["rows"]:
                    if row["analyte"] == analyte:
                        row["status"] = "confirmed"
                        row["review_reason"] = None
                        self.send_json({"ok": True, "status": "confirmed"})
                        return
                self.send_error_json("Value not found.", HTTPStatus.NOT_FOUND)
                return
            if path == "/api/lab/discard":
                data = json.loads(body or b"{}")
                session_id = data.get("session")
                session = SESSIONS.pop(session_id, None)
                if session and session.get("dir"):
                    shutil.rmtree(session["dir"], ignore_errors=True)
                self.send_json({"ok": True})
                return
            if path == "/api/recommend":
                data = json.loads(body or b"{}")
                session_id = data.get("session")
                session = SESSIONS.get(session_id)
                rows = data.get("rows")
                if rows is None:
                    if not session:
                        self.send_error_json("Session not found.", HTTPStatus.NOT_FOUND)
                        return
                    rows = session["rows"]
                if not isinstance(rows, list) or not rows:
                    self.send_error_json("No lab rows to assess.", HTTPStatus.UNPROCESSABLE_ENTITY)
                    return
                intake = data.get("intake") or {}
                assessment = build_recommendation(rows, intake=intake)
                self.send_json(assessment.as_dict())
                return
            if path == "/api/review":
                data = json.loads(body or b"{}")
                option_id = str(data.get("option_id") or "").strip()
                decision = str(data.get("decision") or "").strip().lower()
                if not option_id:
                    self.send_error_json("option_id is required.", HTTPStatus.UNPROCESSABLE_ENTITY)
                    return
                if decision not in {"accept", "reject", "modify"}:
                    self.send_error_json("decision must be accept, reject or modify.",
                                         HTTPStatus.UNPROCESSABLE_ENTITY)
                    return
                REVIEWS.parent.mkdir(parents=True, exist_ok=True)
                entry = {
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "session": str(data.get("session") or "")[:80],
                    "case_id": str(data.get("case_id") or "")[:120],
                    "option_id": option_id[:120],
                    "reviewer": str(data.get("reviewer") or "")[:120],
                    "engine_version": __version__,
                    "rules_hash": rules_fingerprint(),
                    "decision": decision,
                    "reason": str(data.get("reason") or "")[:2000],
                    "version": __version__,
                }
                with REVIEWS.open("a") as fh:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                self.send_json({"ok": True, "path": str(REVIEWS)})
                return
            if path == "/api/chat":
                data = json.loads(body or b"{}")
                message = str(data.get("message") or "").strip()
                if not message:
                    self.send_error_json("Question is empty.", HTTPStatus.UNPROCESSABLE_ENTITY)
                    return
                assessment = data.get("assessment")
                if not isinstance(assessment, dict):
                    session = SESSIONS.get(data.get("session"))
                    if not session:
                        self.send_error_json("Session or assessment required.", HTTPStatus.NOT_FOUND)
                        return
                    assessment = build_recommendation(
                        session["rows"], intake=data.get("intake") or {}
                    ).as_dict()
                history = data.get("history") or []
                if not isinstance(history, list):
                    history = []
                history = [
                    {"role": str(h.get("role") or ""), "text": str(h.get("text") or "")[:500]}
                    for h in history if isinstance(h, dict)
                ][-8:]
                result = answer_question(
                    message, assessment,
                    use_model=data.get("use_model", True),
                    history=history,
                )
                self.send_json(result)
                return
            if path == "/api/feedback":
                data = json.loads(body or b"{}")
                message = str(data.get("message") or "").strip()
                if not message:
                    self.send_error_json("Feedback message is empty.", HTTPStatus.UNPROCESSABLE_ENTITY)
                    return
                FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
                entry = {
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "message": message[:4000],
                    "contact": str(data.get("contact") or "")[:200],
                    "page": str(data.get("page") or "")[:120],
                    "version": __version__,
                    "user_agent": (self.headers.get("User-Agent") or "")[:300],
                }
                with FEEDBACK.open("a") as fh:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                self.send_json({"ok": True})
                return
            if path == "/api/engine/start":
                data = json.loads(body or b"{}")
                phase = data.get("phase", "ocr")
                with OCR_LOCK:
                    llm.load_phase(phase)
                self.send_json(_status_payload())
                return
            self.send_error_json("Unknown API route.", HTTPStatus.NOT_FOUND)
        except json.JSONDecodeError:
            self.send_error_json("Invalid JSON.", HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self.send_error_json(f"Local model files are missing: {exc}", HTTPStatus.SERVICE_UNAVAILABLE)
        except Exception as exc:  # noqa: BLE001
            print(f"[web] POST {path} failed: {exc!r}")
            self.send_error_json("The local engine hit an unexpected error.", HTTPStatus.INTERNAL_SERVER_ERROR)


def serve(host: str = "127.0.0.1", port: int = 8765, *, open_browser: bool = False,
          start_ocr: bool = False) -> None:
    if start_ocr:
        print("[web] starting the OCR engine; this stops any reasoning server")
        llm.load_phase("ocr")
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"[web] materia {__version__} on {url}")
    print("[web] sample case is available without a model; uploads need the OCR engine")
    if open_browser:
        import webbrowser
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[web] stopping")
    finally:
        httpd.server_close()
        _cleanup_uploads()
