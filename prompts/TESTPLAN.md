# TESTPLAN.md (Autodidacticon v1)

## 1. Purpose
Validate that Autodidacticon v1 reliably runs the core learning loop defined in `SPEC.md`: route intake, ingest sources, curate concepts, generate paired cards, persist deterministic records, log interactions, compute learner state from stored evidence, and recommend the next step.

## 2. Scope
### In Scope (v1)
- Intake routing for `source_provided`, `topic_only`, `deepen_topic`.
- Source ingestion and normalized source persistence (`content_hash`, `extraction_status`).
- Concept curation with `label`, `summary`, `depth_level`, misconceptions, relationships.
- Learning/question card generation with required pairing.
- Persistence integrity for `Topic`, `Source`, `Concept`, `LearningUnit`, `Interaction`.
- Retrieval logic for weak/strong detection and mastery score heuristic.
- Adaptation decisions limited to:
  - reinforce weak concepts
  - generate reinforcement cards
  - deepen mastered concepts
  - move topic
- Minimal end-to-end execution from intake through adaptation recommendation.

### Explicit Out of Scope (do not test in v1)
- EverMem or any long-horizon memory subsystem.
- Authentication/authorization flows.
- Production deployment/infrastructure concerns.
- Advanced UI behavior.
- Freeform answer grading.
- Speech/audio grading.
- Spaced-repetition optimizer or advanced pedagogy beyond v1 heuristic.
- Any v2/future features not present in `SPEC.md`.

## 3. Test Levels
### Unit Tests
- Pure behavior and validation for each module contract.
- Deterministic/idempotent logic (hashing keys, thresholds, score formula, route classification).

### Integration Tests
- DB-backed writes/reads across module boundaries.
- Referential integrity, transactional behavior, and idempotent conflict handling.
- Retrieval and adaptation using persisted interactions.

### Minimum End-to-End Test
- One smallest runnable test that executes the full v1 loop on one topic from intake to next-step recommendation with persisted evidence.

## 4. Test Areas by Module
### IntakeRouter
- Objective
  - Correctly classify intake and resolve `topic_id` for new vs existing topic flows.
- Key behaviors to validate
  - Route classification returns exactly one of `source_provided|topic_only|deepen_topic`.
  - `source_provided` when `source_input` exists.
  - `topic_only` when only topic/title exists.
  - `deepen_topic` when existing topic is targeted.
- Happy-path tests
  - New topic + source input => `source_provided`, new `topic_id`.
  - New topic title only => `topic_only`, new `topic_id`.
  - Existing topic selected => `deepen_topic`, existing `topic_id`.
- Edge-case tests
  - Topic title normalization maps equivalent titles to same normalized form.
  - Ambiguous payload (both existing topic and new source) follows deterministic precedence rule.
- Failure-case tests
  - Missing required intake data returns validation error.
  - Unknown topic identifier in deepen flow returns not-found error.
- Minimal test files to create
  - `tests/unit/test_intake_router.py`
  - `tests/integration/test_intake_router_persistence.py`

### SourceIngestion
- Objective
  - Normalize source inputs into canonical text and produce valid `Source` records.
- Key behaviors to validate
  - Supports link/file/text input forms mapped to allowed `source_type`.
  - Computes stable `content_hash` from normalized content.
  - Sets `extraction_status` as `ok|partial|failed`.
  - Emits persisted `Source` record per accepted ingestion.
- Happy-path tests
  - Pasted text ingests with `source_type=text`, non-empty `extracted_text`, `ok`.
  - Re-ingestion of same normalized content under same topic resolves idempotently.
- Edge-case tests
  - Whitespace/case-only variations produce same normalized hash.
  - Partial extraction marks `partial` and still persists record.
- Failure-case tests
  - Extraction failure marks `failed` and returns fallback-needed signal.
  - Duplicate `(topic_id, content_hash)` conflict handled as idempotent success.
- Minimal test files to create
  - `tests/unit/test_source_ingestion.py`
  - `tests/integration/test_source_ingestion_idempotency.py`

### KnowledgeCuration
- Objective
  - Convert normalized source text to a curated concept set suitable for card generation.
- Key behaviors to validate
  - Each concept includes required fields and valid `depth_level`.
  - Misconceptions and relationships are persisted as JSON arrays.
  - Concepts link to correct `topic_id` and optional `source_id`.
- Happy-path tests
  - Non-empty source text returns at least one concept with valid schema.
  - Multiple concepts are persisted and retrievable by topic.
- Edge-case tests
  - Short/simple source produces minimal valid concept set.
  - Re-curation on same source does not produce malformed duplicates when idempotency key/path is reused.
