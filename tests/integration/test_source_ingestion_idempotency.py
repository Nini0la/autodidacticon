def test_duplicate_ingestion_is_idempotent_within_topic(sut, new_ulid, sample_source_text):
    decision = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Plant cells",
            "source_input": sample_source_text,
            "entry_mode": "source_provided",
        }
    )
    first = sut.ingest_source(decision)
    second = sut.ingest_source(decision)

    assert {s["content_hash"] for s in first} == {s["content_hash"] for s in second}
    assert {s["source_id"] for s in first} == {s["source_id"] for s in second}


def test_same_content_is_allowed_across_different_topics(sut, new_ulid, sample_source_text):
    decision_a = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Topic A",
            "source_input": sample_source_text,
            "entry_mode": "source_provided",
        }
    )
    decision_b = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Topic B",
            "source_input": sample_source_text,
            "entry_mode": "source_provided",
        }
    )
    sources_a = sut.ingest_source(decision_a)
    sources_b = sut.ingest_source(decision_b)

    assert decision_a["topic_id"] != decision_b["topic_id"]
    assert sources_a and sources_b
    assert all(src["topic_id"] == decision_a["topic_id"] for src in sources_a)
    assert all(src["topic_id"] == decision_b["topic_id"] for src in sources_b)
