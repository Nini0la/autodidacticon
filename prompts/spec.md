# SPEC.md

## 1. Purpose
Autodidacticon is a persistent learning system, not a transient chat assistant. This spec defines the v1 architecture that converts user topics or source material into structured learning units, logs learner outcomes, and adapts future learning from stored records.

## 2. Goals and Scope
### 2.1 In Scope (v1)
- Intake of topic-only requests and user-provided sources.
- Routing for `source_provided`, `topic_only`, and `deepen_topic` flows.
- Source ingestion and normalization (link/file/text to canonical text).
- Concept curation from normalized content.
- Learning card and paired question card generation.
- Deterministic persistent storage for topics, concepts, units, and interactions.
- Retrieval-based learner-state assessment.
- Next-step adaptation decisions.

### 2.2 Out of Scope (v1)
- Freeform answer grading.
- Audio/speech explanation grading.
- Full spaced-repetition optimizer.
- Complex autonomous long-horizon curriculum planning.
- Full production-grade UI complexity.

## 3. Product Principles
- Learner state is derived from persisted data, never from chat transcript alone.
- Every question interaction is tied to a concrete stored learning unit.
- Adaptation decisions must be explainable by retrieval traces.
- Stored learning artifacts are deterministic and recoverable.
- Topic progression must be explicit and inspectable.

## 4. Functional Requirements
1. User can start from either a topic prompt or source input.
2. System can extract/normalize source content (video transcript, webpage text, document text, pasted text).
3. System can produce curated concepts with depth tagging.
4. System creates at least one `learning` unit and one paired `question` unit per concept.
5. System persists generated units with metadata and concept linkage.
6. User can submit self-assessment on recall outcomes and optional difficulty.
7. System persists interaction records tied to `unit_id`, `concept_id`, and `topic_id`.
8. System can retrieve weakness/strength patterns and summarize learner state.
9. System can recommend next action: reinforce weak concepts, generate reinforcement cards, deepen mastered concepts, or move topic.

## 5. Domain Model
All ids are ULID strings. All timestamps are UTC ISO-8601.

### 5.1 Entities
- `User`
- `Session`
- `Topic`
- `Source`
- `Concept`
- `LearningUnit`
- `Interaction`

### 5.2 Entity Definitions
#### User
- `user_id` (PK)
- `created_at`

#### Session
- `session_id` (PK)
- `user_id` (FK User)
- `started_at`
- `ended_at` (nullable)
- `entry_mode` enum: `source_provided|topic_only|deepen_topic`

#### Topic
- `topic_id` (PK)
- `user_id` (FK User)
- `title`
- `normalized_title`
- `status` enum: `active|paused|completed`
- `created_at`
- `updated_at`

#### Source
- `source_id` (PK)
- `topic_id` (FK Topic)
- `source_type` enum: `youtube|web|pdf|doc|text|generated`
- `source_uri` (nullable for raw text)
- `content_hash` (sha256 of normalized content)
- `extracted_text`
- `extraction_status` enum: `ok|partial|failed`
- `created_at`

#### Concept
- `concept_id` (PK)
- `topic_id` (FK Topic)
- `source_id` (FK Source, nullable)
- `label`
- `summary`
- `depth_level` enum: `intro|core|advanced`
- `misconceptions_json`
- `relationships_json`
- `created_at`

#### LearningUnit
- `unit_id` (PK)
- `topic_id` (FK Topic)
- `concept_id` (FK Concept)
- `card_type` enum: `learning|question`
- `title`
- `content`
- `source_reference`
- `depth_level` enum: `intro|core|advanced`
- `related_unit_id` (self FK; question points to paired learning unit)
- `version`
- `created_at`

#### Interaction
- `interaction_id` (PK)
- `user_id` (FK User)
- `session_id` (FK Session)
- `topic_id` (FK Topic)
- `concept_id` (FK Concept)
- `unit_id` (FK LearningUnit; must be `question`)
- `response_status` enum: `got_it|partially_got_it|did_not_get_it`
- `difficulty` enum: `easy|medium|hard` (nullable)
- `latency_ms` (nullable)
- `created_at`

### 5.3 Cardinality Rules
- One Topic has many Sources, Concepts, and LearningUnits.
- One Concept has exactly one or more learning units and one or more question units over time.
- A question unit must reference a paired learning unit via `related_unit_id`.
- Interaction must reference a question unit and its matching concept/topic.

## 6. Determinism and Idempotency
- `Source.content_hash` is unique per topic to avoid duplicate ingestion.
- Card generation uses deterministic idempotency key:
  `idempotency_key = sha256(topic_id + concept_id + card_type + version_seed)`.
