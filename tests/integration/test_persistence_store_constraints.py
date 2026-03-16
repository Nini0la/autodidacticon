def test_interaction_rejects_learning_unit_reference(sut, new_ulid, sample_source_text):
    user_id = new_ulid()
    session_id = new_ulid()
    ctx = sut.run_source_provided_flow(
        user_id=user_id,
        session_id=session_id,
        topic_title="Mitochondria",
        source_input=sample_source_text,
    )
    learning_unit = ctx["learning_units"][0]

    sut.log_interaction_expect_rejected(
        {
            "user_id": user_id,
            "session_id": session_id,
            "topic_id": ctx["topic_id"],
            "concept_id": learning_unit["concept_id"],
            "unit_id": learning_unit["unit_id"],
            "response_status": "got_it",
            "difficulty": "easy",
        }
    )


def test_interaction_rejects_concept_topic_mismatch(sut, new_ulid, sample_source_text):
    user_id = new_ulid()
    session_id = new_ulid()
    ctx = sut.run_source_provided_flow(
        user_id=user_id,
        session_id=session_id,
        topic_title="Genetics",
        source_input=sample_source_text,
    )
    question_unit = ctx["question_units"][0]

    sut.log_interaction_expect_rejected(
        {
            "user_id": user_id,
            "session_id": session_id,
            "topic_id": new_ulid(),
            "concept_id": new_ulid(),
            "unit_id": question_unit["unit_id"],
            "response_status": "did_not_get_it",
            "difficulty": "hard",
        }
    )
