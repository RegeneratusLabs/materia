/* materia UI mockups — shared fixtures.
 *
 * Design-target content only. Source quotes are taken from corpus/index.sqlite
 * (whitespace-normalised) and verified by tools/check.py. Cases are synthetic.
 * Lab confidence values are illustrative, not a Jev calibration.
 *
 * This file is JSON after the assignment so the stdlib checker can parse it.
 */
window.MATERIA = {
  "meta": {
    "snapshot": "2026-10-30",
    "corpus": "377 documents · 4,012 chunks",
    "note": "Static mockup. Quotes are verbatim from the corpus; cases are synthetic design targets."
  },
  "sources": {
    "ema-ginkgo-interactions": {
      "chunkId": "ema-ginkgo-biloba-l-folium#005",
      "docId": "ema-ginkgo-biloba-l-folium",
      "source": "EMA (HMPC)",
      "tier": "regulatory",
      "jurisdiction": "eu",
      "title": "EU herbal monograph — Ginkgo biloba L., folium",
      "date": "2015-01-28",
      "nextReview": "2027-10-29",
      "section": "interactions",
      "identifier": "EMA/HMPC/321097/2012",
      "url": "https://www.ema.europa.eu/en/documents/herbal-monograph/final-european-union-herbal-monograph-ginkgo-biloba-l-folium_en.pdf",
      "licence": "EMA legal notice — reproduction authorised with acknowledgement",
      "checksum": "sha256:c9a638ea0a54d8cb04800aa5af939386bd2153721acb16fe3971e118036fd95d",
      "quote": "Available studies with warfarin do not indicate that there is an interaction between warfarin and G. biloba products, but adequate monitoring is advised when starting, when changing G. biloba dose, when ending G. biloba intake or if changing product."
    },
    "ema-ginkgo-adverse": {
      "chunkId": "ema-ginkgo-biloba-l-folium#008",
      "docId": "ema-ginkgo-biloba-l-folium",
      "source": "EMA (HMPC)",
      "tier": "regulatory",
      "jurisdiction": "eu",
      "title": "EU herbal monograph — Ginkgo biloba L., folium",
      "date": "2015-01-28",
      "nextReview": "2027-10-29",
      "section": "adverse effects",
      "identifier": "EMA/HMPC/321097/2012",
      "url": "https://www.ema.europa.eu/en/documents/herbal-monograph/final-european-union-herbal-monograph-ginkgo-biloba-l-folium_en.pdf",
      "licence": "EMA legal notice — reproduction authorised with acknowledgement",
      "checksum": "sha256:c9a638ea0a54d8cb04800aa5af939386bd2153721acb16fe3971e118036fd95d",
      "quote": "Bleeding of individual organs has been reported (eye, nose, cerebral and gastrointestinal haemorrhage). The frequency is not known."
    },
    "hc-ginkgo": {
      "chunkId": "hc-nhpid-ginkgo-biloba2#006",
      "docId": "hc-nhpid-ginkgo-biloba2",
      "source": "Health Canada NNHPD",
      "tier": "regulatory",
      "jurisdiction": "ca",
      "title": "GINKGO - GINKGO BILOBA",
      "date": "2025-07-25",
      "nextReview": "2027-10-28",
      "section": "contraindications",
      "identifier": "ginkgo.biloba2",
      "url": "https://webprod.hc-sc.gc.ca/nhpid-bdipsn/atReq?atid=ginkgo.biloba2&lang=eng",
      "licence": "Open Government Licence – Canada",
      "checksum": "sha256:3c30f7e37a7f5048b1ffad981b63de6d6736327ff3a38e7b2d55b6fab9e3bb4a",
      "quote": "Do not use if you are taking blood thinners or other health products that affect blood coagulation (Gardner and McGuffin 2013; Brinker 2010; Bent 2005)."
    },
    "nccih-ginkgo": {
      "chunkId": "nccih-ginkgo#006",
      "docId": "nccih-ginkgo",
      "source": "NCCIH (NIH)",
      "tier": "compendium",
      "jurisdiction": "us",
      "title": "Ginkgo",
      "date": "2021-05-01",
      "nextReview": "2027-04-28",
      "section": "adverse effects",
      "identifier": "https://www.nccih.nih.gov/health/ginkgo",
      "url": "https://www.nccih.nih.gov/health/ginkgo",
      "licence": "US federal work — public domain",
      "checksum": "sha256:0a655880cb5dc9836ba05e3d5b33950d4713af412657f1a31283ce5118dc5e13",
      "quote": "Ginkgo may increase the risk of bleeding in people who are taking anticoagulant drugs, such as warfarin."
    },
    "ema-valerian": {
      "chunkId": "ema-valeriana-officinalis-l-radix#002",
      "docId": "ema-valeriana-officinalis-l-radix",
      "source": "EMA (HMPC)",
      "tier": "regulatory",
      "jurisdiction": "eu",
      "title": "EU herbal monograph — Valeriana officinalis L., radix",
      "date": "2016-02-02",
      "nextReview": "2027-10-29",
      "section": "dosage",
      "identifier": "EMA/HMPC/150848/2015",
      "url": "https://www.ema.europa.eu/en/documents/herbal-monograph/final-european-union-herbal-monograph-valeriana-officinalis-l-radix_en.pdf",
      "licence": "EMA legal notice — reproduction authorised with acknowledgement",
      "checksum": "sha256:a69cc050171e07c01a2b77afdbecc34990e7dfba161bbfc194405fe1119596cb",
      "quote": "Single dose: 400-600 mg dry extract; For relief of mild nervous tension up to 3 times daily."
    },
    "nccih-valerian": {
      "chunkId": "nccih-valerian#004",
      "docId": "nccih-valerian",
      "source": "NCCIH (NIH)",
      "tier": "compendium",
      "jurisdiction": "us",
      "title": "Valerian",
      "date": "2020-04-05",
      "nextReview": "2027-04-28",
      "section": "evidence",
      "identifier": "https://www.nccih.nih.gov/health/valerian",
      "url": "https://www.nccih.nih.gov/health/valerian",
      "licence": "US federal work — public domain",
      "checksum": "sha256:1b52b468539f8dff4faca5c26bd2e06347d075904121a999fc5d2c4782c1a76e",
      "quote": "The evidence on whether valerian is helpful for sleep problems is inconsistent. In its 2017 clinical practice guidelines, the American Academy of Sleep Medicine recommended against using valerian for chronic insomnia in adults."
    },
    "hc-st-johns-wort": {
      "chunkId": "hc-nhpid-stjohnswort-millepertuis-oral2#007",
      "docId": "hc-nhpid-stjohnswort-millepertuis-oral2",
      "source": "Health Canada NNHPD",
      "tier": "regulatory",
      "jurisdiction": "ca",
      "title": "ST. JOHN'S WORT - HYPERICUM PERFORATUM - Oral",
      "date": "2024-07-26",
      "nextReview": "2027-10-28",
      "section": "contraindications",
      "identifier": "stjohnswort.millepertuis.oral2",
      "url": "https://webprod.hc-sc.gc.ca/nhpid-bdipsn/atReq?atid=stjohnswort.millepertuis.oral2&lang=eng",
      "licence": "Open Government Licence – Canada",
      "checksum": "sha256:3dbc52f3c8fc5a38fe4512c8edd88402ece4cc930093fc21f51b40589a09bd8c",
      "quote": "Do not use if you are taking antidepressants, anxiolytics, anti-cancer, cardiovascular, contraceptive medications, blood thinners, anti-HIV agents and/or medications to suppress the immune system"
    },
    "nccih-st-johns-wort": {
      "chunkId": "nccih-st-johns-wort#005",
      "docId": "nccih-st-johns-wort",
      "source": "NCCIH (NIH)",
      "tier": "compendium",
      "jurisdiction": "us",
      "title": "St. John's Wort",
      "date": "2025-05-01",
      "nextReview": "2027-04-28",
      "section": "adverse effects",
      "identifier": "https://www.nccih.nih.gov/health/st-johns-wort",
      "url": "https://www.nccih.nih.gov/health/st-johns-wort",
      "licence": "US federal work — public domain",
      "checksum": "sha256:a08b3abc2daf69193fd3f4d5441f52d7cf816d70f718014e1e37a5860d899dff",
      "quote": "taking St. John’s wort with certain antidepressants or other drugs that affect serotonin (a substance produced by some nerve cells) may lead to increased serotonin-related side effects, which can be serious."
    },
    "nccih-epo": {
      "chunkId": "nccih-evening-primrose-oil#004",
      "docId": "nccih-evening-primrose-oil",
      "source": "NCCIH (NIH)",
      "tier": "compendium",
      "jurisdiction": "us",
      "title": "Evening Primrose Oil",
      "date": "2021-05-01",
      "nextReview": "2027-04-28",
      "section": "evidence",
      "identifier": "https://www.nccih.nih.gov/health/evening-primrose-oil",
      "url": "https://www.nccih.nih.gov/health/evening-primrose-oil",
      "licence": "US federal work — public domain",
      "checksum": "sha256:3b2794bfef6e9528bca2d62083206b5564b325390b6658f6b181c9d51fc44d04",
      "quote": "There’s not enough evidence to support the use of evening primrose oil for any health condition. Evening primrose oil, taken orally, has not been shown to be helpful for relieving symptoms of atopic dermatitis."
    },
    "hc-epo": {
      "chunkId": "hc-nhpid-primrose-onagre2#002",
      "docId": "hc-nhpid-primrose-onagre2",
      "source": "Health Canada NNHPD",
      "tier": "regulatory",
      "jurisdiction": "ca",
      "title": "EVENING PRIMROSE OIL",
      "date": "2026-02-27",
      "nextReview": "2027-10-28",
      "section": "indications",
      "identifier": "primrose.onagre2",
      "url": "https://webprod.hc-sc.gc.ca/nhpid-bdipsn/atReq?atid=primrose.onagre2&lang=eng",
      "licence": "Open Government Licence – Canada",
      "checksum": "sha256:49d6c6d1895b91662e3e3ff1de8e7415b1bcfbe3cab09d0134266486c904c543",
      "quote": "Source of essential fatty acids for the maintenance of good health (Brayfield and Cadart 2024; IOM 2006). Source of omega-6 fatty acids for the maintenance of good health (IOM 2006; Mills and Bone 2005; WHO 2002)."
    },
    "ferritin-interval": {
      "chunkId": "medlineplus-003490#005",
      "docId": "medlineplus-003490",
      "source": "MedlinePlus (NLM)",
      "tier": "compendium",
      "jurisdiction": "us",
      "title": "Ferritin blood test",
      "date": "2026-01-10",
      "nextReview": "2027-04-29",
      "section": "reference interval",
      "identifier": "https://medlineplus.gov/ency/article/003490.htm",
      "url": "https://medlineplus.gov/ency/article/003490.htm",
      "licence": "US federal work — public domain (NLM MedlinePlus)",
      "checksum": "sha256:662deb5df103f00f5284ed2f509d9c9295498fc36ba8bf46306d29f694325de0",
      "quote": "The normal value ranges for blood ferritin are: Male: 30 to 400 nanograms per milliliter (ng/mL) Female: 13 to 150 ng/mL"
    },
    "b12-interval": {
      "chunkId": "medlineplus-003705#005",
      "docId": "medlineplus-003705",
      "source": "MedlinePlus (NLM)",
      "tier": "compendium",
      "jurisdiction": "us",
      "title": "Vitamin B12 level",
      "date": "2026-01-10",
      "nextReview": "2027-04-29",
      "section": "reference interval",
      "identifier": "https://medlineplus.gov/ency/article/003705.htm",
      "url": "https://medlineplus.gov/ency/article/003705.htm",
      "licence": "US federal work — public domain (NLM MedlinePlus)",
      "checksum": "sha256:ce2c1c3c492868b13c9fba6c577ef800ce21d5d44af5f8a7e297d49b06a8d9ae",
      "quote": "Normal values are 299 to 1054 picograms per milliliter (pg/mL), or 219 to 773 picomoles per liter (pmol/L)."
    },
    "tsh-interval": {
      "chunkId": "medlineplus-003684#005",
      "docId": "medlineplus-003684",
      "source": "MedlinePlus (NLM)",
      "tier": "compendium",
      "jurisdiction": "us",
      "title": "TSH test",
      "date": "2026-01-25",
      "nextReview": "2027-04-29",
      "section": "reference interval",
      "identifier": "https://medlineplus.gov/ency/article/003684.htm",
      "url": "https://medlineplus.gov/ency/article/003684.htm",
      "licence": "US federal work — public domain (NLM MedlinePlus)",
      "checksum": "sha256:4f196dc2488ce5ad6f35f845592ea2b582ae9639d1ef28807d750fff45ff07dd",
      "quote": "Normal values range from 0.4 to 4.8 microunits per milliliter (µU/mL)."
    }
  },
  "ask": {
    "question": "I'm 68, on warfarin for atrial fibrillation. Is ginkgo safe for my memory?",
    "questionMeta": "A02 · herb–drug interaction · one context on file",
    "answer": [
      {
        "text": "Health Canada's ginkgo monograph says not to use ginkgo if you are taking blood thinners.",
        "cites": [
          "hc-ginkgo"
        ]
      },
      {
        "text": "The EMA monograph does not report an established warfarin interaction, but advises adequate monitoring when starting, changing, or ending ginkgo.",
        "cites": [
          "ema-ginkgo-interactions"
        ]
      },
      {
        "text": "NCCIH lists ginkgo as possibly increasing bleeding risk in people taking anticoagulants such as warfarin.",
        "cites": [
          "nccih-ginkgo"
        ]
      }
    ],
    "verdict": {
      "label": "VETO",
      "title": "Taking warfarin",
      "body": "Health Canada's contraindication is the most restrictive source, so the deterministic screen blocks ginkgo for this patient. The sources disagree on strength; the disagreement is shown below, not averaged."
    },
    "conflict": {
      "title": "Sources differ on strength",
      "note": "Shown, never synthesised. The safety screen takes the most restrictive warning; the EMA's monitoring advice is retained as context.",
      "sides": [
        {
          "sourceId": "ema-ginkgo-interactions",
          "marker": "Monitoring advised",
          "summary": "No established warfarin interaction; monitor when starting, changing, or ending ginkgo."
        },
        {
          "sourceId": "hc-ginkgo",
          "marker": "Most restrictive",
          "summary": "Do not use with blood thinners or other products that affect coagulation."
        },
        {
          "sourceId": "nccih-ginkgo",
          "marker": "Supports caution",
          "summary": "May increase bleeding risk in people taking anticoagulants such as warfarin."
        }
      ]
    },
    "memory": {
      "query": "Does comfrey help osteoarthritis?",
      "coverage": "0 documents match “comfrey” in the current corpus.",
      "answer": "Comfrey has a history of topical use for joint and muscle pain. I do not have a corpus source for that statement, so treat it as model knowledge, not a citation.",
      "label": "UNCITED · MODEL KNOWLEDGE",
      "next": "Add this to the corpus gap queue? The corpus has no comfrey document to cite."
    }
  },
  "cases": {
    "a02": {
      "id": "A02",
      "initials": "M. R.",
      "age": 68,
      "sex": "male",
      "context": "Atrial fibrillation · warfarin",
      "duration": "not stated",
      "severity": "not stated",
      "query": "I'm on warfarin for atrial fibrillation, 68 years old. Can I take ginkgo for memory?",
      "redFlags": [],
      "check": "No red flags identified from what was described. This is not a diagnosis.",
      "options": [
        {
          "name": "Ginkgo (Ginkgo biloba)",
          "status": "vetoed",
          "reason": "Taking warfarin (VETO).",
          "sourceId": "hc-ginkgo"
        }
      ],
      "safety": {
        "severity": "veto",
        "label": "Taking warfarin",
        "intervention": "Ginkgo (Ginkgo biloba)",
        "sourceId": "hc-ginkgo",
        "note": "The most restrictive source governs. EMA does not establish an interaction but advises monitoring; Health Canada says do not use with blood thinners. Both remain visible."
      },
      "monitor": "No supplement monitoring plan while the veto stands. If the prescriber is considering a change, EMA advises monitoring when starting, changing, or ending ginkgo.",
      "gaps": "The corpus does not answer whether a non-drug memory support option is effective. No replacement option was generated.",
      "evidenceIds": [
        "hc-ginkgo",
        "ema-ginkgo-interactions",
        "nccih-ginkgo",
        "ema-ginkgo-adverse"
      ],
      "conflict": true
    },
    "c02": {
      "id": "C02",
      "initials": "J. T.",
      "age": 34,
      "sex": "male",
      "context": "No medications · no conditions",
      "duration": "6 weeks",
      "severity": "mild",
      "query": "34 year old man with difficulty falling asleep for six weeks, mild. No meds, no conditions. Is magnesium or valerian supported?",
      "redFlags": [],
      "check": "No red flags identified from what was described. This is not a diagnosis.",
      "options": [
        {
          "name": "Valerian root dry extract",
          "status": "offered",
          "reason": "Single dose: 400-600 mg dry extract. For relief of mild nervous tension up to 3 times daily.",
          "sourceId": "ema-valerian",
          "dose": "400-600 mg dry extract",
          "doseVerified": true
        },
        {
          "name": "Magnesium",
          "status": "not-offered",
          "reason": "No retrieved source for magnesium and sleep in this corpus. Not offered.",
          "sourceId": null
        }
      ],
      "safety": {
        "severity": "none",
        "label": "No safety findings",
        "intervention": "—",
        "sourceId": null,
        "note": "No medications, pregnancy, or conditions were reported. The screen has nothing to veto."
      },
      "monitor": "Sleep diary for two weeks; return if insomnia persists or worsens.",
      "gaps": "NCCIH: the evidence on valerian for sleep is inconsistent, and the American Academy of Sleep Medicine recommended against it for chronic insomnia in adults.",
      "evidenceIds": [
        "ema-valerian",
        "nccih-valerian"
      ],
      "conflict": false
    },
    "rf01": {
      "id": "RF01",
      "initials": "R. K.",
      "age": 54,
      "sex": "not stated",
      "context": "Chest pain · sweating · left arm and jaw",
      "duration": "1 hour",
      "severity": "severe",
      "query": "I'm 54 and for the last hour I've had crushing chest pain radiating to my left arm and jaw, and I'm sweating.",
      "redFlags": [
        "rf-chest-pain"
      ],
      "stopped": true,
      "rule": {
        "id": "rf-chest-pain",
        "urgency": "emergency",
        "action": "Call emergency services now. Do not drive yourself.",
        "source": "NHS — heart attack",
        "url": "https://www.nhs.uk/conditions/heart-attack/"
      }
    }
  },
  "lab": {
    "doc": {
      "title": "0013 Bloodspot Amino Acids 11 Profile",
      "lab": "Genova Diagnostics",
      "page": "Page 2",
      "collected": "2012-01-15",
      "reported": "2012-01-16",
      "accession": "A1201160021",
      "unit": "µmol/L",
      "url": "https://www.nutripath.com.au/wp-content/uploads/2015/07/5043-Amino-Acids-11-BloodSpot.pdf",
      "note": "Public “Sample Report” hosted by NutriPath (AU). Local evaluation fixture, not corpus. Not a patient."
    },
    "rows": [
      {
        "analyte": "Lysine",
        "value": 124,
        "unit": "µmol/L",
        "low": 63,
        "high": 220,
        "flag": "",
        "conf": 0.99,
        "status": "confirmed",
        "y": 47.7
      },
      {
        "analyte": "Methionine",
        "value": 10,
        "unit": "µmol/L",
        "low": 10,
        "high": 33,
        "flag": "L",
        "conf": 0.94,
        "status": "confirmed",
        "y": 50.6
      },
      {
        "analyte": "Tryptophan",
        "value": 24,
        "unit": "µmol/L",
        "low": 24,
        "high": 52,
        "flag": "L",
        "conf": 0.91,
        "status": "confirmed",
        "y": 53.4
      },
      {
        "analyte": "Isoleucine",
        "value": 51,
        "unit": "µmol/L",
        "low": 28,
        "high": 96,
        "flag": "",
        "conf": 0.97,
        "status": "confirmed",
        "y": 58.4
      },
      {
        "analyte": "Leucine",
        "value": 126,
        "unit": "µmol/L",
        "low": 59,
        "high": 162,
        "flag": "",
        "conf": 0.98,
        "status": "confirmed",
        "y": 61.3
      },
      {
        "analyte": "Valine",
        "value": 175,
        "unit": "µmol/L",
        "low": 105,
        "high": 266,
        "flag": "",
        "conf": 0.97,
        "status": "confirmed",
        "y": 64.1
      },
      {
        "analyte": "Phenylalanine",
        "value": 40,
        "unit": "µmol/L",
        "low": 37,
        "high": 86,
        "flag": "L",
        "conf": 0.74,
        "status": "review",
        "y": 69
      },
      {
        "analyte": "Histidine",
        "value": 67,
        "unit": "µmol/L",
        "low": 22,
        "high": 99,
        "flag": "",
        "conf": 0.96,
        "status": "confirmed",
        "y": 71.9
      },
      {
        "analyte": "Threonine",
        "value": 101,
        "unit": "µmol/L",
        "low": 54,
        "high": 169,
        "flag": "",
        "conf": 0.95,
        "status": "confirmed",
        "y": 74.8
      },
      {
        "analyte": "Arginine",
        "value": 66,
        "unit": "µmol/L",
        "low": 17,
        "high": 91,
        "flag": "",
        "conf": 0.93,
        "status": "confirmed",
        "y": 79.7
      },
      {
        "analyte": "Taurine",
        "value": 165,
        "unit": "µmol/L",
        "low": 124,
        "high": 282,
        "flag": "",
        "conf": 0.92,
        "status": "ready",
        "y": 82.6
      },
      {
        "analyte": "Tryptophan/LNAA",
        "value": 0.052,
        "unit": "ratio",
        "low": 0.05,
        "high": 0.105,
        "flag": "",
        "conf": 0.9,
        "status": "confirmed",
        "y": 87.4
      }
    ],
    "checks": [
      "Value inside the plausibility range for this analyte",
      "Unit recognised and matches the lab's unit",
      "Reference interval present on the source page",
      "Collection date present",
      "Two independent reads agree (text layer + OCR)"
    ],
    "interpretation": {
      "lowFlag": 3,
      "atOrBelow": 2,
      "insideButFlagged": 1,
      "outsidePlausible": 0,
      "ratio": "0.052",
      "ratioInterval": "0.050–0.105",
      "note": "No corpus pattern rules for this panel. The UI reports the lab's own flags and deterministic checks; it does not diagnose. Phenylalanine is inside the interval but carries the lab's L flag from its quintile ranking."
    }
  },
  "atlas": {
    "nodes": [
      {
        "id": "ginkgo",
        "label": "Ginkgo",
        "x": 190,
        "y": 160
      },
      {
        "id": "warfarin",
        "label": "Warfarin",
        "x": 130,
        "y": 390
      },
      {
        "id": "bleeding",
        "label": "Bleeding",
        "x": 345,
        "y": 500
      },
      {
        "id": "surgery",
        "label": "Surgery",
        "x": 410,
        "y": 285
      },
      {
        "id": "valerian",
        "label": "Valerian",
        "x": 640,
        "y": 160
      },
      {
        "id": "sleep",
        "label": "Sleep",
        "x": 800,
        "y": 270
      },
      {
        "id": "epo",
        "label": "Evening primrose",
        "x": 620,
        "y": 450
      },
      {
        "id": "eczema",
        "label": "Eczema",
        "x": 835,
        "y": 500
      }
    ],
    "edges": [
      {
        "id": "ginkgo-warfarin",
        "from": "ginkgo",
        "to": "warfarin",
        "label": "anticoagulant",
        "conflict": true,
        "description": "Anticoagulant interaction and bleeding risk.",
        "safety": "Most restrictive source governs: Health Canada says do not use ginkgo with blood thinners. The deterministic screen vetoes ginkgo for a patient on warfarin.",
        "sourceIds": [
          "ema-ginkgo-interactions",
          "hc-ginkgo",
          "nccih-ginkgo"
        ],
        "markers": {
          "ema-ginkgo-interactions": "Monitoring advised",
          "hc-ginkgo": "Most restrictive",
          "nccih-ginkgo": "Supports caution"
        }
      },
      {
        "id": "ginkgo-bleeding",
        "from": "ginkgo",
        "to": "bleeding",
        "label": "bleeding risk",
        "conflict": false,
        "description": "Bleeding is an adverse effect listed by EMA; NCCIH flags the same risk.",
        "safety": "Both sources point the same way. There is no divergence to resolve.",
        "sourceIds": [
          "ema-ginkgo-adverse",
          "nccih-ginkgo"
        ],
        "markers": {
          "ema-ginkgo-adverse": "Adverse effect",
          "nccih-ginkgo": "Bleeding risk"
        }
      },
      {
        "id": "ginkgo-surgery",
        "from": "ginkgo",
        "to": "surgery",
        "label": "contraindication",
        "conflict": false,
        "description": "Health Canada says do not use ginkgo if you are having surgery.",
        "safety": "Contraindication is explicit in the cited monograph.",
        "sourceIds": [
          "hc-ginkgo"
        ],
        "markers": {
          "hc-ginkgo": "Contraindication"
        }
      },
      {
        "id": "valerian-sleep",
        "from": "valerian",
        "to": "sleep",
        "label": "evidence gap",
        "conflict": false,
        "description": "A dose exists; evidence for sleep is inconsistent.",
        "safety": "No safety veto. The gap is efficacy, not safety.",
        "sourceIds": [
          "ema-valerian",
          "nccih-valerian"
        ],
        "markers": {
          "ema-valerian": "Dose",
          "nccih-valerian": "Evidence gap"
        }
      },
      {
        "id": "epo-eczema",
        "from": "epo",
        "to": "eczema",
        "label": "efficacy",
        "conflict": true,
        "description": "A permitted fatty-acid claim sits beside a finding of no evidence for eczema.",
        "safety": "Efficacy divergence only. No safety veto is implied by either source.",
        "sourceIds": [
          "nccih-epo",
          "hc-epo"
        ],
        "markers": {
          "nccih-epo": "No evidence",
          "hc-epo": "Permitted claim"
        }
      }
    ],
    "coverage": {
      "total": {
        "covered": 46,
        "n": 104,
        "pct": "44.2%",
        "ci": "[35.1, 53.8]"
      },
      "groups": [
        {
          "label": "Subject questions",
          "covered": 22,
          "n": 53,
          "pct": "41.5%",
          "ci": "[29.3, 54.9]"
        },
        {
          "label": "Lab questions",
          "covered": 20,
          "n": 31,
          "pct": "64.5%",
          "ci": "[46.9, 78.9]"
        },
        {
          "label": "No subject named",
          "covered": 4,
          "n": 20,
          "pct": "20.0%",
          "ci": "[8.1, 41.6]"
        }
      ],
      "audit": "Coverage is not support or accuracy. A stratified audit of 11 covered items found 6 supported, 5 unsupported or uncertain (2026-10-29).",
      "corpus": {
        "docs": 377,
        "chunks": 4012,
        "tiers": {
          "regulatory": 243,
          "compendium": 102,
          "primary": 32
        },
        "jurisdictions": {
          "ca": 222,
          "us": 125,
          "eu": 21,
          "international": 9
        }
      }
    }
  }
};
