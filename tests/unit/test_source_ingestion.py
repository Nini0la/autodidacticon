from conftest import ALLOWED_EXTRACTION_STATUS, ALLOWED_SOURCE_TYPES, assert_ulid


def test_ingest_source_emits_required_source_fields(sut, new_ulid, sample_source_text):
    decision = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Photosynthesis",
            "source_input": sample_source_text,
            "entry_mode": "source_provided",
        }
    )
    topic_id = decision["topic_id"]
    sources = sut.ingest_source(decision)
    assert sources

    for source in sources:
        assert_ulid(source["source_id"], field_name="source_id")
        assert source["topic_id"] == topic_id
        assert source["source_type"] in ALLOWED_SOURCE_TYPES
        assert isinstance(source["content_hash"], str) and source["content_hash"]
        assert isinstance(source["extracted_text"], str)
        assert source["extraction_status"] in ALLOWED_EXTRACTION_STATUS


def test_ingest_source_content_hash_is_stable_on_retry(sut, new_ulid, sample_source_text):
    decision = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Cell biology",
            "source_input": sample_source_text,
            "entry_mode": "source_provided",
        }
    )
    first = sut.ingest_source(decision)
    second = sut.ingest_source(decision)

    first_hashes = {src["content_hash"] for src in first}
    second_hashes = {src["content_hash"] for src in second}
    assert first_hashes == second_hashes
