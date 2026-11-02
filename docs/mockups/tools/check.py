#!/usr/bin/env python3
"""Static checks for the materia UI mockups.

Run from anywhere:
    python3 docs/mockups/tools/check.py
    python3 docs/mockups/tools/check.py --shots

Checks every local reference, ARIA target, quote, lab row, and the coverage
arithmetic against the repo's own artifacts. With --shots it also renders the
primary and secondary states at 1440x1000 using a local Chrome for Testing
headless shell (no network, no npm).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[3]
MOCK = ROOT / "docs" / "mockups"
PAGES = [
    MOCK / "index.html",
    MOCK / "01-reading-room.html",
    MOCK / "02-chartroom.html",
    MOCK / "03-bench.html",
    MOCK / "04-atlas.html",
    MOCK / "05-bench-type.html",
    MOCK / "06-bench-figtree.html",
]
FIXTURES = MOCK / "assets" / "fixtures.js"
SHOTS = MOCK / "assets" / "shots"
REMOTE = re.compile(r"^(?:https?:)?//", re.I)
ARIA_REF = re.compile(r"aria-(labelledby|describedby|controls)=\"([^\"]+)\"")
BUTTON = re.compile(r"<button\b([^>]*)>(.*?)</button>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")
ERRORS: list[str] = []
WARNINGS: list[str] = []


def fail(where: str, message: str) -> None:
    ERRORS.append(f"{where}: {message}")


def warn(where: str, message: str) -> None:
    WARNINGS.append(f"{where}: {message}")


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.refs: list[tuple[str, str]] = []
        self.aria_refs: list[tuple[str, str]] = []
        self.labels: list[str] = []
        self.h1 = 0
        self.lang = ""
        self.title = False
        self.imgs: list[dict] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {key: (value or "") for key, value in attrs_list}
        if tag == "html":
            self.lang = attrs.get("lang", "")
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self.h1 += 1
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "aria-labelledby" in attrs:
            self.aria_refs.append(("aria-labelledby", attrs["aria-labelledby"]))
        if "aria-describedby" in attrs:
            self.aria_refs.append(("aria-describedby", attrs["aria-describedby"]))
        if "aria-controls" in attrs:
            self.aria_refs.append(("aria-controls", attrs["aria-controls"]))
        if tag == "label" and attrs.get("for"):
            self.labels.append(attrs["for"])
        if tag == "img":
            self.imgs.append(attrs)
        for key in ("src", "href", "poster"):
            if attrs.get(key):
                self.refs.append((tag, attrs[key]))

    def handle_startendtag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs_list)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and data.strip():
            self.title = True


def parse_fixtures() -> dict:
    text = FIXTURES.read_text()
    marker = "window.MATERIA = "
    start = text.find(marker)
    if start < 0:
        raise ValueError("fixtures.js does not assign window.MATERIA")
    payload = text[start + len(marker):]
    payload = payload[: payload.rfind(";")].strip()
    return json.loads(payload)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denom * 100), min(100.0, (centre + margin) / denom * 100)


def local_target(page: Path, ref: str) -> Path:
    clean = unquote(urlparse(ref).path)
    return (page.parent / clean).resolve()


def check_page(page: Path) -> None:
    where = page.name
    parser = PageParser()
    parser.feed(page.read_text())
    if not parser.lang:
        fail(where, "html element has no lang")
    if not parser.title:
        fail(where, "no non-empty <title>")
    if parser.h1 != 1:
        fail(where, f"expected exactly one h1, found {parser.h1}")
    if "data-mockup-ready" not in page.read_text():
        fail(where, "page never sets data-mockup-ready")
    if "data-mockup-error" not in page.read_text():
        warn(where, "page has no data-mockup-error guard")

    seen: set[str] = set()
    for item in parser.ids:
        if item in seen:
            fail(where, f"duplicate id={item!r}")
        seen.add(item)
    if "main" not in seen:
        fail(where, "missing #main target")
    if not re.search(r'class="skip-link"[^>]*href="#main"', page.read_text()):
        fail(where, "missing skip link to #main")

    for kind, value in parser.aria_refs:
        for target in value.split():
            if target not in seen:
                fail(where, f"{kind} points at missing id {target!r}")
    for target in parser.labels:
        if target not in seen:
            fail(where, f"label for= points at missing id {target!r}")

    for attrs in parser.imgs:
        if "alt" not in attrs:
            fail(where, "image without alt")

    for match in BUTTON.finditer(page.read_text()):
        attrs, body = match.group(1), match.group(2)
        if "aria-label" in attrs or "aria-labelledby" in attrs:
            continue
        text = TAG.sub("", body)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            fail(where, f"button without accessible name: {match.group(0)[:80]!r}")

    for tag, ref in parser.refs:
        if not ref or ref.startswith("#") or ref.startswith("mailto:"):
            continue
        if REMOTE.match(ref):
            if tag == "a":
                continue
            fail(where, f"remote subresource: <{tag}> {ref}")
            continue
        if ref.startswith("data:"):
            continue
        target = local_target(page, ref)
        if not target.exists():
            fail(where, f"missing local {tag} target: {ref}")
        try:
            target.relative_to(MOCK.resolve())
        except ValueError:
            fail(where, f"local reference escapes docs/mockups: {ref}")

    for css in (MOCK / "assets").rglob("*.css"):
        css_text = css.read_text()
        for ref in re.findall(r"url\(([^)]+)\)", css_text):
            ref = ref.strip(" \"'")
            if REMOTE.match(ref) or ref.startswith("data:"):
                if REMOTE.match(ref):
                    fail(css.name, f"remote CSS resource: {ref}")
                continue
            target = (css.parent / ref).resolve()
            if not target.exists():
                fail(css.name, f"missing CSS target: {ref}")


def check_fixtures(data: dict) -> None:
    sources = data["sources"]
    index = ROOT / "corpus" / "index.sqlite"
    if not index.exists():
        warn("corpus", f"index missing at {index}; quote verification skipped")
        return
    conn = sqlite3.connect(index)
    conn.row_factory = sqlite3.Row
    for key, source in sources.items():
        where = f"fixtures[{key}]"
        row = conn.execute(
            """SELECT d.source,d.tier,d.jurisdiction,d.date,d.licence_name,d.url,
                      d.identifier_value,d.checksum,d.next_review_due,c.text
               FROM chunks c JOIN docs d ON d.doc_id = c.doc_id
               WHERE c.chunk_id = ?""",
            (source["chunkId"],),
        ).fetchone()
        if row is None:
            fail(where, f"chunk {source['chunkId']!r} not in index")
            continue
        if normalize(source["quote"]) not in normalize(row["text"]):
            fail(where, f"quote is not a substring of {source['chunkId']}")
        for key_in, key_db in (
            ("source", "source"), ("tier", "tier"), ("jurisdiction", "jurisdiction"),
            ("date", "date"), ("nextReview", "next_review_due"),
            ("checksum", "checksum"), ("licence", "licence_name"),
            ("identifier", "identifier_value"),
        ):
            if source[key_in] != row[key_db]:
                fail(where, f"{key_in} does not match index: {source[key_in]!r} != {row[key_db]!r}")

    for case_id, case in data["cases"].items():
        for source_id in case.get("evidenceIds", []):
            if source_id not in sources:
                fail(f"cases[{case_id}]", f"unknown evidence source {source_id!r}")
        for option in case.get("options", []):
            if option.get("sourceId") and option["sourceId"] not in sources:
                fail(f"cases[{case_id}]", f"unknown option source {option['sourceId']!r}")
        if case.get("safety", {}).get("sourceId") and case["safety"]["sourceId"] not in sources:
            fail(f"cases[{case_id}]", "unknown safety source")

    for edge in data["atlas"]["edges"]:
        for source_id in edge["sourceIds"]:
            if source_id not in sources:
                fail(f"atlas[{edge['id']}]", f"unknown source {source_id!r}")
        for source_id in edge.get("markers", {}):
            if source_id not in sources:
                fail(f"atlas[{edge['id']}]", f"marker for unknown source {source_id!r}")

    for claim in data["ask"]["answer"]:
        for source_id in claim["cites"]:
            if source_id not in sources:
                fail("ask.answer", f"unknown source {source_id!r}")
    for side in data["ask"]["conflict"]["sides"]:
        if side["sourceId"] not in sources:
            fail("ask.conflict", f"unknown source {side['sourceId']!r}")

    conn.close()


def check_lab(data: dict) -> None:
    truth_path = ROOT / "samples" / "ground_truth" / "nutripath-p2.json"
    if not truth_path.exists():
        warn("lab", "ground truth missing; lab row verification skipped")
        return
    truth = json.loads(truth_path.read_text())
    expected = {row["analyte"].lower(): row for row in truth["rows"]}
    rows = data["lab"]["rows"]
    if len(rows) != len(expected):
        fail("lab", f"expected {len(expected)} rows, found {len(rows)}")
    for row in rows:
        target = expected.get(row["analyte"].lower())
        if target is None:
            fail("lab", f"invented analyte {row['analyte']!r}")
            continue
        for key in ("value", "ref_low", "ref_high"):
            fixture_key = {"ref_low": "low", "ref_high": "high"}.get(key, key)
            if float(row[fixture_key]) != float(target[key]):
                fail("lab", f"{row['analyte']}: {fixture_key} {row[fixture_key]} != {target[key]}")
        if row["unit"] == "ratio" and "unit" not in target:
            continue
        if "unit" in target and row["unit"] != target["unit"]:
            fail("lab", f"{row['analyte']}: unit {row['unit']!r} != {target['unit']!r}")
    image = data["lab"]["doc"].get("image", "assets/nutripath-p2.png")
    if not (MOCK / image).exists():
        fail("lab", f"document image missing: {image}")


def check_coverage(data: dict) -> None:
    coverage = data["atlas"]["coverage"]
    groups = [{"label": "All panel items", **coverage["total"]}] + coverage["groups"]
    for group in groups:
        k, n = group["covered"], group["n"]
        lo, hi = wilson(k, n)
        pct = f"{100 * k / n:.1f}%"
        ci = f"[{lo:.1f}, {hi:.1f}]"
        if group["pct"] != pct:
            fail("coverage", f"{group['label']}: pct {group['pct']} != {pct}")
        if group["ci"] != ci:
            fail("coverage", f"{group['label']}: ci {group['ci']} != {ci}")
    index = ROOT / "corpus" / "index.sqlite"
    if index.exists():
        conn = sqlite3.connect(index)
        docs = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        tiers = dict(conn.execute("SELECT tier, COUNT(*) FROM docs GROUP BY tier").fetchall())
        jurisdictions = dict(conn.execute("SELECT jurisdiction, COUNT(*) FROM docs GROUP BY jurisdiction").fetchall())
        conn.close()
        corpus = coverage["corpus"]
        if corpus["docs"] != docs or corpus["chunks"] != chunks:
            fail("coverage", f"corpus counts {corpus['docs']}/{corpus['chunks']} != {docs}/{chunks}")
        if corpus["tiers"] != tiers:
            fail("coverage", f"tier counts {corpus['tiers']} != {tiers}")
        if corpus["jurisdictions"] != jurisdictions:
            fail("coverage", f"jurisdiction counts {corpus['jurisdictions']} != {jurisdictions}")


def browser() -> str | None:
    env = shutil.which("chrome-headless-shell")
    if env:
        return env
    candidates = sorted(Path.home().glob(
        ".cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"
    ))
    if candidates:
        return str(candidates[-1])
    for name in ("chromium", "chromium-browser", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def png_size(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()[:24]
        return struct.unpack(">II", data[16:24])
    except (OSError, struct.error):
        return None


def take_shots() -> None:
    exe = browser()
    if not exe:
        warn("shots", "no Chrome/Chromium headless binary found; screenshots skipped")
        return
    SHOTS.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("01-reading-room.html", "", "01-reading-room.png", 1000),
        ("01-reading-room.html", "#memory", "01-reading-room-memory.png", 1000),
        ("02-chartroom.html", "", "02-chartroom.png", 1000),
        ("02-chartroom.html", "#rf01", "02-chartroom-emergency.png", 1000),
        ("03-bench.html", "", "03-bench.png", 1000),
        ("03-bench.html", "#interpret", "03-bench-interpret.png", 1000),
        ("04-atlas.html", "", "04-atlas.png", 1000),
        ("04-atlas.html", "#coverage", "04-atlas-coverage.png", 1000),
        ("05-bench-type.html", "?type=lora", "05-bench-type-lora.png", 1000),
        ("05-bench-type.html", "?type=fraunces", "05-bench-type-fraunces.png", 1000),
        ("05-bench-type.html", "?type=nunito", "05-bench-type-nunito.png", 1000),
        ("05-bench-type.html", "?type=figtree", "05-bench-type-figtree.png", 1000),
        ("06-bench-figtree.html", "", "06-bench-figtree.png", 1200),
        ("06-bench-figtree.html", "#interpret", "06-bench-figtree-interpret.png", 1100),
    ]
    for filename, fragment, out_name, height in jobs:
        out = SHOTS / out_name
        with tempfile.TemporaryDirectory(prefix="materia-shot-") as profile:
            url = (MOCK / filename).as_uri() + fragment
            command = [
                exe, "--headless=new", "--no-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", "--hide-scrollbars",
                "--allow-file-access-from-files", f"--user-data-dir={profile}",
                f"--window-size=1440,{height}", "--virtual-time-budget=2500",
                f"--screenshot={out}", url,
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=45)
            if result.returncode != 0 or not out.exists():
                fail("shots", f"{out_name}: render failed ({result.returncode})")
                continue
            size = png_size(out)
            if size != (1440, height):
                fail("shots", f"{out_name}: unexpected size {size}, expected {(1440, height)}")
            # DOM assertion: the page initialised and did not raise.
            dom_command = [
                exe, "--headless=new", "--no-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage",
                "--allow-file-access-from-files", f"--user-data-dir={profile}",
                "--virtual-time-budget=2000", "--dump-dom", url,
            ]
            dom = subprocess.run(dom_command, capture_output=True, text=True, timeout=45)
            if "data-mockup-ready=\"1\"" not in dom.stdout:
                fail("shots", f"{out_name}: data-mockup-ready not set")
            if "data-mockup-error=\"1\"" in dom.stdout:
                fail("shots", f"{out_name}: page reported data-mockup-error")
    print(f"screenshots: {len(jobs)} attempts -> {SHOTS.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shots", action="store_true", help="render screenshots with headless Chrome")
    args = parser.parse_args()

    missing = [page for page in PAGES if not page.exists()]
    if missing:
        for page in missing:
            fail("pages", f"missing {page.relative_to(ROOT)}")
        print("\n".join(ERRORS))
        return 1

    for page in PAGES:
        check_page(page)

    try:
        data = parse_fixtures()
    except Exception as exc:  # noqa: BLE001 - report, do not crash the checker
        fail("fixtures", f"could not parse: {exc}")
        data = None

    if data:
        check_fixtures(data)
        check_lab(data)
        check_coverage(data)
        if not (MOCK / "assets" / "shots").exists():
            warn("shots", "screenshots folder missing; run with --shots")
    if args.shots:
        take_shots()

    for warning in WARNINGS:
        print(f"WARN {warning}")
    for error in ERRORS:
        print(f"FAIL {error}")
    print(f"\n{len(PAGES)} pages · {len(ERRORS)} error(s) · {len(WARNINGS)} warning(s)")
    return 1 if ERRORS else 0


if __name__ == "__main__":
    raise SystemExit(main())
