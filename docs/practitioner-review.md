# materia — practitioner review packet

**Status:** generated from synthetic vignettes, not patient data. 
**Cases:** 51. **Engine:** current `main` rules.

**Reviewer:** ______________________  **Date:** ______________

## How to review

For each case, mark one: **agree**, **unsafe**, or **missing**.
- **agree**: the top option is clinically reasonable and safe for this context.
- **unsafe**: the option or dose should not be offered; write why.
- **missing**: a more appropriate option or referral is absent; write it.

Do not edit the case. The point is to measure the engine, not to make it look right.
The ranking is a proposal; a clinician's judgement is the reference standard.

## iron-with-anaemia

**Intake:** {"age": 42, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Ferritin | 8 | µg/L | 15.0–150.0 | low |
| Haemoglobin | 105 | g/L | 120.0–160.0 | low |
| MCV | 76 | fL | 80.0–100.0 | low |
| CRP | 2 | mg/L | 0.0–5.0 | normal |

**Patterns:** Iron deficiency pattern (likely, 82%, high)

**Options (ranked):**
- **Oral iron** — grade B; 60–120 mg elemental iron on alternate days; flags: none
  - evidence: pmc-pmc13449291#030, pmc-pmc13449291#035, medlineplus-003490#006
  - monitor: Recheck ferritin and haemoglobin 8–12 weeks after starting; treat toward ferritin above 50–100 ng/mL.
- **Iron absorption and tolerance** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: pmc-pmc13449291#031
  - monitor: Take iron with a small amount of food if needed; separate it from tea, coffee, calcium and antacids.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## iron-without-anaemia

**Intake:** {"age": 35, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Ferritin | 22 | µg/L | 15.0–150.0 | normal |
| Haemoglobin | 135 | g/L | 120.0–160.0 | normal |
| MCV | 88 | fL | 80.0–100.0 | normal |

**Patterns:** Iron deficiency pattern (possible, 62%, moderate)

**Options (ranked):**
- **Oral iron** — grade B; 60–120 mg elemental iron on alternate days; flags: none
  - evidence: pmc-pmc13449291#030, pmc-pmc13449291#035, medlineplus-003490#006
  - monitor: Recheck ferritin and haemoglobin 8–12 weeks after starting; treat toward ferritin above 50–100 ng/mL.
- **Iron absorption and tolerance** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: pmc-pmc13449291#031
  - monitor: Take iron with a small amount of food if needed; separate it from tea, coffee, calcium and antacids.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## iron-overload-veto

**Intake:** {"age": 42, "sex": "male", "conditions": ["hemochromatosis"]}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Ferritin | 8 | µg/L | 15.0–150.0 | low |

**Patterns:** Iron deficiency pattern (possible, 62%, moderate)

**Options (ranked):**
- none offered
**Withheld:** Oral iron (withheld: iron overload / haemochromatosis); Iron absorption and tolerance (withheld: iron overload / haemochromatosis)

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## b12-deficiency

**Intake:** {"age": 60, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Vitamin B12 | 150 | pmol/L | 219.0–773.0 | low |
| MCV | 102 | fL | 80.0–100.0 | high |

**Patterns:** Vitamin B12 deficiency pattern (possible, 72%, moderate)

**Options (ranked):**
- **Oral vitamin B12** — grade B; 2 mg/day oral cyanocobalamin; flags: none
  - evidence: pmc-pmc13634279#069, pmc-pmc13634279#076, medlineplus-003705#006
  - monitor: Recheck B12 and methylmalonic acid after 8–12 weeks; confirm the cause if deficiency is proven.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## b12-borderline-with-macrocytosis

**Intake:** {"age": 55, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| B12 | 260 | pmol/L | 219.0–773.0 | normal |
| MCV | 102 | fL | 80.0–100.0 | high |

**Patterns:** Vitamin B12 deficiency pattern (possible, 72%, moderate)

**Options (ranked):**
- **Oral vitamin B12** — grade B; 2 mg/day oral cyanocobalamin; flags: none
  - evidence: pmc-pmc13634279#069, pmc-pmc13634279#076, medlineplus-003705#006
  - monitor: Recheck B12 and methylmalonic acid after 8–12 weeks; confirm the cause if deficiency is proven.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## vitamin-d-deficiency

**Intake:** {"age": 35, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| 25-hydroxyvitamin D | 30 | nmol/L | 75.0–250.0 | low |

**Patterns:** Vitamin D insufficiency (possible, 66%, moderate)

**Options (ranked):**
- **Vitamin D3 (cholecalciferol)** — grade A; 1,000–2,500 IU/day (25–62.5 µg); flags: none
  - evidence: hc-nhpid-vitamin-d-hd#004, pmc-pmc13363889#048, hc-nhpid-vitamin-d-hd#002
  - monitor: Repeat 25(OH)D after 8–12 weeks; check calcium if the dose is high or kidney disease is present.
- **Sun exposure and diet** — grade C; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-002405#004
  - monitor: Discuss skin-cancer risk, latitude, season and skin type; repeat 25(OH)D after 8–12 weeks.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## vitamin-d-insufficiency

**Intake:** {"age": 50, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Vitamin D | 45 | nmol/L | 75.0–250.0 | low |

**Patterns:** Vitamin D insufficiency (possible, 66%, moderate)

**Options (ranked):**
- **Vitamin D3 (cholecalciferol)** — grade A; 1,000–2,500 IU/day (25–62.5 µg); flags: none
  - evidence: hc-nhpid-vitamin-d-hd#004, pmc-pmc13363889#048, hc-nhpid-vitamin-d-hd#002
  - monitor: Repeat 25(OH)D after 8–12 weeks; check calcium if the dose is high or kidney disease is present.
- **Sun exposure and diet** — grade C; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-002405#004
  - monitor: Discuss skin-cancer risk, latitude, season and skin type; repeat 25(OH)D after 8–12 weeks.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## hypercalcaemia-veto

**Intake:** {"age": 60, "sex": "female", "conditions": ["hypercalcemia"]}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| 25-hydroxyvitamin D | 30 | nmol/L | 75.0–250.0 | low |

**Patterns:** Vitamin D insufficiency (possible, 66%, moderate)

**Options (ranked):**
- none offered
**Withheld:** Vitamin D3 (cholecalciferol) (withheld: high blood calcium); Sun exposure and diet (withheld: high blood calcium)

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## liver-enzyme-elevation

**Intake:** {"age": 50, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| ALT | 65 | U/L | 4.0–36.0 | high |
| AST | 45 | U/L | 8.0–33.0 | high |
| GGT | 55 | U/L | 5.0–40.0 | high |

**Patterns:** Liver enzyme elevation (possible, 65%, moderate)

**Options (ranked):**
- **Investigate the cause** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003473#006, medlineplus-003472#006
  - monitor: Repeat the panel in 2–4 weeks; review alcohol, medicines, viral hepatitis and metabolic risk; image the liver if persistent.
- **Milk thistle (silymarin)** — grade C; 140–600 mg silymarin/day; flags: none
  - evidence: hc-nhpid-milk-thistle-oral#004, nccih-milk-thistle#004, nccih-milk-thistle#005
  - monitor: Repeat liver enzymes after 4–8 weeks; stop if enzymes rise or new symptoms appear.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## normal-liver-enzymes

**Intake:** {"age": 50, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| ALT | 20 | U/L | 4.0–36.0 | normal |

**Patterns:** none

**Options (ranked):**
- none offered

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## high-triglycerides

**Intake:** {"age": 45, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Triglycerides | 3.2 | mmol/L | 0.4–1.7 | high |
| HDL | 0.8 | mmol/L | 1.0–3.0 | low |

**Patterns:** Elevated triglycerides (possible, 64%, moderate); Low HDL cholesterol (possible, 60%, moderate)

**Options (ranked):**
- **Diet, exercise and weight** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003493#006
  - monitor: Repeat the fasting lipid panel after 8–12 weeks; address alcohol, refined carbohydrate, weight and activity.
- **Omega-3 fatty acids (EPA + DHA)** — grade B; 1,000–5,000 mg EPA + DHA/day; flags: none
  - evidence: hc-nhpid-fish-oil-huile-poisson#003, pmc-pmc13467960#001
  - monitor: Repeat the fasting lipid panel after 8–12 weeks; review bleeding risk if on anticoagulants.
- **Activity, diet and weight** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-007810#006
  - monitor: Repeat the lipid panel after 8–12 weeks; review activity, saturated fat, refined carbohydrate, weight, smoking and diabetes.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## fish-allergy-veto

**Intake:** {"age": 45, "sex": "male", "conditions": ["fish allergy"]}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Triglycerides | 3.2 | mmol/L | 0.4–1.7 | high |

**Patterns:** Elevated triglycerides (possible, 56%, moderate)

**Options (ranked):**
- **Diet, exercise and weight** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003493#006
  - monitor: Repeat the fasting lipid panel after 8–12 weeks; address alcohol, refined carbohydrate, weight and activity.
**Withheld:** Omega-3 fatty acids (EPA + DHA) (withheld: fish or shellfish allergy)

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## normal-panel

**Intake:** {"age": 30, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Ferritin | 120 | µg/L | 30.0–400.0 | normal |
| Vitamin B12 | 500 | pmol/L | 219.0–773.0 | normal |
| ALT | 20 | U/L | 4.0–36.0 | normal |
| Triglycerides | 1 | mmol/L | 0.4–1.7 | normal |

**Patterns:** none

**Options (ranked):**
- none offered

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## pregnancy-iron-flag

**Intake:** {"age": 30, "sex": "female", "contexts": ["pregnancy"]}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Ferritin | 8 | µg/L | 15.0–150.0 | low |

**Patterns:** Iron deficiency pattern (possible, 62%, moderate)

**Options (ranked):**
- **Oral iron** — grade B; 60–120 mg elemental iron on alternate days; flags: pregnant
  - evidence: pmc-pmc13449291#030, pmc-pmc13449291#035, medlineplus-003490#006
  - monitor: Recheck ferritin and haemoglobin 8–12 weeks after starting; treat toward ferritin above 50–100 ng/mL.
- **Iron absorption and tolerance** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: pmc-pmc13449291#031
  - monitor: Take iron with a small amount of food if needed; separate it from tea, coffee, calcium and antacids.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## folate-pattern-without-option

**Intake:** {"age": 32, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Folate | 4 | nmol/L | 6.12–38.52 | low |
| Homocysteine | 18 | µmol/L | 5.0–15.0 | high |
| MCV | 100 | fL | 80.0–100.0 | normal |

**Patterns:** Folate deficiency pattern (possible, 68%, moderate); High homocysteine (possible, 58%, moderate)

**Options (ranked):**
- **Folic acid** — grade B; 400–1,000 µg/day folic acid; flags: none
  - evidence: medlineplus-000354#005, hc-nhpid-multi-vitmin-doses#001, medlineplus-003686#005
  - monitor: Recheck folate and B12 after 8–12 weeks.
- **Homocysteine cause review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: pmc-pmc13401327#010
  - monitor: Repeat homocysteine after addressing a proven deficiency; recheck B12, folate, B6 and renal function.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## triglycerides-with-anticoagulant-flag

**Intake:** {"age": 55, "sex": "male", "medications": ["warfarin"]}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Triglycerides | 3.2 | mmol/L | 0.4–1.7 | high |

**Patterns:** Elevated triglycerides (possible, 56%, moderate)

**Options (ranked):**
- **Diet, exercise and weight** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003493#006
  - monitor: Repeat the fasting lipid panel after 8–12 weeks; address alcohol, refined carbohydrate, weight and activity.
- **Omega-3 fatty acids (EPA + DHA)** — grade B; 1,000–5,000 mg EPA + DHA/day; flags: taking an anticoagulant
  - evidence: hc-nhpid-fish-oil-huile-poisson#003, pmc-pmc13467960#001
  - monitor: Repeat the fasting lipid panel after 8–12 weeks; review bleeding risk if on anticoagulants.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## low-magnesium

**Intake:** {"age": 38, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Magnesium | 0.62 | mmol/L | 0.7–0.91 | low |

**Patterns:** Low serum magnesium (possible, 55%, moderate)

**Options (ranked):**
- **Oral magnesium** — grade B; 300–350 mg/day elemental magnesium; flags: none
  - evidence: pmc-pmc13391447#026, pmc-pmc13391447#012, hc-nhpid-multi-vitmin-doses#004
  - monitor: Recheck magnesium and kidney function after 4–8 weeks; reduce the dose if diarrhea occurs.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## thyroid-underactive-referral

**Intake:** {"age": 48, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| TSH | 8.2 | mIU/L | 0.4–4.8 | high |
| Free T4 | 8 | pmol/L | 9.0–19.0 | low |

**Patterns:** Underactive thyroid pattern (possible, 55%, high)

**Options (ranked):**
- **Thyroid function review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003684#006, medlineplus-003517#006
  - monitor: Repeat TSH and free T4; check thyroid peroxidase antibodies; review medicines, pregnancy and iodine intake.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## prediabetes-range

**Intake:** {"age": 52, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| HbA1c | 5.9 | % | 4.0–5.6 | high |

**Patterns:** Dysglycaemia pattern (possible, 58%, moderate)

**Options (ranked):**
- **Metabolic risk review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003640#005, medlineplus-003640#006
  - monitor: Repeat A1C or fasting glucose; assess blood pressure, lipids, kidney function and weight.
- **Berberine** — grade C; 1 g/day berberine; flags: none
  - evidence: pmc-pmc11723399#036, pmc-pmc13606907#002, epmc-42653808#003
  - monitor: Recheck A1C or fasting glucose after 8–12 weeks; review glucose-lowering medicines and liver enzymes.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## diabetes-range-referral

**Intake:** {"age": 58, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| HbA1c | 7.2 | % | 4.0–5.6 | high |

**Patterns:** Dysglycaemia pattern (possible, 58%, high)

**Options (ranked):**
- **Metabolic risk review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003640#005, medlineplus-003640#006
  - monitor: Repeat A1C or fasting glucose; assess blood pressure, lipids, kidney function and weight.
- **Berberine** — grade C; 1 g/day berberine; flags: none
  - evidence: pmc-pmc11723399#036, pmc-pmc13606907#002, epmc-42653808#003
  - monitor: Recheck A1C or fasting glucose after 8–12 weeks; review glucose-lowering medicines and liver enzymes.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## elevated-ldl-referral

**Intake:** {"age": 55, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| LDL | 3.8 | mmol/L | 0.0–2.6 | high |

**Patterns:** Elevated LDL cholesterol (possible, 55%, moderate)

**Options (ranked):**
- **Cardiovascular risk review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-007812#005, medlineplus-007812#006
  - monitor: Repeat the lipid panel; review blood pressure, smoking, diabetes, kidney function and family history.
- **Curcumin (turmeric extract)** — grade C; 1,500 mg/day curcuminoids; flags: none
  - evidence: hc-nhpid-curcumin-curcumine2#003, pmc-pmc12736498#025, hc-nhpid-curcumin-curcumine2#004
  - monitor: Repeat the lipid panel after 8–12 weeks; stop if liver enzymes rise or new symptoms appear.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## normal-ldl

**Intake:** {"age": 40, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| LDL | 2 | mmol/L | 0.0–2.6 | normal |

**Patterns:** none

**Options (ranked):**
- none offered

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## hypercalcaemia-lab-veto

**Intake:** {"age": 60, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| 25-hydroxyvitamin D | 30 | nmol/L | 75.0–250.0 | low |
| Calcium | 2.7 | mmol/L | 2.2–2.58 | high |

**Patterns:** High blood calcium (possible, 62%, high); Vitamin D insufficiency (possible, 66%, moderate)

**Options (ranked):**
- **High calcium review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003477#006
  - monitor: Repeat calcium; check PTH, 25(OH)D, kidney function and malignancy risk; urgent if symptoms are present.
**Withheld:** Vitamin D3 (cholecalciferol) (withheld: calcium 2.7 mmol/L > 2.58 mmol/L); Sun exposure and diet (withheld: calcium 2.7 mmol/L > 2.58 mmol/L)

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## magnesium-kidney-veto

**Intake:** {"age": 62, "sex": "male", "conditions": ["kidney disease"]}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Magnesium | 0.6 | mmol/L | 0.7–0.91 | low |

**Patterns:** Low serum magnesium (possible, 55%, moderate)

**Options (ranked):**
- none offered
**Withheld:** Oral magnesium (withheld: kidney disease)

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## milk-thistle-ragweed-veto

**Intake:** {"age": 45, "sex": "female", "conditions": ["ragweed allergy"]}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| ALT | 65 | U/L | 4.0–36.0 | high |

**Patterns:** Liver enzyme elevation (possible, 60%, moderate)

**Options (ranked):**
- **Investigate the cause** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003473#006, medlineplus-003472#006
  - monitor: Repeat the panel in 2–4 weeks; review alcohol, medicines, viral hepatitis and metabolic risk; image the liver if persistent.
**Withheld:** Milk thistle (silymarin) (withheld: ragweed / daisy-family allergy)

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## pregnancy-milk-thistle-flag

**Intake:** {"age": 30, "sex": "female", "contexts": ["pregnancy"]}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| ALT | 65 | U/L | 4.0–36.0 | high |

**Patterns:** Liver enzyme elevation (possible, 60%, moderate)

**Options (ranked):**
- **Investigate the cause** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003473#006, medlineplus-003472#006
  - monitor: Repeat the panel in 2–4 weeks; review alcohol, medicines, viral hepatitis and metabolic risk; image the liver if persistent.
- **Milk thistle (silymarin)** — grade C; 140–600 mg silymarin/day; flags: pregnant
  - evidence: hc-nhpid-milk-thistle-oral#004, nccih-milk-thistle#004, nccih-milk-thistle#005
  - monitor: Repeat liver enzymes after 4–8 weeks; stop if enzymes rise or new symptoms appear.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## iron-overload-referral

**Intake:** {"age": 50, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Ferritin | 800 | µg/L | 30.0–400.0 | high |
| Transferrin saturation | 60 | % | 20.0–50.0 | high |

**Patterns:** Iron overload pattern (possible, 62%, high)

**Options (ranked):**
- **Iron overload review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003490#006, medlineplus-003488#006
  - monitor: Repeat fasting ferritin and transferrin saturation; check HFE genotype and liver iron where indicated.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## hypercalcaemia-referral

**Intake:** {"age": 60, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Calcium | 2.9 | mmol/L | 2.2–2.58 | high |

**Patterns:** High blood calcium (possible, 62%, high)

**Options (ranked):**
- **High calcium review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003477#006
  - monitor: Repeat calcium; check PTH, 25(OH)D, kidney function and malignancy risk; urgent if symptoms are present.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## marked-inflammation-referral

**Intake:** {"age": 45, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| CRP | 120 | mg/L | 0.0–5.0 | high |

**Patterns:** Raised inflammatory marker (possible, 52%, high)

**Options (ranked):**
- **Inflammation cause review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003356#005, medlineplus-003356#006
  - monitor: Repeat CRP and look for infection, inflammation, autoimmune disease or malignancy.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## severe-hypertriglyceridaemia

**Intake:** {"age": 45, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Triglycerides | 7 | mmol/L | 0.4–1.7 | high |

**Patterns:** Elevated triglycerides (possible, 56%, high)

**Options (ranked):**
- **Urgent triglyceride review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003493#006
  - monitor: Arrange urgent clinical review; repeat fasting lipids and address alcohol, diet, diabetes and medicines.
- **Diet, exercise and weight** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003493#006
  - monitor: Repeat the fasting lipid panel after 8–12 weeks; address alcohol, refined carbohydrate, weight and activity.
**Withheld:** Omega-3 fatty acids (EPA + DHA) (critical value: Triglycerides 7 mmol/L)

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## berberine-pregnancy-veto

**Intake:** {"age": 32, "sex": "female", "contexts": ["pregnancy"]}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| HbA1c | 5.9 | % | 4.0–5.6 | high |

**Patterns:** Dysglycaemia pattern (possible, 58%, moderate)

**Options (ranked):**
- **Metabolic risk review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003640#005, medlineplus-003640#006
  - monitor: Repeat A1C or fasting glucose; assess blood pressure, lipids, kidney function and weight.
**Withheld:** Berberine (withheld: pregnant)

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## critical-potassium

**Intake:** {"age": 60, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Potassium | 6.5 | mmol/L | 3.7–5.2 | high |

**Patterns:** none

**Options (ranked):**
- none offered

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## zinc-deficiency

**Intake:** {"age": 45, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Zinc | 8 | µmol/L | 10.0–18.0 | low |

**Patterns:** Zinc deficiency pattern (possible, 55%, moderate)

**Options (ranked):**
- **Oral zinc** — grade C; 50 mg/day elemental zinc; flags: none
  - evidence: pmc-pmc13512597#048, pmc-pmc13512597#016, pmc-pmc13512597#065
  - monitor: Recheck serum zinc and haemoglobin at 3 months; monitor copper during prolonged use.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## critical-inr

**Intake:** {"age": 65, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| INR | 5.5 | ratio | 0.8–1.2 | high |

**Patterns:** none

**Options (ranked):**
- none offered

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## critical-bicarbonate

**Intake:** {"age": 60, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Bicarbonate | 8 | mmol/L | 22–29 | low |

**Patterns:** none

**Options (ranked):**
- none offered

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## low-hdl-lifestyle

**Intake:** {"age": 45, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| HDL | 0.8 | mmol/L | 1.0–3.0 | low |

**Patterns:** Low HDL cholesterol (possible, 55%, moderate)

**Options (ranked):**
- **Activity, diet and weight** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-007810#006
  - monitor: Repeat the lipid panel after 8–12 weeks; review activity, saturated fat, refined carbohydrate, weight, smoking and diabetes.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## critical-platelets

**Intake:** {"age": 60, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Platelets | 8 | 10^9/L | 150.0–400.0 | low |

**Patterns:** Low platelets (possible, 58%, high)

**Options (ranked):**
- **Low platelet cause review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: pmc-pmc13678706#064, pmc-pmc13678706#065, pmc-pmc13678706#074
  - monitor: Repeat the FBC and film; assess bleeding, medicines, heparin exposure, liver/spleen and infection.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## high-homocysteine-referral

**Intake:** {"age": 45, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Homocysteine | 18 | µmol/L | 5.0–15.0 | high |

**Patterns:** High homocysteine (possible, 58%, moderate)

**Options (ranked):**
- **Homocysteine cause review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: pmc-pmc13401327#010
  - monitor: Repeat homocysteine after addressing a proven deficiency; recheck B12, folate, B6 and renal function.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## b12-normal-mma-high

**Intake:** {"age": 60, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Vitamin B12 | 350 | pmol/L | 219.0–773.0 | normal |
| Methylmalonic acid | 400 | nmol/L | 0.0–270.0 | high |

**Patterns:** Vitamin B12 deficiency pattern (possible, 60%, moderate)

**Options (ranked):**
- **Oral vitamin B12** — grade B; 2 mg/day oral cyanocobalamin; flags: none
  - evidence: pmc-pmc13634279#069, pmc-pmc13634279#076, medlineplus-003705#006
  - monitor: Recheck B12 and methylmalonic acid after 8–12 weeks; confirm the cause if deficiency is proven.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## critical-newborn-potassium

**Intake:** {"age": 0, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Potassium | 7.2 | mmol/L | 3.7–5.2 | high |

**Patterns:** none

**Options (ranked):**
- none offered

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## newborn-potassium-not-adult-critical

**Intake:** {"age": 0, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Potassium | 6.5 | mmol/L | 3.7–5.2 | high |

**Patterns:** none

**Options (ranked):**
- none offered

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## child-potassium-adult-limit

**Intake:** {"age": 8, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Potassium | 6.5 | mmol/L | 3.7–5.2 | high |

**Patterns:** none

**Options (ranked):**
- none offered

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## reduced-egfr-referral

**Intake:** {"age": 65, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| eGFR | 45 | mL/min/1.73m2 | 90.0–200.0 | low |

**Patterns:** Reduced kidney filtration (possible, 60%, moderate)

**Options (ranked):**
- **Kidney function review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: pmc-pmc13525924#001, pmc-pmc13525924#003
  - monitor: Repeat eGFR after at least 3 months; check urine albumin-to-creatinine ratio, blood pressure, diabetes and medicines.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## reduced-egfr-magnesium-veto

**Intake:** {"age": 65, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| eGFR | 25 | mL/min/1.73m2 | 90.0–200.0 | low |
| Magnesium | 0.6 | mmol/L | 0.7–0.91 | low |

**Patterns:** Reduced kidney filtration (possible, 60%, moderate); Low serum magnesium (possible, 55%, moderate)

**Options (ranked):**
- **Kidney function review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: pmc-pmc13525924#001, pmc-pmc13525924#003
  - monitor: Repeat eGFR after at least 3 months; check urine albumin-to-creatinine ratio, blood pressure, diabetes and medicines.
**Withheld:** Oral magnesium (withheld: egfr 25 mL/min/1.73m2 < 30 mL/min/1.73m2)

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## high-uric-acid-lifestyle

**Intake:** {"age": 50, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Uric acid | 550 | µmol/L | 238.0–511.0 | high |

**Patterns:** High uric acid (possible, 55%, moderate)

**Options (ranked):**
- **Hydration, alcohol and purine review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003476#005
  - monitor: Repeat uric acid; assess gout, kidney function, alcohol, purine intake and medicines.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## high-bilirubin-referral

**Intake:** {"age": 50, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Bilirubin | 35 | µmol/L | 3.0–20.0 | high |

**Patterns:** Raised bilirubin (possible, 58%, moderate)

**Options (ranked):**
- **Bilirubin cause review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003479#004, medlineplus-003479#006
  - monitor: Repeat and fractionate bilirubin; check liver enzymes, blood count/haemolysis and medicines.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## low-albumin-referral

**Intake:** {"age": 55, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Albumin | 30 | g/L | 34.0–54.0 | low |

**Patterns:** Low albumin (possible, 58%, moderate)

**Options (ranked):**
- **Albumin cause review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003480#004, medlineplus-003480#006
  - monitor: Repeat albumin; check liver enzymes, kidney function, CRP and protein intake/absorption.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## high-platelets-referral

**Intake:** {"age": 50, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Platelets | 600 | 10^9/L | 150.0–400.0 | high |

**Patterns:** High platelets (possible, 55%, moderate)

**Options (ranked):**
- **Platelet cause review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: pmc-pmc13678706#060, pmc-pmc13678706#074
  - monitor: Repeat the FBC; assess iron status, CRP, infection and malignancy; refer if persistent.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## low-platelets-referral

**Intake:** {"age": 50, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Platelets | 80 | 10^9/L | 150.0–400.0 | low |

**Patterns:** Low platelets (possible, 58%, moderate)

**Options (ranked):**
- **Low platelet cause review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: pmc-pmc13678706#064, pmc-pmc13678706#065, pmc-pmc13678706#074
  - monitor: Repeat the FBC and film; assess bleeding, medicines, heparin exposure, liver/spleen and infection.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## hyperthyroid-referral

**Intake:** {"age": 40, "sex": "female"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Free T4 | 30 | pmol/L | 12.0–22.0 | high |
| TSH | 0.02 | mIU/L | 0.4–4.8 | low |

**Patterns:** Overactive thyroid pattern (possible, 60%, moderate)

**Options (ranked):**
- **Overactive thyroid review** — grade B; no dose (lifestyle/referral); flags: none
  - evidence: medlineplus-003517#006, medlineplus-003684#006
  - monitor: Repeat TSH and free T4; add T3 and thyroid antibodies where indicated; review medicines and iodine.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---

## amino-acid-panel-referral

**Intake:** {"age": 54, "sex": "male"}

| finding | value | unit | lab range | direction |
|---|---:|---|---|---|
| Methionine | 8 | µmol/L | 10.0–33.0 | low |
| Tryptophan | 20 | µmol/L | 24.0–52.0 | low |

**Patterns:** Amino-acid panel review (possible, 45%, moderate)

**Options (ranked):**
- **Amino-acid panel review** — grade C; no dose (lifestyle/referral); flags: none
  - evidence: pmc-pmc13447054#002, pmc-pmc13447054#003, pmc-pmc13447054#008
  - monitor: Repeat fasting in the same specimen type; interpret with age-specific intervals, nutrition, liver, kidney, medicines and sample handling.

**Review:** [ ] agree  [ ] unsafe  [ ] missing  
**Why / what is missing:** 

---
