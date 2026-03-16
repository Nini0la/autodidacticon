def test_adaptation_prefers_reinforcement_for_weak_state(sut, new_ulid):
    weak_state = {
        "mastery_score": 0.25,
        "weak_concepts": [new_ulid()],
        "strong_concepts": [],
        "evidence_references": [new_ulid()],
        "recommended_next_action_candidates": ["reinforce weak concepts"],
    }
    plan = sut.decide_next_step(weak_state)
    action = sut.normalize_action(sut.action_value(plan))
    assert action in {"reinforce_weak_concepts", "generate_reinforcement_cards"}


def test_adaptation_allows_deepen_or_move_on_strong_state(sut, new_ulid):
    strong_state = {
        "mastery_score": 0.92,
        "weak_concepts": [],
        "strong_concepts": [new_ulid(), new_ulid()],
        "evidence_references": [new_ulid()],
        "recommended_next_action_candidates": ["deepen mastered concepts", "move topic"],
    }
    plan = sut.decide_next_step(strong_state)
    action = sut.normalize_action(sut.action_value(plan))
    assert action in {"deepen_mastered_concepts", "move_topic"}
