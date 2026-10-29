# Shipped configuration — what runs, and which measurement justifies it

Every choice here is backed by a number in `docs/gate_report.md` / `docs/scores.json`. If a number moves,
this file must move with it.

## Answering a question

| Situation | Behaviour | Evidence |
|---|---|---|
| Lab question (analyte detected) and a covering document exists | One reference sentence in the prompt, thinking on, 768 cap; answer returned with the reference and an attribution label | **Lab-hint: 102/104, 104/104 answered, lab 29/30** (closed: 102/104, 102 answered, lab 28/30) |
| Lab question, no covering document | Exact closed-book prompt; answer labelled `memory` | Uncovered items are identical to closed-book by construction (10/10 verified) |
| Herb / nutrient / referral question | **Closed-book.** No evidence is injected (byte-identical prompt) | Full retrieval −3.8 pts, coverage-routed −2.8 pts; herb coverage is ~25–46% and only ~50% precise |
| No reference at all | Answer labelled `memory`, no citation shown | Never fabricate a source (AGENTS.md #6) |

Two rules that are not negotiable in code:

- **Block evidence is never combined with thinking.** A full `EVIDENCE` block plus deliberation produced no
  answer in 14/20 items (Experiment 5).
- **Evidence is one sentence.** Anything longer turns the question into a reading task this model cannot
  finish.

## Attribution

`materia/attribute.py` decides whether the shown reference can be presented as a source:

1. entity consistency — the reference's distinctive tokens must appear in the question, or the answer is
   `memory` (this caught an astragalus chunk attributed to an echinacea answer);
2. lexical support — ≥2 shared content terms and ≥20% of the answer's terms present.

False `memory` labels are acceptable. False `grounded` labels are not. Measured: 7 grounded attributions in
104 answers, of which the hand-audited sample was 8/9 genuinely supported (`docs/attribution.md`).

## Symptom sheets

1. Intake parsed into slots; missing slots are asked for, never guessed.
2. Red-flag gate runs first and can only escalate (8/8 on the vignette set; 6/6 emergencies stopped).
3. Safety screen is deterministic and corpus-backed; **vetoed interventions are removed from the model's
   context before generation**, not censored afterwards (0/4 vetoed offers after this change, was 4/4).
4. Sheet is capped at three options, then checked against the output contract (citation per option, dose
   present in the cited chunk, no diagnosis language, no vetoed intervention).
5. Option lines whose cited chunk does not carry them are **dropped** with a truthful note
   (`verify.drop_unsupported`, threshold 0.2, stemming, ≥2 shared terms).
6. Result: 24/24 contract-clean in the full v2 run, and 8/8 on the integrated drop-and-verify run with zero
   unsupported claims remaining.

## Runtime

- Reasoning server: `MiniCPM5-2B-Q8_0`, `-c 4096 -np 2 -t 6 --jinja --no-reasoning-preserve`, port 8099.
  Restarted by the RSS guard at 3.5 GB; without that the box degrades to ~9 tok/s and long runs stall.
- OCR: `MiniCPM-OCR-1_0-Q4_K_M` + `mmproj-model-f16-4x`, `-c 16384`, port 18499. Load by phase, never
  alongside the reasoning server.
- Vintage matters: every number in this repo names the corpus index it used via
  `results/gate_manifest.json`.

## What is deliberately not shipped

- **Herb retrieval.** The model's closed-book prior beats the corpus on herb questions at every
  configuration tried.
- **The model reranker.** 93/104 with it, 94/104 without, 50% more time (Experiment 7).
- **Full evidence blocks with deliberation.** They do not terminate.
- **Memory answers presented as cited.** They are labelled and cannot be rendered with a source.

## Limits, stated where they cannot be missed

- The panel is 104 items the project author wrote; the 98.1% is not a clinical accuracy claim.
- Coverage is 42.3% of the panel and the herb half of it is only ~50% precise.
- Attribution is lexical, not entailment; its threshold has been calibrated against stored sheets and one
  hand audit, not practitioner labels.
- Nothing here has been reviewed by a practitioner.
- **Measurement noise is ~1 item in 104** at `-np 2` (one herb item flipped between two runs with identical
  prompts). Treat any difference below 2 items as noise; use `-np 1` and repeat runs before claiming one.
