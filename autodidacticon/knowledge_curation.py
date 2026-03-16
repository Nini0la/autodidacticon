from __future__ import annotations

import re
from typing import Any

from .models import DepthLevel
from .persistence_store import ConceptPayload, get_store


class KnowledgeCuration:
    def __init__(self) -> None:
        self.store = get_store()

    def curate_concepts(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        sources = self._resolve_sources(payload)
        concepts = self._curate_once(sources)
        if concepts:
            return concepts

        # Single fallback regeneration attempt for v1.
        fallback_sources = [s for s in sources if s.extracted_text.strip()]
        concepts = self._curate_once(fallback_sources, fallback=True)
        if concepts:
            return concepts
        raise ValueError("refined_input_required")

    def _resolve_sources(self, payload: dict[str, Any]) -> list[Any]:
        raw_sources = payload.get("source_records") or payload.get("sources")
        source_ids = payload.get("source_ids")
        if raw_sources:
            ids = [str(s["source_id"]) for s in raw_sources if isinstance(s, dict) and "source_id" in s]
            if ids:
                return self.store.get_sources(ids)
        if source_ids:
            return self.store.get_sources([str(source_id) for source_id in source_ids])
        raise ValueError("source_records or source_ids required")

    def _curate_once(self, sources: list[Any], *, fallback: bool = False) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for source in sources:
            if source.extraction_status == "failed":
                continue
            snippets = self._extract_snippets(source.extracted_text)
            if not snippets and fallback:
                snippets = [source.extracted_text.strip()]
            if not snippets:
                continue

            for idx, snippet in enumerate(snippets):
                label = self._make_label(snippet)
                if not label:
                    continue
                depth = self._depth_for_index(idx)
                concept = self.store.upsert_concept(
                    ConceptPayload(
                        topic_id=source.topic_id,
                        source_id=source.source_id,
                        label=label,
                        summary=snippet[:220],
                        depth_level=depth,
                        misconceptions_json=[
                            f"{label} is often confused with memorizing terms only."
                        ],
                        relationships_json=[{"type": "derived_from", "source_id": source.source_id}],
                    )
                )
                out.append(self.store.serialize(concept))

        return out

    def _extract_snippets(self, text: str) -> list[str]:
        parts = [p.strip() for p in re.split(r"[.!?\n;]+", text) if p.strip()]
        return parts[:2] or ([text.strip()] if text.strip() else [])

    def _make_label(self, text: str) -> str:
        words = [w for w in re.findall(r"[A-Za-z0-9']+", text) if w]
        if not words:
            return ""
        return " ".join(words[:4]).title()

    def _depth_for_index(self, idx: int) -> DepthLevel:
        if idx == 0:
            return DepthLevel.intro
        if idx == 1:
            return DepthLevel.core
        return DepthLevel.advanced


def curate_concepts(payload: dict[str, Any] | None = None, **kwargs: Any) -> list[dict[str, Any]]:
    data = dict(payload or {})
    data.update(kwargs)
    return KnowledgeCuration().curate_concepts(data)
