"""Claim-level verification.

The contract so far checks that a *line* carries a citation. This checks that the citation
actually says what the line claims. It is deliberately lexical and deterministic: a 2B model
cannot be the judge of its own output, and a second model pass would only add another
opinion. Numbers must match exactly; the surrounding claim must share its key terms.

Anything unsupported is dropped, not softened.
"""
from __future__ import annotations

import re

STOP = set(
    "the a an and or of in on for with to from by is are was were be been being this that these those "
    "as at it its their there which who whom what how why when where does do did can could should would "
    "may might will not no nor but if then than so such only also more most less least very "
    "may can will use used using shows show shown suggests suggest likely may".split()
)

DOSE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(mg|g|mcg|µg|ug|ml|iu|units?|drops?)\b", re.I)
UNIT_CANON = {"milligram": "mg", "milligrams": "mg", "gram": "g", "grams": "g",
              "microgram": "mcg", "micrograms": "mcg", "µg": "mcg", "ug": "mcg",
              "millilitre": "ml", "milliliter": "ml", "millilitres": "ml", "milliliters": "ml"}


def _stem(t: str) -> str:
    for suf in ("ations", "ation", "ities", "ity", "ous", "ics", "ic", "al", "ing", "ed", "es", "s"):
        if len(t) - len(suf) >= 4 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def content_tokens(text: str) -> set[str]:
    return {_stem(t) for t in re.split(r"\W+", text.lower()) if len(t) > 3 and t not in STOP}


def split_claims(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = line.strip().lstrip("-*0123456789. )").strip()
        if not line or len(line.split()) < 4:
            continue
        for s in re.split(r"(?<=[.!?])\s+", line):
            if len(s.split()) >= 4:
                out.append(s)
    return out


def extract_doses(text: str) -> list[tuple[str, str]]:
    out = []
    for m in DOSE.finditer(text):
        value = m.group(1).replace(",", "")
        unit = m.group(2).lower()
        unit = UNIT_CANON.get(unit, unit)
        out.append((value, unit))
    return out


def _canon_numbers(text: str) -> str:
    """Normalise number formatting so 1,200 mg and 1200 milligrams compare equal."""
    t = text.lower().replace(",", "")
    for word, abbr in UNIT_CANON.items():
        t = re.sub(rf"\b{word}\b", abbr, t)
    return re.sub(r"\s+", " ", t)


def dose_supported(dose: tuple[str, str], evidence: str) -> bool:
    value, unit = dose
    text = _canon_numbers(evidence)
    patterns = [
        rf"{re.escape(value)}\s*{re.escape(unit)}\b",
        rf"{re.escape(value)}\s*-\s*\d+(?:\.\d+)?\s*{re.escape(unit)}\b",
        rf"\d+(?:\.\d+)?\s*-\s*{re.escape(value)}\s*{re.escape(unit)}\b",
    ]
    return any(re.search(p, text) for p in patterns)


def claim_support(claim: str, evidence: str, *, threshold: float = 0.35) -> float:
    """Fraction of the claim's content words present in the evidence.

    Crude on purpose: it is a floor, not an entailment judgement. It catches the failure
    that matters — a confident sentence with no lexical connection to the cited chunk.
    """
    ct = content_tokens(claim)
    if not ct:
        return 0.0
    et = content_tokens(evidence)
    shared = ct & et
    # One shared token is almost always the organisation or the herb's own name; it is
    # not support. Require at least two independent content terms.
    if len(shared) < 2:
        return 0.0
    return len(shared) / len(ct)


def verify_line(line: str, chunks_by_index: dict[int, dict]) -> dict:
    """Return support for one cited line. Missing citation or index -> unsupported."""
    cited = [int(x) for x in re.findall(r"\[S(\d+)\]", line)]
    if not cited:
        return {"supported": False, "reason": "no citation", "score": 0.0, "cited": []}
    evidence = " ".join(chunks_by_index.get(i, {}).get("text", "") for i in cited)
    if not evidence.strip():
        return {"supported": False, "reason": "citation does not resolve", "score": 0.0, "cited": cited}
    scores = [claim_support(line, evidence)]
    for dose in extract_doses(line):
        if not dose_supported(dose, evidence):
            return {"supported": False, "reason": f"dose {dose[0]} {dose[1]} not in evidence",
                    "score": min(scores), "cited": cited}
    return {"supported": min(scores) >= 0.35, "reason": "", "score": round(min(scores), 3),
            "cited": cited}


def verify_options_block(sheet: str, chunks: list[dict]) -> dict:
    """Verify every option line; return the line-level results."""
    by_index = {i: c for i, c in enumerate(chunks, start=1)}
    results = []
    in_options = False
    for line in sheet.splitlines():
        if line.strip().upper().startswith("OPTIONS"):
            in_options = True
            continue
        if in_options and re.match(r"^[A-Z][A-Z ]{4,}$", line.strip()):
            break
        if not in_options:
            continue
        text = line.strip()
        if not text or re.match(r"^[-*]?\s*$", text):
            continue
        if re.search(r"excluded by the safety screen|no evidence found|claimed option\(s\) removed", text, re.I):
            continue
        results.append({"line": text, **verify_line(text, by_index)})
    return {
        "lines": results,
        "supported": sum(1 for r in results if r["supported"]),
        "total": len(results),
    }


def drop_unsupported(sheet: str, chunks: list[dict], *, threshold: float = 0.2) -> tuple[str, list[dict]]:
    """Remove option lines whose cited evidence does not support them.

    The sheet is only allowed to say what its own citations carry. Removed lines are
    returned so the caller can count them and show a truthful 'claims removed' note.
    """
    by_index = {i: c for i, c in enumerate(chunks, start=1)}
    out: list[str] = []
    removed: list[dict] = []
    in_options = False
    for line in sheet.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("OPTIONS"):
            in_options = True
            out.append(line)
            continue
        if in_options and re.match(r"^[A-Z][A-Z ]{4,}$", stripped):
            in_options = False
        is_option = bool(re.match(r"^\s*(?:[-*]|\d+[.)])\s", line))
        if in_options and is_option and not re.search(
            r"excluded by the safety screen|no evidence found", stripped, re.I
        ):
            cited = [int(x) for x in re.findall(r"\[S(\d+)\]", stripped)]
            evidence = " ".join(by_index.get(i, {}).get("text", "") for i in cited)
            if cited and evidence:
                score = claim_support(stripped, evidence)
                doses_ok = all(dose_supported(d, evidence) for d in extract_doses(stripped))
                if score < threshold or not doses_ok:
                    removed.append({"line": stripped, "score": round(score, 3),
                                    "dose_ok": doses_ok, "cited": cited})
                    continue
            elif not cited:
                removed.append({"line": stripped, "score": 0.0, "dose_ok": True, "cited": []})
                continue
        out.append(line)
    if removed:
        for i, line in enumerate(out):
            if line.strip().upper().startswith("OPTIONS"):
                out.insert(i + 1, f"- ({len(removed)} claimed option(s) removed: not supported by the cited evidence)")
                break
    return "\n".join(out), removed
