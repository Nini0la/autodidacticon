from __future__ import annotations

from typing import Any

from .models import EntryMode
from .persistence_store import get_store


class IntakeRouter:
    def __init__(self) -> None:
        self.store = get_store()

    def route_intake(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = str(payload.get("user_id", "")).strip()
        session_id = str(payload.get("session_id", "")).strip()
        topic_title = payload.get("topic_title")
        topic_id = payload.get("topic_id")
        source_input = payload.get("source_input")
        entry_mode = payload.get("entry_mode")
        intent = payload.get("intent")

        if not user_id or not session_id:
            raise ValueError("user_id and session_id are required")

        route = self._resolve_route(entry_mode=entry_mode, intent=intent, topic_id=topic_id, source_input=source_input)

        self.store.ensure_user(user_id)
        self.store.ensure_session(session_id, user_id, EntryMode(route))

        if route == EntryMode.deepen_topic.value:
            if not topic_id:
                raise ValueError("topic_id is required for deepen_topic")
            topic = self.store.get_topic(str(topic_id))
            if topic.user_id != user_id:
                raise ValueError("topic does not belong to user")
            return {
                "route": route,
                "entry_mode": route,
                "user_id": user_id,
                "session_id": session_id,
                "topic_id": topic.topic_id,
                "topic_title": topic.title,
            }

        if not isinstance(topic_title, str) or not topic_title.strip():
            raise ValueError("topic_title is required for source_provided/topic_only")
        topic = self.store.create_or_get_topic(user_id=user_id, title=topic_title)
        return {
            "route": route,
            "entry_mode": route,
            "user_id": user_id,
            "session_id": session_id,
            "topic_id": topic.topic_id,
            "topic_title": topic.title,
            "normalized_title": topic.normalized_title,
            "source_input": source_input,
        }

    def _resolve_route(
        self,
        *,
        entry_mode: Any,
        intent: Any,
        topic_id: Any,
        source_input: Any,
    ) -> str:
        # Precedence is deterministic:
        # 1) explicit deepen intent/mode, 2) any source input, 3) topic-only.
        if entry_mode == EntryMode.deepen_topic.value or intent == EntryMode.deepen_topic.value:
            return EntryMode.deepen_topic.value
        if source_input is not None and str(source_input).strip() != "":
            return EntryMode.source_provided.value
        if topic_id and entry_mode == EntryMode.deepen_topic.value:
            return EntryMode.deepen_topic.value
        return EntryMode.topic_only.value


def route_intake(payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    data = dict(payload or {})
    data.update(kwargs)
    return IntakeRouter().route_intake(data)