- Failure-case tests
  - Empty concept output triggers one regenerate attempt then explicit refined-input request signal.
  - Invalid depth tag rejected by validation.
- Minimal test files to create
  - `tests/unit/test_knowledge_curation.py`
  - `tests/integration/test_knowledge_curation_persistence.py`

### CardGenerator
- Objective
  - Generate deterministic paired `learning` and `question` units per concept.
- Key behaviors to validate
  - At least one one-to-one pair per concept.
  - Question unit `related_unit_id` points to learning unit.
  - `depth_level`, `source_reference`, and `concept_id/topic_id` are consistent.
  - Idempotency key prevents duplicate cards for same key.
- Happy-path tests
  - For one concept, generator creates exactly one learning + one paired question.
  - Question `related_unit_id` references created learning unit.
- Edge-case tests
  - Multiple concepts create valid pair sets for each concept.
  - Same concept with new `version_seed` creates new versioned units.
- Failure-case tests
  - Missing pair in generated batch causes transaction rejection/regeneration signal.
  - Invalid card type rejected.
- Minimal test files to create
  - `tests/unit/test_card_generator.py`
  - `tests/integration/test_card_generator_pairing.py`

### PersistenceStore
- Objective
  - Guarantee transactional, referentially valid, deterministic persistence and retrieval.
- Key behaviors to validate
  - FK constraints enforce entity linkage.
  - Unique constraints enforce source idempotency.
  - Duplicate idempotency events return existing records (not duplicate rows).
  - Query interfaces return data needed by retriever/adaptation.
- Happy-path tests
  - Transaction writes source + concepts + units atomically.
  - Interaction insert succeeds when unit is a question unit.
- Edge-case tests
  - Nullable fields (`source_uri`, `source_id`, `difficulty`, `latency_ms`) handled correctly.
  - Concurrent duplicate insert attempts resolve deterministically.
- Failure-case tests
  - FK violation rejected (e.g., concept references missing topic).
  - Interaction against non-question unit rejected.
- Minimal test files to create
  - `tests/integration/test_persistence_store_constraints.py`
  - `tests/integration/test_persistence_store_idempotency.py`

### LearnerStateRetriever
- Objective
  - Compute topic learner state from persisted interactions only.
- Key behaviors to validate
  - Weak/strong concept detection uses v1 thresholds.
  - Mastery score formula and clamping are correct.
  - Output includes evidence interaction IDs.
  - Returns recommendation candidates for adaptation.
- Happy-path tests
  - Mixed interactions produce expected weak/strong lists.
  - Topic mastery equals weighted mean across concept scores (interaction-weighted, capped).
- Edge-case tests
  - No interactions returns safe empty/initial state.
  - Boundary values at exact thresholds behave as specified (`>=`, `<=`).
- Failure-case tests
  - Retrieval timeout returns safe fallback recommendation path (`reinforce_recent_weak`) from most recent available interactions.
  - Corrupt/missing interaction references are handled without crashing, with explicit error/report.
- Minimal test files to create
  - `tests/unit/test_learner_state_retriever.py`
  - `tests/integration/test_learner_state_retriever_queries.py`

### AdaptationEngine
- Objective
  - Select next-step action using learner state and v1 strategy set only.
- Key behaviors to validate
  - Chooses from allowed actions only.
  - Decision includes explicit reason tied to retriever evidence.
  - Prioritizes weak-concept reinforcement before deepening.
- Happy-path tests
  - Weak concepts present => `reinforce weak concepts` or `generate reinforcement cards`.
  - Strong/mastered concepts with no active weak blockers => `deepen mastered concepts`.
  - Stable strong state across topic => `move topic`.
- Edge-case tests
  - Mixed weak and strong concepts picks weak-first action.
  - Sparse evidence still returns deterministic action.
- Failure-case tests
  - Missing learner-state fields returns validation error.
  - Unsupported recommendation candidate from retriever is rejected and replaced with safe default.
- Minimal test files to create
  - `tests/unit/test_adaptation_engine.py`
  - `tests/integration/test_adaptation_engine_with_retriever.py`

## 5. Entity and Storage Integrity Tests
### Referential Integrity Expectations
- `Topic.user_id` must exist in `users`.
- `Source.topic_id` must exist in `topics`.
- `Concept.topic_id` must exist in `topics`; `source_id` if present must exist in `sources`.
- `LearningUnit.topic_id` and `concept_id` must exist and match same topic domain.
- `Interaction` must reference existing `user`, `session`, `topic`, `concept`, and `unit`.
- Interaction `unit_id` must reference `learning_units.card_type='question'`.
- Interaction `topic_id`/`concept_id` must match the referenced question unit’s topic/concept.

