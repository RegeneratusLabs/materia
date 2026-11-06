"""Grounded conversational layer over an assessment.

The assessment is the source of truth. With a local OpenAI-compatible model configured, the
model explains it; without one, a deterministic responder answers from the same object. In
both cases the answer may not add an option, a dose, or a diagnosis that is not in the
assessment.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from . import config
from .verify import dose_supported, extract_doses

PATTERN_COVERAGE = (
    "iron, vitamin B12, folate, vitamin D, liver enzymes and triglycerides"
)


def _options(assessment: dict) -> list[dict]:
    return assessment.get("recommendations") or []


def _patterns(assessment: dict) -> list[dict]:
    return assessment.get("patterns") or []


def _urgent_note(patterns: list[dict]) -> str:
    urgent = [p.get("label") for p in patterns if p.get("severity") in ("high", "critical")]
    if not urgent:
        return ""
    return "Needs prompt clinical attention: " + ", ".join(urgent) + ". "


def _evidence_ids(assessment: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for o in _options(assessment):
        for e in o.get("evidence") or []:
            out[e.get("chunk_id", "")] = e.get("text", "")
        for e in (o.get("safety") or {}).get("notes") or []:
            out[e.get("chunk_id", "")] = e.get("text", "")
        for e in o.get("notes") or []:
            out[e.get("chunk_id", "")] = e.get("text", "")
    for p in _patterns(assessment):
        for cid in p.get("citations") or []:
            out.setdefault(cid, "")
    for alert in assessment.get("critical_alerts") or []:
        cid = alert.get("citation")
        if cid:
            # The alert text lives in the critical-values table; the citation resolves
            # to the corresponding chunk, so a model can cite it.
            out.setdefault(cid, "")
    return {k: v for k, v in out.items() if k}


def _option_by_name(question: str, options: list[dict]) -> dict | None:
    low = question.lower()
    for o in options:
        name = (o.get("intervention") or "").lower()
        if not name:
            continue
        tokens = [t for t in re.split(r"\W+", name) if len(t) > 3]
        if name in low or (tokens and all(t in low for t in tokens)):
            return o
    return None


def _cite(ids: list[str]) -> str:
    seen = [i for i in dict.fromkeys(ids) if i]
    return " [" + ", ".join(seen) + "]" if seen else ""


def _fallback(question: str, assessment: dict) -> dict:
    low = question.lower()
    options = _options(assessment)
    patterns = _patterns(assessment)
    gaps = assessment.get("gaps") or []
    withheld = assessment.get("withheld") or []

    alerts = assessment.get("critical_alerts") or []
    if alerts:
        text = "Critical values need attention first: " + "; ".join(
            f"{a['analyte']} {a['value']:g} {a['unit']} — {a['action']}" for a in alerts
        ) + " Supplement and herb options are withheld until these are addressed."
        return {"answer": text, "citations": [a.get("citation") for a in alerts if a.get("citation")],
                "mode": "assessment", "grounded": True}

    if not options and not patterns:
        text = (
            "This panel did not match a cited pattern. The engine's current patterns cover "
            f"{PATTERN_COVERAGE}. No supplement or herb option is offered without a matched pattern "
            "and a resolvable source. That is a coverage gap, not a clean result."
        )
        return {"answer": text, "citations": [], "mode": "assessment", "grounded": True}

    target = _option_by_name(question, options)
    if target:
        flags = (target.get("safety") or {}).get("flags") or []
        dose = (target.get("dose") or {}).get("text")
        text = (
            f"{target['intervention']} (grade {target['grade']}). "
            + (f"Dose: {dose}. " if dose else "No dose — this is a lifestyle or referral step. ")
            + f"Why: {target.get('goal', '')} "
            + f"Monitor: {target.get('monitoring', {}).get('text', '')}"
        )
        if flags:
            text += f" Safety flags: {', '.join(flags)}."
        ids = [e.get("chunk_id", "") for e in target.get("evidence") or []]
        return {"answer": text.strip(), "citations": ids, "mode": "assessment", "grounded": True}

    if any(k in low for k in ("dose", "how much", "dosage", "mg", "iu", "µg")):
        dosed = [o for o in options if (o.get("dose") or {}).get("text")]
        withheld = assessment.get("withheld") or []
        if not dosed and withheld:
            text = "No dosed option was offered. " + " ".join(
                f"{w['intervention']}: {w['reason']}." for w in withheld
            )
        elif not dosed:
            text = "No dosed option passed the evidence and safety gates. The assessment may contain lifestyle or referral steps."
        else:
            text = "Doses in this assessment: " + "; ".join(
                f"{o['intervention']} — {o['dose']['text']} ({o['dose']['chunk_id']})" for o in dosed
            ) + "."
        ids = [o["dose"]["chunk_id"] for o in dosed] + list(_evidence_ids(assessment))
        return {"answer": text, "citations": list(dict.fromkeys(ids)), "mode": "assessment", "grounded": True}

    medications = [str(m).lower() for m in (assessment.get("intake") or {}).get("medications") or []]
    medication_asked = any(m and m in low for m in medications)
    if medication_asked or any(k in low for k in (
        "safe", "risk", "interact", "pregnan", "breastfeed", "warfarin", "anticoag",
        "withheld", "why not", "not offered",
    )):
        lines = []
        for o in options:
            flags = (o.get("safety") or {}).get("flags") or []
            if flags:
                notes = " ".join(
                    str(n.get("text", ""))[:220] for n in (o.get("safety") or {}).get("notes") or []
                ).strip()
                lines.append(f"{o['intervention']}: {', '.join(flags)}." + (f" {notes}" if notes else ""))
        for w in withheld:
            lines.append(f"{w['intervention']} is withheld — {w['reason']}.")
        contexts = {str(c).lower() for c in (assessment.get("intake") or {}).get("contexts") or []}
        asked = {"pregnancy": "pregnan", "breastfeeding": "breastfeed", "anticoagulant": "anticoag"}
        missing = [label for label, token in asked.items() if token in low and label not in contexts]
        if missing:
            lines.append("The intake did not record " + ", ".join(missing) +
                         ", so that screen was not applied. Add it and rebuild the assessment before relying on this answer.")
        if not lines:
            lines.append("No safety flag or veto applied to this assessment. That is not a guarantee; "
                         "the intake fields drive the screen.")
        return {"answer": " ".join(lines), "citations": list(_evidence_ids(assessment)),
                "mode": "assessment", "grounded": True}

    if any(k in low for k in ("rank", "score", "first", "why this", "why is this")):
        if not options:
            text = "No option is ranked because none passed the gates."
        else:
            text = "Ranking: " + "; ".join(
                f"{o['intervention']} {o.get('score', 0):.2f} "
                f"(match {round((o.get('score_parts') or {}).get('match', 0) * 100)}%, "
                f"evidence {round((o.get('score_parts') or {}).get('evidence', 0) * 100)}%, "
                f"severity {round((o.get('score_parts') or {}).get('severity', 0) * 100)}%, "
                f"rank ×{(o.get('score_parts') or {}).get('rank_hint', 1)})"
                for o in options
            ) + "."
        return {"answer": text, "citations": list(_evidence_ids(assessment)),
                "mode": "assessment", "grounded": True}

    if any(k in low for k in ("why", "evidence", "source", "cite", "support")):
        parts = []
        for o in options:
            sources = "; ".join(
                f"{e.get('chunk_id', '')} ({e.get('title', '')[:70]})"
                for e in (o.get("evidence") or [])[:3]
            )
            parts.append(f"{o['intervention']} is supported by {sources}.")
        if not parts:
            parts.append("No option is offered, so there is no supporting source to show.")
        return {"answer": " ".join(parts), "citations": [i for i in _evidence_ids(assessment)], "mode": "assessment", "grounded": True}

    if any(k in low for k in ("confirm", "test", "check", "diagnos")):
        lines = []
        for p in patterns:
            if p.get("confirm"):
                lines.append(f"{p['label']}: " + " ".join(p["confirm"]))
        if not lines:
            lines.append("No pattern matched, so there is no confirmatory step to list.")
        return {"answer": " ".join(lines), "citations": [c for p in patterns for c in p.get("citations") or []], "mode": "assessment", "grounded": True}

    if any(k in low for k in ("monitor", "follow", "repeat", "retest")):
        lines = [f"{o['intervention']}: {o['monitoring']['text']}" for o in options if o.get("monitoring")]
        if not lines:
            lines.append("No option is offered, so there is no monitoring plan to show.")
        return {"answer": " ".join(lines), "citations": [o["monitoring"]["chunk_id"] for o in options if o.get("monitoring")], "mode": "assessment", "grounded": True}

    if any(k in low for k in ("tell me more", "explain", "details", "summary", "more about")):
        lines = []
        for o in options:
            dose = (o.get("dose") or {}).get("text") or "no dose (lifestyle/referral)"
            flags = ", ".join((o.get("safety") or {}).get("flags") or []) or "no safety flags"
            monitor = (o.get("monitoring") or {}).get("text") or "no monitoring text"
            evidence = ", ".join(e.get("chunk_id", "") for e in (o.get("evidence") or [])[:3])
            lines.append(f"{o['intervention']}. Goal: {o.get('goal')}. Dose: {dose}. Flags: {flags}. Monitor: {monitor}. Evidence: {evidence}.")
        for w in assessment.get("withheld") or []:
            lines.append(f"{w['intervention']} was withheld: {w['reason']}.")
        if not lines:
            lines.append("No option is offered, so there is no further detail to show.")
        return {"answer": " ".join(lines), "citations": list(_evidence_ids(assessment)), "mode": "assessment", "grounded": True}

    # Default: a short, honest summary.
    pat = "; ".join(f"{p['label']} ({p['status']}, {round(p['confidence'] * 100)}%)" for p in patterns) or "none"
    opt = "; ".join(
        f"{o['intervention']} — {(o.get('dose') or {}).get('text') or 'no dose, lifestyle/referral'}"
        for o in options
    ) or "none passed the gates"
    gap = "; ".join(g["label"] for g in gaps) if gaps else "none stated"
    withheld = assessment.get("withheld") or []
    withheld_text = " Withheld: " + "; ".join(
        f"{w.get('intervention')} ({w.get('reason')})" for w in withheld
    ) + "." if withheld else ""
    text = _urgent_note(patterns) + f"Patterns: {pat}. Options: {opt}.{withheld_text} Gaps: {gap}."
    return {"answer": text, "citations": list(_evidence_ids(assessment)), "mode": "assessment", "grounded": True}


# --------------------------------------------------------------------------- model

def _model_messages(question: str, assessment: dict, history: list[dict] | None = None) -> list[dict]:
    # Keep the context small enough for a 2B model with a 2048-token window. The full
    # assessment object is for the deterministic responder and the UI; the model only
    # needs the decision, the dose, the safety flags and the citation ids.
    compact = {
        "intake": assessment.get("intake"),
        "patterns": [
            {
                "label": p.get("label"), "status": p.get("status"),
                "confidence": p.get("confidence"), "severity": p.get("severity"),
                "supporting": [s.get("detail") for s in p.get("supporting") or []],
            }
            for p in assessment.get("patterns") or []
        ],
        "recommendations": [
            {
                "id": o.get("id"), "intervention": o.get("intervention"),
                "kind": o.get("kind"), "grade": o.get("grade"), "goal": o.get("goal"),
                "dose": (o.get("dose") or {}).get("text"),
                "monitoring": (o.get("monitoring") or {}).get("text"),
                "safety_flags": (o.get("safety") or {}).get("flags") or [],
                "evidence_ids": [e.get("chunk_id") for e in o.get("evidence") or []],
                "score": o.get("score"),
                "score_parts": o.get("score_parts"),
            }
            for o in assessment.get("recommendations") or []
        ],
        "withheld": assessment.get("withheld"),
        "gaps": assessment.get("gaps"),
        "critical_alerts": assessment.get("critical_alerts"),
    }
    system = (
        "You are materia's clinical explainer. Answer ONLY from the ASSESSMENT below. "
        "Do not add an intervention, a dose, a diagnosis, or a claim that is not in it. "
        "If the assessment does not cover the question, say so plainly. "
        "Every factual sentence must end with a chunk id from evidence_ids in square brackets, "
        "for example [pmc-pmc13449291#030]. Do not cite field names like [patterns] or "
        "[recommendations]. Keep the answer under 120 words."
    )
    messages = [{"role": "system", "content": system}]
    # A short, bounded history so a follow-up ("and the dose?") is actually conversational.
    # The assessment is still the source of truth; history is only prior wording.
    for item in (history or [])[-4:]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()[:240]
        if not text:
            continue
        role = "assistant" if (item or {}).get("role") == "bot" else "user"
        messages.append({"role": role, "content": text})
    messages.append(
        {"role": "user", "content": "ASSESSMENT:\n" + json.dumps(compact, ensure_ascii=False)[:12000]
         + "\n\nQUESTION: " + question}
    )
    return messages


def _call_model(messages: list[dict], *, timeout: float | None = None) -> str | None:
    timeout = timeout if timeout is not None else config.CHAT_TIMEOUT
    base = (config.CHAT_BASE_URL or "").rstrip("/")
    if not base:
        return None
    model = config.CHAT_MODEL or "local"
    key = config.CHAT_API_KEY or ""
    body = {
        "model": model, "messages": messages, "temperature": 0.0, "max_tokens": 300,
        # llama.cpp/llama-server and recent vLLM accept this; without it the 2B spends
        # the whole budget in reasoning and returns an empty content field.
        "chat_template_kwargs": {"enable_thinking": False},
    }
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
        return None
    try:
        return (data["choices"][0]["message"].get("content") or "").strip()
    except (KeyError, IndexError, TypeError):
        return None


def _grounded(answer: str, assessment: dict, question: str = "") -> tuple[bool, str]:
    """Reject a model answer that introduces a dose not in the cited evidence."""
    low = (question or "").lower()
    if any(k in low for k in ("dose", "dosage", "how much", "how many mg")) and not extract_doses(answer):
        return False, "dose question without a dose in the answer"
    evidence = _evidence_ids(assessment)
    for number, unit in extract_doses(answer):
        if not any(dose_supported((number, unit), text) for text in evidence.values()):
            return False, f"dose {number} {unit} is not in the assessment's evidence"
    cited = re.findall(r"\[([a-z0-9._-]+#[0-9]{3})\]", answer, re.I)
    if not cited:
        return False, "no chunk citation in the model answer"
    unknown = [c for c in cited if c not in evidence]
    if unknown:
        return False, f"citation not in the assessment: {unknown[0]}"
    return True, ""


def _prepend_critical(result: dict, assessment: dict) -> dict:
    alerts = assessment.get("critical_alerts") or []
    if not alerts or "critical values need attention" in result.get("answer", "").lower():
        return result
    note = "Critical values need attention first: " + "; ".join(
        f"{a['analyte']} {a['value']:g} {a['unit']} — {a['action']}" for a in alerts
    ) + " "
    result["answer"] = note + result.get("answer", "")
    result["citations"] = list(dict.fromkeys(
        [a.get("citation") for a in alerts if a.get("citation")] + (result.get("citations") or [])
    ))
    return result


def answer(question: str, assessment: dict, *, use_model: bool = True,
           history: list[dict] | None = None) -> dict:
    question = (question or "").strip()
    if not question:
        return _prepend_critical(
            {"answer": "Ask a question about the assessment.", "citations": [],
             "mode": "assessment", "grounded": True},
            assessment,
        )
    if use_model:
        text = _call_model(_model_messages(question, assessment, history))
        if text:
            ok, reason = _grounded(text, assessment, question)
            if ok:
                return _prepend_critical(
                    {"answer": text, "citations": list(_evidence_ids(assessment)),
                     "mode": "model", "grounded": True},
                    assessment,
                )
            fallback = _fallback(question, assessment)
            fallback["mode"] = "rejected-model"
            fallback["reason"] = reason
            return _prepend_critical(fallback, assessment)
    return _prepend_critical(_fallback(question, assessment), assessment)
