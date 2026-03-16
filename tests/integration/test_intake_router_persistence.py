from conftest import ALLOWED_SOURCE_TYPES


def test_source_provided_flow_links_sources_to_resolved_topic(sut, new_ulid, sample_source_text):
    decision = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Photosynthesis",
            "source_input": sample_source_text,
            "entry_mode": "source_provided",
        }
    )
    assert sut.route_value(decision) == "source_provided"

    sources = sut.ingest_source(decision)
    assert sources
    assert all(source["topic_id"] == decision["topic_id"] for source in sources)


def test_topic_only_flow_can_continue_into_source_material_stage(sut, new_ulid):
    decision = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Linear algebra",
            "entry_mode": "topic_only",
        }
    )
    assert sut.route_value(decision) == "topic_only"

    sources = sut.ingest_source(decision)
    assert sources
    assert all(source["topic_id"] == decision["topic_id"] for source in sources)
    assert all(source["source_type"] in ALLOWED_SOURCE_TYPES for source in sources)
