"""Deterministic clinical layer: findings -> patterns.

This module is deliberately not a model. It normalises a lab report into canonical
findings, applies cited pattern rules, and returns a hypothesis with its supporting and
conflicting evidence. The recommendation layer consumes the pattern; the model only
explains it.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RULES_DIR = Path(__file__).resolve().parent / "rules"

# Severity order used for sorting and for the "most important first" output.
SEVERITY_RANK = {"critical": 4, "high": 3, "moderate": 2, "low": 1, "unknown": 0}


# --------------------------------------------------------------------------- intake

MED_CONTEXTS = {
    "warfarin": "anticoagulant",
    "apixaban": "anticoagulant",
    "rivaroxaban": "anticoagulant",
    "dabigatran": "anticoagulant",
    "edoxaban": "anticoagulant",
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
    "omeprazole": "ppi",
    "esomeprazole": "ppi",
    "lansoprazole": "ppi",
    "pantoprazole": "ppi",
    "hydrochlorothiazide": "thiazide",
    "hctz": "thiazide",
    "chlorthalidone": "thiazide",
    "indapamide": "thiazide",
}

CONDITION_CONTEXTS = {
    "hemochromatosis": "iron_overload",
    "haemochromatosis": "iron_overload",
    "iron overload": "iron_overload",
    "hypercalcemia": "hypercalcaemia",
    "hypercalcaemia": "hypercalcaemia",
    "high calcium": "hypercalcaemia",
    "kidney stone": "kidney_stones",
    "renal stone": "kidney_stones",
    "nephrolithiasis": "kidney_stones",
    "fish allergy": "fish_allergy",
    "shellfish allergy": "fish_allergy",
    "bleeding disorder": "bleeding_disorder",
    "ragweed": "ragweed_allergy",
    "chrysanthemum": "ragweed_allergy",
    "daisy allergy": "ragweed_allergy",
    "diabetes": "diabetes",
    "liver disease": "liver_disease",
    "fatty liver": "liver_disease",
    "hepatitis": "liver_disease",
    "kidney disease": "kidney_disease",
    "renal impairment": "kidney_disease",
    "epilepsy": "antiepileptic",
    "hypothyroid": "thyroid_hormone",
    "transplant": "transplant",
    "cancer": "cancer_therapy",
    "chemotherapy": "cancer_therapy",
}


@dataclass
class Intake:
    age: int | None = None
    sex: str | None = None
    contexts: set[str] = field(default_factory=set)
    medications: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    symptoms: list[str] = field(default_factory=list)
    raw: str = ""
    missing: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "age": self.age,
            "sex": self.sex,
            "contexts": sorted(self.contexts),
            "medications": self.medications,
            "conditions": self.conditions,
            "symptoms": self.symptoms,
            "missing": self.missing,
        }


def _add_contexts(text: str, intake: Intake) -> None:
    low = text.lower()
    for word, ctx in MED_CONTEXTS.items():
        if re.search(rf"\b{re.escape(word)}\b", low):
            intake.contexts.add(ctx)
    for phrase, ctx in CONDITION_CONTEXTS.items():
        if phrase in low:
            intake.contexts.add(ctx)
    if re.search(r"\bpregnan|\bexpecting\b", low):
        intake.contexts.add("pregnancy")
    if re.search(r"breastfeed|breast-feed|nursing|lactat", low):
        intake.contexts.add("breastfeeding")
    if re.search(r"\bsurgery\b|\boperation\b", low):
        intake.contexts.add("surgery")


def parse_intake(*, text: str = "", data: dict | None = None) -> Intake:
    """Structured intake first, free text second. Never invents a field."""
    data = data or {}
    intake = Intake(
        age=data.get("age"),
        sex=(data.get("sex") or "").lower() or None,
        raw=text or "",
    )
    if intake.age is not None:
        try:
            intake.age = int(intake.age)
        except (TypeError, ValueError):
            intake.age = None
    for key in ("medications", "conditions", "symptoms"):
        value = data.get(key) or []
        if isinstance(value, str):
            value = [value]
        setattr(intake, key, [str(v).strip() for v in value if str(v).strip()])
    for ctx in data.get("contexts") or []:
        intake.contexts.add(str(ctx).strip().lower())

    blob = " ".join([
        text or "",
        " ".join(intake.medications),
        " ".join(intake.conditions),
        " ".join(intake.symptoms),
        str(data.get("notes") or ""),
    ])
    _add_contexts(blob, intake)
    if intake.age is not None and intake.age < 12:
        intake.contexts.add("child")

    if intake.age is None:
        intake.missing.append("age")
    if not intake.sex:
        intake.missing.append("sex")
    if not intake.contexts:
        intake.missing.append("medications/conditions/pregnancy status")
    return intake


# --------------------------------------------------------------------------- catalog

@dataclass
class Analyte:
    id: str
    name: str
    aliases: list[str]
    unit: str
    units: dict[str, float]
    ref: dict[str, list[float]]
    ref_source: str = ""
    critical: dict[str, float] = field(default_factory=dict)


_CATALOG: list[Analyte] | None = None
_ALIASES: dict[str, Analyte] | None = None


def load_catalog() -> list[Analyte]:
    global _CATALOG, _ALIASES
    if _CATALOG is not None:
        return _CATALOG
    raw = yaml.safe_load((RULES_DIR / "analytes.yaml").read_text())
    catalog: list[Analyte] = []
    aliases: dict[str, Analyte] = {}
    for item in raw:
        a = Analyte(
            id=item["id"], name=item["name"], aliases=item.get("aliases") or [],
            unit=item["unit"], units={str(k): float(v) for k, v in (item.get("units") or {}).items()},
            ref={str(k): [float(x) for x in v] for k, v in (item.get("ref") or {}).items()},
            ref_source=item.get("ref_source") or "",
            critical={str(k): float(v) for k, v in (item.get("critical") or {}).items()},
        )
        catalog.append(a)
        for alias in {a.id, a.name.lower(), *(x.lower() for x in a.aliases)}:
            aliases[alias] = a
    _CATALOG, _ALIASES = catalog, aliases
    return catalog


def _aliases() -> dict[str, Analyte]:
    load_catalog()
    assert _ALIASES is not None
    return _ALIASES


def canonicalize(name: str) -> Analyte | None:
    key = re.sub(r"\s+", " ", (name or "").strip().lower())
    key = key.replace("µ", "u").replace("μ", "u")
    aliases = _aliases()
    if key in aliases:
        return aliases[key]
    # Try without a parenthetical suffix and without a trailing colon.
    key2 = re.sub(r"\s*\([^)]*\)", "", key).strip(" :")
    if key2 in aliases:
        return aliases[key2]
    return None


def convert(value: float, from_unit: str, to_unit: str, analyte: Analyte | None) -> float | None:
    if analyte is None:
        return value
    src = (from_unit or "").strip()
    dst = (to_unit or "").strip()
    if not src or not dst or src == dst:
        return value
    factors = analyte.units
    if src not in factors or dst not in factors:
        return None
    # factors are relative to the canonical unit; convert through it
    return value * factors[src] / factors[dst]


# --------------------------------------------------------------------------- findings

@dataclass
class Finding:
    analyte: str
    canonical: str
    value: float | None
    unit: str
    ref_low: float | None
    ref_high: float | None
    direction: str
    severity: str
    page: int | None = None
    raw: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "analyte": self.analyte,
            "canonical": self.canonical,
            "value": self.value,
            "unit": self.unit,
            "ref_low": self.ref_low,
            "ref_high": self.ref_high,
            "direction": self.direction,
            "severity": self.severity,
            "page": self.page,
        }


def _ref_for(analyte: Analyte, sex: str | None) -> tuple[float | None, float | None]:
    key = "female" if (sex or "").lower().startswith("f") else "male" if sex else "female"
    ref = analyte.ref.get(key) or analyte.ref.get("female") or analyte.ref.get("male")
    if not ref:
        return None, None
    return float(ref[0]), float(ref[1])


def make_finding(row: dict, intake: Intake | None = None) -> Finding | None:
    """One report row -> canonical Finding, or None when there is no usable number."""
    name = str(row.get("analyte") or row.get("name") or "").strip()
    if not name:
        return None
    value = row.get("value")
    if value is None:
        value_text = str(row.get("value_text") or "").strip()
        m = re.fullmatch(r"([<>])\s*(\d+(?:\.\d+)?)", value_text)
        if not m:
            return None
        # Keep the bound as the value and mark the direction: a limit is still a finding.
        value = float(m.group(2))
        if m.group(1) == "<":
            row = {**row, "flag": row.get("flag") or "L"}
        else:
            row = {**row, "flag": row.get("flag") or "H"}
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    analyte = canonicalize(name)
    canonical = analyte.id if analyte else re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    unit = str(row.get("unit") or "").strip()
    ref_low = row.get("ref_low")
    ref_high = row.get("ref_high")
    if analyte:
        if not unit:
            unit = analyte.unit
        if ref_low is None and ref_high is None:
            ref_low, ref_high = _ref_for(analyte, intake.sex if intake else None)
        # Put value and interval in the canonical unit. If the printed unit is not in
        # the catalog, keep the printed value and unit rather than relabelling it.
        cv = convert(value, unit, analyte.unit, analyte)
        if cv is not None:
            value = cv
            if ref_low is not None:
                converted = convert(float(ref_low), unit, analyte.unit, analyte)
                if converted is not None:
                    ref_low = converted
            if ref_high is not None:
                converted = convert(float(ref_high), unit, analyte.unit, analyte)
                if converted is not None:
                    ref_high = converted
            unit = analyte.unit

    lab_flag = str(row.get("flag") or "").strip().upper()
    if lab_flag in ("L", "H"):
        direction = "low" if lab_flag == "L" else "high"
    elif ref_low is not None and value < ref_low:
        direction = "low"
    elif ref_high is not None and value > ref_high:
        direction = "high"
    else:
        direction = "normal"

    severity = "low"
    if direction != "normal":
        severity = "moderate"
    if analyte and analyte.critical:
        if analyte.critical.get("low") is not None and value <= analyte.critical["low"]:
            severity = "critical"
        if analyte.critical.get("high") is not None and value >= analyte.critical["high"]:
            severity = "critical"
    return Finding(
        analyte=name, canonical=canonical, value=value, unit=unit,
        ref_low=ref_low, ref_high=ref_high, direction=direction, severity=severity,
        page=row.get("page"), raw=dict(row),
    )


def findings_from_rows(rows: list[dict], intake: Intake | None = None) -> list[Finding]:
    out = []
    for row in rows:
        f = make_finding(row, intake)
        if f is not None:
            out.append(f)
    return out


# --------------------------------------------------------------------------- patterns

@dataclass
class PatternAssessment:
    id: str
    label: str
    category: str
    severity: str
    confidence: float
    status: str
    matched: list[dict]
    supporting: list[dict]
    against: list[dict]
    confirm: list[str]
    citations: list[str]
    severity_note: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label, "category": self.category,
            "severity": self.severity, "confidence": round(self.confidence, 3),
            "status": self.status, "matched": self.matched,
            "supporting": self.supporting, "against": self.against,
            "confirm": self.confirm, "citations": self.citations,
            "severity_note": self.severity_note,
        }


def _finding_map(findings: list[Finding]) -> dict[str, Finding]:
    out: dict[str, Finding] = {}
    for f in findings:
        # Keep the most abnormal finding for an analyte if the report repeats it.
        prev = out.get(f.canonical)
        if prev is None or SEVERITY_RANK.get(f.severity, 0) > SEVERITY_RANK.get(prev.severity, 0):
            out[f.canonical] = f
    return out


def _threshold_in_unit(criterion: dict, f: Finding) -> float | None:
    value = criterion.get("value")
    if value is None:
        return None
    unit = criterion.get("unit")
    analyte = canonicalize(f.analyte)
    if unit and unit != f.unit and analyte:
        return convert(float(value), unit, f.unit, analyte)
    return float(value)


def _match_criterion(criterion: dict, index: dict[str, Finding]) -> tuple[bool, str]:
    if not isinstance(criterion, dict):
        return False, "malformed criterion"
    if "all" in criterion or "any" in criterion or "not" in criterion:
        return _match_node(criterion, index)
    analyte_id = criterion.get("analyte")
    if not analyte_id:
        return False, "criterion has no analyte"
    f = index.get(analyte_id)
    if f is None:
        return False, f"{analyte_id} not on this report"
    if criterion.get("present") is False:
        return True, f"{analyte_id} absent"
    if f.value is None:
        return False, f"{analyte_id} has no numeric value"
    if "ref" in criterion:
        ref = criterion["ref"]
        if ref == "low":
            ok = f.ref_low is not None and f.value < f.ref_low
        elif ref == "high":
            ok = f.ref_high is not None and f.value > f.ref_high
        elif ref == "normal":
            ok = (f.ref_low is None or f.value >= f.ref_low) and (f.ref_high is None or f.value <= f.ref_high)
        else:
            return False, f"unknown ref {ref!r}"
        return ok, f"{analyte_id} {'below' if ref == 'low' else 'above' if ref == 'high' else 'within'} range"
    if "op" in criterion:
        threshold = _threshold_in_unit(criterion, f)
        if threshold is None:
            return False, f"{analyte_id}: cannot convert threshold to {f.unit}"
        op = criterion["op"]
        ops = {
            "<": f.value < threshold, "<=": f.value <= threshold,
            ">": f.value > threshold, ">=": f.value >= threshold,
            "==": abs(f.value - threshold) < 1e-9,
        }
        if op not in ops:
            return False, f"unknown op {op!r}"
        return ops[op], f"{analyte_id} {f.value:g} {f.unit} {op} {threshold:g} {f.unit}"
    # No operator and no ref: treat as presence.
    return True, f"{analyte_id} present"


def _match_node(node: Any, index: dict[str, Finding]) -> tuple[bool, str]:
    if isinstance(node, list):
        results = [_match_criterion(c, index) for c in node]
        ok = all(r[0] for r in results)
        return ok, "; ".join(r[1] for r in results)
    if not isinstance(node, dict):
        return False, "malformed rule"
    if "all" in node:
        results = [_match_criterion(c, index) for c in node["all"]]
        return all(r[0] for r in results), "; ".join(r[1] for r in results)
    if "any" in node:
        results = [_match_criterion(c, index) for c in node["any"]]
        if any(r[0] for r in results):
            return True, next(r[1] for r in results if r[0])
        return False, "; ".join(r[1] for r in results)
    if "not" in node:
        ok, reason = _match_criterion(node["not"], index)
        return (not ok), f"not ({reason})"
    return _match_criterion(node, index)


def load_patterns() -> list[dict]:
    return yaml.safe_load((RULES_DIR / "clinical_patterns.yaml").read_text())["patterns"]


def assess(findings: list[Finding], intake: Intake | None = None) -> list[PatternAssessment]:
    index = _finding_map(findings)
    results: list[PatternAssessment] = []
    for rule in load_patterns():
        ok, reason = _match_node(rule["when"], index)
        if not ok:
            continue
        confidence = float(rule.get("base_confidence", 0.6))
        matched = [{"criterion": rule["when"], "detail": reason}]
        supporting: list[dict] = []
        against: list[dict] = []
        for item in rule.get("supporting") or []:
            hit, why = _match_criterion(item["when"], index)
            if hit:
                confidence += float(item.get("weight", 0.0))
                supporting.append({"detail": why, "note": item.get("note", ""),
                                   "weight": item.get("weight", 0.0)})
        for item in rule.get("against") or []:
            hit, why = _match_criterion(item["when"], index)
            if hit:
                confidence -= float(item.get("weight", 0.0))
                against.append({"detail": why, "note": item.get("note", ""),
                                "weight": item.get("weight", 0.0)})
        confidence = max(0.05, min(0.95, confidence))

        severity = rule.get("severity", "moderate")
        severity_note = ""
        for override in rule.get("severity_rules") or []:
            hit, why = _match_criterion(override["when"], index)
            if hit:
                severity = override["severity"]
                severity_note = override.get("note", why)
                break

        status = "likely" if confidence >= 0.75 else "possible"
        results.append(PatternAssessment(
            id=rule["id"], label=rule["label"], category=rule.get("category", "other"),
            severity=severity, confidence=confidence, status=status,
            matched=matched, supporting=supporting, against=against,
            confirm=list(rule.get("confirm") or []), citations=list(rule.get("citations") or []),
            severity_note=severity_note,
        ))
    results.sort(key=lambda p: (SEVERITY_RANK.get(p.severity, 0), p.confidence), reverse=True)
    return results


_CRITICAL: list[dict] | None = None


def load_critical_values() -> list[dict]:
    global _CRITICAL
    if _CRITICAL is None:
        raw = yaml.safe_load((RULES_DIR / "critical_values.yaml").read_text())
        _CRITICAL = raw.get("values") or []
    return _CRITICAL


def critical_alerts(findings: list[Finding], *, age: int | None = None) -> list[dict]:
    """Values outside the cited critical limits, with the action and source.

    Newborn limits are used when age < 1; otherwise the adult limits. The lab's own
    critical-value policy still wins.
    """
    index = _finding_map(findings)
    alerts: list[dict] = []
    newborn = age is not None and age < 1
    child = age is not None and 1 <= age < 12
    for rule in load_critical_values():
        f = index.get(rule["analyte"])
        if f is None or f.value is None:
            continue
        limits = rule.get("newborn") or {} if newborn else {}
        low = limits.get("low", rule.get("low"))
        high = limits.get("high", rule.get("high"))
        direction = None
        if low is not None and f.value <= float(low):
            direction = "low"
        elif high is not None and f.value >= float(high):
            direction = "high"
        if direction is None:
            continue
        citation = rule.get("newborn_citation") if newborn and rule.get("newborn_citation") else rule.get("citation", "")
        alerts.append({
            "analyte": f.analyte, "canonical": f.canonical, "value": f.value,
            "unit": f.unit, "direction": direction,
            "limit": low if direction == "low" else high,
            "age_group": "newborn" if newborn else "child" if child else "adult",
            "age_note": ("Adult critical limits used; the lab's paediatric policy wins."
                         if child else ""),
            "action": rule.get("action", "Urgent clinical assessment."),
            "citation": citation,
        })
    return alerts


def summarise(findings: list[Finding]) -> dict:
    return {
        "findings": [f.as_dict() for f in findings],
        "abnormal": [f.as_dict() for f in findings if f.direction != "normal"],
        "missing": [f.analyte for f in findings if f.value is None],
    }


def load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def match_criterion(criterion: dict, findings: list[Finding]) -> tuple[bool, str]:
    """Public wrapper used by the recommendation safety layer."""
    return _match_criterion(criterion, _finding_map(findings))
