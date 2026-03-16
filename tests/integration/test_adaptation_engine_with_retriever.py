def _seed_topic_for_state(sut, *, user_id, session_id, topic_title, source_input, outcome, difficulty, count):
    ctx = sut.run_source_provided_flow(
        user_id=user_id,
        session_id=session_id,
        topic_title=topic_title,
        source_input=source_input,
    )
    question = ctx["question_units"][0]
    for i in range(count):
        sut.log_interaction(
            {
                "user_id": user_id,
                "session_id": session_id,
                "topic_id": ctx["topic_id"],
                "concept_id": question["concept_id"],
                "unit_id": question["unit_id"],
                "response_status": outcome,
                "difficulty": difficulty,
                "idempotency_key": f"{topic_title}-{i}",
            }
        )
    state = sut.retrieve_state(user_id=user_id, topic_id=ctx["topic_id"])
    return question["concept_id"], state


def test_adaptation_reinforces_weak_concepts_from_retrieved_state(sut, new_ulid, sample_source_text):
    concept_id, state = _seed_topic_for_state(
        sut,
        user_id=new_ulid(),
        session_id=new_ulid(),
        topic_title="Adapt weak",
        source_input=sample_source_text,
        outcome="did_not_get_it",
        difficulty="hard",
        count=6,
    )
    assert concept_id in sut.weak_concepts(state)

    plan = sut.decide_next_step(state)
    action = sut.normalize_action(sut.action_value(plan))
    assert action in {"reinforce_weak_concepts", "generate_reinforcement_cards"}


def test_adaptation_deepens_or_moves_for_strong_retrieved_state(sut, new_ulid, sample_source_text):
    concept_id, state = _seed_topic_for_state(
        sut,
        user_id=new_ulid(),
        session_id=new_ulid(),
        topic_title="Adapt strong",
        source_input=sample_source_text,
        outcome="got_it",
        difficulty="easy",
        count=8,
    )
    assert concept_id in sut.strong_concepts(state)

    plan = sut.decide_next_step(state)
    action = sut.normalize_action(sut.action_value(plan))
    assert action in {"deepen_mastered_concepts", "move_topic"}
