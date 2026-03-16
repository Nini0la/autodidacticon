from collections import Counter

from conftest import ALLOWED_CARD_TYPES, ALLOWED_DEPTH_LEVELS, assert_ulid


def test_generate_cards_creates_learning_question_pairs(sut, new_ulid, sample_source_text):
    ctx = sut.run_source_provided_flow(
        user_id=new_ulid(),
        session_id=new_ulid(),
        topic_title="Photosynthesis",
        source_input=sample_source_text,
    )
    units = ctx["units"]
    concepts = ctx["concepts"]
    assert units

    learning_units, question_units = sut.split_units(units)
    assert learning_units
    assert question_units

    learning_ids = {u["unit_id"] for u in learning_units}
    by_concept = Counter((u["concept_id"], u["card_type"]) for u in units)

    for concept in concepts:
        concept_id = concept["concept_id"]
        assert by_concept[(concept_id, "learning")] >= 1
        assert by_concept[(concept_id, "question")] >= 1

    for unit in units:
        assert_ulid(unit["unit_id"], field_name="unit_id")
        assert unit["card_type"] in ALLOWED_CARD_TYPES
        assert unit["depth_level"] in ALLOWED_DEPTH_LEVELS
        if unit["card_type"] == "question":
            assert unit.get("related_unit_id") in learning_ids


def test_generate_cards_retry_preserves_idempotent_shape(sut, new_ulid, sample_source_text):
    decision = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Chloroplast function",
            "source_input": sample_source_text,
            "entry_mode": "source_provided",
        }
    )
    sources = sut.ingest_source(decision)
    concepts = sut.curate_concepts(sources)

    first = sut.generate_cards(concepts, depth_level="core")
    second = sut.generate_cards(concepts, depth_level="core")

    first_shape = Counter((u["concept_id"], u["card_type"], int(u.get("version", 1))) for u in first)
    second_shape = Counter((u["concept_id"], u["card_type"], int(u.get("version", 1))) for u in second)
    assert first_shape == second_shape
