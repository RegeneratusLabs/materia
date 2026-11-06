"""materia command line.

    materia status
    materia corpus --stats
    materia ocr samples/pages/nutripath-p2.png
    materia ingest samples/pages/nutripath-p2.png --truth samples/ground_truth/nutripath-p2.json
    materia ask "Is St John's wort safe with warfarin?"
    materia symptom "68 year old on warfarin, can I take ginkgo for memory?"
    materia recommend case.json
    materia chat case.json "Why iron?"

Everything it prints is traceable: no answer without a chunk id, no number without its
citation, and a review flag wherever a deterministic check failed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, calc, config, extract, llm, ocr, parse, symptom, verify
from .attribute import attribute as attribute_answer
from .corpus.index import open_index, stats as corpus_stats
from .prompt import build_freeform, build_prompt_hint
from .retrieve import Retriever, choose_reference, grounded_chunks, group_conflicts


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
    hint_chunk = choose_reference(args.question, grounded) if grounded else None
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


def cmd_recommend(args: argparse.Namespace) -> int:
    from .recommend import load_case, open_corpus, recommend, render_text

    rows, intake = load_case(args.input)
    assessment = recommend(rows, intake=intake, conn=open_corpus(args.index))
    if args.json:
        print(json.dumps(assessment.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(render_text(assessment))
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    from .chat import answer
    from .recommend import load_case, open_corpus, recommend

    rows, intake = load_case(args.input)
    assessment = recommend(rows, intake=intake, conn=open_corpus(args.index)).as_dict()
    if not args.question:
        args.question = input("Ask materia: ").strip()
    result = answer(args.question, assessment, use_model=not args.no_model)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["answer"])
        if result.get("citations"):
            print("\nSources: " + ", ".join(result["citations"]))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .webapp.server import serve
    serve(args.host, args.port, open_browser=args.open, start_ocr=args.start_ocr)
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    """Check the local install: Python, corpus, rules, samples and review set."""
    from .clinical import load_patterns
    from .recommend import load_recommendations

    ok = True
    print(f"materia {__version__}")
    print(f"python  {sys.version.split()[0]}")
    index = config.CORPUS_DIR / "index.sqlite"
    if index.exists():
        stats = corpus_stats(index)
        print(f"corpus  {stats.get('docs')} docs / {stats.get('chunks')} chunks")
    else:
        print(f"corpus  MISSING {index}")
        ok = False
    try:
        patterns = load_patterns()
        options = load_recommendations()
        print(f"rules   {len(patterns)} patterns / {len(options)} options")
    except Exception as exc:  # noqa: BLE001 - doctor must report, not crash
        print(f"rules   FAIL {exc!r}")
        ok = False
    sample = config.ROOT / "materia" / "webapp" / "static" / "assets" / "sample-nutrient.json"
    print(f"sample  {'ok' if sample.exists() else 'MISSING'} {sample}")
    if not sample.exists():
        ok = False
    vignettes = config.ROOT / "data" / "clinical_vignettes.json"
    if vignettes.exists():
        import json
        data = json.loads(vignettes.read_text())
        review = sum(1 for c in data.get("cases") or [] if c.get("review", True))
        print(f"review  {review} cases / {len(data.get('cases') or [])} total")
    else:
        print(f"review  MISSING {vignettes}")
        ok = False
    print(f"models  {'ok' if config.LLAMA_SERVER.exists() else 'optional missing'} {config.LLAMA_SERVER}")
    print("status  " + ("OK" if ok else "FAIL"))
    return 0 if ok else 1


def cmd_models(args: argparse.Namespace) -> int:
    """List local GGUF weights and the CPU model configuration."""
    from . import llm

    print(f"models dir: {config.MODELS_DIR}")
    found = sorted(config.MODELS_DIR.rglob("*.gguf")) if config.MODELS_DIR.exists() else []
    if not found:
        print("  no .gguf files found")
    for path in found:
        size = path.stat().st_size / 1e9
        print(f"  {size:5.2f} GB  {path}")
    print(f"llama-server: {'found' if config.LLAMA_SERVER.exists() else 'missing'}  ({config.LLAMA_SERVER})")
    print(f"reason model: {config.REASON_GGUF}")
    print(f"chat endpoint: {config.CHAT_BASE_URL or 'none (deterministic fallback)'}")
    if args.check:
        print(f"reason server healthy: {llm.health(config.REASON_PORT)}")
    return 0


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
    ap = argparse.ArgumentParser(
        prog="materia", description="materia — cited clinical decision-support engine"
    )
    ap.add_argument("--version", action="version", version=f"materia {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("doctor", help="check the local install end to end").set_defaults(fn=cmd_doctor)
    p = sub.add_parser("models", help="list local GGUF weights and the CPU model config")
    p.add_argument("--check", action="store_true", help="ping the local reason server")
    p.set_defaults(fn=cmd_models)

    p = sub.add_parser("serve", help="run the local web app")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--open", action="store_true", help="open the browser after starting")
    p.add_argument("--start-ocr", action="store_true",
                   help="start the OCR model before serving (stops any reasoning server)")
    p.set_defaults(fn=cmd_serve)

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

    p = sub.add_parser("chat", help="ask a grounded question about an assessment")
    p.add_argument("input", help="JSON file with rows and optional intake")
    p.add_argument("question", nargs="?", default="")
    p.add_argument("--index", default=str(config.CORPUS_DIR / "index.sqlite"))
    p.add_argument("--no-model", action="store_true", help="deterministic answer only")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_chat)

    p = sub.add_parser("recommend", help="blood test rows -> cited supplement/herb options")
    p.add_argument("input", help="JSON file with rows and optional intake")
    p.add_argument("--index", default=str(config.CORPUS_DIR / "index.sqlite"))
    p.add_argument("--json", action="store_true", help="machine-readable assessment")
    p.set_defaults(fn=cmd_recommend)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
