# Corpus v0 — what is in it, what is not, and why

**Built:** 2026-10-28 · **Validator:** `python -m materia.corpus.schema validate corpus/docs` → schema OK
**Index:** `python -m materia.corpus.index` → `corpus/index.sqlite`

## Numbers

| Metric | Value |
|---|---|
| Documents | **330** |
| Chunks | 3,794 |
| Words | 463,842 |
| Chunks per document (mean) | 11.5 |
| Licence-clear (redistributable) | **330 / 330** |
| Publication dates | 2006-07-13 → 2026-09-25 |

| Source | Docs | Tier | Jurisdiction | Licence | Access |
|---|---|---|---|---|---|
| Health Canada NNHPD | 222 | regulatory | ca | OGL-Canada | HTML, 182 single + 40 multi-ingredient |
| NCCIH (NIH) | 56 | compendium | us | US federal, public domain | HTML |
| NCI PDQ | 23 | primary | us | US federal, public domain | HTML |
| EMA (HMPC) | 21 | regulatory | eu | EMA reuse, attribution | PDF, harvested from the sitemap |
| Europe PMC CC-BY | 8 | primary | international | CC BY | REST API, licence-filtered |

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
