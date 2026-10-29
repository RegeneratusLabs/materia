# Corpus v0 — what is in it, what is not, and why

**Built:** 2026-10-28 · **Validator:** `python -m materia.corpus.schema validate corpus/docs` → schema OK
**Index:** `python -m materia.corpus.index` → `corpus/index.sqlite`

## Numbers

| Metric | Value |
|---|---|
| Documents | **367** |
| Chunks | 3,951 |
| Words | 463,842 |
| Chunks per document (mean) | 11.5 |
| Licence-clear (redistributable) | **367 / 367** |
| Publication dates | 2006-07-13 → 2026-09-25 |

| Source | Docs | Tier | Jurisdiction | Licence | Access |
|---|---|---|---|---|---|
| Health Canada NNHPD | 222 | regulatory | ca | OGL-Canada | HTML, 182 single + 40 multi-ingredient |
| NCCIH (NIH) | 56 | compendium | us | US federal, public domain | HTML |
| NCI PDQ | 23 | primary | us | US federal, public domain | HTML |
| EMA (HMPC) | 21 | regulatory | eu | EMA reuse, attribution | PDF, harvested from the sitemap |
| Europe PMC CC-BY | 8 | primary | international | CC BY | REST API, licence-filtered |
| MedlinePlus lab tests | 18 | compendium | us | US federal, public domain | encyclopedia articles, Normal/Abnormal Results |
| MedlinePlus symptoms | 19 | compendium | us | US federal, public domain | "When to Contact a Medical Professional" |

Section mix: other 1,384 · dosage 679 · indications 412 · adverse effects 340 · methodology 233 · cautions 227 · evidence 126 · contraindications 109 · interactions 15 · pharmacology 2.
Assertion mix: other 1,619 · safety 691 · dose 679 · efficacy 538.

## Coverage against the 104-item panel

`scripts/grounding.py` → `data/panel_grounding.json`.

**31/104 items (29.8%) have a retrieved chunk that lexically supports the gold option** (≥25% content-word
overlap). By category: lab 11/30, herb–drug 8/26, herb–safety 5/20, nutrient–drug 4/12, referral 0/8.

That number is a *lower bound on coverage* and an upper bound on nothing. The test is deliberately dumb —
a gold option phrased as a conclusion ("reduced contraceptive efficacy via CYP3A4 induction") shares few
content words with a monograph that says "do not use with oral contraceptives". It is used as a coverage
instrument, not as an accuracy claim. The honest reading: **the corpus grounds roughly a third of the panel
lexically, and the referral branch is empty** — which is exactly the gap the NICE source was meant to fill.

## What is missing, and why

| Source | Status | Reason |
|---|---|---|
| NICE CKS (referral red flags) | **blocked** | `cks.nice.org.uk` returns 403 "CKS is only available in the UK" from this host. Needs a UK-routed fetch or a manual download. |
| ODS fact sheets | **blocked** | Cloudflare interstitial on `ods.od.nih.gov`. |
| LiverTox / LactMed (NCBI Bookshelf) | **blocked** | reCAPTCHA challenge on `ncbi.nlm.nih.gov/books`. |
| NHS inform | **blocked** | 403 from this host. |
| EMA EU herbal monographs | **deferred** | Documents are open and the sitemap enumerates them, but it is 164 pages (~1.1 GB of XML) and rate-limits. A targeted slug crawl for the ~24 panel herbs is the cheaper path; the full sitemap harvest is a batch job for later. |
| SA Pathology reference intervals | **deferred** | 33-page SI-unit handbook (approved 30/7/26) is perfect for the lab path, but the PDF carries no licence statement. Not shipped until the terms are confirmed. |
| MSK About Herbs | **excluded** | Free to read, not redistributable. The handover called this "open"; it is not. |
| WHO monographs | **excluded** | Mostly CC BY-NC-SA; non-commercial terms conflict with an Apache-2.0 product. |
| ESCOP, Natural Medicines | **excluded** | Paid, redistribution restricted. |

Access was tested, not assumed: each blocked source returned 403/404/reCAPTCHA from this host on
2026-10-28. The adapters are written so a manually downloaded file can be dropped into `corpus/raw/` and
ingested without a crawler.

## Freshness

Every document carries `revised`, `retrieved_at`, `next_review_due` (regulatory 12 months, compendium 6,
primary 120) and a `sha256` of the fetched bytes. `next_review_due` is rendered with the citation. The
refresh job is **not yet written** — it is scheduled work, listed as such rather than claimed.

## Reproduce

```bash
.venv/bin/python -m materia.corpus.hc        # Health Canada: 182 single + 41 product
.venv/bin/python -m materia.corpus.web --source nccih
.venv/bin/python -m materia.corpus.web --source nci
.venv/bin/python -m materia.corpus.schema validate corpus/docs
.venv/bin/python -m materia.corpus.index
.venv/bin/python scripts/grounding.py
```

Raw source files are not committed (`corpus/raw/` is gitignored); the parsed documents are, because both
licences permit redistribution with attribution. Health Canada content is attributed by `source` and `url`
on every document; NCI and NCCIH likewise.


## Update 2026-10-29 — EMA and CC-BY additions, coverage measured

