# Gate 0 — does the OCR path survive a real lab report?

**Run:** 2026-10-28 · **Model:** `MiniCPM-OCR-1_0-Q4_K_M.gguf` + `mmproj-model-f16-4x.gguf` (Apache-2.0)
**Runtime:** llama.cpp b11936, CPU only, `-c 16384 -t 6 --n-gpu-layers 0`, port 18499
**Artifacts:** `results/gate0_clean.json`, `results/gate0_degraded.json`

## Verdict

**Pass, with a small-n caveat.** 12/12 numeric values and 12/12 reference intervals recovered exactly, with
zero silently wrong values, on both a clean 200 dpi render and a degraded variant. The path is viable; Jev
(Phase B) is not needed to make the lab upload defensible at this stage.

The caveat is not the model, it is the test: one document, twelve fields, and a synthetic degradation rather
than a real phone photograph. n=12 gives a 95% CI of [75.7, 100] on field accuracy. Gate 0 should be re-run
when Josh supplies a real text-PDF + phone-photo pair of the same panel.

## Document

`NutriPath / Genova Diagnostics — "0013 Bloodspot Amino Acids 11 Profile" sample report` (public PDF,
watermarked "Sample Report", patient "John Doe"). Page 2 is a dense multi-column results table: analyte,
result, a quintile-ranking bar with its own min/max labels, and the lab's 95% reference range. SI units
(µmol/L), dates in `MM/DD/YYYY`, an "L" flag column, and an asterisked ratio row.

Chosen deliberately because it is hostile to naive extraction: the numbers in the bar labels (92, 183, 12,
28…) sit between the result and the reference range, so anything that "finds the numbers" scrambles the
values. Ground truth was transcribed by reading the 200 dpi render (`samples/ground_truth/nutripath-p2.json`).

Provenance and licence note: `samples/provenance.json`. The document is used locally for evaluation only and
is **not** redistributed — `samples/raw/` is gitignored. Corpus eligibility rules do not apply to eval
fixtures, but the distinction is recorded so it cannot leak into a shipped corpus.

## Method

1. PDF → PNG at 200 dpi (pymupdf).
2. `Table Recognition:` prompt → OTSL (`<fcel>`, `<lcel>`, `<ecel>`, `<nl>`), which preserves columns.
3. Deterministic OTSL → rows → records: numbered analyte, next numeric cell is the result, last range-shaped
   cell is the lab interval, unit taken from the header (with a per-row `ratio` override).
4. Deterministic plausibility gate (`materia/extract.py`): physiological bounds, recognised unit, interval
   present and not inverted, collection date present, value not 100× outside the interval. Bounds are wide
   plausibility bounds, **not** reference intervals.
5. Two-read check: text layer versus OCR, compared as a set of numbers. The text layer on this document is
   structurally scrambled (column order is not preserved), so row alignment is impossible; the check is
   completeness, and it is labelled as such in the artifact.

## Results

| Condition | Rows | Values | Ref intervals | Silent wrong | Two-read | OCR time | Tokens |
|---|---|---|---|---|---|---|---|
| Clean render, 200 dpi | 12/12 | **12/12 = 100% [75.7, 100]** | 12/12 | **0** | 33/33 both reads | 26.7 s | 799 |
| Degraded (4° rotate, 0.6×, JPEG q40) | 12/12 | **12/12 = 100% [75.7, 100]** | 12/12 | **0** | 33/33 both reads | 86.8 s | 769 |

No spurious rows, no missing rows, no wrong values, no wrong intervals in either condition. RSS after load:
1.96 GB; the degraded image took 3.2× longer for the same output (more visual tokens for less information).

## What broke on the way, and what now prevents it

| Failure | Cause | Fix | Regression test |
|---|---|---|---|
| Output cut mid-table | 8k context: ~1.8k visual tokens + 3k output overflowed a 1700×2200 page | OCR context raised to 16384; truncation detected (`</otsl>` missing or `finish=length`) | `test_truncated_otsl_does_not_crash` |
| 0 rows extracted | `re.split` with a capture group returns the group body ("fcel"), not the tag ("<fcel>") | tokenizer captures the whole tag | `test_parse_otsl_rows_and_cells` |
| Bar labels could have become results | naive "first number" extraction | OTSL cells keep columns; result is the cell after the analyte | `test_extract_uses_result_not_bar_labels` |
| `63-220` read as `63` and `-220` | hyphen treated as a minus sign | lookbehind in `numbers_in` | covered by two-read count |
| Ratio row inherited µmol/L | single unit per table | per-row `ratio` override | `test_extract_uses_result_not_bar_labels` |

## Limits, stated plainly

- **One document.** Re-run before trusting the ingest path on general panels.
- **Synthetic degradation.** A rotated, downscaled JPEG is cleaner than a phone photo of a curl-edged
  printout under a ceiling light. Josh's real pair is the test that matters.
- **The plausibility table covers 12 amino acids plus common panel analytes.** Anything not in
  `materia/extract.py::PLAUSIBLE` is flagged "not in plausibility table" and goes to review — safe, but it
  means a new panel type needs its bounds added before it can auto-accept anything.
- **Header block is weak.** OTSL flattened the patient/date block: the date-of-birth label came out as
  `Patient: 02/05/1962`, so patient identity and DOB are not reliable from the table parse. They are
  supplementary fields; the collection date is present in the header row and was captured. Page-level
  deterministic checks (patient/date) are still Gate 0 work, and a failure there must route to review.

## Reproduce

```bash
.venv/bin/python scripts/gate0.py --image samples/pages/nutripath-p2.png \
  --truth samples/ground_truth/nutripath-p2.json --pdf samples/raw/nutripath-aminoacids.pdf --label clean
.venv/bin/python scripts/make_sample_variants.py
.venv/bin/python scripts/gate0.py --image samples/pages/nutripath-p2-degraded.jpg \
  --truth samples/ground_truth/nutripath-p2.json --pdf samples/raw/nutripath-aminoacids.pdf --label degraded
```
