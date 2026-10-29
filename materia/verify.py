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


def content_tokens(text: str) -> set[str]:
    return {t for t in re.split(r"\W+", text.lower()) if len(t) > 3 and t not in STOP}


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
    return len(ct & et) / len(ct)


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
        if re.search(r"excluded by the safety screen|no evidence found", text, re.I):
            continue
        results.append({"line": text, **verify_line(text, by_index)})
    return {
        "lines": results,
        "supported": sum(1 for r in results if r["supported"]),
        "total": len(results),
    }
