from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EntryMode(str, Enum):
    source_provided = "source_provided"
    topic_only = "topic_only"
    deepen_topic = "deepen_topic"


class TopicStatus(str, Enum):
    active = "active"
    paused = "paused"
    completed = "completed"


class SourceType(str, Enum):
    youtube = "youtube"
    web = "web"
    pdf = "pdf"
    doc = "doc"
    text = "text"
    generated = "generated"


class ExtractionStatus(str, Enum):
    ok = "ok"
    partial = "partial"
    failed = "failed"


class DepthLevel(str, Enum):
    intro = "intro"
    core = "core"
    advanced = "advanced"


class CardType(str, Enum):
    learning = "learning"
    question = "question"


class ResponseStatus(str, Enum):
    got_it = "got_it"
    partially_got_it = "partially_got_it"
    did_not_get_it = "did_not_get_it"


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class EntityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class User(EntityModel):
    user_id: str
    created_at: str


class Session(EntityModel):
    session_id: str
    user_id: str
    started_at: str
    ended_at: str | None = None
    entry_mode: EntryMode


class Topic(EntityModel):
    topic_id: str
    user_id: str
    title: str
    normalized_title: str
    status: TopicStatus = TopicStatus.active
    created_at: str
    updated_at: str


class Source(EntityModel):
    source_id: str
    topic_id: str
    source_type: SourceType
    source_uri: str | None = None
    content_hash: str
    extracted_text: str
    extraction_status: ExtractionStatus
    created_at: str


class Concept(EntityModel):
    concept_id: str
    topic_id: str
    source_id: str | None = None
    label: str
    summary: str
    depth_level: DepthLevel
    misconceptions_json: list[str] = Field(default_factory=list)
    relationships_json: list[dict[str, Any] | str] = Field(default_factory=list)
    created_at: str


class LearningUnit(EntityModel):
    unit_id: str
    topic_id: str
    concept_id: str
    card_type: CardType
    title: str
    content: str
    source_reference: str | None = None
    depth_level: DepthLevel
    related_unit_id: str | None = None
    version: int = 1
    created_at: str


class Interaction(EntityModel):
    interaction_id: str
    user_id: str
    session_id: str
    topic_id: str
    concept_id: str
    unit_id: str
    response_status: ResponseStatus
    difficulty: Difficulty | None = None
    latency_ms: int | None = None
    created_at: str
    idempotency_key: str | None = None
