# materia — clinical engine design

**Status:** 2026-10-31. This is the working design for the blood-test → recommendation engine.
It supersedes the earlier "no diagnosis, no dose" framing in `AGENTS.md`; the provenance and safety
constraints remain.

## Objective

Input: a blood test (PDF/photo or structured rows), plus a short intake.
Output: a cited clinical assessment and ranked supplement/herb options, then a conversation about
them.

The engine must be **reliable before it is broad**. A narrow set of patterns with defensible sources
is better than 200 patterns with thin ones. Every number is reproducible from a chunk in
`corpus/index.sqlite`; every option is withheld if its citation does not resolve.

## Source of truth

No single book is the source of truth. The engine uses a hierarchy, and displays the tier:

| Tier | Examples | Use |
|---|---|---|
| Regulatory | Health Canada NNHPD monographs, EMA herbal monographs | dose range, indication, contraindication |
| Primary | CC-BY systematic reviews, RCTs, consensus statements via Europe PMC | thresholds, comparative efficacy, monitoring |
| Compendium | MedlinePlus, NCCIH, NCI PDQ, ODS (public domain) | lab interpretation, safety context |
| Traditional | NHPID traditional-use claims, pharmacopoeias | historical use, only with the label visible |

A traditional claim is never rendered as if it were trial evidence. A guideline is not a licence to
invent a dose: the dose must exist verbatim in a cited chunk.

**The naturopathic/integrative frame** is a data field, not a separate epistemology. It changes which
options are considered (nutrients, herbs, lifestyle, referral) and the order of the therapeutic
hierarchy, not whether a claim needs a source.

## Ontology

```
Report row ──► Finding ──► Pattern ──► Goal ──► Intervention ──► Option
                  │            │                       │
                  │            └─ citations          ├─ dose chunk
                  └─ lab interval / unit              ├─ evidence chunks
                                                       ├─ monitoring chunk
                                                       └─ safety rules
```

- **Finding**: canonical analyte, value in canonical unit, the lab's own interval, direction, severity.
- **Pattern**: a cited hypothesis (e.g. "iron deficiency pattern"), with `possible`/`likely`, supporting
  and conflicting findings, confirmatory tests, citations.
