from conftest import ALLOWED_ROUTES, assert_ulid


def test_route_intake_source_provided(sut, new_ulid, sample_source_text):
    decision = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Photosynthesis basics",
            "source_input": sample_source_text,
            "entry_mode": "source_provided",
        }
    )
    assert sut.route_value(decision) == "source_provided"
    assert_ulid(decision["topic_id"], field_name="topic_id")


def test_route_intake_topic_only(sut, new_ulid):
    decision = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Distributed systems",
            "entry_mode": "topic_only",
        }
    )
    assert sut.route_value(decision) == "topic_only"
    assert_ulid(decision["topic_id"], field_name="topic_id")


def test_route_intake_deepen_topic(sut, new_ulid):
    seed = sut.route_intake(
        {
            "user_id": new_ulid(),
            "session_id": new_ulid(),
            "topic_title": "Seed topic",
            "entry_mode": "topic_only",
        }
    )
    existing_topic_id = seed["topic_id"]
    decision = sut.route_intake(
        {
            "user_id": seed["user_id"],
            "session_id": new_ulid(),
            "topic_id": existing_topic_id,
            "entry_mode": "deepen_topic",
            "intent": "deepen_topic",
        }
    )
    route = sut.route_value(decision)
    assert route in ALLOWED_ROUTES
    assert route == "deepen_topic"
    assert decision["topic_id"] == existing_topic_id


def test_route_intake_deepen_unknown_topic_rejected(sut, new_ulid):
    payload = {
        "user_id": new_ulid(),
        "session_id": new_ulid(),
        "topic_id": new_ulid(),
        "entry_mode": "deepen_topic",
        "intent": "deepen_topic",
    }
    try:
        sut.route_intake(payload)
    except Exception:
        return
    raise AssertionError("Unknown topic_id in deepen_topic flow should be rejected.")
