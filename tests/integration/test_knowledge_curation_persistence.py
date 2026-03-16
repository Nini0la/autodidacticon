from conftest import ALLOWED_DEPTH_LEVELS


def test_curated_concepts_persist_with_topic_and_source_links(sut, new_ulid, sample_source_text):
    decision = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Cell respiration",
            "source_input": sample_source_text,
            "entry_mode": "source_provided",
        }
    )
    sources = sut.ingest_source(decision)
    source_ids = {s["source_id"] for s in sources}

    concepts = sut.curate_concepts(sources)
    assert concepts
    for concept in concepts:
        assert concept["topic_id"] == decision["topic_id"]
        if concept.get("source_id") is not None:
            assert concept["source_id"] in source_ids


def test_curated_concepts_keep_valid_depth_and_json_arrays(sut, new_ulid, sample_source_text):
    decision = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Plant metabolism",
            "source_input": sample_source_text,
            "entry_mode": "source_provided",
        }
    )
    concepts = sut.curate_concepts(sut.ingest_source(decision))
    assert concepts

    for concept in concepts:
        assert concept["depth_level"] in ALLOWED_DEPTH_LEVELS
        assert isinstance(concept.get("misconceptions_json", []), list)
        assert isinstance(concept.get("relationships_json", []), list)