- **Goal**: what the pattern calls for (restore iron stores, lower triglycerides), not a product.
- **Intervention**: nutrient, herb, food, referral, or "no supplement; investigate".
- **Option**: intervention + dose range + evidence + monitoring + safety flags + grade + score.
  Lifestyle and referral steps are first-class options with no dose; a supplement/herb option must
  carry a dose that resolves to a cited chunk. A dose may cite more than one chunk when the sources
  disagree (e.g. a review's typical range and a regulatory upper intake); the conflict is displayed,
  not silently resolved.

## The equation

Each option is scored, but hard gates run first:

```
if any veto context or avoid_if criterion: exclude (show as withheld)
if citation/dose check fails: exclude (show as withheld)
if no evidence chunk: exclude (show as gap)

match    = pattern.confidence                    # 0.05–0.95
evidence = mean(tier_weight) × mean(recency)     # regulatory 1.0, primary 0.9, compendium 0.7,
                                                 # traditional 0.4; recency 1.0 ≤2y, 0.92 ≤5y,
                                                 # 0.85 ≤10y, 0.75 older
severity = severity_rank / 4                     # critical 4, high 3, moderate 2, low 1
score    = (0.45·match + 0.35·evidence + 0.20·severity) × rank_hint
```

The weights are a starting prior, not a measured optimum. They are exposed in the JSON
(`score_parts`) so a practitioner can see why one option outranks another. The next calibration step
is practitioner-labelled ranking data, not a hand-tuned weight.

Confidence for a pattern:

```
confidence = base + Σ supporting.weight − Σ against.weight
```

Every weight is attached to a cited criterion. A pattern cannot reach `likely` on a single borderline
value if a conflicting finding is present.

## Safety

Three independent gates, in this order:

1. **Red flags** (`materia/rules/red_flags.yaml`) — emergency/urgent symptoms stop the flow before any model
   call.
2. **Rule-level context** — `veto_contexts` excludes an option (e.g. iron in haemochromatosis,
   vitamin D in hypercalcaemia, fish oil in fish allergy); `flag_contexts` keeps it but surfaces the
   warning (pregnancy, kidney disease, anticoagulants, child).
3. **Evidence-level cautions** — the monograph/trial chunks cited by the option, shown verbatim.

A veto is never argued with. A withheld option remains visible as "withheld: reason" so the
practitioner can see the screen worked.

## Output contract

```json
{
  "intake": {...},
  "findings": [...],
  "patterns": [{"id","label","status","confidence","severity","supporting","against",
                "confirm","citations"}],
  "recommendations": [{"id","intervention","kind","goal","grade","dose",
                       "evidence","monitoring","safety","score","score_parts"}],
  "withheld": [{"intervention","reason","detail"}],
  "gaps": [{"pattern","reason"}],
  "disclaimer": "..."
}
```

Rules:

- No recommendation without a resolved evidence chunk.
- No dose number that is not a substring of its cited dose chunk(s).
- No diagnosis stated as fact; `possible`/`likely` only.
- No option that the safety screen vetoed.
- If nothing covers the case, say so and record the gap.

## Evaluation

The current measured/unmeasured boundary is maintained in `docs/validation.md`.

"High success rate" needs a definition. Three layers:

1. **Citation integrity (automated, every commit).** Every rule resolves; every dose is a substring;
   every citation chunk exists; every withheld option has a reason; every note shares content with
   its cited chunk. This is the analogue of Gate 4's contract check.
2. **Pattern agreement (practitioner-labelled vignettes).** 50–100 synthetic lab panels with a
   practitioner's expected pattern/option set. Measure: pattern precision/recall, top-1 option
   agreement, unsafe-option rate, no-evidence precision. Report n and 95% CI. The current set is 72
   contract vignettes (50 in the clinician review subset); it is not yet practitioner-labelled.
3. **Conversation grounding.** The chat layer must answer from the assessment object; a model answer
   without a valid chunk citation, or with a dose not in the evidence, is rejected and the
   deterministic answer is shown. On 29 grounded questions, the deterministic path scored 29/29 and
   the local MiniCPM5-2B Q8 scored 29/29 (27 model answers, 2 rejected
   and replaced); the Q4 variant also scored 29/29 (23 model answers, 1 deterministic answer, 5 rejected). The current
   multi-turn set is 17 turns; Q8 used the model for 15 of 17, Q4 for 12 of 17, and both passed
   the contract. A larger CPU model is optional, not required.
4. **Practitioner review.** The Plan view writes accept / modify / reject labels to
   `~/.materia/reviews.jsonl`; each label carries the reviewer, engine version and a hash of the
   rule files. The review completion screen shows the decision counts and downloads the JSONL;
   `scripts/review_report.py` reports accept rate per option with n and a 95% Wilson interval. Those labels are the calibration set for the ranking weights.

The first number to publish is not accuracy. It is **citation integrity and veto recall**, because a
recommendation engine that cites the wrong chunk is worse than one that says "no evidence".

## Model stack

The recommendation engine is deterministic and needs no model. The conversational layer is separate
and model-agnostic:

- Default local: **MiniCPM5-2B on CPU** — Q4_K_M (1.5 GB) for low RAM, Q8_0 (2.7 GB) for
  higher quality. Both run under `llama.cpp`; no GPU is required.
- Optional larger CPU model: a 3B–7B open-weight GGUF served behind the same OpenAI-compatible
  endpoint, configured by `MATERIA_CHAT_BASE_URL` / `MATERIA_CHAT_MODEL`. Measure it before
  shipping; a larger model is not automatically better at the citation contract.
- With no endpoint configured, the deterministic responder answers from the assessment object.
  A configured model is used only to explain the same object; its answer is rejected if it
  introduces a dose or citation that is not in the assessment.
- No closed APIs. Fine-tuning is allowed only after retrieval/rules have their own numbers; the
  measured failure on this task is not knowledge, it is selection and citation.

**CPU runbook.** The commands, RAM guidance and measured Q4/Q8 results are in
`docs/model-runbook.md`. The chat benchmark can be pointed at any OpenAI-compatible CPU endpoint
with `--base-url` / `--model`.

Do **not** fine-tune yet. The binding constraints are evidence coverage, pattern thresholds and
practitioner ranking labels — a better model cannot invent the missing citations, and a fine-tune
on the synthetic contract set would overfit it.

The model receives the assessment JSON + a bounded recent conversation history + evidence snippets,
and may only:
- explain an option,
- compare options,
- answer "what would change this",
- say "the evidence does not cover that".

It may not add an option, change a dose, or overrule a veto. A post-hoc checker rejects any answer
that introduces an intervention or dose not in the assessment, and rejects a “what dose?” answer
that contains no dose at all.

## What is built now

- `materia/clinical.py` — canonical analytes, unit conversion, findings, pattern matching.
- `materia/recommend.py` — evidence graph, dose/citation validation, safety, ranking, JSON/text output.
- `materia/rules/analytes.yaml`, `materia/rules/clinical_patterns.yaml`, `materia/rules/recommendations.yaml`.
- `scripts/ingest_pmc.py` — CC-BY full-text ingestion (iron, B12, vitamin D, silymarin, turmeric,
  berberine, omega-3, FBC, magnesium).
- `scripts/ingest_nhpid_dose_rows.py` — clean adult dose rows from the Health Canada
  multi-vitamin/mineral monograph (folate, B12, iron, magnesium, zinc) with the values unchanged.
- `materia recommend case.json` — CLI.
- `materia chat case.json "Why iron?"` — grounded chat CLI.
- `POST /api/recommend`, `POST /api/chat` and `POST /api/review`; a "Plan" tab in the web app with
  intake, patterns, options, withheld options, gaps, sources, a chat box and accept/modify/reject
  buttons. Reviews are local JSONL labels for ranking calibration.
- `scripts/review_cases.py` — interactive agree/unsafe/missing review of the vignette set.
- `scripts/make_review_csv.py` — blank 50-row label sheet for spreadsheet review.
- `scripts/import_reviews.py` — import offline CSV labels with the same reviewer/version/rule-hash
  provenance as the web mode.
- `scripts/audit_rules.py` — rule/citation/dose/freshness audit; writes `docs/rules-audit.md`.
- `GET /api/review/cases` and the web "Review cases" mode — the same 31-case labelling workflow
  in the browser, writing to the same local JSONL.
- Medication flags for PPIs (iron/B12/magnesium), thiazides (vitamin D) and antiplatelets/
  anticoagulants (fish oil), each with a CC-BY source chunk.
- `materia/rules/critical_values.yaml` — adult critical limits from a CC-BY survey of hospital
  point-of-care policies (`pmc-pmc13115040`). A critical value withholds supplement/herb options,
  keeps referral/lifestyle steps, and raises a critical banner in the Plan and chat.
- Tests: 164 passing; citation integrity, dose support, note support, pattern matching, veto
  behaviour, chat citation rejection, review API.
- 24 patterns / 31 options (10 supplement-herb, 5 lifestyle, 16 referral).
- Chat contract set: 29 questions, deterministic 29/29, MiniCPM5-2B Q8 29/29 (27 model answers, 2 rejected) and Q4 29/29 (23 model answers, 1 deterministic answer, 5 rejected). CPU only;
  a larger CPU model is optional.
- Synthetic contract set: `data/clinical_vignettes.json` + `scripts/eval_recommend.py`,
  **73/73 = 100% [95.0, 100.0]** on pattern/top-option/withheld/flags/gap/severity/citation. This is a
  self-authored contract set, not clinical validation.

## Next

1. Get the 50-case clinician review labelled and publish the first agreement/CI numbers.
2. Turn the review JSONL into a calibration report and re-rank with it.
3. Measure a 3B CPU model on the same 28+17 chat contract; keep Q4 as the low-RAM fallback.
4. Add a defensible amino-acid/nutrition evidence source, or keep the amino-acid demo explicitly
   out of scope until one exists.
5. Expand patterns only where the evidence and a dose/interaction profile are both defensible.