- **EMA**: 131 monograph URLs harvested from the sitemap (164 pages, 129 s, 4 workers), of which 21
  concern panel herbs (ginkgo, echinacea, valerian, saw palmetto, milk thistle, garlic, lavender,
  passionflower, lemon balm, chamomile, green tea, frankincense/boswellia, feverfew, curcuma).
  Their monographs use the fixed numbered structure (4.1 indications … 4.8 undesirable effects), so
  chunks carry real claim types. Hypericum, panax, withania and piper were **not found** in the sitemap
  document set — the sitemap is not a complete inventory, and a targeted per-herb crawl is still needed.
- **Europe PMC CC-BY**: 18 targeted queries, 16 accepted, then 8 rejected by hand as off-topic
  (recorded in `corpus/rejected.json`). 8 shipped. Abstracts only, `tier: primary`,
  `date_precision: year` because only the publication year is available.
- **Coverage** (`scripts/coverage.py` → `data/panel_coverage.json`): **34/104 = 32.7%** of panel items
  have a retrieved chunk from the question's entity document carrying the right claim type.
  By category: herb–drug 73.1%, herb–safety 45.0%, nutrient–drug 16.7%, lab 6.7%, referral 0%.
  Coverage is not support — a stratified sample is audited separately.


## Update 2026-10-29 (later) — MedlinePlus fills the lab and referral branches

37 public-domain NLM MedlinePlus encyclopedia articles: **18 lab test pages** (ferritin, serum iron,
TIBC, B12, TSH, free T4, T3, ALT, AST, GGT, CRP, CBC, A1C, ESR, creatinine, calcium, magnesium,
cholesterol) and **19 symptom pages** with "When to Contact a Medical Professional" sections.

- **Lab coverage 0 → 60%** (18/30), referral 1/8 → 3/8, overall **42.3%**.
- Unlike the herb branch, the lab coverage is genuinely supported: audited chunks are the normal ranges
  and abnormal-result interpretations for the analyte in question (Free T4 0.8–1.9 ng/dL, B12 <299 pg/mL
  as a deficiency threshold, TIBC higher in iron deficiency).
- **Accuracy did not move**: lab-only retrieval stayed at 94/104. The model already knew these items; the
  corpus now makes them citable rather than better answered. Coverage is not the binding constraint on
  accuracy — it is the binding constraint on *citation*.

## Coverage has two denominators (2026-10-29, round 6)

Reporting a single coverage number was misleading. Two populations behave differently:

| Population | n | Covered | Rate |
|---|---|---|---|
| All panel items | 104 | 44 | 42.3% |
| **Herb/nutrient questions that name their subject** | 53 | 20 | **37.7%** |
| Lab questions | 31 | 20 | 64.5% |
| Questions that name no subject | 20 | (4 spurious) | not a coverage population |

**Correction (round 8).** The 60.7% reported earlier was wrong. It used keyword entity detection as the
denominator, which attributed spurious entities — a question asking "which herbal product causes
hepatotoxicity" was counted as a fish-oil question because the word appeared in it. Hand-labelling all 104
questions (`data/panel_subject_labels.json`) gives 53 that name their subject, 31 lab, and 20 that name no
subject at all. On the correct denominator, herb coverage is **37.7%**, not 60.7%.

The remaining 48 items **do not name an entity at all** — "which of these is a red flag", "which
supplement interacts with…", or an analyte alone. Entity-based coverage cannot apply to them, and they are
answered closed-book, where they score 100% (73/73 of the non-lab panel).

`scripts/coverage_gaps.py` → `data/coverage_gaps.json` classifies every uncovered item:

| Reason | n | What it means |
|---|---|---|
| No entity detected in the question | 34 | out of scope for entity retrieval, not a corpus gap |
| Entity document exists, no chunk of the right claim type/terms | 15 | **retrieval precision**, not acquisition |
| Lab analyte not covered by a test document | 11 | missing lab articles for those analytes |

Only **two** items are genuine missing-document gaps (comfrey, berberine). Everything else is either out of
scope by design or a precision problem. That is the honest end state of Phase 2: coverage of the questions
retrieval is built for is 60.7%, the residual is mostly precision, and chasing 100% across a denominator
that includes non-entity questions would be measuring the wrong thing.

Corpus is now **376 documents / 4,005 chunks** after adding 9 more lab analytes (albumin, bilirubin, HDL,
LDL, lipid profile, triglycerides, potassium, sodium, uric acid). Three attempted articles were skipped by
the parser (folate deficiency, vitamin D, magnesium deficiency) because they carry no mappable
normal/abnormal results sections — recorded as skipped rather than forced in.

## Entity-matching bug and its effect (round 8)

`find_entities` matched aliases as **substrings**, so the fish-oil alias `epa` matched inside
"h**epa**tic" and "h**epatotoxicity**". Consequences: a fish-oil document was attributed to questions about
liver injury, coverage was inflated, and reference selection could pick a document about the wrong substance.
Fixed to whole-word matching with lookarounds (apostrophes and hyphens still work: "st john's wort",
"5-htp"), with a regression test.

Effect on the panel: H03 ("which herbal product is associated with hepatotoxicity") previously retrieved a
fish-oil monograph; it now returns saw-palmetto drug-induced liver injury and liver-failure text. Coverage
did not move (37.7%), because the spurious matches were concentrated in the 20 no-subject items — but the
questions that *do* name their subject now retrieve better material.

**All panel numbers quoted before this fix were produced with the buggy matcher.** The shipped configuration
is being re-run under the fixed code so the quoted figure matches the implementation.
