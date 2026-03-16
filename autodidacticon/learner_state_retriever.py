from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import Difficulty, ResponseStatus
from .persistence_store import get_store


def _score_interaction(response_status: str, difficulty: str | None) -> float:
    base = {
        ResponseStatus.got_it.value: 1.0,
        ResponseStatus.partially_got_it.value: 0.5,
        ResponseStatus.did_not_get_it.value: 0.0,
    }[response_status]
    if difficulty == Difficulty.hard.value:
        base -= 0.15
    return max(0.0, min(1.0, base))


class LearnerStateRetriever:
    def __init__(self, *, recent_window: int = 20, per_concept_weight_cap: int = 10) -> None:
        self.store = get_store()
        self.recent_window = recent_window
        self.per_concept_weight_cap = per_concept_weight_cap

    def get_topic_state(self, user_id: str, topic_id: str) -> dict[str, Any]:
        errors: list[str] = []
        try:
            rows = self.store.get_interactions(user_id=user_id, topic_id=topic_id, limit=self.recent_window)
        except TimeoutError:
            fallback = self.store.get_recent_user_interactions(user_id=user_id, limit=self.recent_window)
            evidence = [i.interaction_id for i in fallback]
            return {
                "user_id": user_id,
                "topic_id": topic_id,
                "concept_performance": {},
                "weak_concepts": [],
                "strong_concepts": [],
                "mastery_score": 0.0,
                "evidence_references": evidence,
                "recommended_next_action_candidates": ["reinforce_recent_weak"],
                "errors": ["retrieval_timeout"],
            }

        concept_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "got_it_count": 0,
                "did_not_get_it_count": 0,
                "hard_count": 0,
                "score_sum": 0.0,
                "interaction_ids": [],
            }
        )
        evidence_ids: list[str] = []
        for row in rows:
            try:
                concept_id = row.concept_id
                status = row.response_status.value
                difficulty = row.difficulty.value if row.difficulty else None
                stats = concept_stats[concept_id]
                stats["count"] += 1
                stats["got_it_count"] += 1 if status == ResponseStatus.got_it.value else 0
                stats["did_not_get_it_count"] += 1 if status == ResponseStatus.did_not_get_it.value else 0
                stats["hard_count"] += 1 if difficulty == Difficulty.hard.value else 0
                stats["score_sum"] += _score_interaction(status, difficulty)
                stats["interaction_ids"].append(row.interaction_id)
                evidence_ids.append(row.interaction_id)
            except Exception as exc:
                errors.append(f"corrupt_interaction:{getattr(row, 'interaction_id', 'unknown')}:{exc}")

        weak: list[str] = []
        strong: list[str] = []
        concept_performance: dict[str, dict[str, Any]] = {}
        weighted_total = 0.0
        total_weight = 0
        for concept_id, stats in concept_stats.items():
            count = max(1, int(stats["count"]))
            did_not_rate = stats["did_not_get_it_count"] / count
            hard_rate = stats["hard_count"] / count
            got_it_rate = stats["got_it_count"] / count
            concept_score = max(0.0, min(1.0, stats["score_sum"] / count))

            if did_not_rate >= 0.30 or hard_rate >= 0.40:
                weak.append(concept_id)
            if got_it_rate >= 0.75 and hard_rate <= 0.20:
                strong.append(concept_id)

            concept_performance[concept_id] = {
                "interaction_count": count,
                "got_it_rate": got_it_rate,
                "did_not_get_it_rate": did_not_rate,
                "hard_difficulty_rate": hard_rate,
                "mastery_score": concept_score,
                "evidence_interaction_ids": list(stats["interaction_ids"]),
            }

            weight = min(count, self.per_concept_weight_cap)
            weighted_total += concept_score * weight
            total_weight += weight

        mastery_score = (weighted_total / total_weight) if total_weight else 0.0
        if weak:
            candidates = ["reinforce weak concepts", "generate reinforcement cards"]
        elif strong and mastery_score >= 0.9:
            candidates = ["deepen mastered concepts", "move topic"]
        elif strong:
            candidates = ["deepen mastered concepts"]
        else:
            candidates = ["reinforce weak concepts"]

        state: dict[str, Any] = {
            "user_id": user_id,
            "topic_id": topic_id,
            "concept_performance": concept_performance,
            "weak_concepts": weak,
            "strong_concepts": strong,
            "mastery_score": mastery_score,
            "evidence_references": evidence_ids,
            "recommended_next_action_candidates": candidates,
        }
        if errors:
            state["errors"] = errors
        return state


def retrieve_learner_state(
    payload: dict[str, Any] | None = None,
    user_id: str | None = None,
    topic_id: str | None = None,
) -> dict[str, Any]:
    data = dict(payload or {})
    if user_id is None:
        user_id = data.get("user_id")
    if topic_id is None:
        topic_id = data.get("topic_id")
    if user_id is None or topic_id is None:
        raise ValueError("user_id and topic_id are required")
    return LearnerStateRetriever().get_topic_state(str(user_id), str(topic_id))
