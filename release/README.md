# materia — practitioner feedback build (0.2.0)

This is the first packaged build of the Figtree Bench front end with the lab half of the engine behind it. It is a local web app: one process, one browser tab, no cloud calls, no telemetry.

It is a **feedback build**, not a clinical product. It does not diagnose, generate a protocol, or claim clinical accuracy.

## What is in the box

- `materia serve`: a small local web app and JSON API, standard library only
- the Figtree Bench review surface (`materia/webapp/static/`)
- the local lab pipeline: PDF render → MiniCPM-OCR → OTSL row extraction → deterministic plausibility checks → human confirmation
- a sample amino-acid report that works without any model running
- a local feedback record at `~/.materia/feedback.jsonl`

Not in the box: model weights (they are large and licensed separately), authentication, a database, or a hosted multi-user service.

## Requirements

- Python 3.12+
- the wheel: `release/materia-0.2.0-py3-none-any.whl`
- for uploads:
  - `llama.cpp` build with `llama-server`
  - `MiniCPM-OCR-1_0-Q4_K_M.gguf` and `mmproj-model-f16-4x.gguf`
- for the sample case: none of the model files are needed

The reasoning model is not used by this lab surface. Starting the OCR engine stops any reasoning server because the two must not run together on a 16 GB box.

## Install

From the release folder, the two scripts do the same thing as the manual steps:

```bash
cd release
./install.sh
./run.sh
```

Manual install:

```bash
python3 -m venv ~/.materia-venv
~/.materia-venv/bin/pip install --upgrade pip
~/.materia-venv/bin/pip install release/materia-0.2.0-py3-none-any.whl
```

Point at the local models (edit the paths to match the machine):

```bash
export MATERIA_LLAMA_DIR="$HOME/bin/llamacpp/llama-b11936"
export MATERIA_OCR_GGUF="$HOME/models/minicpm-ocr/MiniCPM-OCR-1_0-Q4_K_M.gguf"
export MATERIA_OCR_MMPROJ="$HOME/models/minicpm-ocr/mmproj-model-f16-4x.gguf"
```

Optional: keep feedback in a different place with `MATERIA_APP_DATA` (default `~/.materia`).

## Run

Sample only, no models:

```bash
~/.materia-venv/bin/materia serve --host 127.0.0.1 --port 8765 --open
```

With OCR for uploads:

```bash
~/.materia-venv/bin/materia serve --start-ocr --host 127.0.0.1 --port 8765 --open
```

The server prints the URL. Open it in a browser.

`--start-ocr` starts the OCR model before serving. Uploads also start it on demand if the weights are configured. The first start takes a while on CPU; reading one uploaded page can take several minutes on CPU; 5+ minutes was observed on the 6-core host.

The sample starts with **0 of 12 checked**. That is deliberate: no value is marked as checked until someone compares it with the page. The sample's three lab-flagged values open in the “Needs a look” state.

## What a practitioner can do

1. Open the **sample report** and step through the 12 values.
2. Select a value; compare it with the highlighted row on the page.
3. Tick “I compared this number with the report”, then “Looks right”.
4. Open **What this means** for the lab's own notes and the explicit limits.
5. Choose **New report** and upload a PDF/PNG/JPG.
6. Use **Feedback** to leave a note; it is stored locally.

The sample is pre-labelled as a public sample report. Uploaded reports are labelled as uploaded reports.

## Privacy and safety

- **Use de-identified reports only.** There is no PII de-identification model in this build.
- Uploads are stored in a temporary directory and removed when the server exits. Do not rely on them as a record.
- The sample and uploaded reports have no row overlay on uploads; the sample keeps its printed-row highlight.
- Confirmed values are browser/session state, not a medical record.
- The server has **no authentication**. Bind it to `127.0.0.1` or a private tailnet. Do not expose it publicly.
- The app has no telemetry. Feedback is local JSONL.
- Nothing here is a diagnosis, a protocol, or a substitute for a practitioner's judgement.

## Tailscale preview (for Josh)

```bash
setsid nohup ~/.materia-venv/bin/materia serve \
  --host 100.86.176.62 --port 8777 \
  >/tmp/materia-app.log 2>&1 </dev/null &
echo $! >/tmp/materia-app.pid
```

Open `http://homelab.taildace6c.ts.net:8777/`. Tailnet only; no Funnel. Stop with:

```bash
kill "$(cat /tmp/materia-app.pid)"
```

## Build the wheel

```bash
.venv/bin/pip wheel . --no-deps -w release
sha256sum release/*.whl > release/SHA256SUMS
```

The wheel contains the HTML, JS, CSS, Figtree font files, the sample image, and the sample ground truth. It does **not** contain model weights.

## Known limits in this build

- Lab review only. The Ask and Symptom flows are not in this surface yet.
- Uploads try up to the first four pages of a PDF. Uploaded reports have no row-highlight overlay; the sample keeps its printed-row highlight.
- OCR quality is not clinically validated, and there is no per-field confidence model in this build. A field that cannot be checked is sent to review.
- No authentication, multi-user separation, audit log, or durable case store.
- No PII de-identification.
- The sample is 12 amino-acid values from a public Genova report; it is not a patient record.

## Feedback loop

Collect `~/.materia/feedback.jsonl` after the cohort (or the path shown in the feedback dialog, which follows `MATERIA_APP_DATA`). Each line is JSON: timestamp, message, optional contact, page, version, user agent. Do not ask practitioners to include patient details.

The questions worth asking the first cohort:

- Did the page feel like a review, or still like a lab console?
- Which value did you not trust, and why?
- Was the confirmation step obvious without reading instructions?
- What was missing before you would use this in a consult?
- Did the “What this means” page say too much or too little?
