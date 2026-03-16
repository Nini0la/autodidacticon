import pytest

from conftest import assert_ulid


def _log_series(
    sut,
    *,
    user_id: str,
    session_id: str,
    topic_id: str,
    concept_id: str,
    unit_id: str,
    statuses: list[str],
    difficulties: list[str | None],
    key_prefix: str,
) -> list[str]:
    logged_ids: list[str] = []
    for idx, (status, difficulty) in enumerate(zip(statuses, difficulties, strict=True)):
        payload = {
            "user_id": user_id,
            "session_id": session_id,
            "topic_id": topic_id,
            "concept_id": concept_id,
            "unit_id": unit_id,
            "response_status": status,
            "difficulty": difficulty,
            "idempotency_key": f"{key_prefix}-{idx}",
        }
        logged = sut.log_interaction(payload)
        assert_ulid(logged["interaction_id"], field_name="interaction_id")
        logged_ids.append(logged["interaction_id"])
    return logged_ids


def test_weak_concept_detection_threshold(sut, new_ulid, sample_source_text):
    user_id = new_ulid()
    session_id = new_ulid()
    ctx = sut.run_source_provided_flow(
        user_id=user_id,
        session_id=session_id,
        topic_title="Weak threshold",
        source_input=sample_source_text,
    )
    question = ctx["question_units"][0]

    statuses = ["did_not_get_it"] * 3 + ["got_it"] * 7
    difficulties = ["hard"] * 3 + ["easy"] * 7
    _log_series(
        sut,
        user_id=user_id,
        session_id=session_id,
        topic_id=ctx["topic_id"],
        concept_id=question["concept_id"],
        unit_id=question["unit_id"],
        statuses=statuses,
        difficulties=difficulties,
        key_prefix="weak",
    )
    state = sut.retrieve_state(user_id=user_id, topic_id=ctx["topic_id"])
    assert question["concept_id"] in sut.weak_concepts(state)


def test_strong_concept_detection_threshold(sut, new_ulid, sample_source_text):
    user_id = new_ulid()
    session_id = new_ulid()
    ctx = sut.run_source_provided_flow(
        user_id=user_id,
        session_id=session_id,
        topic_title="Strong threshold",
        source_input=sample_source_text,
    )
    question = ctx["question_units"][0]

    statuses = ["got_it"] * 8
    difficulties = ["easy"] * 8
    _log_series(
        sut,
        user_id=user_id,
        session_id=session_id,
        topic_id=ctx["topic_id"],
        concept_id=question["concept_id"],
        unit_id=question["unit_id"],
        statuses=statuses,
        difficulties=difficulties,
        key_prefix="strong",
    )
    state = sut.retrieve_state(user_id=user_id, topic_id=ctx["topic_id"])
    assert question["concept_id"] in sut.strong_concepts(state)


def test_mastery_score_heuristic_and_evidence_ids(sut, new_ulid, sample_source_text):
    user_id = new_ulid()
    session_id = new_ulid()
    ctx = sut.run_source_provided_flow(
        user_id=user_id,
        session_id=session_id,
        topic_title="Mastery score",
        source_input=sample_source_text,
    )
    question = ctx["question_units"][0]

    logged_ids = _log_series(
        sut,
        user_id=user_id,
        session_id=session_id,
        topic_id=ctx["topic_id"],
        concept_id=question["concept_id"],
        unit_id=question["unit_id"],
        statuses=["got_it"],
        difficulties=["hard"],
        key_prefix="mastery",
    )
    state = sut.retrieve_state(user_id=user_id, topic_id=ctx["topic_id"])

    score = sut.mastery_score(state)
    assert score == pytest.approx(0.85, abs=1e-6)
    assert set(logged_ids).issubset(sut.evidence_ids(state))
