from conftest import assert_ulid


def test_duplicate_source_ingestion_returns_existing_record(sut, new_ulid, sample_source_text):
    decision = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Carbon cycle",
            "source_input": sample_source_text,
            "entry_mode": "source_provided",
        }
    )
    first = sut.ingest_source(decision)
    second = sut.ingest_source(decision)
    assert {s["source_id"] for s in first} == {s["source_id"] for s in second}


def test_interaction_logging_is_idempotent_with_client_key(sut, new_ulid, sample_source_text):
    user_id = new_ulid()
    session_id = new_ulid()
    ctx = sut.run_source_provided_flow(
        user_id=user_id,
        session_id=session_id,
        topic_title="Cell signaling",
        source_input=sample_source_text,
    )
    question = ctx["question_units"][0]
    idem_key = f"log-{new_ulid()}"

    payload = {
        "user_id": user_id,
        "session_id": session_id,
        "topic_id": ctx["topic_id"],
        "concept_id": question["concept_id"],
        "unit_id": question["unit_id"],
        "response_status": "partially_got_it",
        "difficulty": "medium",
        "idempotency_key": idem_key,
    }
    first = sut.log_interaction(payload)
    second = sut.log_interaction(payload)

    assert_ulid(first["interaction_id"], field_name="interaction_id")
    assert_ulid(second["interaction_id"], field_name="interaction_id")
    assert first["interaction_id"] == second["interaction_id"]