### Uniqueness / Idempotency Expectations
- `sources` unique constraint on `(topic_id, content_hash)` prevents duplicate ingestion.
- Card generation idempotency key (`sha256(topic_id + concept_id + card_type + version_seed)`) prevents duplicate cards for same key.
- Interaction logging with repeated client idempotency key must not create duplicate interaction rows.

### Card Pairing Integrity
- For each concept generation batch, minimum one learning/question pair must exist.
- Every question unit has non-null `related_unit_id` to a learning unit in same topic/concept lineage.
- Paired units share coherent `depth_level` and `version`.

### Interaction-to-Question-Unit Integrity
- Logging interaction against learning card is rejected.
- Logging interaction against question card with mismatched concept/topic is rejected.
- Valid question interaction persists and is queryable by `user_id`, `topic_id`, and `created_at`.

## 6. Retrieval and Progress Tests
- Weak concept detection
  - In a recent window (default last 20 question interactions/topic), mark weak if:
    - `did_not_get_it` rate `>= 0.30`, or
    - `difficulty=hard` rate `>= 0.40`.
- Strong concept detection
  - Mark strong only if both:
    - `got_it` rate `>= 0.75`
    - `difficulty=hard` rate `<= 0.20`.
- Mastery score computation
  - Concept score uses:
    - `got_it=1.0`, `partially_got_it=0.5`, `did_not_get_it=0.0`
    - minus `0.15` penalty for `difficulty=hard`
    - clamped to `[0,1]`.
  - Topic mastery is weighted mean by interaction count (with cap behavior verified).
- Evidence references
  - `get_topic_state(user_id, topic_id)` returns `interaction_id` evidence list supporting weak/strong and recommendation candidates.
  - Evidence IDs correspond to persisted rows in the queried topic.

## 7. Adaptation Tests (v1 only)
- Reinforce weak concepts
  - When weak list is non-empty, adaptation output prioritizes reinforcement action with weak concept IDs.
- Generate reinforcement cards
  - For weak concepts needing new practice material, adaptation requests/returns reinforcement question units.
- Deepen mastered concepts
  - When strong/mastered concepts exist and weak blockers are below threshold, adaptation chooses deepen action.
- Move topic
  - When topic mastery and strong coverage satisfy configured v1 criteria, adaptation recommends moving topic.
- Constraints
  - No testing of complex autonomous curriculum planning, spaced repetition optimizer, or non-spec pedagogical logic.

## 8. Minimum Runnable E2E Test
### Scenario
Single user, one session, one source-provided topic using pasted text.

### Steps
1. Create session with `entry_mode=source_provided`.
2. Call intake with `topic_title` and `source_input` text; assert route `source_provided`, topic created.
3. Run source ingestion; assert `Source` row persisted with `content_hash` and `extraction_status in (ok|partial)`.
4. Run concept curation; assert at least one concept persisted with valid depth level.
5. Run card generation; assert at least one learning/question pair persisted and correctly linked.
6. Submit one or more interactions on returned question units with varied `response_status`.
7. Retrieve learner state; assert mastery score present, weak/strong logic consistent with inserted interactions, evidence IDs returned.
8. Run adaptation; assert action is one of allowed v1 actions with explicit reason referencing retrieved evidence.

### Pass Criteria
- Entire loop completes without manual DB edits.
- All persisted links satisfy FK/pairing constraints.
- Recommendation is explainable from stored interactions.

## 9. Proposed Test File Layout
```text
tests/
  conftest.py
  unit/
    test_intake_router.py
    test_source_ingestion.py
    test_knowledge_curation.py
    test_card_generator.py
    test_learner_state_retriever.py
    test_adaptation_engine.py
  integration/
    test_intake_router_persistence.py
    test_source_ingestion_idempotency.py
    test_knowledge_curation_persistence.py
    test_card_generator_pairing.py
    test_persistence_store_constraints.py
    test_persistence_store_idempotency.py
    test_learner_state_retriever_queries.py
    test_adaptation_engine_with_retriever.py
  e2e/
    test_minimal_v1_loop.py
```

## 10. Acceptance Gates
Minimum gate set for v1-valid implementation:
1. All unit tests for the seven core modules pass.
2. Integration tests confirm FK integrity, uniqueness, idempotent conflict handling, and pairing integrity.
3. Retrieval tests pass exact threshold and mastery formula checks (including boundary conditions).
4. Adaptation tests only emit allowed v1 actions with explicit evidence-based reason.
5. Minimal E2E test passes from intake through adaptation with persisted evidence.
6. Re-running same source ingestion/card generation path does not create unintended duplicates.
7. Every stored interaction is verifiably tied to a stored `question` unit and matching concept/topic.
