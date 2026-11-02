# materia — four web UI directions

**Status:** static design mockups, 2026-10-30. Not production code. Not current CLI output.

**Preview over Tailscale:** `http://homelab.taildace6c.ts.net:4180/` — this is live while the preview server is running (see [Preview](#preview-over-tailscale)). The server is bound to the Tailscale interface only, so it is reachable from the tailnet and not the public internet.

## What this is

Four clickable directions for the materia interface, each demonstrated on its strongest surface. They use real source quotes from the current corpus, the real public sample lab report from Gate 0, and the product's hard rules: cite or label, show conflicts instead of synthesising them, stop on red flags, and never hide a safety veto.

| # | Direction | Thesis | Hero surface | Secondary state |
|---|---|---|---|---|
| 01 | **Reading Room** | The answer is the interface | Cited answer + source rail | Memory/uncited mode |
| 02 | **Chartroom** | The case is the interface | Case sheet + safety rail | Emergency stop |
| 03 | **Bench** | The document is the interface | Scan + extracted lab values | Interpretation limits |
| 04 | **Atlas** | The corpus is the interface | Provenance/conflict map | Coverage with n and CI |

Open [index.html](index.html) for the gallery, screenshots, comparison table, and the recommendation.

## Recommendation

Build **Reading Room** as the answer surface and carry **Chartroom's permanent safety rail** into it. Reading Room makes the citation the interface, which is the product thesis. Chartroom contributes the safety rail and the stop state. Bench is the obvious lab-review flow; Atlas is the best provenance and corpus-QA view.

If only one direction is built next, build Reading Room.

## Files

```text
docs/mockups/
  index.html                  gallery, comparison, recommendation
  01-reading-room.html        cited answer, conflict block, memory mode
  02-chartroom.html           case queue, safety rail, emergency stop
  03-bench.html               scan review, confirmation, interpretation limits
  04-atlas.html               provenance map, source comparison, coverage
  05-bench-type.html          Bench with four type systems and a live switcher
  06-bench-figtree.html        the chosen Figtree direction, rebuilt soft
  assets/
    base.css                  shared reset, a11y, drawer primitives
    fixtures.js               all mock content; JSON after the assignment
    fonts/                    brand faces (local)
    fonts/type-studies.css    @font-face rules for the four type systems
    fonts/type/               Lora, Fraunces, Nunito, Nunito Sans, Figtree,
                              DM Mono, JetBrains Mono
    nutripath-p2.png          web-sized derivative of the public sample report
    shots/                    generated 1440x1000 screenshots
  tools/check.py              static checks, quote validation, screenshot runner
  README.md
```

## Bench, Figtree rebuild

[`06-bench-figtree.html`](06-bench-figtree.html) is the chosen next step from the type study: Bench in Figtree, rebuilt to feel like a calm review rather than a lab console.

What changed:
- cool sage-mist palette with a botanical line accent; no cream background, no dark console
- Figtree throughout, with tabular figures instead of monospace for the values
- a 30 px card language, a progress ring, and pill controls instead of a dense table
- twelve values grouped the way the lab groups them, with one row expanded at a time
- language softened: “What we read”, “To finish”, “Needs a look”, “Looks right”
- the same hard mechanics underneath: source image, two reads, reading certainty, a human confirmation before a value is checked
- a separate “What this means” state that keeps the interpretation to the lab's own notes

Direct link: `http://homelab.taildace6c.ts.net:4180/06-bench-figtree.html`

## Bench type study

[`05-bench-type.html`](05-bench-type.html) keeps the Bench layout, cool palette, data, and interactions fixed and changes only the type. The switcher in the top bar flips between four softer systems; the page also accepts `?type=lora`, `?type=fraunces`, `?type=nunito`, or `?type=figtree`.

| System | Display | Body | Numeric | Feel |
|---|---|---|---|---|
| Soft editorial | Lora | Nunito Sans | IBM Plex Mono | Rounded serif curves over a soft humanist body |
| Warm serif | Fraunces | Nunito Sans | DM Mono | The warmest; a soft, slightly wonky serif at a lighter weight |
| Rounded | Nunito | Nunito Sans | DM Mono | Fully rounded terminals; friendly but legible |
| Clean soft | Figtree | Figtree | JetBrains Mono | Soft geometric sans; modern and quiet |

All four keep Bench's original cool palette, plus a 14 px panel radius and pill-shaped controls. The background is not cream. The type files are local in `assets/fonts/type/`; they were downloaded from Google Fonts under the SIL Open Font License 1.1. No runtime network request is made.

Screenshots: `assets/shots/05-bench-type-*.png`.

## How to open

Open `index.html` directly in a browser, or use the Tailscale preview. The Bench type study is at `05-bench-type.html`. No build step, no package install, no network requests at runtime.

```bash
xdg-open docs/mockups/index.html
```

If a direct `file://` open is inconvenient, serve the folder locally:

```bash
python3 -m http.server 4180 --bind 127.0.0.1 --directory docs/mockups
```

## Preview over Tailscale

The preview is a static file server bound to the host's Tailscale address. It serves only `docs/mockups/`, so the repo, corpus, results, and logs are not exposed.

```bash
setsid nohup python3 -m http.server 4180 \
  --bind 100.86.176.62 \
  --directory /home/josh/projects/materia/docs/mockups \
  >/tmp/materia-mockups.log 2>&1 </dev/null &
echo $! >/tmp/materia-mockups.pid
```

Check it:

```bash
curl -fsS http://100.86.176.62:4180/ | grep -q '<title>materia'
curl -fsS -o /dev/null -w '%{http_code}\n' http://homelab.taildace6c.ts.net:4180/
curl -fsS -o /dev/null -w '%{http_code}\n' http://100.86.176.62:4180/assets/fonts/fonts.css
```

Links:

- `http://homelab.taildace6c.ts.net:4180/` — gallery, MagicDNS, preferred
- `http://homelab.taildace6c.ts.net:4180/06-bench-figtree.html` — soft Figtree Bench
- `http://homelab.taildace6c.ts.net:4180/05-bench-type.html` — four type systems
- `http://100.86.176.62:4180/` — direct Tailscale IP fallback

This is tailnet-only. There is no Funnel and no public exposure. The mockups contain no real patient data. The sample report is a public “Sample Report” fixture, visibly labelled.

Stop it:

```bash
kill "$(cat /tmp/materia-mockups.pid)"
```

If port 4180 or the direct bind is blocked, the fallback is a scoped Tailscale Serve mapping on a free port (for example 8451). Do not change the existing mappings on 443 or 8443–8450. The preview server is the low-impact option and does not modify Tailscale's serve config.

## Data provenance

`assets/fixtures.js` is the single source of mock content. Quotes are verbatim modulo whitespace and line breaks; `tools/check.py` verifies each one against `corpus/index.sqlite`.

| Used for | Chunk(s) |
|---|---|
| Ginkgo / warfarin conflict | `ema-ginkgo-biloba-l-folium#005`, `hc-nhpid-ginkgo-biloba2#006`, `nccih-ginkgo#006` |
| Ginkgo adverse effects | `ema-ginkgo-biloba-l-folium#008` |
| Valerian dose / evidence | `ema-valeriana-officinalis-l-radix#002`, `nccih-valerian#004` |
| St John's wort contraindications | `hc-nhpid-stjohnswort-millepertuis-oral2#007`, `nccih-st-johns-wort#005` |
| Evening primrose divergence | `nccih-evening-primrose-oil#004`, `hc-nhpid-primrose-onagre2#002` |
| Lab reference intervals | `medlineplus-003490#005`, `medlineplus-003705#005`, `medlineplus-003684#005` |
| Emergency red flag | `materia/rules/red_flags.yaml` (`rf-chest-pain`, NHS citation) |

Source metadata (publisher, tier, jurisdiction, date, next review, identifier, licence, checksum) is copied from the indexed documents and checked against the same rows.

The lab page is a web-sized derivative of `samples/pages/nutripath-p2.png`, itself a render of the public Genova Diagnostics “0013 Bloodspot Amino Acids 11 Profile” sample report hosted by NutriPath (AU). It is a local Gate 0 fixture, not corpus, and not patient data.

## What is real, what is illustrative

Real:
- source quotes and metadata
- the sample lab report values and the lab's own intervals
- corpus coverage numbers from `docs/gate_report.md`
- the product rules the UI enforces: citation per claim, conflicts shown, veto removed before generation, red-flag stop before a model call

Illustrative:
- the cases and the model-written answer prose
- read-confidence percentages (not a `MiniCPM-OCR-Jev` calibration)
- the “two reads agree” status line
- the interface itself

Not built:
- backend, API, routing, authentication
- model or OCR calls
- state persistence
- a framework or component library

## Checks

```bash
python3 docs/mockups/tools/check.py
python3 docs/mockups/tools/check.py --shots
```

The checker uses only the Python standard library. It verifies seven pages (the gallery, four directions, the type study, and the Figtree rebuild) and renders fourteen states:

- every page has one `h1`, a language, a title, a skip link, unique IDs, valid ARIA targets, image `alt`, and named buttons
- no remote subresources; all local references resolve and stay inside `docs/mockups/`
- every source quote is a substring of its indexed chunk, and every metadata field matches the index
- the 12 lab rows match `samples/ground_truth/nutripath-p2.json`
- the coverage percentages and CI strings match a recomputed Wilson interval
- `--shots` renders fourteen states at 1440×1000 (and 1200 for the Figtree rebuild) and asserts `data-mockup-ready="1"`

Screenshots live in `assets/shots/`. The checker finds the local Chrome for Testing headless shell; if no browser is present, screenshots are skipped with a warning.

## Known limits

- Desktop-first. The layouts stack at 1024, 900, and 620 px, but this is not a mobile design.
- The four directions are alternatives, not four screens of one app. Each hero surface is built; the others are represented by a secondary state or a strip.
- The graph in Atlas is visual; the connection selector, list view, and source table are the keyboard-accessible paths.
- Coverage is not support or accuracy. The audit is small (11 items) and is reported as counts, not a claim.
- The preview server is a detached process. A host reboot or a killed PID takes the link down.

## Next step

Pick a direction from the gallery. The recommended v1 is Reading Room with Chartroom's safety rail; then wire that shell to the existing CLI outputs rather than adding more mockups.
