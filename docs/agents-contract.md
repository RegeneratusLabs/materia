# materia — agent contract

> **Status: not installed.** The canonical destination is `AGENTS.md` in the project root.
> Writing that file is blocked in this session because the desktop client cannot render
> approval prompts for protected agent-instruction files. When approvals work, install with:
>
>     mv docs/agents-contract.md AGENTS.md
>
> Content below is final and reviewed with Josh on 2026-10-28.

---

Project-level contract for any agent working in this directory. `HANDOVER.md` carries the state
transfer; this file carries the rules. If they conflict, `HANDOVER.md` wins on facts, this file wins
on behaviour.

## What this is

A cited evidence engine for naturopathic and holistic practitioners. It surfaces evidence with
sources a practitioner can check. It is **not** a diagnostic tool, **not** a protocol generator, and
**not** a chatbot with opinions.

## Non-negotiables

1. **Open weights only.** No OpenAI, no closed APIs — not in the product, not in the evals, not
   "just for comparison".
2. **Retrieval before training.** The measured problem is elicitation, not knowledge: the same model
   went 71.7% → 95.2% on the same questions purely by being allowed to reason for 60 words. Do not
   fine-tune until a retrieval layer has its own numbers.
3. **No uncited clinical claim.** If a claim cannot be tied to a retrieved source, it is not
   rendered. Not softened, not hedged — removed.
4. **The model never emits a protocol.** It surfaces evidence and a cited rationale. Safety screening
   is deterministic code, not model output.
5. **No number without n and a 95% CI.** 46 items at 97.8% is 88.7–99.6. A bare percentage is a claim
   you cannot defend.
6. **Never invent a source.** If the corpus does not answer, say so. Fabricated citations are the one
   unrecoverable failure for a product whose entire value is provenance.

## Scoring — read before touching `results/`

```bash
python3 docs/rescore.py results/v2_budget.jsonl
```

Expected: `99/104 = 95.2% [89.2, 97.9]`.

**Score from the stored `got` field. Do not re-parse the stored `text`/`reason` fields.** They are
head-truncated at write time, so re-parsing disagrees with what the model actually answered on every
record with `finish == "length"`. This already produced a false score (101/104) and a false
"p = 0.008" claim once in this project. There is one sanctioned scoring path: `docs/rescore.py`.

## Running the model

```bash
cd ~/bin/llamacpp/llama-b11936 && ./llama-server \
  -m ~/models/minicpm5/MiniCPM5-2B-Q8_0.gguf \
  -c 4096 -np 2 -t 6 --jinja --no-reasoning-preserve --port 8099
```

Weights live outside the repo at `~/models/minicpm5/` (Q8_0 2,556 MB, Q4_K_M 1,489 MB). llama.cpp
build 11936, no GPU, ~16 tok/s generation and ~70 tok/s prefill on this host.

**Restart the server between long runs.** RSS climbs to ~7.7 GB after two hours even with
`--no-reasoning-preserve`; the box then thrashes swap and the model appears to slow to 0.4 tok/s.
Watch `ps -o rss= -C llama-server`.

## Prompt scaffolding

Exactly one instruction is earned:

> Think for at most 60 words, then reply with ONLY the letter of the single best option (A, B, C or
> D). No explanation after the letter.

For fast MCQ passes, disable thinking outright with `chat_template_kwargs:
{"enable_thinking": false}` — ~2 output tokens instead of ~180, a 40x speedup.

Do **not** add instructions telling the model to distrust its priors, ignore its expectations, or
reinterpret units. Both variants tested scored below the budget alone (90.4% and 93.3% vs 95.2%),
and they induce the self-doubt loop that breaks it on lab values.

## Conventions

- All measured numbers live in `docs/scores.json` and trace to a file in `results/`. If you compute
  something, write it down with n and CI.
- Panels are JSON arrays of `{"id","cat","q","o":{"A"..},"a"}`. Any new panel must have shuffled
  option order with a balanced gold distribution — verify before running.
- Treat truncation honestly: a generation that hit the token cap and emitted nothing is
  **unanswered**, not wrong. Report both denominators.
- Logs in `logs/` are evidence, not scratch. Leave them.

## Know-how

The reusable method and a tested harness live in the Hermes skill `local-gguf-capability-eval`
(`scripts/eval_harness.py`). Read it before building a new eval; it carries the pitfalls that cost
hours here.
