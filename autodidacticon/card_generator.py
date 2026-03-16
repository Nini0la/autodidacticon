from __future__ import annotations

from typing import Any

from .models import CardType, DepthLevel
from .persistence_store import LearningUnitPayload, get_store
from .utils import deterministic_card_key, parse_version


class CardGenerator:
    def __init__(self) -> None:
        self.store = get_store()

    def generate_cards(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        concepts = self._resolve_concepts(payload)
        if not concepts:
            raise ValueError("concept_records or concept_ids required")

        depth_level = DepthLevel(payload.get("depth_level", "core"))
        version_seed = str(payload.get("version_seed", "v1"))
        version = parse_version(version_seed)

        all_units: list[dict[str, Any]] = []
        for concept in concepts:
            learning_key = deterministic_card_key(
                concept.topic_id, concept.concept_id, CardType.learning.value, version_seed
            )
            learning = self.store.upsert_learning_unit(
                LearningUnitPayload(
                    topic_id=concept.topic_id,
                    concept_id=concept.concept_id,
                    card_type=CardType.learning,
                    title=f"{concept.label}: Learn",
                    content=concept.summary,
                    source_reference=concept.source_id,
                    depth_level=depth_level,
                    related_unit_id=None,
                    version=version,
                    idempotency_key=learning_key,
                )
            )

            question_key = deterministic_card_key(
                concept.topic_id, concept.concept_id, CardType.question.value, version_seed
            )
            question = self.store.upsert_learning_unit(
                LearningUnitPayload(
                    topic_id=concept.topic_id,
                    concept_id=concept.concept_id,
                    card_type=CardType.question,
                    title=f"{concept.label}: Recall",
                    content=f"Explain {concept.label.lower()} in your own words.",
                    source_reference=concept.source_id,
                    depth_level=depth_level,
                    related_unit_id=learning.unit_id,
                    version=version,
                    idempotency_key=question_key,
                )
            )
            all_units.extend([self.store.serialize(learning), self.store.serialize(question)])

        learning_count = sum(1 for unit in all_units if unit["card_type"] == CardType.learning.value)
        question_count = sum(1 for unit in all_units if unit["card_type"] == CardType.question.value)
        if learning_count < 1 or question_count < 1:
            raise ValueError("missing_pair")
        return all_units

    def _resolve_concepts(self, payload: dict[str, Any]) -> list[Any]:
        concept_records = payload.get("concept_records") or payload.get("concepts")
        concept_ids = payload.get("concept_ids")
        if concept_records:
            ids = [str(c["concept_id"]) for c in concept_records if isinstance(c, dict) and "concept_id" in c]
            if ids:
                return self.store.get_concepts(ids)
        if concept_ids:
            return self.store.get_concepts([str(concept_id) for concept_id in concept_ids])
        return []


def generate_cards(payload: dict[str, Any] | None = None, **kwargs: Any) -> list[dict[str, Any]]:
    data = dict(payload or {})
    data.update(kwargs)
    return CardGenerator().generate_cards(data)
