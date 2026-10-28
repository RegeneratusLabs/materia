"""Symptom workflow: intake → red flags → safety screen → cited options sheet.

The contract is narrow on purpose. The output may cite what a monograph or guideline says,
including a dose quoted verbatim; it may not compose a personalised regimen, assert a
diagnosis, or keep an option that the safety screen vetoed.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import yaml

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"

REQUIRED_SECTIONS = (
    "WHAT YOU DESCRIBED",
    "CHECK FIRST",
    "OPTIONS",
    "SAFETY SCREEN",
    "MONITOR",
    "EVIDENCE GAPS",
)

DIAGNOSIS_PATTERNS = [
    r"\byou (likely |probably )?have (?!described|mentioned|reported|noticed|said|told|had)\b",
    r"\bdiagnosis is\b",
    r"\byou are suffering from\b",
    r"\bthis confirms\b",
    r"\bindicates? [a-z]+ (disease|disorder|syndrome)\b",
]

DOSE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(mg|g|mcg|µg|ug|ml|iu|units?|drops?)\b", re.I)

MEDS = {
    "warfarin": "warfarin",
    "apixaban": "doac",
    "rivaroxaban": "doac",
    "dabigatran": "doac",
    "edoxaban": "doac",
    "clopidogrel": "antiplatelet",
    "aspirin": "antiplatelet",
    "levothyroxine": "thyroid_hormone",
    "thyroxine": "thyroid_hormone",
    "carbamazepine": "antiepileptic",
    "valproate": "antiepileptic",
    "lamotrigine": "antiepileptic",
    "phenytoin": "antiepileptic",
    "methotrexate": "immunosuppression",
    "cyclosporin": "immunosuppression",
    "tacrolimus": "immunosuppression",
    "azathioprine": "immunosuppression",
    "prednisolone": "immunosuppression",
    "metformin": "diabetes",
    "insulin": "diabetes",
    "gliclazide": "diabetes",
    "sertraline": "ssri",
    "fluoxetine": "ssri",
    "escitalopram": "ssri",
    "citalopram": "ssri",
    "paroxetine": "ssri",
    "venlafaxine": "ssri",
    "phenelzine": "ssri",
    "tranylcypromine": "ssri",
}

CONDITIONS = {
    "diabetes": "diabetes",
    "liver disease": "liver_disease",
    "fatty liver": "liver_disease",
    "hepatitis": "liver_disease",
    "kidney disease": "kidney_disease",
    "renal impairment": "kidney_disease",
    "epilepsy": "antiepileptic",
    "under active thyroid": "thyroid_hormone",
    "hypothyroid": "thyroid_hormone",
    "transplant": "transplant",
    "cancer": "cancer_therapy",
    "chemotherapy": "cancer_therapy",
}


@dataclass
class Intake:
    raw: str
    age: int | None = None
    contexts: list[str] = field(default_factory=list)
    symptom: str = ""
    duration: str = ""
    severity: str = ""
    missing: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "age": self.age,
            "contexts": self.contexts,
            "symptom": self.symptom,
            "duration": self.duration,
            "severity": self.severity,
        }


def load_rules() -> dict:
    red = yaml.safe_load((RULES_DIR / "red_flags.yaml").read_text())
    safety = yaml.safe_load((RULES_DIR / "safety.yaml").read_text())
    return {"red_flags": red["rules"], "safety": safety}


def parse_intake(text: str) -> Intake:
    low = text.lower()
    intake = Intake(raw=text)
    m = re.search(r"\b(\d{1,3})\s*(?:yo|y/o|years? old|year old)\b", low)
    if m:
        intake.age = int(m.group(1))
    if re.search(r"\bpregnan|\bexpecting\b", low):
        intake.contexts.append("pregnancy")
    if re.search(r"breastfeed|breast-feed|nursing|lactat", low):
        intake.contexts.append("breastfeeding")
    if intake.age is not None and intake.age < 12:
        intake.contexts.append("child")

    for word, ctx in MEDS.items():
        if re.search(rf"\b{word}\b", low) and ctx not in intake.contexts:
            intake.contexts.append(ctx)
    for phrase, ctx in CONDITIONS.items():
        if phrase in low and ctx not in intake.contexts:
            intake.contexts.append(ctx)
    if re.search(r"\bsurgery\b|\boperation\b", low):
        intake.contexts.append("surgery")

    m = re.search(r"(?:for|about)\s+(\d+)\s*(day|days|week|weeks|month|months)", low)
    if m:
        intake.duration = f"{m.group(1)} {m.group(2)}"
    if re.search(r"\bsevere|unbearable|worst\b", low):
        intake.severity = "severe"
    elif re.search(r"\bmild\b", low):
        intake.severity = "mild"
    elif re.search(r"\bmoderate\b", low):
        intake.severity = "moderate"

    # what is missing, in the order a practitioner would ask
    if intake.age is None:
        intake.missing.append("age")
    if not re.search(r"\b(male|female|man|woman)\b", low):
        intake.missing.append("sex")
    if not intake.contexts:
        intake.missing.append("medications/conditions/pregnancy status")
    if not intake.duration:
        intake.missing.append("duration")
    if not intake.severity:
        intake.missing.append("severity")
    intake.symptom = text.strip()
    return intake


def red_flag_check(text: str, rules: list[dict]) -> list[dict]:
    hits: list[dict] = []
    low = text.lower()
    for rule in rules:
        for pattern in rule["patterns"]:
            if re.search(pattern, low):
                hits.append(
                    {
                        "id": rule["id"],
                        "urgency": rule["urgency"],
                        "action": rule["action"],
                        "citation": rule["citation"],
                        "matched": pattern,
                    }
                )
                break
    hits.sort(key=lambda h: 0 if h["urgency"] == "emergency" else 1)
    return hits


def safety_screen(
    intake: Intake, interventions: list[str], conn: sqlite3.Connection, safety_rules: dict
) -> list[dict]:
    """Deterministic: corpus topic + intervention entity -> veto or flag, with a citation."""
    findings: list[dict] = []
    for ctx in intake.contexts:
        cfg = safety_rules["contexts"].get(ctx)
        if not cfg:
            continue
        rows = conn.execute(
            """
            SELECT c.chunk_id, c.text, c.section, d.doc_id, d.source, d.jurisdiction
            FROM chunks c JOIN docs d ON d.doc_id = c.doc_id
            WHERE c.topics LIKE ? AND c.section IN ('contraindications','cautions','adverse_effects')
            LIMIT 800
            """,
            (f'%"{cfg["topic"]}"%',),
        ).fetchall()
        for iv in interventions:
            key = iv.lower().strip()
            if len(key) < 3:
                continue
            for row in rows:
                if key in row["text"].lower():
                    findings.append(
                        {
                            "context": ctx,
                            "label": cfg.get("label", ctx),
                            "severity": cfg["severity"],
                            "intervention": iv,
                            "chunk_id": row["chunk_id"],
                            "source": row["source"],
                            "jurisdiction": row["jurisdiction"],
                            "excerpt": row["text"][:240],
                        }
                    )
                    break

    for rule in safety_rules.get("overlay", []):
        if rule["context"] not in intake.contexts:
            continue
        for iv in interventions:
            if "*" in rule["applies_to"] or any(a in iv.lower() for a in rule["applies_to"]):
                findings.append(
                    {
                        "context": rule["context"],
                        "label": rule["context"],
                        "severity": rule["severity"],
                        "intervention": iv,
                        "chunk_id": rule["id"],
                        "source": rule["citation"]["source"],
                        "excerpt": rule["reason"],
                    }
                )
    return findings


def vetoed(findings: list[dict]) -> set[str]:
    return {f["intervention"].lower() for f in findings if f["severity"] == "veto"}


SENTINEL = re.compile(r"no evidence found in the corpus", re.I)
EXCLUDED = re.compile(r"excluded by the safety screen", re.I)


def enforce_vetoes(sheet: str, findings: list[dict]) -> tuple[str, list[str]]:
    """Remove vetoed interventions from OPTIONS.

    The safety screen is authoritative code; the generation is advisory prose. If the
    model suggests ginkgo to someone on warfarin while correctly listing the risk, the
    option is removed and replaced with a pointer to the screen, not softened.
    """
    vetoed = {f["intervention"].lower() for f in findings if f["severity"] == "veto"}
    if not vetoed:
        return sheet, []
    out: list[str] = []
    removed: list[str] = []
    in_options = False
    for line in sheet.splitlines():
        if line.strip().upper().startswith("OPTIONS"):
            in_options = True
            out.append(line)
            continue
        if in_options and re.match(r"^[A-Z][A-Z ]{4,}$", line.strip()):
            in_options = False
        if (
            in_options
            and any(v in line.lower() for v in vetoed)
            and re.match(r"^\s*(?:[-*]|\d+[.)])\s", line)
        ):
            removed.append(line.strip())
            continue
        out.append(line)
    if removed:
        # insert the pointer right after the OPTIONS heading block
        for i, line in enumerate(out):
            if line.strip().upper().startswith("OPTIONS"):
                note = "- Excluded by the safety screen (see SAFETY SCREEN): " + ", ".join(
                    sorted({v for v in vetoed})
                )
                out.insert(i + 1, note)
                break
    return "\n".join(out), removed


def contract_check(sheet: str, chunks: list[dict], findings: list[dict]) -> list[str]:
    """Machine-checkable invariants. Any violation means the sheet is not shown."""
    issues: list[str] = []
    upper = sheet.upper()
    for section in REQUIRED_SECTIONS:
        if section not in upper:
            issues.append(f"missing section: {section}")

    options_block = _section(sheet, "OPTIONS")
    if options_block:
        for line in options_block.splitlines():
            text = line.strip()
            if not text or text.startswith("#") or text.upper().startswith("OPTIONS"):
                continue
            if EXCLUDED.search(text):
                continue
            if not re.search(r"\[S\d+\]", text) and not SENTINEL.search(text):
                issues.append(f"uncited option line: {text[:70]}")
        cited = {f"S{n}" for n in re.findall(r"\[S(\d+)\]", options_block)}
        texts = " ".join(c.get("text", "") for c in chunks).lower()
        for m in DOSE_RE.finditer(options_block):
            dose = m.group(0).lower().replace(" ", "")
            if dose not in texts.replace(" ", ""):
                issues.append(f"dose not found in cited evidence: {m.group(0)}")

    for pattern in DIAGNOSIS_PATTERNS:
        if re.search(pattern, sheet, re.I):
            issues.append(f"diagnosis language: {pattern}")

    offered = "\n".join(
        line for line in _section(sheet, "OPTIONS").splitlines() if not EXCLUDED.search(line)
    ).lower()
    for iv in vetoed(findings):
        if iv and iv in offered:
            issues.append(f"vetoed intervention offered: {iv}")
    return issues


def _section(sheet: str, name: str) -> str:
    m = re.search(rf"{name}[^\n]*\n(.*?)(?:\n[A-Z][A-Z ]+[^\n]*\n|$)", sheet, re.S)
    return m.group(1) if m else ""


# --------------------------------------------------------------------- output sheet

SHEET_SPEC = """You are a cited evidence assistant for naturopathic and integrative practitioners.
You produce an evidence sheet. You do not diagnose, and you do not prescribe.

