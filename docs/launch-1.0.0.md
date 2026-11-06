# Launch copy — materia 1.0.0

Social copy for the 1.0.0 release. Claims are limited to what `docs/validation.md` records:
contract tests and a self-authored vignette set, not clinical accuracy. Use the teaser
(`build/marketing/materia-teaser-1080p.mp4`, also attached to the GitHub release) as the visual.

## Primary post

> **materia 1.0.0 — a cited clinical decision-support engine that runs on your own machine.**
>
> Drop in a blood panel: it flags the findings against the lab's own intervals, maps them to cited
> clinical patterns, and returns ranked supplement and herb options with dose ranges, monitoring and
> contraindications. Every claim resolves to a source chunk — if a citation or the dose isn't in that
> chunk, the option is withheld and shown as withheld. Safety screening is deterministic code, not model
> judgement. Options for a practitioner to accept, modify or reject; not a diagnosis, not a prescription.
>
> **Stack (100% open weights, no GPU, no cloud):** OpenBMB `MiniCPM5-2B` (Q4/Q8 GGUF) for the grounded
> chat and passage reranking, OpenBMB `MiniCPM-OCR-1.0` for lab-report table OCR, llama.cpp on CPU,
> Python 3.12, SQLite BM25 retrieval with section weighting, a YAML evidence graph with a deterministic
> safety screen, and a no-framework local web app.
>
> 401 licence-clear documents · 5,207 citable chunks · 24 patterns / 31 options · 164 tests ·
> 73/73 contract cases. Clinician labels are still 0/50, so there is no clinical-accuracy claim yet —
> the measured/unmeasured boundary is in `docs/validation.md`.
>
> github.com/RegeneratusLabs/materia

## Short variant

> materia 1.0.0: blood panel in, cited supplement and herb options out — every claim traceable to a
> source, withheld when the citation doesn't hold. 100% open weights on CPU: OpenBMB MiniCPM5-2B for
> chat and reranking, MiniCPM-OCR-1.0 for lab-report OCR, llama.cpp, SQLite BM25, a deterministic
> safety screen. Not a diagnosis, not a prescription. Local, no cloud, no telemetry.
> github.com/RegeneratusLabs/materia

## Hashtags

`#openweights` `#OpenBMB` `#llamacpp` `#healthtech` `#naturopathic` `#integrativemedicine` `#localai`

## Notes

- Do not quote a clinical-accuracy percentage. The only percentages that exist are contract-test and
  MCQ-benchmark results, and the vignettes were written by the same project that wrote the engine.
- "No GPU" and "CPU-only chat" are measured (Q4 and Q8 2B GGUF). A 3B–7B CPU model is unmeasured.
- The teaser's on-screen claims are limited to what the app displays plus the stated guarantees
  (local, cited, no diagnosis). See `build/marketing/README.md`.