- Re-running generation with same key must not create duplicates.
- Interaction logging supports client-provided idempotency key to avoid duplicate writes on retries.

## 7. Architecture and Module Boundaries

### 7.1 Modules
1. `ChatSessionInterface`
2. `IntakeRouter`
3. `SourceIngestion`
4. `KnowledgeCuration`
5. `CardGenerator`
6. `PersistenceStore`
7. `LearnerStateRetriever`
8. `AdaptationEngine`

### 7.2 Responsibilities
#### ChatSessionInterface
- Accept user input.
- Request next action from orchestrator.
- Render learning and question cards.
- Capture self-assessment signals.

#### IntakeRouter
- Classify input into one of:
  `source_provided|topic_only|deepen_topic`.
- Resolve `topic_id` (new or existing).

#### SourceIngestion
- Parse source input.
- Extract text.
- Normalize, chunk, and hash content.
- Emit `Source` records.

#### KnowledgeCuration
- Derive concept set from normalized text.
- Output concept graph with misconceptions and relations.

#### CardGenerator
- Generate concise learning cards and paired recall cards.
- Enforce one-to-one pairing at minimum.
- Attach source references and depth levels.

#### PersistenceStore
- Own transactional writes and reads.
- Enforce referential integrity and uniqueness.
- Provide query interfaces for learner-state computation.

#### LearnerStateRetriever
- Aggregate interactions by concept/topic.
- Compute mastery and detect weak/strong concepts.
- Return explanation-friendly summary.

#### AdaptationEngine
- Choose next step based on retrieved learner state.
- Strategies: reinforce weak concepts, generate reinforcement cards, deepen mastered concepts, or move topic.

## 8. Storage Schema (SQL-oriented)

```sql
create table users (
  user_id text primary key,
  created_at timestamptz not null
);

create table sessions (
  session_id text primary key,
  user_id text not null references users(user_id),
  started_at timestamptz not null,
  ended_at timestamptz,
  entry_mode text not null check (entry_mode in ('source_provided','topic_only','deepen_topic'))
);

create table topics (
  topic_id text primary key,
  user_id text not null references users(user_id),
  title text not null,
  normalized_title text not null,
  status text not null check (status in ('active','paused','completed')),
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table sources (
  source_id text primary key,
  topic_id text not null references topics(topic_id),
  source_type text not null check (source_type in ('youtube','web','pdf','doc','text','generated')),
  source_uri text,
  content_hash text not null,
  extracted_text text not null,
  extraction_status text not null check (extraction_status in ('ok','partial','failed')),
  created_at timestamptz not null,
  unique(topic_id, content_hash)
);

create table concepts (
  concept_id text primary key,
  topic_id text not null references topics(topic_id),
  source_id text references sources(source_id),
  label text not null,
  summary text not null,
  depth_level text not null check (depth_level in ('intro','core','advanced')),
  misconceptions_json jsonb not null default '[]'::jsonb,
  relationships_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null
);

create table learning_units (
  unit_id text primary key,
  topic_id text not null references topics(topic_id),
  concept_id text not null references concepts(concept_id),
  card_type text not null check (card_type in ('learning','question')),
  title text not null,
  content text not null,
  source_reference text,
  depth_level text not null check (depth_level in ('intro','core','advanced')),
  related_unit_id text references learning_units(unit_id),
  version integer not null default 1,
  created_at timestamptz not null
);

create table interactions (
  interaction_id text primary key,
  user_id text not null references users(user_id),
  session_id text not null references sessions(session_id),
  topic_id text not null references topics(topic_id),
  concept_id text not null references concepts(concept_id),
  unit_id text not null references learning_units(unit_id),
  response_status text not null check (response_status in ('got_it','partially_got_it','did_not_get_it')),
  difficulty text check (difficulty in ('easy','medium','hard')),
  latency_ms integer,
  created_at timestamptz not null
);

create index idx_interactions_user_topic on interactions(user_id, topic_id, created_at desc);
create index idx_units_topic_concept on learning_units(topic_id, concept_id);
create index idx_concepts_topic on concepts(topic_id);
```

## 9. Retrieval Patterns

### 9.1 Weak Concepts Query
Weak if either condition holds in recent window (default last 20 question interactions/topic):
- `did_not_get_it` rate >= 0.30
- `hard` difficulty rate >= 0.40

### 9.2 Strong Concepts Query
Strong if both conditions hold:
- `got_it` rate >= 0.75
- `hard` difficulty rate <= 0.20

