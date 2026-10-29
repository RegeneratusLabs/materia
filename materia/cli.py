"""materia command line.

    materia status
    materia corpus --stats
    materia ocr samples/pages/nutripath-p2.png
    materia ingest samples/pages/nutripath-p2.png --truth samples/ground_truth/nutripath-p2.json
    materia ask "Is St John's wort safe with warfarin?"
    materia symptom "68 year old on warfarin, can I take ginkgo for memory?"

Everything it prints is traceable: no answer without a chunk id, no number without its
citation, and a review flag wherever a deterministic check failed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import calc, config, extract, llm, ocr, parse, symptom, verify
from .attribute import attribute as attribute_answer
from .corpus.index import open_index, stats as corpus_stats
from .prompt import build_freeform, build_prompt_hint
from .retrieve import Retriever, grounded_chunks, group_conflicts


def _retriever(index: str | None = None) -> Retriever:
    path = Path(index or config.CORPUS_DIR / "index.sqlite")
    if not path.exists():
        sys.exit(f"corpus index missing at {path}; run: python -m materia.corpus.index")
    return Retriever(open_index(path), k=5, per_doc=2)


def cmd_status(_: argparse.Namespace) -> int:
    print(json.dumps(llm.status(), indent=1))
    idx = config.CORPUS_DIR / "index.sqlite"
    if idx.exists():
        print(json.dumps(corpus_stats(idx), indent=1))
    return 0


def cmd_corpus(args: argparse.Namespace) -> int:
    idx = Path(args.index)
    if not idx.exists():
        sys.exit(f"no index at {idx}; run: python -m materia.corpus.index")
    print(json.dumps(corpus_stats(idx), indent=1))
    return 0


def cmd_ocr(args: argparse.Namespace) -> int:
    llm.load_phase("ocr")
    page = ocr.ocr_page(args.file, mode=args.mode, max_tokens=args.max_tokens)
    print(page["text"])
    if page.get("truncated"):
        print("\n[truncated — raise --max-tokens or OCR context]", file=sys.stderr)
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    llm.load_phase("ocr")
    page = ocr.ocr_page(args.file, mode="table", max_tokens=args.max_tokens)
    rows = ocr.extract_lab_rows(ocr.parse_otsl(page["text"]))
    truth = json.loads(Path(args.truth).read_text()) if args.truth else None
    collected = (truth or {}).get("collected_at")
    print(f"{'analyte':22s} {'value':>8s} {'unit':8s} {'interval':>14s}  review")
    for r in rows:
        issues = extract.check(r, collected_at=collected)
        print(
            f"{r['analyte'][:22]:22s} {str(r['value']):>8s} {str(r['unit'])[:8]:8s} "
            f"{str(r['ref_text'] or ''):>14s}  {'; '.join(issues) if issues else 'ok'}"
        )
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    """Answer a free-text question.

    Uses hint mode: one reference sentence, thinking enabled, then post-hoc attribution.
    Block evidence plus deliberation collapses on this model (docs/gate3.md); a sentence does not.
    """
    r = _retriever(args.index)
    chunks = r.search(args.question)
    grounded = grounded_chunks(chunks, args.question)
    if grounded:
        import re as _re

        from .verify import content_tokens

        # A named drug makes this an interaction question; prefer interaction/contraindication
        # sections over generic safety prose that happens to repeat the herb's name.
        drug = _re.search(
            r"\b(warfarin|apixaban|rivaroxaban|dabigatran|clopidogrel|aspirin|sertraline|fluoxetine|"
            r"escitalopram|citalopram|paroxetine|venlafaxine|levothyroxine|carbamazepine|valproate|"
            r"methotrexate|cyclosporin|tacrolimus|metformin|insulin|prednisolone)\b",
            args.question, _re.I,
        )
        pool = grounded
        if drug:
            typed = [c for c in grounded if c["section"] in ("interactions", "contraindications", "cautions")]
            pool = typed or grounded
        q_terms = content_tokens(args.question)
        hint_chunk = max(pool, key=lambda c: len(q_terms & content_tokens(c["text"])))
    else:
        hint_chunk = chunks[0] if chunks else None
    llm.ensure_reason(ctx=8192, parallel=2)

    if not hint_chunk:
        print("[memory mode] No corpus document covers this question. The answer is from model "
              "knowledge, not a source — verify before use.\n")
        out = llm.chat([{"role": "user", "content": build_freeform(args.question)}],
                       max_tokens=260, enable_thinking=False)
        _ = args
        print(out["text"].strip() or "(no answer)")
        return 0

    prompt = build_prompt_hint(
        {"q": args.question, "o": {}}, hint_chunk, config.RULE_FREEFORM, smart=True
    )
    out = llm.chat([{"role": "user", "content": prompt}], max_tokens=420, timeout=1200)
    answer = out["text"].strip()
    if not answer and out.get("finish") == "length":
        out = llm.chat([{"role": "user", "content": prompt}], max_tokens=900, timeout=1800)
        answer = out["text"].strip()
    if not answer:
        print("No answer produced within the budget (the model reasoned past the cap).")
        print(f"\nReference that was shown: {hint_chunk['chunk_id']} · {hint_chunk['source']}")
        return 0
    attribution = attribute_answer(answer, hint_chunk)

    print(answer)
    print()
    if attribution["mode"] == "grounded":
        print(f"Reference: {hint_chunk['chunk_id']} · {hint_chunk['source']} · {hint_chunk['date']} · "
              f"{hint_chunk['section']}")
        print(f"  {hint_chunk['text'][:300]}…")
    else:
        print("[memory mode] The shown reference does not carry this answer. Treat it as model "
              "knowledge, not a cited claim — verify before use.")
        print(f"  reference shown: {hint_chunk['chunk_id']} · {hint_chunk['source']}")
    return 0


def cmd_symptom(args: argparse.Namespace) -> int:
    rules = symptom.load_rules()
    conn = open_index(args.index) if Path(args.index).exists() else None
    intake = symptom.parse_intake(args.text)
    red = symptom.red_flag_check(args.text, rules["red_flags"])

    print("WHAT YOU DESCRIBED")
    print(f"  {args.text.strip()}")
    print("\nCHECK FIRST")
    if red:
        for h in red:
            print(f"  {h['urgency'].upper()}: {h['action']} ({h['citation']['source']})")
        if red[0]["urgency"] == "emergency":
            print("\nStopped: emergency red flag. No supplement advice will be produced.")
            return 0
    else:
        print("  No red flags identified from what was described. This is not a diagnosis.")

    if conn is None:
        sys.exit("corpus index missing; run: python -m materia.corpus.index")
    r = Retriever(conn, k=5, per_doc=2)
    chunks = r.search(args.text)
    ivs = symptom.candidate_interventions(args.text, chunks, r.lex)
    findings = symptom.safety_screen(intake, ivs, conn, rules["safety"])

    print("\nSAFETY SCREEN")
    if findings:
        for f in findings:
            print(f"  {f['severity'].upper():5s} {f['intervention']} in {f.get('label', f['context'])} — "
                  f"{f['source']} [{f['chunk_id']}]")
    else:
        print("  No safety findings for the stated context.")

    llm.ensure_reason(ctx=8192, parallel=2)
    screened = symptom.screen_chunks(chunks, findings)
    prompt = symptom.build_prompt(args.text, screened, findings, red, intake)
    out = llm.chat([{"role": "user", "content": prompt}], max_tokens=args.max_tokens, timeout=1200)
    sheet = symptom.limit_options(out["text"], 3)
    sheet, removed = symptom.enforce_vetoes(sheet, findings)
    sheet, dropped = verify.drop_unsupported(sheet, screened, threshold=0.2)
    issues = symptom.contract_check(sheet, chunks, findings)
    print("\n" + sheet.strip())
    if removed:
        print("\n[vetoed options removed by the safety screen]")
    print("\nEVIDENCE")
    for i, c in enumerate(chunks, start=1):
        print(f"[S{i}] {c['chunk_id']} · {c['source']} · {c['date']} · {c['section']}")
    if issues:
        print("\nCONTRACT VIOLATIONS — sheet withheld from production use")
        for i in issues:
            print(f"  - {i}")
    return 0 if not issues else 1


def cmd_labs(args: argparse.Namespace) -> int:
    values = json.loads(Path(args.values).read_text())
    out = {}
    for name, fn in (
        ("tsat", lambda: calc.tsat(values["iron"], values["tibc"])),
        ("corrected_calcium", lambda: calc.corrected_calcium(values["calcium"], values["albumin"])),
        ("egfr", lambda: calc.egfr_ckd_epi_2021(values["creatinine"], values["age"], values["sex"])),
        ("fib4", lambda: calc.fib4(values["age"], values["ast"], values["alt"], values["platelets"])),
        ("homa_ir", lambda: calc.homa_ir(values["glucose"], values["insulin"])),
    ):
        if all(k in values for k in {"tsat": ("iron", "tibc"), "corrected_calcium": ("calcium", "albumin"),
                                     "egfr": ("creatinine", "age", "sex"),
                                     "fib4": ("age", "ast", "alt", "platelets"),
                                     "homa_ir": ("glucose", "insulin")}[name]):
            out[name] = fn()
    print(json.dumps(out, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="materia")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status").set_defaults(fn=cmd_status)

    p = sub.add_parser("corpus")
    p.add_argument("--index", default=str(config.CORPUS_DIR / "index.sqlite"))
    p.set_defaults(fn=cmd_corpus)

    p = sub.add_parser("ocr")
    p.add_argument("file")
    p.add_argument("--mode", choices=["text", "table"], default="table")
    p.add_argument("--max-tokens", type=int, default=3000)
    p.set_defaults(fn=cmd_ocr)

    p = sub.add_parser("ingest")
    p.add_argument("file")
    p.add_argument("--truth", default="")
    p.add_argument("--max-tokens", type=int, default=3000)
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("ask")
    p.add_argument("question")
    p.add_argument("--index", default=str(config.CORPUS_DIR / "index.sqlite"))
    p.set_defaults(fn=cmd_ask)

    p = sub.add_parser("symptom")
    p.add_argument("text")
    p.add_argument("--index", default=str(config.CORPUS_DIR / "index.sqlite"))
    p.add_argument("--max-tokens", type=int, default=900)
    p.set_defaults(fn=cmd_symptom)

    p = sub.add_parser("labs")
    p.add_argument("values", help="JSON file of lab inputs")
    p.set_defaults(fn=cmd_labs)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
