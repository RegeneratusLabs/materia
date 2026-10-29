from materia.attribute import attribute

CHUNK = {"chunk_id": "ema-ginkgo#005", "source": "EMA (HMPC)",
         "text": "Concomitant use with anticoagulants such as warfarin increases bleeding risk."}


def test_supported_option_is_grounded():
    out = attribute("Ginkgo's antiplatelet effect adds to anticoagulation and increases bleeding risk", CHUNK)
    assert out["mode"] == "grounded" and out["chunk_id"] == "ema-ginkgo#005"


def test_unrelated_option_is_memory():
    out = attribute("Kava causes hepatotoxicity", CHUNK)
    assert out["mode"] == "memory" and "does not carry" in out["reason"]


def test_no_reference_is_memory():
    out = attribute("Anything", None)
    assert out["mode"] == "memory" and out["chunk_id"] is None


def test_entity_mismatch_is_not_grounded():
    chunk = {"chunk_id": "nccih-astragalus#005", "source": "NCCIH", "entities": ["Astragalus"],
             "text": "Astragalus may be safe when used orally. Immune effects are uncertain."}
    out = attribute("Echinacea, because of immunostimulant effects", chunk,
                    question="Which herb should be avoided with immunosuppressants? Echinacea?")
    assert out["mode"] == "memory" and "Astragalus" in out["reason"]


def test_entity_match_keeps_grounded():
    chunk = {"chunk_id": "ema-ginkgo#005", "source": "EMA", "entities": ["Ginkgo"],
             "text": "Concomitant use with anticoagulants such as warfarin increases bleeding risk."}
    out = attribute("Ginkgo increases bleeding risk with warfarin", chunk,
                    question="Is ginkgo safe with warfarin?")
    assert out["mode"] == "grounded"
