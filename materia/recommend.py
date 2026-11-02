"""Cited recommendation engine: pattern -> option, with dose, safety and monitoring.

The engine is deterministic. It does not ask a model to choose an intervention. Every
option comes from a rule with a source chunk; every dose is checked against that chunk;
every safety veto is code. The model's job, later, is to explain this object in
conversation.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
import yaml

from . import config
from .clinical import (
    Intake,
    PatternAssessment,
    SEVERITY_RANK,
    assess,
    critical_alerts,
    findings_from_rows,
    match_criterion,
    parse_intake,
)
from .verify import claim_support, dose_supported, extract_doses

RULES_DIR = Path(__file__).resolve().parent / "rules"

TIER_WEIGHT = {"regulatory": 1.0, "primary": 0.9, "compendium": 0.7, "traditional": 0.4}
CONTEXT_LABEL = {
    "pregnancy": "pregnant",
    "breastfeeding": "breastfeeding",
    "anticoagulant": "taking an anticoagulant",
    "antiplatelet": "taking an antiplatelet",
    "iron_overload": "iron overload / haemochromatosis",
    "hypercalcaemia": "high blood calcium",
    "kidney_disease": "kidney disease",
    "kidney_stones": "kidney stones",
    "liver_disease": "liver disease",
    "child": "child under 12",
    "fish_allergy": "fish or shellfish allergy",
    "bleeding_disorder": "bleeding disorder",
    "ragweed_allergy": "ragweed / daisy-family allergy",
    "surgery": "surgery scheduled",
    "thyroid_hormone": "taking thyroid hormone",
    "diabetes": "diabetes",
    "ppi": "taking a proton-pump inhibitor",
    "thiazide": "taking a thiazide diuretic",
    "ssri": "taking an SSRI",
    "immunosuppression": "immunosuppressed",
    "transplant": "transplant recipient",
    "cancer_therapy": "undergoing cancer therapy",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


@dataclass
class Evidence:
    chunk_id: str
    text: str
    source: str
    tier: str
    date: str
    section: str
    title: str
    url: str = ""
    identifier: str = ""

    def as_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id, "text": self.text, "source": self.source,
            "tier": self.tier, "date": self.date, "section": self.section,
            "title": self.title, "url": self.url, "identifier": self.identifier,
        }


@dataclass
class Option:
    id: str
    pattern: str
    intervention: str
    kind: str
    goal: str
    grade: str
    dose_text: str | None
    dose_quote: str
    dose_chunk: str
    dose_note: str
    evidence: list[Evidence]
    monitoring_text: str
    monitoring_chunk: str
    safety_flags: list[str]
    safety_notes: list[Evidence]
    notes: list[Evidence]
    score: float
    score_parts: dict
    status: str = "offered"

    def as_dict(self) -> dict:
        return {
            "id": self.id, "pattern": self.pattern, "intervention": self.intervention,
            "kind": self.kind, "goal": self.goal, "grade": self.grade,
            "dose": ({"text": self.dose_text, "quote": self.dose_quote,
                      "chunk_id": self.dose_chunk, "note": self.dose_note}
                     if self.dose_text else None),
            "evidence": [e.as_dict() for e in self.evidence],
            "monitoring": {"text": self.monitoring_text, "chunk_id": self.monitoring_chunk},
            "safety": {"flags": self.safety_flags,
                       "notes": [e.as_dict() for e in self.safety_notes]},
            "notes": [e.as_dict() for e in self.notes],
            "score": round(self.score, 3), "score_parts": self.score_parts,
            "status": self.status,
        }


@dataclass
class Withheld:
    id: str
    intervention: str
    pattern: str
    reason: str
    detail: str = ""

    def as_dict(self) -> dict:
        return {"id": self.id, "intervention": self.intervention,
                "pattern": self.pattern, "reason": self.reason, "detail": self.detail}


@dataclass
class Assessment:
    intake: Intake
    findings: list
    patterns: list[PatternAssessment]
    options: list[Option]
    withheld: list[Withheld]
    gaps: list[dict] = field(default_factory=list)
    critical_alerts: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "intake": self.intake.as_dict(),
            "findings": [f.as_dict() for f in self.findings],
            "patterns": [p.as_dict() for p in self.patterns],
            "recommendations": [o.as_dict() for o in self.options],
            "withheld": [w.as_dict() for w in self.withheld],
            "gaps": self.gaps,
            "critical_alerts": self.critical_alerts,
            "disclaimer": (
                "Clinical decision support only. Patterns are hypotheses, not diagnoses. "
                "Every option is an evidence-linked suggestion for a qualified practitioner "
                "to accept, modify or reject; this is not a prescription."
            ),
        }


# --------------------------------------------------------------------------- corpus

def rules_fingerprint() -> str:
    """Stable short hash of the rule files, so a label can be tied to an engine version."""
    h = hashlib.sha256()
    for path in sorted(RULES_DIR.glob("*.yaml")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:12]


def open_corpus(path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(path) if path else config.CORPUS_DIR / "index.sqlite"
    if not path.exists():
        raise FileNotFoundError(f"corpus index missing: {path}; run python -m materia.corpus.index")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _chunk(conn: sqlite3.Connection, chunk_id: str) -> Evidence | None:
    row = conn.execute(
        """
        SELECT c.chunk_id, c.text, c.section, d.source, d.tier, d.date, d.title,
               d.url, d.identifier_value
        FROM chunks c JOIN docs d ON d.doc_id = c.doc_id
        WHERE c.chunk_id = ?
        """,
        (chunk_id,),
    ).fetchone()
    if not row:
        return None
    return Evidence(
        chunk_id=row["chunk_id"], text=row["text"], source=row["source"],
        tier=row["tier"], date=row["date"], section=row["section"],
        title=row["title"], url=row["url"] or "", identifier=row["identifier_value"] or "",
    )


# --------------------------------------------------------------------------- rules

def load_recommendations() -> list[dict]:
    return yaml.safe_load((RULES_DIR / "recommendations.yaml").read_text())["recommendations"]


def validate_rule(rule: dict, conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    dose = rule.get("dose") or {}
    dose_chunks = dose.get("chunks") or ([dose["chunk"]] if dose.get("chunk") else [])
    if not dose_chunks:
        if rule.get("kind") not in ("lifestyle", "referral"):
            issues.append("no dose chunk for a supplement/herb option")
    else:
        evs = []
        for cid in dose_chunks:
            ev = _chunk(conn, cid)
            if ev is None:
                issues.append(f"dose chunk missing from corpus: {cid}")
            else:
                evs.append(ev)
        if evs:
            text = " ".join(_norm(ev.text) for ev in evs)
            quote = _norm(dose.get("quote", ""))
            if quote and quote not in text:
                issues.append(f"dose quote not found in {', '.join(dose_chunks)}: {quote!r}")
            for number, unit in extract_doses(dose.get("text", "")):
                if not dose_supported((number, unit), text):
                    issues.append(f"dose {number} {unit} not supported by {', '.join(dose_chunks)}")
    for cid in rule.get("evidence") or []:
        if _chunk(conn, cid) is None:
            issues.append(f"evidence chunk missing: {cid}")
    monitoring = rule.get("monitoring") or {}
    if monitoring.get("chunk") and _chunk(conn, monitoring["chunk"]) is None:
        issues.append(f"monitoring chunk missing: {monitoring['chunk']}")
    for label, items in (("safety note", (rule.get("safety") or {}).get("notes") or []),
                         ("note", rule.get("notes") or [])):
        for item in items:
            cid = item.get("chunk")
            if not cid:
                issues.append(f"{label} has no chunk: {item.get('text', '')[:50]}")
                continue
            ev = _chunk(conn, cid)
            if ev is None:
                issues.append(f"{label} chunk missing: {cid}")
            elif claim_support(item.get("text", ""), ev.text) < 0.2:
                issues.append(f"{label} not supported by {cid}: {item.get('text', '')[:60]}")
    return issues


# --------------------------------------------------------------------------- ranking

def _recency(date: str) -> float:
    m = re.match(r"(\d{4})", date or "")
    if not m:
        return 0.8
    year = int(m.group(1))
    age = 2026 - year
    if age <= 2:
        return 1.0
    if age <= 5:
        return 0.92
    if age <= 10:
        return 0.85
    return 0.75


def _evidence_score(evidence: list[Evidence]) -> tuple[float, dict]:
    if not evidence:
        return 0.0, {"tier": 0.0, "recency": 0.0, "n": 0}
    tier_scores = [TIER_WEIGHT.get(e.tier, 0.5) for e in evidence]
    recency = [_recency(e.date) for e in evidence]
    tier = sum(tier_scores) / len(tier_scores)
    rec = sum(recency) / len(recency)
    return tier * rec, {"tier": round(tier, 3), "recency": round(rec, 3), "n": len(evidence)}


def score_option(pattern: PatternAssessment, evidence: list[Evidence], rank_hint: float = 1.0) -> tuple[float, dict]:
    ev, ev_parts = _evidence_score(evidence)
    severity = SEVERITY_RANK.get(pattern.severity, 2) / 4.0
    score = (0.45 * pattern.confidence + 0.35 * ev + 0.20 * severity) * rank_hint
    return score, {
        "match": round(pattern.confidence, 3),
        "evidence": round(ev, 3),
        "severity": round(severity, 3),
        "rank_hint": rank_hint,
        "evidence_detail": ev_parts,
    }


# --------------------------------------------------------------------------- safety

def _contexts_text(intake: Intake) -> str:
    return ", ".join(CONTEXT_LABEL.get(c, c) for c in sorted(intake.contexts))


def _screen(rule: dict, intake: Intake, findings: list) -> tuple[bool, list[str], str]:
    safety = rule.get("safety") or {}
    contexts = set(intake.contexts)
    veto = [c for c in safety.get("veto_contexts") or [] if c in contexts]
    if veto:
        labels = ", ".join(CONTEXT_LABEL.get(c, c) for c in veto)
        return False, [], f"withheld: {labels}"
    flags = [CONTEXT_LABEL.get(c, c) for c in safety.get("flag_contexts") or [] if c in contexts]
    for item in safety.get("flag_if") or []:
        hit, why = match_criterion(item["when"], findings)
        if hit:
            flags.append(item.get("label") or why)
    for criterion in safety.get("avoid_if") or []:
        hit, why = match_criterion(criterion, findings)
        if hit:
            return False, flags, f"withheld: {why}"
    return True, flags, ""


# --------------------------------------------------------------------------- engine

def recommend(
    rows: list[dict],
    *,
    intake: Intake | dict | None = None,
    conn: sqlite3.Connection | None = None,
) -> Assessment:
    conn = conn or open_corpus()
    if isinstance(intake, dict):
        intake_obj = parse_intake(data=intake)
    elif isinstance(intake, Intake):
        intake_obj = intake
    else:
        intake_obj = parse_intake()

    findings = findings_from_rows(rows, intake_obj)
    alerts = critical_alerts(findings, age=intake_obj.age)
    for alert in alerts:
        ev = _chunk(conn, alert.get("citation") or "")
        if ev is not None:
            alert.update({
                "chunk_id": ev.chunk_id, "source": ev.source, "title": ev.title,
                "text": ev.text, "date": ev.date,
            })
    patterns = assess(findings, intake_obj)
    by_id = {p.id: p for p in patterns}

    options: list[Option] = []
    withheld: list[Withheld] = []
    gaps: list[dict] = []

    for rule in load_recommendations():
        pattern = by_id.get(rule.get("pattern"))
        if pattern is None:
            continue
        if rule.get("when"):
            matched, _ = match_criterion({"all": rule["when"]}, findings)
            if not matched:
                continue
        issues = validate_rule(rule, conn)
        if issues:
            withheld.append(Withheld(
                id=rule["id"], intervention=rule.get("intervention", rule["id"]),
                pattern=rule["pattern"], reason="citation check failed",
                detail="; ".join(issues),
            ))
            continue
        allowed, flags, reason = _screen(rule, intake_obj, findings)
        if not allowed:
            withheld.append(Withheld(
                id=rule["id"], intervention=rule.get("intervention", rule["id"]),
                pattern=rule["pattern"], reason=reason,
            ))
            continue

        evidence = [e for cid in (rule.get("evidence") or []) if (e := _chunk(conn, cid))]
        if not evidence:
            withheld.append(Withheld(
                id=rule["id"], intervention=rule.get("intervention", rule["id"]),
                pattern=rule["pattern"], reason="no evidence chunks resolved",
            ))
            continue
        score, parts = score_option(pattern, evidence, float(rule.get("rank_hint", 1.0)))
        dose = rule.get("dose") or {}
        monitoring = rule.get("monitoring") or {}
        safety_notes = []
        for item in (rule.get("safety") or {}).get("notes") or []:
            if ev := _chunk(conn, item.get("chunk", "")):
                safety_notes.append(ev)
        notes = []
        for item in rule.get("notes") or []:
            if ev := _chunk(conn, item.get("chunk", "")):
                notes.append(ev)

        options.append(Option(
            id=rule["id"], pattern=rule["pattern"],
            intervention=rule.get("intervention", rule["id"]),
            kind=rule.get("kind", "other"), goal=rule.get("goal", ""),
            grade=rule.get("grade", "C"),
            dose_text=dose.get("text") or None, dose_quote=dose.get("quote", ""),
            dose_chunk=", ".join(dose.get("chunks") or ([dose["chunk"]] if dose.get("chunk") else [])),
            dose_note=dose.get("note", ""),
            evidence=evidence,
            monitoring_text=monitoring.get("text", ""),
            monitoring_chunk=monitoring.get("chunk", ""),
            safety_flags=flags, safety_notes=safety_notes, notes=notes,
            score=score, score_parts=parts,
        ))

    if alerts:
        critical_names = ", ".join(f"{a['analyte']} {a['value']:g} {a['unit']}" for a in alerts)
        kept = []
        for o in options:
            if o.kind in ("lifestyle", "referral"):
                kept.append(o)
            else:
                withheld.append(Withheld(
                    id=o.id, intervention=o.intervention, pattern=o.pattern,
                    reason=f"critical value: {critical_names}",
                ))
        options = kept

    options.sort(key=lambda o: o.score, reverse=True)
    offered_patterns = {o.pattern for o in options}
    for p in patterns:
        if p.id not in offered_patterns and not any(w.pattern == p.id for w in withheld):
            gaps.append({
                "pattern": p.id, "label": p.label,
                "reason": "no recommendation rule matched this pattern",
            })

    return Assessment(
        intake=intake_obj, findings=findings, patterns=patterns,
        options=options, withheld=withheld, gaps=gaps, critical_alerts=alerts,
    )


# --------------------------------------------------------------------------- rendering

def render_text(a: Assessment) -> str:
    lines: list[str] = []
    lines.append("MATERIA — clinical assessment")
    facts = []
    if a.intake.age is not None:
        facts.append(f"age {a.intake.age}")
    if a.intake.sex:
        facts.append(a.intake.sex)
    if a.intake.contexts:
        facts.append(_contexts_text(a.intake))
    lines.append("Context: " + (", ".join(facts) if facts else "not supplied"))
    lines.append("")
    if a.critical_alerts:
        lines.append("URGENT — CRITICAL VALUES")
        for alert in a.critical_alerts:
            lines.append(f"  {alert['analyte']} {alert['value']:g} {alert['unit']} "
                         f"({alert['direction']} critical limit {alert['limit']}) — {alert['action']}")
            lines.append(f"    source: {alert['citation']}")
        lines.append("  Supplement and herb options are withheld until these are addressed.")
        lines.append("")

    lines.append("FINDINGS")
    if not a.findings:
        lines.append("  No numeric findings were read.")
    for f in a.findings:
        ref = ""
        if f.ref_low is not None and f.ref_high is not None:
            ref = f" (lab range {f.ref_low:g}–{f.ref_high:g})"
        lines.append(f"  {f.analyte:18s} {f.value:g} {f.unit:10s} {f.direction:6s}{ref}")
    lines.append("")

    lines.append("PATTERNS")
    if not a.patterns:
        lines.append("  No cited pattern matched this panel.")
    for p in a.patterns:
        lines.append(f"  {p.label} — {p.status} ({p.confidence:.0%}), severity {p.severity}")
        for s in p.supporting:
            lines.append(f"    + {s['detail']}" + (f" — {s['note']}" if s.get("note") else ""))
        for s in p.against:
            lines.append(f"    - {s['detail']}" + (f" — {s['note']}" if s.get("note") else ""))
        if p.severity_note:
            lines.append(f"    ! {p.severity_note}")
    lines.append("")

    lines.append("RECOMMENDATIONS")
    if not a.options:
        lines.append("  No option passed the evidence and safety gates for this panel.")
    for i, o in enumerate(a.options, start=1):
        lines.append(f"  {i}. {o.intervention} — grade {o.grade}, score {o.score:.2f}")
        lines.append(f"     For: {o.goal}")
        if o.dose_text:
            lines.append(f"     Dose: {o.dose_text}")
            lines.append(f"     Source: {o.dose_chunk}")
        else:
            lines.append("     No dose — this is a lifestyle or referral step.")
        if o.dose_note:
            lines.append(f"     Note: {o.dose_note}")
        if o.safety_flags:
            lines.append("     Safety flags: " + "; ".join(o.safety_flags))
        if o.monitoring_text:
            lines.append(f"     Monitor: {o.monitoring_text}")
        for n in o.notes:
            lines.append(f"     · {n.text[:260].strip()}")
        lines.append("")

    if a.withheld:
        lines.append("WITHHELD BY THE SAFETY OR CITATION GATE")
        for w in a.withheld:
            lines.append(f"  {w.intervention}: {w.reason}" + (f" ({w.detail})" if w.detail else ""))
        lines.append("")

    if a.gaps:
        lines.append("EVIDENCE GAPS")
        for g in a.gaps:
            lines.append(f"  {g['label']}: {g['reason']}")
        lines.append("")

    lines.append("EVIDENCE")
    seen: set[str] = set()
    for o in a.options:
        for e in o.evidence:
            if e.chunk_id in seen:
                continue
            seen.add(e.chunk_id)
            lines.append(f"  [{e.chunk_id}] {e.source} · {e.tier} · {e.date} · {e.section}")
            lines.append(f"    {e.text[:400].strip()}")
    lines.append("")
    lines.append("Clinical decision support only. Patterns are hypotheses, not diagnoses; "
                 "every option is for a qualified practitioner to accept or reject.")
    return "\n".join(lines)


def load_case(path: str | Path) -> tuple[list[dict], dict]:
    data = json.loads(Path(path).read_text())
    rows = data.get("rows") or data.get("findings") or []
    intake = data.get("intake") or data.get("patient") or {}
    return rows, intake
