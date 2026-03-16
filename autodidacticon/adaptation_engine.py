from __future__ import annotations

import re
from typing import Any

ALLOWED_ACTIONS = {
    "reinforce_weak_concepts",
    "generate_reinforcement_cards",
    "deepen_mastered_concepts",
    "move_topic",
}

_CANDIDATE_TO_ACTION = {
    "reinforce_weak_concepts": "reinforce_weak_concepts",
    "reinforce_recent_weak": "reinforce_weak_concepts",
    "generate_reinforcement_cards": "generate_reinforcement_cards",
    "deepen_mastered_concepts": "deepen_mastered_concepts",
    "move_topic": "move_topic",
}


def _normalize_action_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


class AdaptationEngine:
    def decide_next_step(self, state: dict[str, Any]) -> dict[str, Any]:
        if "state" in state and isinstance(state.get("state"), dict):
            nested = dict(state["state"])
            if {"mastery_score", "weak_concepts", "strong_concepts"}.issubset(nested.keys()):
                state = nested

        required = {"mastery_score", "weak_concepts", "strong_concepts"}
        missing = sorted(k for k in required if k not in state)
        if missing:
            raise ValueError(f"missing learner state fields: {missing}")

        weak = [str(c) for c in (state.get("weak_concepts") or [])]
        strong = [str(c) for c in (state.get("strong_concepts") or [])]
        mastery = float(state["mastery_score"])
        evidence = [str(i) for i in (state.get("evidence_references") or [])]
        raw_candidates = [str(c) for c in (state.get("recommended_next_action_candidates") or [])]
        candidates = [_CANDIDATE_TO_ACTION.get(_normalize_action_name(c), "") for c in raw_candidates]
        candidates = [c for c in candidates if c]

        if weak:
            if "generate_reinforcement_cards" in candidates:
                action = "generate_reinforcement_cards"
            else:
                action = "reinforce_weak_concepts"
            reason = f"Weak concepts present ({len(weak)}); prioritize reinforcement from {len(evidence)} evidence interactions."
        elif mastery >= 0.9 and strong:
            if "move_topic" in candidates:
                action = "move_topic"
            else:
                action = "deepen_mastered_concepts"
            reason = (
                f"High mastery ({mastery:.2f}) with strong concept coverage ({len(strong)}); "
                f"evidence count={len(evidence)}."
            )
        elif strong:
            action = "deepen_mastered_concepts"
            reason = f"Strong concepts detected ({len(strong)}) and no weak blockers in evidence ({len(evidence)} rows)."
        else:
            action = "reinforce_weak_concepts"
            reason = f"Sparse or inconclusive evidence ({len(evidence)} rows); choosing safe reinforcement action."

        if action not in ALLOWED_ACTIONS:
            action = "reinforce_weak_concepts"
            reason = "Unsupported candidate set; defaulting to safe v1 reinforcement."

        return {
            "action": action,
            "reason": reason,
            "evidence_references": evidence,
            "target_weak_concepts": weak,
            "target_strong_concepts": strong,
        }


def decide_next_step(state: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    payload = dict(state or kwargs.get("state") or {})
    if "state" in payload and isinstance(payload.get("state"), dict) and len(payload) == 1:
        payload = dict(payload["state"])
    if not payload:
        payload = kwargs
    return AdaptationEngine().decide_next_step(payload)
