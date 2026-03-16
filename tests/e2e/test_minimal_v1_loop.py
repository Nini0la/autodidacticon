from conftest import assert_ulid


def test_minimal_v1_loop_intake_to_adaptation(sut, new_ulid, sample_source_text):
    user_id = new_ulid()
    session_id = new_ulid()

    ctx = sut.run_source_provided_flow(
        user_id=user_id,
        session_id=session_id,
        topic_title="End-to-end v1 topic",
        source_input=sample_source_text,
    )

    first_question = ctx["question_units"][0]
    interaction = sut.log_interaction(
        {
            "user_id": user_id,
            "session_id": session_id,
            "topic_id": ctx["topic_id"],
            "concept_id": first_question["concept_id"],
            "unit_id": first_question["unit_id"],
            "response_status": "partially_got_it",
            "difficulty": "medium",
            "idempotency_key": f"e2e-{new_ulid()}",
        }
    )
    assert_ulid(interaction["interaction_id"], field_name="interaction_id")

    state = sut.retrieve_state(user_id=user_id, topic_id=ctx["topic_id"])
    assert 0.0 <= sut.mastery_score(state) <= 1.0
    assert interaction["interaction_id"] in sut.evidence_ids(state)

    adaptation = sut.decide_next_step(state)
    normalized_action = sut.normalize_action(sut.action_value(adaptation))
    assert normalized_action in {
        "reinforce_weak_concepts",
        "generate_reinforcement_cards",
        "deepen_mastered_concepts",
        "move_topic",
    }
