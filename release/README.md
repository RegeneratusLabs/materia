# materia 1.0.0 — local product

Extract, install, run:

```bash
tar xzf materia-1.0.0-local.tar.gz
cd materia-1.0.0
./install.sh
./run.sh
```

The default sample is a **synthetic nutrient/lipid panel** and works with no model. The
amino-acid sample is a coverage-gap demo. Uploads need the OCR weights and `--start-ocr`.

No GPU, no vLLM, no cloud calls, no telemetry. The optional chat model is a small CPU GGUF
served by `llama.cpp`; the deterministic responder works without it.

This is a local clinical decision-support product, not a medical device. It does not diagnose,
prescribe, or claim clinical accuracy. Read `docs/validation.md` before quoting any number.
