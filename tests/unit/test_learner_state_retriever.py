from conftest import ALLOWED_RESPONSE_STATUS, assert_ulid


def test_get_topic_state_returns_required_fields(sut, new_ulid, sample_source_text):
    user_id = new_ulid()
    session_id = new_ulid()
    ctx = sut.run_source_provided_flow(
        user_id=user_id,
        session_id=session_id,
        topic_title="Photosynthesis",
        source_input=sample_source_text,
    )
    question = ctx["question_units"][0]

    logged = sut.log_interaction(
        {
            "user_id": user_id,
            "session_id": session_id,
            "topic_id": ctx["topic_id"],
            "concept_id": question["concept_id"],
            "unit_id": question["unit_id"],
            "response_status": "got_it",
            "difficulty": "easy",
        }
    )
    assert_ulid(logged["interaction_id"], field_name="interaction_id")

    state = sut.retrieve_state(user_id=user_id, topic_id=ctx["topic_id"])
    score = sut.mastery_score(state)
    assert 0.0 <= score <= 1.0

    evidence = sut.evidence_ids(state)
    assert logged["interaction_id"] in evidence


def test_get_topic_state_uses_question_interactions_only(sut, new_ulid, sample_source_text):
    user_id = new_ulid()
    session_id = new_ulid()
    ctx = sut.run_source_provided_flow(
        user_id=user_id,
        session_id=session_id,
        topic_title="Biochemistry",
        source_input=sample_source_text,
    )
    question = ctx["question_units"][0]

    payload = {
        "user_id": user_id,
        "session_id": session_id,
        "topic_id": ctx["topic_id"],
        "concept_id": question["concept_id"],
        "unit_id": question["unit_id"],
        "response_status": "partially_got_it",
        "difficulty": "medium",
    }
    assert payload["response_status"] in ALLOWED_RESPONSE_STATUS
    logged = sut.log_interaction(payload)
    assert_ulid(logged["interaction_id"], field_name="interaction_id")

    state = sut.retrieve_state(user_id=user_id, topic_id=ctx["topic_id"])
    weak = sut.weak_concepts(state)
    strong = sut.strong_concepts(state)
    assert weak.isdisjoint(strong)
