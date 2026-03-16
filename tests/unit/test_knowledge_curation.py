from conftest import ALLOWED_DEPTH_LEVELS, assert_ulid


def test_curate_concepts_emits_valid_concept_records(sut, new_ulid, sample_source_text):
    decision = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Photosynthesis",
            "source_input": sample_source_text,
            "entry_mode": "source_provided",
        }
    )
    sources = sut.ingest_source(decision)
    concepts = sut.curate_concepts(sources)
    assert concepts

    for concept in concepts:
        assert_ulid(concept["concept_id"], field_name="concept_id")
        assert concept["topic_id"] == decision["topic_id"]
        assert isinstance(concept["label"], str) and concept["label"]
        assert isinstance(concept["summary"], str) and concept["summary"]
        assert concept["depth_level"] in ALLOWED_DEPTH_LEVELS


def test_curate_concepts_preserves_source_and_json_fields(sut, new_ulid, sample_source_text):
    decision = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Plant physiology",
            "source_input": sample_source_text,
            "entry_mode": "source_provided",
        }
    )
    sources = sut.ingest_source(decision)
    source_ids = {s["source_id"] for s in sources}
    concepts = sut.curate_concepts(sources)

    for concept in concepts:
        if concept.get("source_id") is not None:
            assert concept["source_id"] in source_ids
        misconceptions = concept.get("misconceptions_json", [])
        relationships = concept.get("relationships_json", [])
        assert isinstance(misconceptions, list)
        assert isinstance(relationships, list)