Reply with EXACTLY these six headings, in this order, and nothing else:

WHAT YOU DESCRIBED
one or two lines restating the presentation. No interpretation.

CHECK FIRST
state any red flags supplied under RED FLAGS. If there are none, say: "No red flags identified from what was described. This is not a diagnosis."

OPTIONS
one line per option, formatted as:
- <intervention> — <what the evidence says in one sentence> — <dose exactly as stated in the evidence, or "dose not stated"> [S<n>]
Only use the numbered evidence. If nothing in the evidence supports an option, write "No evidence found in the corpus for this presentation."

SAFETY SCREEN
list each supplied safety finding, or "No safety findings for the stated context."

MONITOR
what to track and when to return.

EVIDENCE GAPS
where sources disagree, where evidence is absent, and what is traditional-use only.

Hard rules: every line in OPTIONS must carry [S<n>]. Never invent a dose or a citation. Never say "you have" a condition.
"""


def evidence_block(chunks: list[dict]) -> str:
    lines = ["EVIDENCE"]
    for i, c in enumerate(chunks, start=1):
        lines.append(
            f"[S{i}] {c['chunk_id']} · {c['source']} · {c['tier']} · {c['jurisdiction']} · "
            f"{c['date']} · section={c['section']}"
        )
        lines.append(c["text"].strip())
        lines.append("")
    return "\n".join(lines)


def build_prompt(
    question: str, chunks: list[dict], findings: list[dict], red_hits: list[dict], intake: "Intake"
) -> str:
    red = (
        "\n".join(f"- {h['id']} ({h['urgency']}): {h['action']}" for h in red_hits)
        if red_hits
        else "none"
    )
    safety = (
        "\n".join(
            f"- {f['intervention']} in {f.get('label', f['context'])}: {f['severity'].upper()} — "
            f"{f['excerpt'][:180]} [{f['source']}]"
            for f in findings
        )
        if findings
        else "none"
    )
    return (
        SHEET_SPEC
        + "\n\nRED FLAGS (from the deterministic gate)\n"
        + red
        + "\n\nSAFETY FINDINGS (deterministic screen; a VETO means the option must not appear)\n"
        + safety
        + "\n\nINTAKE\n"
        + f"age={intake.age}, contexts={intake.contexts}, duration={intake.duration or 'unknown'}, "
        + f"severity={intake.severity or 'unknown'}"
        + "\n\n"
        + evidence_block(chunks)
        + "\nPRESENTATION\n"
        + question
    )


def candidate_interventions(question: str, chunks: list[dict], lex: dict[str, str]) -> list[str]:
    from .retrieve import find_entities

    found = find_entities(question, lex)
    for c in chunks:
        for e in c.get("entities") or []:
            if e and e not in found and len(e) < 60:
                found.append(e)
    return found[:12]