### 9.3 Mastery Score (v1 heuristic)
For each concept:
- `score = 1.0*got_it + 0.5*partially_got_it + 0.0*did_not_get_it`
- Apply penalty `-0.15` when `difficulty=hard`
- Clamp [0,1]
Topic mastery = weighted mean across concept scores (weight by interaction count, capped).

### 9.4 Retrieval Contract
`LearnerStateRetriever.get_topic_state(user_id, topic_id)` computes and returns:
- concept performance map,
- weak and strong concept lists,
- mastery score,
- evidence references (`interaction_id` list),
- recommended next action candidates.

## 10. End-to-End Flow

### 10.1 Source-Provided Flow
1. Create/find session and topic.
2. Ingest and normalize source.
3. Curate concepts.
4. Generate paired cards.
5. Persist sources, concepts, units.
6. Present learning cards, then question cards.
7. Log interactions.
8. Retrieve learner state.
9. Recommend next step.

### 10.2 Topic-Only Flow
1. Create/find session and topic.
2. Source foundational material (retrieval or generated baseline).
3. Continue from step 3 of source-provided flow.

### 10.3 Deepen Existing Topic Flow
1. Resolve existing topic.
2. Retrieve prior concepts, units, and learner state.
3. Identify mastered vs weak zones.
4. Generate deeper cards for mastered concepts and reinforcement cards for weak concepts.
5. Persist and continue teach/recall loop.

## 11. Failure Cases and Handling
- Source extraction failure: mark `extraction_status=failed`, prompt user for alternate source or pasted text.
- Partial extraction: mark `partial`, continue with confidence warning.
- Empty concept output: regenerate once with fallback prompt; if still empty, request refined input.
- Card generation mismatch (missing pair): reject transaction and regenerate concept batch.
- Persistence conflict (duplicate hash/key): treat as idempotent success and return existing records.
- Retrieval timeout: return safe fallback recommendation (`reinforce_recent_weak`) computed from the most recent available interactions.

## 12. API / Interface Behavior (v1)

### 12.1 HTTP API
- `POST /v1/sessions`
  - Request: `{ user_id, entry_mode }`
  - Response: `{ session_id, started_at }`

- `POST /v1/intake`
  - Request: `{ session_id, user_id, topic_title?, source_input? }`
  - Response: `{ topic_id, route, source_ids[] }`

- `POST /v1/topics/{topic_id}/curate`
  - Request: `{ source_ids[] }`
  - Response: `{ concept_ids[] }`

- `POST /v1/topics/{topic_id}/cards`
  - Request: `{ concept_ids[], depth_level }`
  - Response: `{ unit_ids[], pairs_created }`

- `GET /v1/topics/{topic_id}/next-units`
  - Query: `user_id`, `session_id`
  - Response: `{ learning_units[], question_units[] }`

- `POST /v1/interactions`
  - Request: `{ user_id, session_id, topic_id, concept_id, unit_id, response_status, difficulty? }`
  - Response: `{ interaction_id }`

- `GET /v1/topics/{topic_id}/state`
  - Query: `user_id`
  - Response: `{ mastery_score, weak_concepts[], strong_concepts[], recommendation }`

- `POST /v1/topics/{topic_id}/adapt`
  - Request: `{ user_id }`
  - Response: `{ action, reason, next_units? }`

### 12.2 Agent Tool Contracts (Internal)
- `route_intake(input) -> route_decision`
- `ingest_source(route_decision) -> source_records`
- `curate_concepts(source_records) -> concept_records`
- `generate_cards(concept_records) -> unit_records`
- `log_interaction(interaction_input) -> interaction_id`
- `retrieve_learner_state(user_id, topic_id) -> state`
- `decide_next_step(state) -> adaptation_plan`

## 13. Observability and Acceptance

### 13.1 Required Events
- intake routed
- source ingested
- concepts curated
- cards generated
- interaction logged
- learner state computed
- adaptation decided

### 13.2 v1 Acceptance Criteria
1. End-to-end loop runs from intake to adaptation without manual DB edits.
2. Every interaction is linked to stored question unit and concept.
3. Re-running intake on same source does not duplicate source/cards unexpectedly.
4. Learner-state summary correctly reflects stored interaction evidence.
5. Next-step recommendation includes explicit evidence basis.

## 14. Build Sequence
1. Implement domain entities and schema.
2. Implement intake routing and source ingestion.
3. Implement concept curation and card generation.
4. Implement persistence + idempotency.
5. Implement interaction logging.
6. Implement learner-state retrieval.
7. Implement adaptation engine.
8. Validate with minimal viable loop test.
