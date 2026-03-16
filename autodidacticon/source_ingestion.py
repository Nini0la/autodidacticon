from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .models import EntryMode, ExtractionStatus, SourceType
from .persistence_store import SourcePayload, get_store
from .utils import normalize_whitespace


class SourceIngestion:
    def __init__(self) -> None:
        self.store = get_store()

    def ingest_source(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        route_decision = dict(payload.get("route_decision", payload))
        topic_id = str(route_decision.get("topic_id", "")).strip()
        route = str(route_decision.get("route", route_decision.get("entry_mode", EntryMode.topic_only.value)))
        if not topic_id:
            raise ValueError("topic_id is required for source ingestion")
        topic = self.store.get_topic(topic_id)

        source_input = route_decision.get("source_input")
        if route == EntryMode.topic_only.value and source_input is None:
            source_input = f"Foundational overview for {topic.title}"
            source_type = SourceType.generated
            source_uri = None
            extracted_text = source_input
            extraction_status = ExtractionStatus.ok
        else:
            source_type, source_uri, extracted_text, extraction_status = self._extract_source(source_input)

        source = self.store.upsert_source(
            SourcePayload(
                topic_id=topic_id,
                source_type=source_type,
                source_uri=source_uri,
                extracted_text=normalize_whitespace(extracted_text),
                extraction_status=extraction_status,
            )
        )
        return [self.store.serialize(source)]

    def _extract_source(
        self,
        source_input: Any,
    ) -> tuple[SourceType, str | None, str, ExtractionStatus]:
        if isinstance(source_input, str):
            text = source_input.strip()
            if text.startswith("http://") or text.startswith("https://"):
                source_type = self._source_type_from_uri(text)
                return source_type, text, text, ExtractionStatus.partial
            if text:
                return SourceType.text, None, text, ExtractionStatus.ok
            return SourceType.text, None, "", ExtractionStatus.failed

        if isinstance(source_input, dict):
            if "text" in source_input:
                text = str(source_input.get("text", "")).strip()
                status = ExtractionStatus.ok if text else ExtractionStatus.failed
                return SourceType.text, None, text, status
            if "uri" in source_input or "url" in source_input:
                uri = str(source_input.get("uri") or source_input.get("url"))
                uri = uri.strip()
                if not uri:
                    return SourceType.web, None, "", ExtractionStatus.failed
                return self._source_type_from_uri(uri), uri, uri, ExtractionStatus.partial
            if "path" in source_input:
                path = Path(str(source_input["path"]))
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    return SourceType.doc, str(path), "", ExtractionStatus.failed
                status = ExtractionStatus.ok if text.strip() else ExtractionStatus.failed
                source_type = SourceType.pdf if path.suffix.lower() == ".pdf" else SourceType.doc
                return source_type, str(path), text, status

        return SourceType.text, None, "", ExtractionStatus.failed

    def _source_type_from_uri(self, uri: str) -> SourceType:
        parsed = urlparse(uri)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()
        if "youtube.com" in host or "youtu.be" in host:
            return SourceType.youtube
        if path.endswith(".pdf"):
            return SourceType.pdf
        if path.endswith(".doc") or path.endswith(".docx"):
            return SourceType.doc
        return SourceType.web


def ingest_source(payload: dict[str, Any] | None = None, **kwargs: Any) -> list[dict[str, Any]]:
    data = dict(payload or {})
    data.update(kwargs)
    return SourceIngestion().ingest_source(data)
