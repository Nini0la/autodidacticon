from __future__ import annotations

import dataclasses
import importlib
import inspect
import itertools
import os
import re
from typing import Any, Callable, Iterable, Mapping, Sequence

import pytest


ALLOWED_ROUTES = {"source_provided", "topic_only", "deepen_topic"}
ALLOWED_SOURCE_TYPES = {"youtube", "web", "pdf", "doc", "text", "generated"}
ALLOWED_EXTRACTION_STATUS = {"ok", "partial", "failed"}
ALLOWED_DEPTH_LEVELS = {"intro", "core", "advanced"}
ALLOWED_CARD_TYPES = {"learning", "question"}
ALLOWED_RESPONSE_STATUS = {"got_it", "partially_got_it", "did_not_get_it"}
ALLOWED_DIFFICULTY = {"easy", "medium", "hard", None}
ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def to_plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict") and callable(value.dict):
        return value.dict()
    if isinstance(value, Mapping):
        return {k: to_plain(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_plain(v) for v in value]
    if hasattr(value, "__dict__"):
        return to_plain(vars(value))
    return value


def ensure_mapping(value: Any, *, context: str) -> dict[str, Any]:
    plain = to_plain(value)
    assert isinstance(plain, Mapping), f"{context} must return a mapping, got {type(plain).__name__}"
    return dict(plain)


def ensure_record_list(
    value: Any,
    *,
    context: str,
    list_keys: Iterable[str],
    singular_required_keys: Iterable[str],
) -> list[dict[str, Any]]:
    plain = to_plain(value)
    if isinstance(plain, Sequence) and not isinstance(plain, (str, bytes, bytearray)):
        records = plain
    elif isinstance(plain, Mapping):
        records = None
        for key in list_keys:
            if key in plain:
                nested = to_plain(plain[key])
                assert isinstance(nested, Sequence) and not isinstance(
                    nested, (str, bytes, bytearray)
                ), f"{context}.{key} must be a list"
                records = nested
                break
        if records is None:
            if all(k in plain for k in singular_required_keys):
                records = [plain]
            else:
                raise AssertionError(
                    f"{context} did not return records list or singular record with keys "
                    f"{sorted(singular_required_keys)}"
                )
    else:
        raise AssertionError(f"{context} returned unsupported type: {type(plain).__name__}")

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(records):
        assert isinstance(item, Mapping), f"{context}[{idx}] must be a mapping"
        normalized.append(dict(item))
    return normalized


def likely_signature_type_error(exc: TypeError) -> bool:
    msg = str(exc).lower()
    needles = [
        "missing",
        "unexpected keyword",
        "positional argument",
        "required positional",
        "takes",
        "got an unexpected",
    ]
    return any(n in msg for n in needles)


def invoke_contract(
    fn: Callable[..., Any],
    *,
    payload: Mapping[str, Any] | None = None,
    positional: Sequence[Any] = (),
) -> Any:
    errors: list[str] = []
    attempts: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    if payload is not None:
        attempts.append(((payload,), {}))
        attempts.append(((), dict(payload)))
    if positional:
        attempts.append((tuple(positional), {}))

    for args, kwargs in attempts:
        try:
            return fn(*args, **kwargs)
        except TypeError as exc:
            if likely_signature_type_error(exc):
                errors.append(f"{fn.__name__}{args}{kwargs}: {exc}")
                continue
            raise
    details = "\n".join(errors) if errors else "no compatible invocation attempts"
    raise AssertionError(f"Could not invoke contract callable `{fn.__name__}`.\n{details}")


def import_module_if_exists(module_name: str) -> Any | None:
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        return None


def resolve_from_ref(ref: str) -> Callable[..., Any]:
    if ":" not in ref:
        raise AssertionError(f"Invalid callable reference `{ref}`. Use format `module:attr.path`.")
    module_name, attr_path = ref.split(":", 1)
    module = importlib.import_module(module_name)
    obj: Any = module
    for part in attr_path.split("."):
        obj = getattr(obj, part)
    assert callable(obj), f"Resolved reference `{ref}` is not callable"
    return obj


def resolve_contract_callable(
    *,
    env_key: str,
    function_candidates: Sequence[tuple[str, str]],
    class_candidates: Sequence[tuple[str, str, str]],
) -> Callable[..., Any]:
    explicit = os.getenv(env_key)
    if explicit:
        return resolve_from_ref(explicit)

    for module_name, function_name in function_candidates:
        module = import_module_if_exists(module_name)
        if not module:
            continue
        fn = getattr(module, function_name, None)
        if callable(fn):
            return fn

    for module_name, class_name, method_name in class_candidates:
        module = import_module_if_exists(module_name)
        if not module:
            continue
        cls = getattr(module, class_name, None)
        if not inspect.isclass(cls):
            continue
        method = getattr(cls, method_name, None)
        if method is None:
            continue
        if inspect.isfunction(method):
            try:
                instance = cls()
            except Exception:
                continue
            bound = getattr(instance, method_name, None)
            if callable(bound):
                return bound
        elif callable(method):
            return method

    searched = [
        *[f"{m}.{f}" for m, f in function_candidates],
        *[f"{m}.{c}.{meth}" for m, c, meth in class_candidates],
    ]
    raise AssertionError(
        f"Could not resolve contract callable for {env_key}. "
        f"Set {env_key}=module:callable to configure test binding.\nSearched: {searched}"
    )


@dataclasses.dataclass(frozen=True)
class Contracts:
    route_intake: Callable[..., Any]
    ingest_source: Callable[..., Any]
    curate_concepts: Callable[..., Any]
    generate_cards: Callable[..., Any]
    log_interaction: Callable[..., Any]
    retrieve_learner_state: Callable[..., Any]
    decide_next_step: Callable[..., Any]


@dataclasses.dataclass
class SUT:
    contracts: Contracts

    def route_intake(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return ensure_mapping(
            invoke_contract(self.contracts.route_intake, payload=payload),
            context="route_intake",
        )

    def ingest_source(self, route_decision: Mapping[str, Any]) -> list[dict[str, Any]]:
        payload_variants = [
            {"route_decision": dict(route_decision)},
            dict(route_decision),
        ]
        last_error: AssertionError | None = None
        for payload in payload_variants:
            try:
                result = invoke_contract(self.contracts.ingest_source, payload=payload)
                return ensure_record_list(
                    result,
                    context="ingest_source",
                    list_keys=("source_records", "sources", "records"),
                    singular_required_keys=(
                        "source_id",
                        "topic_id",
                        "source_type",
                        "content_hash",
                        "extracted_text",
                        "extraction_status",
                    ),
                )
            except AssertionError as exc:
                last_error = exc
        raise AssertionError(f"ingest_source invocation failed: {last_error}")

    def curate_concepts(self, source_records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        source_ids = [r["source_id"] for r in source_records if "source_id" in r]
        payload_variants = [
            {"source_records": list(source_records)},
            {"source_ids": source_ids},
            {"sources": list(source_records)},
        ]
        last_error: AssertionError | None = None
        for payload in payload_variants:
            try:
                result = invoke_contract(self.contracts.curate_concepts, payload=payload)
                return ensure_record_list(
                    result,
                    context="curate_concepts",
                    list_keys=("concept_records", "concepts", "records"),
                    singular_required_keys=(
                        "concept_id",
                        "topic_id",
                        "label",
                        "summary",
                        "depth_level",
                    ),
                )
            except AssertionError as exc:
                last_error = exc
        raise AssertionError(f"curate_concepts invocation failed: {last_error}")

    def generate_cards(
        self,
        concept_records: Sequence[Mapping[str, Any]],
        *,
        depth_level: str = "core",
    ) -> list[dict[str, Any]]:
        concept_ids = [c["concept_id"] for c in concept_records if "concept_id" in c]
        payload_variants = [
            {"concept_records": list(concept_records), "depth_level": depth_level},
            {"concept_ids": concept_ids, "depth_level": depth_level},
            {"concepts": list(concept_records), "depth_level": depth_level},
        ]
        last_error: AssertionError | None = None
        for payload in payload_variants:
            try:
                result = invoke_contract(self.contracts.generate_cards, payload=payload)
                return ensure_record_list(
                    result,
                    context="generate_cards",
                    list_keys=("unit_records", "units", "records"),
                    singular_required_keys=(
                        "unit_id",
                        "topic_id",
                        "concept_id",
                        "card_type",
                        "title",
                        "content",
                        "depth_level",
                    ),
                )
            except AssertionError as exc:
                last_error = exc
        raise AssertionError(f"generate_cards invocation failed: {last_error}")

    def log_interaction(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        result = invoke_contract(self.contracts.log_interaction, payload=payload)
        plain = to_plain(result)
        if isinstance(plain, str):
            return {"interaction_id": plain}
        return ensure_mapping(plain, context="log_interaction")

    def log_interaction_expect_rejected(self, payload: Mapping[str, Any]) -> None:
        try:
            result = self.log_interaction(payload)
        except Exception:
            return
        status = str(result.get("status", "")).lower()
        has_error_key = "error" in result or "errors" in result
        rejected_status = status in {"error", "failed", "rejected", "invalid"}
        assert has_error_key or rejected_status, (
            "Invalid interaction should be rejected. Expected exception or explicit error payload."
        )

    def retrieve_state(self, *, user_id: str, topic_id: str) -> dict[str, Any]:
        payload = {"user_id": user_id, "topic_id": topic_id}
        result = invoke_contract(
            self.contracts.retrieve_learner_state,
            payload=payload,
            positional=(user_id, topic_id),
        )
        return ensure_mapping(result, context="retrieve_learner_state")

    def decide_next_step(self, state: Mapping[str, Any]) -> dict[str, Any]:
        result = invoke_contract(
            self.contracts.decide_next_step,
            payload={"state": dict(state)},
            positional=(state,),
        )
        plain = to_plain(result)
        if isinstance(plain, str):
            return {"action": plain}
        return ensure_mapping(plain, context="decide_next_step")

    def route_value(self, route_decision: Mapping[str, Any]) -> str:
        for key in ("route", "entry_mode", "flow", "intake_route"):
            if key in route_decision:
                return str(route_decision[key])
        raise AssertionError("route decision must include one of route/entry_mode/flow/intake_route")

    def action_value(self, adaptation_output: Mapping[str, Any]) -> str:
        for key in ("action", "recommendation", "next_action"):
            if key in adaptation_output:
                return str(adaptation_output[key])
        raise AssertionError("adaptation output must include action/recommendation/next_action")

    def normalize_action(self, raw_action: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", raw_action.strip().lower()).strip("_")
        aliases = {
            "reinforce_weak_concepts": "reinforce_weak_concepts",
            "reinforce_recent_weak": "reinforce_weak_concepts",
            "generate_reinforcement_cards": "generate_reinforcement_cards",
            "deepen_mastered_concepts": "deepen_mastered_concepts",
            "move_topic": "move_topic",
            "reinforceweakconcepts": "reinforce_weak_concepts",
            "generatereinforcementcards": "generate_reinforcement_cards",
            "deepenmasteredconcepts": "deepen_mastered_concepts",
            "movetopic": "move_topic",
        }
        return aliases.get(normalized, normalized)

    def split_units(self, units: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        learning = [dict(u) for u in units if u.get("card_type") == "learning"]
        question = [dict(u) for u in units if u.get("card_type") == "question"]
        return learning, question

    def weak_concepts(self, state: Mapping[str, Any]) -> set[str]:
        return _concept_set_from_state(state, keys=("weak_concepts", "weak_concept_ids"))

    def strong_concepts(self, state: Mapping[str, Any]) -> set[str]:
        return _concept_set_from_state(state, keys=("strong_concepts", "strong_concept_ids"))

    def evidence_ids(self, state: Mapping[str, Any]) -> set[str]:
        candidates = []
        for key in ("evidence_references", "evidence", "interaction_ids"):
            if key in state:
                candidates = to_plain(state[key]) or []
                break
        if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes, bytearray)):
            return set()
        out: set[str] = set()
        for item in candidates:
            plain = to_plain(item)
            if isinstance(plain, Mapping):
                for key in ("interaction_id", "id"):
                    if key in plain:
                        out.add(str(plain[key]))
                        break
            elif plain is not None:
                out.add(str(plain))
        return out

    def mastery_score(self, state: Mapping[str, Any]) -> float:
        for key in ("mastery_score", "topic_mastery"):
            if key in state:
                return float(state[key])
        raise AssertionError("learner state must include mastery_score (or topic_mastery)")

    def run_source_provided_flow(
        self,
        *,
        user_id: str,
        session_id: str,
        topic_title: str,
        source_input: str,
        depth_level: str = "core",
    ) -> dict[str, Any]:
        decision = self.route_intake(
            {
                "user_id": user_id,
                "session_id": session_id,
                "topic_title": topic_title,
                "source_input": source_input,
                "entry_mode": "source_provided",
            }
        )
        topic_id = decision.get("topic_id")
        assert isinstance(topic_id, str) and topic_id, "route_intake must resolve topic_id"
        sources = self.ingest_source(decision)
        concepts = self.curate_concepts(sources)
        units = self.generate_cards(concepts, depth_level=depth_level)
        learning_units, question_units = self.split_units(units)
        assert concepts, "curate_concepts must produce at least one concept in source-provided flow"
        assert learning_units, "generate_cards must produce at least one learning unit"
        assert question_units, "generate_cards must produce at least one question unit"
        return {
            "route_decision": decision,
            "topic_id": topic_id,
            "sources": sources,
            "concepts": concepts,
            "units": units,
            "learning_units": learning_units,
            "question_units": question_units,
        }


def _concept_set_from_state(state: Mapping[str, Any], *, keys: Sequence[str]) -> set[str]:
    records: Any = []
    for key in keys:
        if key in state:
            records = to_plain(state[key]) or []
            break
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)):
        return set()

    out: set[str] = set()
    for item in records:
        plain = to_plain(item)
        if isinstance(plain, Mapping):
            for concept_key in ("concept_id", "id", "label"):
                if concept_key in plain:
                    out.add(str(plain[concept_key]))
                    break
        elif plain is not None:
            out.add(str(plain))
    return out


@pytest.fixture(scope="session")
def contracts() -> Contracts:
    modules = {
        "intake": (
            "autodidacticon.intake_router",
            "autodidacticon.modules.intake_router",
            "intake_router",
        ),
        "ingest": (
            "autodidacticon.source_ingestion",
            "autodidacticon.modules.source_ingestion",
            "source_ingestion",
        ),
        "curate": (
            "autodidacticon.knowledge_curation",
            "autodidacticon.modules.knowledge_curation",
            "knowledge_curation",
        ),
        "cards": (
            "autodidacticon.card_generator",
            "autodidacticon.modules.card_generator",
            "card_generator",
        ),
        "store": (
            "autodidacticon.persistence_store",
            "autodidacticon.modules.persistence_store",
            "persistence_store",
        ),
        "retriever": (
            "autodidacticon.learner_state_retriever",
            "autodidacticon.modules.learner_state_retriever",
            "learner_state_retriever",
        ),
        "adapt": (
            "autodidacticon.adaptation_engine",
            "autodidacticon.modules.adaptation_engine",
            "adaptation_engine",
        ),
    }

    return Contracts(
        route_intake=resolve_contract_callable(
            env_key="AUTODIDACTICON_ROUTE_INTAKE_REF",
            function_candidates=[(m, "route_intake") for m in modules["intake"]],
            class_candidates=[(m, "IntakeRouter", "route_intake") for m in modules["intake"]],
        ),
        ingest_source=resolve_contract_callable(
            env_key="AUTODIDACTICON_INGEST_SOURCE_REF",
            function_candidates=[(m, "ingest_source") for m in modules["ingest"]],
            class_candidates=[(m, "SourceIngestion", "ingest_source") for m in modules["ingest"]],
        ),
        curate_concepts=resolve_contract_callable(
            env_key="AUTODIDACTICON_CURATE_CONCEPTS_REF",
            function_candidates=[(m, "curate_concepts") for m in modules["curate"]],
            class_candidates=[(m, "KnowledgeCuration", "curate_concepts") for m in modules["curate"]],
        ),
        generate_cards=resolve_contract_callable(
            env_key="AUTODIDACTICON_GENERATE_CARDS_REF",
            function_candidates=[(m, "generate_cards") for m in modules["cards"]],
            class_candidates=[(m, "CardGenerator", "generate_cards") for m in modules["cards"]],
        ),
        log_interaction=resolve_contract_callable(
            env_key="AUTODIDACTICON_LOG_INTERACTION_REF",
            function_candidates=[(m, "log_interaction") for m in modules["store"]],
            class_candidates=[(m, "PersistenceStore", "log_interaction") for m in modules["store"]],
        ),
        retrieve_learner_state=resolve_contract_callable(
            env_key="AUTODIDACTICON_RETRIEVE_LEARNER_STATE_REF",
            function_candidates=[(m, "retrieve_learner_state") for m in modules["retriever"]],
            class_candidates=[(m, "LearnerStateRetriever", "get_topic_state") for m in modules["retriever"]],
        ),
        decide_next_step=resolve_contract_callable(
            env_key="AUTODIDACTICON_DECIDE_NEXT_STEP_REF",
            function_candidates=[(m, "decide_next_step") for m in modules["adapt"]],
            class_candidates=[(m, "AdaptationEngine", "decide_next_step") for m in modules["adapt"]],
        ),
    )


@pytest.fixture
def sut(contracts: Contracts) -> SUT:
    return SUT(contracts=contracts)


def int_to_ulid(n: int) -> str:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    if n < 0:
        raise ValueError("ULID counter must be non-negative")
    out = []
    value = n
    while value:
        value, rem = divmod(value, 32)
        out.append(alphabet[rem])
    encoded = "".join(reversed(out)) or "0"
    return ("0" * 26 + encoded)[-26:]


@pytest.fixture
def new_ulid() -> Callable[[], str]:
    counter = itertools.count(1)

    def _next_ulid() -> str:
        return int_to_ulid(next(counter))

    return _next_ulid


@pytest.fixture
def sample_source_text() -> str:
    return (
        "Photosynthesis converts light energy into chemical energy. "
        "Plants use chlorophyll in chloroplasts to capture sunlight, then produce glucose and oxygen."
    )


def assert_ulid(value: Any, *, field_name: str) -> None:
    assert isinstance(value, str), f"{field_name} must be a string"
    assert ULID_RE.match(value), f"{field_name} must be ULID-like (26 chars Crockford Base32): {value}"


__all__ = [
    "ALLOWED_ROUTES",
    "ALLOWED_SOURCE_TYPES",
    "ALLOWED_EXTRACTION_STATUS",
    "ALLOWED_DEPTH_LEVELS",
    "ALLOWED_CARD_TYPES",
    "ALLOWED_RESPONSE_STATUS",
    "ALLOWED_DIFFICULTY",
    "assert_ulid",
]
