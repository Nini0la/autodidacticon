from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from .models import (
    CardType,
    Concept,
    DepthLevel,
    Difficulty,
    EntryMode,
    ExtractionStatus,
    Interaction,
    LearningUnit,
    ResponseStatus,
    Session,
    Source,
    SourceType,
    Topic,
    TopicStatus,
    User,
)
from .utils import generate_ulid, normalize_title, now_utc_iso, stable_content_hash


@dataclass(frozen=True)
class SourcePayload:
    topic_id: str
    source_type: SourceType
    source_uri: str | None
    extracted_text: str
    extraction_status: ExtractionStatus


@dataclass(frozen=True)
class ConceptPayload:
    topic_id: str
    source_id: str | None
    label: str
    summary: str
    depth_level: DepthLevel
    misconceptions_json: list[str]
    relationships_json: list[dict[str, Any] | str]


@dataclass(frozen=True)
class LearningUnitPayload:
    topic_id: str
    concept_id: str
    card_type: CardType
    title: str
    content: str
    source_reference: str | None
    depth_level: DepthLevel
    related_unit_id: str | None
    version: int
    idempotency_key: str


class PersistenceStore:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.sessions: dict[str, Session] = {}
        self.topics: dict[str, Topic] = {}
        self.sources: dict[str, Source] = {}
        self.concepts: dict[str, Concept] = {}
        self.learning_units: dict[str, LearningUnit] = {}
        self.interactions: dict[str, Interaction] = {}

        self._topic_by_user_title: dict[tuple[str, str], str] = {}
        self._source_by_topic_hash: dict[tuple[str, str], str] = {}
        self._concept_by_unique_key: dict[tuple[str, str | None, str], str] = {}
        self._unit_by_idempotency_key: dict[str, str] = {}
        self._interaction_by_idempotency_key: dict[str, str] = {}

        self._source_ids_by_topic: dict[str, list[str]] = defaultdict(list)
        self._concept_ids_by_topic: dict[str, list[str]] = defaultdict(list)
        self._unit_ids_by_topic: dict[str, list[str]] = defaultdict(list)
        self._interaction_ids_by_user_topic: dict[tuple[str, str], list[str]] = defaultdict(list)

    def _as_dict(self, model: Any) -> dict[str, Any]:
        return model.model_dump()

    def ensure_user(self, user_id: str) -> User:
        existing = self.users.get(user_id)
        if existing:
            return existing
        user = User(user_id=user_id, created_at=now_utc_iso())
        self.users[user_id] = user
        return user

    def ensure_session(self, session_id: str, user_id: str, entry_mode: EntryMode) -> Session:
        self.ensure_user(user_id)
        existing = self.sessions.get(session_id)
        if existing:
            if existing.user_id != user_id:
                raise ValueError("session_id belongs to a different user")
            return existing
        session = Session(
            session_id=session_id,
            user_id=user_id,
            started_at=now_utc_iso(),
            entry_mode=entry_mode,
        )
        self.sessions[session_id] = session
        return session

    def create_or_get_topic(self, *, user_id: str, title: str) -> Topic:
        self.ensure_user(user_id)
        normalized = normalize_title(title)
        key = (user_id, normalized)
        topic_id = self._topic_by_user_title.get(key)
        if topic_id:
            topic = self.topics[topic_id]
            if topic.status != TopicStatus.completed:
                topic = topic.model_copy(update={"updated_at": now_utc_iso()})
                self.topics[topic_id] = topic
            return topic

        topic = Topic(
            topic_id=generate_ulid(),
            user_id=user_id,
            title=title.strip(),
            normalized_title=normalized,
            status=TopicStatus.active,
            created_at=now_utc_iso(),
            updated_at=now_utc_iso(),
        )
        self.topics[topic.topic_id] = topic
        self._topic_by_user_title[key] = topic.topic_id
        return topic

    def get_topic(self, topic_id: str) -> Topic:
        topic = self.topics.get(topic_id)
        if not topic:
            raise KeyError(f"topic not found: {topic_id}")
        return topic

    def upsert_source(self, payload: SourcePayload) -> Source:
        self.get_topic(payload.topic_id)
        content_hash = stable_content_hash(payload.extracted_text)
        unique_key = (payload.topic_id, content_hash)
        existing_id = self._source_by_topic_hash.get(unique_key)
        if existing_id:
            return self.sources[existing_id]

        source = Source(
            source_id=generate_ulid(),
            topic_id=payload.topic_id,
            source_type=payload.source_type,
            source_uri=payload.source_uri,
            content_hash=content_hash,
            extracted_text=payload.extracted_text,
            extraction_status=payload.extraction_status,
            created_at=now_utc_iso(),
        )
        self.sources[source.source_id] = source
        self._source_by_topic_hash[unique_key] = source.source_id
        self._source_ids_by_topic[source.topic_id].append(source.source_id)
        return source

    def get_source(self, source_id: str) -> Source:
        source = self.sources.get(source_id)
        if not source:
            raise KeyError(f"source not found: {source_id}")
        return source

    def get_sources(self, source_ids: Iterable[str]) -> list[Source]:
        return [self.get_source(source_id) for source_id in source_ids]

    def list_topic_sources(self, topic_id: str) -> list[Source]:
        return [self.sources[source_id] for source_id in self._source_ids_by_topic.get(topic_id, [])]

    def upsert_concept(self, payload: ConceptPayload) -> Concept:
        topic = self.get_topic(payload.topic_id)
        if payload.source_id is not None:
            source = self.get_source(payload.source_id)
            if source.topic_id != topic.topic_id:
                raise ValueError("source.topic_id must match concept.topic_id")

        concept_key = (payload.topic_id, payload.source_id, normalize_title(payload.label))
        existing_id = self._concept_by_unique_key.get(concept_key)
        if existing_id:
            return self.concepts[existing_id]

        concept = Concept(
            concept_id=generate_ulid(),
            topic_id=payload.topic_id,
            source_id=payload.source_id,
            label=payload.label.strip(),
            summary=payload.summary.strip(),
            depth_level=payload.depth_level,
            misconceptions_json=list(payload.misconceptions_json),
            relationships_json=list(payload.relationships_json),
            created_at=now_utc_iso(),
        )
        self.concepts[concept.concept_id] = concept
        self._concept_by_unique_key[concept_key] = concept.concept_id
        self._concept_ids_by_topic[concept.topic_id].append(concept.concept_id)
        return concept

    def get_concept(self, concept_id: str) -> Concept:
        concept = self.concepts.get(concept_id)
        if not concept:
            raise KeyError(f"concept not found: {concept_id}")
        return concept

    def get_concepts(self, concept_ids: Iterable[str]) -> list[Concept]:
        return [self.get_concept(concept_id) for concept_id in concept_ids]

    def list_topic_concepts(self, topic_id: str) -> list[Concept]:
        return [self.concepts[concept_id] for concept_id in self._concept_ids_by_topic.get(topic_id, [])]

    def upsert_learning_unit(self, payload: LearningUnitPayload) -> LearningUnit:
        topic = self.get_topic(payload.topic_id)
        concept = self.get_concept(payload.concept_id)
        if concept.topic_id != topic.topic_id:
            raise ValueError("learning unit concept/topic mismatch")

        existing_id = self._unit_by_idempotency_key.get(payload.idempotency_key)
        if existing_id:
            return self.learning_units[existing_id]

        if payload.card_type == CardType.question:
            if not payload.related_unit_id:
                raise ValueError("question unit must include related_unit_id")
            related = self.learning_units.get(payload.related_unit_id)
            if related is None:
                raise ValueError("related_unit_id must reference existing learning unit")
            if related.card_type != CardType.learning:
                raise ValueError("related_unit_id must point to a learning unit")
            if related.topic_id != payload.topic_id or related.concept_id != payload.concept_id:
                raise ValueError("related learning unit must match topic/concept")

        unit = LearningUnit(
            unit_id=generate_ulid(),
            topic_id=payload.topic_id,
            concept_id=payload.concept_id,
            card_type=payload.card_type,
            title=payload.title.strip(),
            content=payload.content.strip(),
            source_reference=payload.source_reference,
            depth_level=payload.depth_level,
            related_unit_id=payload.related_unit_id,
            version=payload.version,
            created_at=now_utc_iso(),
        )
        self.learning_units[unit.unit_id] = unit
        self._unit_by_idempotency_key[payload.idempotency_key] = unit.unit_id
        self._unit_ids_by_topic[unit.topic_id].append(unit.unit_id)
        return unit

    def get_learning_unit(self, unit_id: str) -> LearningUnit:
        unit = self.learning_units.get(unit_id)
        if not unit:
            raise KeyError(f"learning unit not found: {unit_id}")
        return unit

    def list_topic_units(self, topic_id: str) -> list[LearningUnit]:
        return [self.learning_units[unit_id] for unit_id in self._unit_ids_by_topic.get(topic_id, [])]

    def log_interaction(self, payload: dict[str, Any]) -> Interaction:
        idempotency_key = payload.get("idempotency_key")
        if idempotency_key:
            existing_id = self._interaction_by_idempotency_key.get(str(idempotency_key))
            if existing_id:
                return self.interactions[existing_id]

        user_id = str(payload["user_id"])
        session_id = str(payload["session_id"])
        topic_id = str(payload["topic_id"])
        concept_id = str(payload["concept_id"])
        unit_id = str(payload["unit_id"])

        self.ensure_user(user_id)
        session = self.sessions.get(session_id)
        if session is None:
            raise ValueError("unknown session_id")
        if session.user_id != user_id:
            raise ValueError("session_id/user_id mismatch")

        topic = self.get_topic(topic_id)
        if topic.user_id != user_id:
            raise ValueError("topic does not belong to user")

        concept = self.get_concept(concept_id)
        if concept.topic_id != topic_id:
            raise ValueError("concept/topic mismatch")

        unit = self.get_learning_unit(unit_id)
        if unit.card_type != CardType.question:
            raise ValueError("interactions may only be logged for question units")
        if unit.topic_id != topic_id or unit.concept_id != concept_id:
            raise ValueError("interaction topic/concept must match question unit linkage")

        response_status = ResponseStatus(payload["response_status"])
        difficulty_value = payload.get("difficulty")
        difficulty = Difficulty(difficulty_value) if difficulty_value is not None else None
        latency = payload.get("latency_ms")
        latency_ms = int(latency) if latency is not None else None

        interaction = Interaction(
            interaction_id=generate_ulid(),
            user_id=user_id,
            session_id=session_id,
            topic_id=topic_id,
            concept_id=concept_id,
            unit_id=unit_id,
            response_status=response_status,
            difficulty=difficulty,
            latency_ms=latency_ms,
            created_at=now_utc_iso(),
            idempotency_key=str(idempotency_key) if idempotency_key is not None else None,
        )
        self.interactions[interaction.interaction_id] = interaction
        self._interaction_ids_by_user_topic[(user_id, topic_id)].append(interaction.interaction_id)
        if idempotency_key is not None:
            self._interaction_by_idempotency_key[str(idempotency_key)] = interaction.interaction_id
        return interaction

    def get_interactions(self, *, user_id: str, topic_id: str, limit: int | None = None) -> list[Interaction]:
        ids = list(self._interaction_ids_by_user_topic.get((user_id, topic_id), []))
        interactions = [self.interactions[i] for i in ids]
        interactions.sort(key=lambda i: i.created_at, reverse=True)
        if limit is not None:
            interactions = interactions[:limit]
        return interactions

    def get_recent_user_interactions(self, *, user_id: str, limit: int = 20) -> list[Interaction]:
        all_rows = [i for i in self.interactions.values() if i.user_id == user_id]
        all_rows.sort(key=lambda i: i.created_at, reverse=True)
        return all_rows[:limit]

    def serialize(self, model: Any) -> dict[str, Any]:
        return self._as_dict(model)


_STORE = PersistenceStore()


def get_store() -> PersistenceStore:
    return _STORE


def log_interaction(payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    data = dict(payload or {})
    data.update(kwargs)
    interaction = get_store().log_interaction(data)
    return {"interaction_id": interaction.interaction_id}
