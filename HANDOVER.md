# materia — Handover Brief

**Date:** 2026-10-28 · **Author:** Hermes (Josh's co-founder agent, running on `homelab`)
**Supersedes:** nothing — this is the first handover. The chat transcript is not a source; this file is.
**Purpose:** State transfer for DSH, taking over `materia` on `homelab`. Read top to bottom before touching anything.

---

## TL;DR

- **The product is a cited evidence engine for naturopathic / holistic practitioners.** Not a protocol generator, not a chatbot, not a diagnosis tool.
- **Everything measured so far is closed-book model knowledge. There is no retrieval, no corpus, no fine-tuning in this repo yet.** That is deliberate, and it is the single most important thing to understand before continuing.
- **Headline result:** `MiniCPM5-2B` Q8_0 scores **95.2% (99/104, 95% CI 89.2–97.9)** on a naturopathic MCQ panel it has never been trained on, with a 60-word reasoning budget. Same model, no budget, direct answer: **71.7%** on the 46-item predecessor.
- **External anchor:** **49.5% (198/400, CI 44.6–54.4)** on MedQA-USMLE. Chance is 25%. This is an *upper bound* — MedQA is in pretraining.
- **Do NOT fine-tune for knowledge.** The evidence says the knowledge is already in the weights and is an *elicitation* problem, not a training problem. The fix is retrieval + scaffolding.
- **Prompt scaffolding: one instruction only.** "Think for at most 60 words, then answer." Every extra meta-instruction tried so far scored *lower* (3 of 3 conditions), though with n=104 none reached statistical significance. Details in §4 and §8 — do not tell the model to distrust its priors.
- **Not done:** retrieval layer, evidence corpus, OCR run, PubMedQA, MedXpertQA, HealthBench, safety gate, UI, practitioner testing.
- **First task:** §10 step 3 — prove `MiniCPM-OCR-1.0` on a real lab report, then step 5 build the corpus. Do not start with training.
- **Stack is 100% OpenBMB:** `MiniCPM5-2B` (reasoning), `MiniCPM-OCR-1.0` (documents), `MiniCPM-OCR-Jev` (per-region OCR confidence). All Apache-2.0. Never all resident at once — load by phase, peak 3.2 GB.

---

## 1. What it is

A tool for naturopaths, nutritionists, herbalists and functional-medicine practitioners that answers clinical questions with **citations they can check**, rather than asserting protocols. Josh's framing: *"putting better uses of AI out there, in the more natural and holistic ways."* Global open-source project.

**Global by default, jurisdiction as data (Josh, 2026-10-28).** Nothing in the product, corpus or defaults is tied to one country. Units, reference intervals, scheduling and permitted claims differ by market and are carried as fields, not hardcoded. The first build target happens to be English-language, but that is a starting point, not a scope limit.

**Explicitly NOT:**
- not a diagnostic tool
- not an autonomous prescriber (it never outputs a protocol — it surfaces evidence + a cited rationale)
- not a regulated medical device product (Josh's call, 2026-10-28: "fuck regulation, this is a global open source model")
- not fine-tuned on scraped naturopathic content — there is no such corpus (verified: zero `naturopath` / `functional medicine` datasets on HF)

**v1 shape:** local model + retrieval over a curated corpus + deterministic safety rules + citations on every claim.

---

## 2. Architecture (LOCKED — do not re-litigate)

**Stack is 100% OpenBMB (Josh, 2026-10-28).** Three models, each doing one job:

| Role | Model | Params | Weights (GGUF) | Licence |
|---|---|---|---|---|
| Reasoning | `openbmb/MiniCPM5-2B` | 2B | Q8_0 2,556 MB · Q4_K_M 1,489 MB | Apache-2.0 |
| Document OCR | `openbmb/MiniCPM-OCR-1.0` | 1.3B | Q4_K_M **505 MB + mmproj 859 MB** = 1,364 MB | Apache-2.0 |
| OCR confidence | `openbmb/MiniCPM-OCR-Jev` | 2B | Q4_K_M **1,215 MB + mmproj 640 MB** = 1,855 MB | Apache-2.0 |

`MiniCPM-OCR-1.0` — released 2026-10-26. First OCR-specific model in the MiniCPM-V/o family. SOTA 93.68 on Real5-OmniDocBench, leading on OmniDocBench v1.6 / Wild-OmniDocBench / olmOCR-Bench, 54.7 on OCRBench v2. Handles scans, curved pages, skewed pages, photographs and recaptured documents — i.e. phone photos of lab printouts, which is the actual input. English + Chinese. GGUF, llama.cpp and Ollama from day one, DSpark variants (~55% faster end-to-end).

**`MiniCPM-OCR-Jev` is the important one nobody mentions.** It is not a generative OCR model: it is `Qwen3.5-2B` with the `lm_head` replaced by a **binary classification head**. Input = region image + candidate text + category (text/formula/table); output = one score 0–1, "is this candidate correct". That is why it is fast and stable.

JevOCRBench AUROC ×100 = **93.6** overall (text 94.6, formula 93.1, **table 91.1**), above JEV-35B-A3B (90.1). Model-agnostic: 91.9–93.4 when scoring parses from MiniCPM-OCR 1.0, GLM-OCR, PaddleOCR-VL-1.6 or Xiaomi-OCR-0.

For this project it is the citation-auditability principle applied to input: **a lab value that OCR'd at 0.72 does not silently populate the record — it goes to the user for confirmation.** Start at 0.85 for numeric lab fields and 0.70 for free text, then calibrate on real panels (§6 Gate 0).

Four things about Jev that must not be forgotten:

1. **AUROC is ranking, not accuracy.** 93.6 does not mean "93.6% of auto-accepted values are right". It means correct candidates rank above incorrect ones 93.6% of the time. The auto-accept accuracy at a given threshold must be *measured on your own documents* — this is OpenBMB's own warning on the card.
2. **Tables are the weakest category (91.1), and lab reports are tables.** That is exactly the region type this project cares most about. Calibrate on lab tables specifically, not on prose.
3. **Error costs are asymmetric.** A false "needs review" costs a practitioner three seconds. A false "looks fine" puts a wrong clinical number in a record. Set the threshold high, accept a higher review rate, and monitor the two numbers separately.
4. **Jev scores fidelity, not sense.** It answers "did we read the glyphs correctly", not "is this value plausible", "is this the right patient", or "is this a lab typo". Those need a separate deterministic plausibility gate (value within a physically possible range for that analyte, units recognised, collection date present). Two gates, two different questions, neither substitutes for the other.

**Load by phase, never all at once.** OCR + Jev together are 3.2 GB; the text engine is 2.8 GB. A document-ingest pass peaks at ~3.2 GB, a query pass at ~2.8 GB. Keep all three warm only on 16 GB machines.

**Best-of-N is available and cheap, but not the default.** Because Jev is model-agnostic, you can parse each region with two OCR engines and let Jev pick the higher-scoring candidate — a real quality lift at ingest time. It costs a second non-OpenBMB OCR dependency (GLM-OCR, PaddleOCR-VL or Xiaomi-OCR), which conflicts with the all-OpenBMB decision, so treat it as a fallback lever to pull only if single-engine accuracy on real panels disappoints. Jev selects among existing candidates, so it cannot invent a better parse than the best candidate offers.

One dependency is **not** OpenBMB: the reference pipeline uses `PP-DocLayoutV3` (PaddlePaddle) for layout detection and reading order. For single-column lab reports you can skip layout entirely and feed whole pages — tables are handled. That keeps the shipped stack fully OpenBMB.

```
Intake note / lab PDF / phone photo
   │
   ├─ MiniCPM-OCR-1.0            page → markdown/HTML, tables preserved
   │  + MiniCPM-OCR-Jev          per-region 0–1 confidence → gate at 0.85 for numbers
   │
   ├─ Structured extraction      analyte · value · unit · the LAB'S interval · date
   │                             (numeric fields only enter the record above threshold)
   │
   ├─ OpenMed privacy-filter/NER de-identify + structure free text
   │
   ├─ Evidence corpus  ← THE MOAT         (built out in DSH, see §2.1)
   │
   ├─ Hybrid retrieval (BM25 + dense) + source-ID assignment
   │
   ├─ MiniCPM5-2B Q8_0           60-word reasoning budget; every claim carries a source ID
   │
   ├─ Claim→passage verification  second pass: does passage P actually support claim C?
   │
   ├─ Deterministic safety gate   rules, NOT an LLM: pregnancy, lactation, anticoagulants,
   │                             thyroid, immunosuppressants, liver disease, paediatric,
   │                             hepatotoxins, jurisdiction-specific scheduling
   │
   └─ SOAP note + cited rationale + "where evidence is absent or conflicting"
```

### 2.1 Corpus schema (DSH builds this)

The corpus is the project. It must be built to a schema that makes citation inevitable:

```json
{
  "doc_id": "ema-monograph-echinacea-2024",
  "source": "EMA herbal monograph",
  "tier": "regulatory",
  "title": "Echinacea purpurea — herbal monograph",
  "date": "2024-03-01",
  "url": "https://...",
  "identifier": { "type": "ema", "value": "EMA/HMPC/..." },
  "jurisdiction": "eu",
  "language": "en",
  "chunks": [
    {
      "chunk_id": "ema-monograph-echinacea-2024#003",
      "text": "Not recommended in patients with progressive systemic disease...",
      "section": "contraindications",
      "topics": ["autoimmune", "contraindication"],
      "analytes": [],
      "entities": ["Echinacea purpurea"]
    }
  ]
}
```

Non-negotiables for every document:

- **`tier`** ∈ `primary` (RCT, systematic review, Cochrane) · `regulatory` (EMA, ESCOP, WHO, and national regulators) · `compendium` (MSK About Herbs, LiverTox, Natural Medicines) · `traditional` (historical use). The UI renders tier with the citation; a traditional-use claim must never look like an RCT.
- **`jurisdiction`** is a field, never a hardcode. `international` for WHO/ESCOP; `eu`, `us`, `uk`, `ca`, `au`, `nz` etc. for national regulators. A claim that is permitted in one market and restricted in another must say so — that is a feature, not an edge case.
- **`identifier`** must be resolvable by a human in one click (PMID, DOI, EMA doc number, ARTG number).
- **`date`** is mandatory. A 2009 monograph and a 2024 one are not interchangeable, and the UI shows the date next to the claim.
- **Every chunk carries `section`** so the retrieval prompt can tell a contraindication from a pharmacology note. Most RAG failures on monographs are section-blindness.
- **No document enters without a resolvable identifier.** If you cannot cite it, it is not corpus — it is a note.

Suggested build order: lab reference intervals (small, finite, unblocks the whole lab path) → herb monographs for the 104-item panel's herbs → herb–drug interaction pairs → nutrient–drug interactions → referral red flags. That order follows the measured failure classes in §4.

**Settled decisions:**

| Decision | Settled by | To reopen it you would need |
|---|---|---|
| Retrieval over fine-tuning for factual knowledge | evidence (see §4), Josh agreed 2026-10-28 | a corpus that does not exist, plus a demonstration that fine-tuning beats base+RAG |
| Whole stack is OpenBMB, including OCR | Josh, 2026-10-28 | a measured failure of MiniCPM-OCR on real lab reports |
| OCR confidence gates numeric extraction | design (Jev exists; not using it is indefensible) | — |
| Small local open-weight models, not an API | Josh (anti-closed-source, no OpenAI) | — |
| OpenMed used for extraction/PII only, never as the reasoning engine | measurement: 2,255 of 2,278 OpenMed repos are `token-classification` | — |
| Reasoning budget in the prompt | measurement (§4) | a better scaffold that beats it on the 104-item panel |
| Safety gate is deterministic code, not model output | design principle | — |

---

## 3. Hardware / environment reality — verified 2026-10-28

| Item | Value | Command |
|---|---|---|
| Host | `homelab` (same machine DSH runs on) | `hostname` |
| CPU / RAM | i5-8500T, 6 threads, 15.8 GB | `nproc; free -m` |
| GPU | none | `nvidia-smi` |
| Disk free | 361 GB on `/` | `df -h /home` |
| Model | `~/models/minicpm5/MiniCPM5-2B-Q8_0.gguf` 2,556 MB; `...Q4_K_M.gguf` 1,489 MB | `ls -l ~/models/minicpm5/*.gguf` |
| Runtime | llama.cpp build 11936 (v0.7.0-dev), `~/bin/llamacpp/llama-b11936/llama-server` | `llama-server --version` |
| Throughput | **70 tok/s prefill, 16 tok/s generation** (Q4, 6 threads, no GPU) | observed during eval |
| Live process | `llama-server` on `127.0.0.1:8099`, `-c 4096 -np 2 -t 6 --jinja --no-reasoning-preserve` | `ps -C llama-server` |

### Measured footprint — 2026-10-28

Four configs run on this host, RSS read from `/proc` after load and again under a live request.
Raw log: `logs/footprint_2026-10-28.txt`. Reproduce: `scripts/footprint_probe.sh`.

| Config | RAM after load | RAM under request | Direct MCQ latency |
|---|---|---|---|
| Q4_K_M, 1024 ctx, 1 slot | 2,497 MB | 2,504 MB | 893 ms |
| Q4_K_M, 2048 ctx, 1 slot | 2,539 MB | 2,546 MB | 884 ms |
| Q8_0, 2048 ctx, 1 slot | 2,697 MB | 2,703 MB | 1,158 ms |
| Q8_0, 4096 ctx, 2 slots | 2,781 MB | 2,788 MB | 1,253 ms |

Three conclusions:

1. **~2.8 GB is the whole engine.** Weights dominate; the KV cache is noise (1024 → 4096 ctx costs 284 MB).
2. **A fresh Q8 server is 2.8 GB — the 7.7 GB observed after 2h21m was entirely the leak.** This is a process-watchdog problem, not a hardware problem.
3. **Tiering:** 8 GB mini-PC/Pi 5 = comfortable; 4 GB Pi 5 = tight but real on Q4 at 1024 ctx; 8 GB phone = plausible at the 1B tier only. **`MiniCPM5-1B` is unmeasured — testing it on the 104-item panel is the experiment that decides whether a phone build is viable.**

The real constraint is not RAM but generation speed: ~16 tok/s at 6 threads means a 250-token reasoned answer takes ~20 s. Fine for "interpret this panel", bad for conversational ping-pong.

### Latency budget — measured 2026-10-28, estimates labelled

| Path | Measured / estimated | On this host | Basis |
|---|---|---|---|
| Direct lookup, no reasoning | **measured** | **0.9–1.3 s** | four configs, `logs/footprint_2026-10-28.txt` |
| Discussion turn, 60-word budget (~250 tok) | **measured** (throughput) | **~16–20 s** | 16 tok/s generation + prefill at 70 tok/s |
| Discussion turn, unbudgeted (~446 tok) | **measured** (throughput) | **~28–40 s** | same; 2-worker wall clock was 15.4 min / 46 items |
| OCR one dense lab page | **estimate** | **15–45 s** | 1.3B VLM + 859 MB projector, CPU-only, ~1.8k visual tokens; GPU reference is 1.2 pages/s on an RTX 5090 |
| Jev, per region | **estimate** | **1–2 s** | 2B + 640 MB projector, 1 output token |
| Jev, 30 numeric fields, batched ×4 | **estimate** | **10–20 s** | sequential would be 30–60 s |

**Design consequences, not just numbers:**

1. **Ingest and chat are separable in time.** OCR + Jev run once per document, in the background, and the structured record is cached indefinitely. A user never waits for OCR while chatting. Show progress at upload, then forget it.
2. **Only gate what matters.** Run Jev on numeric lab fields, not on every region — free text (patient name, lab comments) will be read by a human anyway. That cuts Jev calls by roughly 80% and the ingest bottleneck with it.
3. **The 60-word budget is what makes chat viable.** Unbudgeted reasoning more than doubles the wait for no accuracy gain on this workload (§4).
4. **This host is not the target.** It is a CPU reference rig. Expect roughly 4–6× faster on Apple Silicon, which is what turns a 20 s discussion turn into a 4 s one.

Feasible here: 2B-class models Q4/Q8 on CPU, ~1 s per direct MCQ, ~20 s per budgeted reasoned answer. Not feasible: interactive chat latency, anything ≥8B at usable speed, any training.

---

## 4. State of the world — verified 2026-10-28

**Every number below is the generation-time `got` field from the stored JSONL, uppercased.** Reproduce with `docs/scores.json` and the files in `results/`. Do not re-derive scores by re-parsing stored text — see §8.

| Condition | n | Score | 95% CI | Answered | Mean reasoning tok | Hit cap |
|---|---|---|---|---|---|---|
| MedQA-USMLE, direct answer | 400 | **49.5%** | 44.6–54.4 | 400/400 | 2 | 0 |
| MedQA-USMLE, reasoning (1000-tok cap) | 60 | 46.7% | 34.6–59.1 | 47/60 | 844 | 40 |
| v1 panel (46), direct answer | 46 | 71.7% | 57.5–82.7 | 46/46 | 2 | 0 |
| v1 panel (46), reasoning unbounded | 46 | 93.5% | 82.5–97.8 | 46/46 | 446 | 8 |
| v1 panel (46), **60-word budget, Q4_K_M** | 46 | 97.8% | 88.7–99.6 | 46/46 | 249 | 5 |
| v1 panel (46), **60-word budget, Q8_0** | 46 | **100%** | 92.3–100 | 46/46 | 179 | 0 |
| v2 panel (104, shuffled), **60-word budget, Q8_0** | 104 | **95.2%** | 89.2–97.9 | 104/104 | 184 | 5 |
| v2 panel, budget + "never convert units / ignore priors" | 104 | 90.4% | 83.2–94.7 | 103/104 | 219 | 7 |
| v2 panel, budget + "reference interval is authoritative" | 104 | 93.3% | 86.8–96.7 | 104/104 | 229 | 6 |

**Prompt-variant comparisons on the identical 104 items (paired):**
- budget → never-convert/distrust: fixed 3, broke 8, exact McNemar **p = 0.227** (not significant)
- budget → interval-authoritative: fixed 2, broke 4, **p = 0.688** (not significant)

Honest reading: **no extra instruction helped; two of three trends went negative; none reached significance at n=104.** The earlier claim that the distrust rule was "significantly worse (p=0.008)" was a scoring bug and has been retracted — see §8.

**Free-text probes (12, no scaffolding):** Q8 answered 7/12, Q4 answered 6/12. All failures are the same shape — the model reasons until the token cap and emits nothing. Notably it **refused to fabricate citations** (asked for three RCTs on reishi for HbA1c: said it could not verify them) and **rejected false premises** (no herb cures type 2 diabetes; vitamin C does not cure cancer; refused to endorse swapping levothyroxine for iodine).

**Artifact audit:**

| Path | Count | Command |
|---|---|---|
| `results/*.jsonl` | 11 files, 1,126 scored rows | `wc -l results/*.jsonl` |
| `data/herbal_set.json` | 46 items (v1) | — |
| `data/herbal_set_v2_extra.json` | 58 items (authored later) | — |
| `data/herbal_set_104.json` | **104 items, option order shuffled, gold balanced A30/B22/C26/D26** | — |
| `data/medqa_*.json` | 1,273 questions (full test split) | — |
| `data/pubmedqa_*.json` | 1,000 questions — **downloaded, never run** | — |
| `data/probes.json` | 12 free-text probes | — |
| `docs/scores.json` | machine-readable score table | — |

**Panel composition (104):** herb-drug 26, herb-safety 20, nutrient-drug 12, lab 30, referral 8, safety 6, nutrient-safety 1, nutrient-lab 1.

**Not done, and it matters:** no retrieval, no corpus, no safety gate, no UI, no practitioner has seen it, **no OCR run** (`MiniCPM-OCR-1.0` and `Jev` identified and sized but not executed on a single document), PubMedQA never run, MedXpertQA/HealthBench/PhysicianBench never run.

**Extrapolation, labelled as such:** the 95.2% is on 104 multiple-choice items I wrote. Real patient files are longer, messier and multi-turn. Expect a material drop; nobody has measured it.

---

## 5. Where everything lives

**Same host as DSH. No transfer required.** Note `~/hermes-shared` is a symlink: `/home/josh/hermes-shared → /media/josh/Files/hermes-shared`. Use the real path when handing paths to anything that does not expand `~`.

| What | Absolute path |
|---|---|
| Project root | `/media/josh/Files/hermes-shared/projects/materia` |
| Panels | `.../data/herbal_set_104.json` (primary), `herbal_set.json` (v1), `herbal_set_v2_extra.json`, `probes.json` |
| Public benchmark data | `.../data/medqa_*.json`, `.../data/pubmedqa_*.json` |
| Raw results | `.../results/*.jsonl` |
| Scripts | `.../scripts/{run_eval,eval_v2,eval_v3,brief_test,brief_test_q8,analyze}.py` |
| Logs | `.../logs/*.txt`, `.../logs/*.log` |
| Scores | `.../docs/scores.json` |
| **Model weights (outside repo, do not move in)** | `/home/josh/models/minicpm5/MiniCPM5-2B-Q8_0.gguf` (2,556 MB), `MiniCPM5-2B-Q4_K_M.gguf` (1,489 MB) |
| **OCR + confidence weights (not yet downloaded)** | target `/home/josh/models/minicpm-ocr/`: `MiniCPM-OCR-1_0-Q4_K_M.gguf` (505 MB) + `mmproj-model-f16-4x.gguf` (859 MB) from `openbmb/MiniCPM-OCR-1.0-gguf`; `MiniCPM-OCR-Jev-Q4_K_M.gguf` (1,215 MB) + `mmproj-model-f16.gguf` (640 MB) from `openbmb/MiniCPM-OCR-Jev-gguf` |
| llama.cpp binaries | `/home/josh/bin/llamacpp/llama-b11936/` |
| Reusable harness + method | Hermes skill `local-gguf-capability-eval` (scripts/eval_harness.py) |

---

## 6. The work — probes and gates, in cost order

**Gate 1 — PubMedQA (data already on disk).**
Question: can it read a paper and answer from it? Inputs: `data/pubmedqa_*.json` (1,000 items). Cost: ~30 min CPU, 200 items. Gate: **≥70%** (4B medical models sit at 71–77%). Fallback if below: it changes nothing about retrieval design but caps expectations for single-shot reading — move to Gate 3 anyway.

**Gate 2 — MedXpertQA (`TsinghuaC3I/MedXpertQA`, ungated).**
Question: recall or reasoning? Cost: ~45 min CPU, 200 items. Gate: **≥10%** (4B models 15.8–18.2%; guessing ≈ 25% on 4-option, so read against a shuffled baseline, not raw). Fallback: a near-zero score means treat it as a recall engine and keep the retrieval layer doing the reasoning.

**Gate 3 — retrieval wiring (the real work).**
Question: does putting monographs and reference ranges in context close the known gaps? Inputs: the 104-item panel + a corpus of ≥200 herb monographs and reference intervals. Cost: 1–2 days. Gate: **≥95.2% baseline held AND ≥90% of claims traceable to a retrieved source**. Fallback: if accuracy drops, the retrieval is injecting noise — cut the corpus to the specific failure classes (see §7) before widening it.

**Gate 4 — panel expansion to 200+ with real monograph content.** Gate: per-category ≥90% with herb-safety specifically ≥95%.

---

## 7. Standing guard rails (non-negotiable)

1. **No fine-tuning until retrieval has been measured.** The evidence says elicitation is the problem. Training before testing that is burning compute on the wrong theory.
2. **Never report a percentage without n and a confidence interval.** 46 items at 97.8% is 88.7–99.6.
3. **Every claim in a document must be reproducible from an artifact in this repo.** If you compute a score, write the file you computed it from.
4. **Score from the stored `got` field, not by re-parsing stored text.** See §8.
5. **Open weights only.** No OpenAI, no closed APIs, in the product or the eval.
6. **The model never emits an uncited clinical claim.** If it cannot cite it, it says so.
7. **State truncation honestly.** A generation that hit the token cap and emitted nothing is *unanswered*, not *wrong*. Report both denominators.
8. **Real outputs only.** If it was not run, it is "not run". Fabricated numbers in a handover are worse than gaps.

---

## 8. Toolchain notes

- **The stored-text trap (this bit me, do not repeat it).** `results/*.jsonl` stores `text[:600]` and `reason[:800–3000]` — head-truncated. The generation-time parser read the *full* text and the *tail* of the reasoning. Re-parsing the stored head produces different answers on every record whose `finish == "length"`. **Use the `got` field.** This produced a false retraction-worthy claim (p=0.008) during the first pass.
- **Lowercase parser bug.** `re.search(r'\b([ABCD])\b', text, re.I)` matches the article "a" and returns `'a'` as an answer. One row in `v2_*` has `got: "a"`. Anchor uppercase only.
- **`--no-reasoning-preserve` is mandatory but not sufficient.** Observed RSS growth on the Q8 server: 2.9 GB at start → **7.7 GB after 2h21m**. It is still growing. Restart the server between long runs; watch `ps -o rss= -C llama-server`. Symptom of the thrash: generation drops to 0.4 tok/s and looks like a slow model.
- **`enable_thinking` is the real lever**, not `/no_think`. `chat_template_kwargs: {"enable_thinking": false}` → ~2 output tokens (40x faster on MCQs). Appending `/no_think` to the prompt still burns 80–120 reasoning tokens.
- **Prebuilt llama.cpp:** the `/releases/latest` endpoint carries only `nightly-tag.txt`. List releases and take the newest tag with `llama-bNNNNN-bin-ubuntu-x64.tar.gz`.
- **HF benchmarks without a framework:** `https://datasets-server.huggingface.co/rows?dataset=...&config=...&split=...&offset=&length=100`, max 100 rows per request.
- Full method, pitfalls and the tested harness: Hermes skill **`local-gguf-capability-eval`** → `scripts/eval_harness.py`.

---

## 9. Open questions — flag, do NOT resolve

1. **Corpus source.** MSK About Herbs + LiverTox are open. LiverTox is NIH-public. EMA/ESCOP monographs and Natural Medicines (TRC) are licensed — Josh needs to decide whether to buy or stay open-only. Cost differs by an order of magnitude.
2. **TCM in scope?** Josh uses a TCM lens personally. Adding Chinese-language materia medica roughly doubles the corpus and needs a Chinese-capable embedding model.
3. **Q4 vs Q8 for the shipping target.** Q8 wins on discipline (0/46 vs 5/46 hitting the cap) but costs 1.07 GB. On Josh's M1 Max this is free; on a phone it is not.
4. **Practitioner testing.** Nobody outside Josh has used it. Three to five naturopaths reviewing 20 real de-identified consults would settle more than another 100 synthetic items.
5. **Public naming.** `materia` collides with materia.com (music-tech). Irrelevant for a local project; needs a vet before any public release.

---

## 10. First actions, in order

1. **Establish local state.** `hostname; nproc; free -m; df -h /home; ls ~/models/minicpm5/; curl -s localhost:8099/health`. If the server is not up, start it:
   ```bash
   cd ~/bin/llamacpp/llama-b11936 && ./llama-server \
     -m ~/models/minicpm5/MiniCPM5-2B-Q8_0.gguf \
     -c 4096 -np 2 -t 6 --jinja --no-reasoning-preserve --port 8099
   ```
2. **Verify one number before trusting the rest.** Re-score `results/v2_budget.jsonl` from the `got` field: `python3 docs/rescore.py results/v2_budget.jsonl` must print 99/104 = 95.2%. If you get 101/104 you are re-parsing truncated text (§8).
3. **Prove the OCR path before building on it (Gate 0).** Download `MiniCPM-OCR-1.0-gguf` Q4_K_M + `mmproj-model-f16-4x.gguf`, OCR one real lab report (a text PDF and a phone photo of a printout — ideally the same panel in both forms), and check that every analyte, value, unit and the lab's own interval survive into a table. Test at least one non-US report: the unit-system fault line is SI (pmol/L, mmol/L, nmol/L) vs US conventional (ng/dL, mg/dL), and the model's priors default to US units. Then run `MiniCPM-OCR-Jev` over the same page and confirm its per-region scores separate the clean values from a deliberately blurred or skewed region. **Gate: 100% of numeric fields recovered correctly on a clean page; Jev score ≥0.85 on clean regions and visibly lower on the degraded one.** If OCR fails here, the lab-upload feature is speculation and Josh needs to know immediately.
4. **Run Gate 1 (PubMedQA, data already on disk).** Cheap, and it settles recall-vs-reasoning before you invest in the corpus.
5. **Build the corpus to the §2.1 schema**, in the stated order — reference intervals first, because it unblocks the entire lab path and is finite. Every document needs a resolvable identifier; anything you cannot cite is a note, not corpus.
6. **Wire retrieval and re-run the 104-item panel** under the same 60-word budget. Compare against 95.2%, paired, per category.
7. **Report honestly:** real outputs, explicit recommendation, the denominator and CI on every number, no hype, no fabricated results.

---

## Josh's context

- Vibe coder, pragmatic, high velocity. Runs parallel subagent swarms on large tasks. Hates CSS-guessing.
- **Direct answer first, verdict before evidence.** No warm-ups. Options with a clear recommendation.
- Wants plain-language analogies and hand-holding on mechanisms, but not on decisions.
- Cost-conscious; anti-closed-source; **no OpenAI, open weights only**.
- No meta-commentary in deliverables — no ✅, no process notes, no "let me know if you need anything else".
- Explain decisions in chat; do not point at markdown files instead of answering.
- Chinese name 乔森 (Qiáo Sēn); Sunshine Coast, Brisbane time. Health-food retail management background — he will fact-check herbal claims.
- **The lesson he does not want repeated:** do not present a number you cannot reproduce from an artifact. This handover exists partly because that happened once.
