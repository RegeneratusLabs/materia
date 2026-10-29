# Attribution — when is an answer actually supported by the reference it was shown?

Hint mode shows the model one reference sentence and does not ask it to cite (`docs/gate3.md`,
Experiment 9). That moves the citation question into the system: after the model answers, does the shown
reference actually carry the chosen answer? `materia/attribute.py` answers that, and the product uses it to
decide between `grounded` (show the source) and `memory` (label it as unsupported).

## The rule

1. **Entity consistency first.** If the reference's document entity has distinctive tokens and none appear
   in the question, the reference is about something else and the answer is `memory`. This is what catches
   an astragalus safety chunk being shown for an echinacea question. Titles are wordy, so generic words
   ("test", "level", "blood", "monograph", "health", "professional") are ignored, and short analyte acronyms
   (TSH, T3, T4, B12, GGT, ALT, AST, CRP, ESR) are kept. Parenthetical acronyms are kept too, because
   "Gamma-glutamyl transferase (GGT)" must match a question that says GGT.
2. **Lexical support second.** At least two content terms shared between the answer and the reference, with
   light stemming, and ≥20% of the answer's content terms present.

Anything that fails is labelled `memory`, never "cited". False `memory` labels are acceptable — they cost a
citation, not correctness. False `grounded` labels are not.

## Hand audit of the nine attributions from the hint run (n=104 panel)

| Item | Verdict | Note |
|---|---|---|
| H02 ginkgo × warfarin | supported | EMA interactions names anticoagulants/antiplatelets |
| H05 grapefruit × CYP3A4 | supported | NCI dietary interactions, intestinal CYP3A4 |
| H08 5-HTP × sertraline | supported | Health Canada caution names serotonergic activity |
| H23 ephedra cardiovascular | supported | NCCIH ban text, serious safety risks |
| H25 echinacea × immunosuppressants | **NOT supported** | reference was an **astragalus** safety chunk — the case that motivated the entity rule |
| L04 ferritin as acute-phase reactant | supported | MedlinePlus "higher ferritin … inflammation" |
| L05 B12 <299 pg/mL deficiency | supported | MedlinePlus "possible sign of vitamin B12 deficiency" |
| E08 bitter orange sympathomimetic | borderline | chunk is generic safety text; claim may appear later in the chunk |
| L30 raised methylmalonic acid | supported | B12 deficiency page |

Eight of nine supported or plausible; one clear false positive. The entity rule then removes that case and
also two conservative false negatives (H03 fish oil/kava, L03 TIBC/iron studies), leaving **7 grounded
attributions out of 104** — small, and stated as such.

## What this is not

It is not an entailment check. Two shared terms can be coincidence, and a genuinely supporting paraphrase
with different vocabulary is labelled `memory`. The threshold and the two-term floor were calibrated against
the stored sheets and this audit, not against practitioner labels. That calibration is the next step before
these labels are shown to users as anything stronger than "reference shown".
