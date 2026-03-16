# PLAN.md

## Project
Autodidacticon

## Working framing
Autodidacticon is an AI-powered self-learning companion system that:
1. helps a user learn a topic,
2. curates or generates learning material,
3. converts that material into structured learning units,
4. stores those learning units and user interactions persistently,
5. uses stored history to adapt future learning.

It is not just “an LLM chat.”  
The core idea is persistent, structured learning memory.

---

## Core product idea
A user chats with the agent and says either:
- what they want to learn, or
- provides source material to learn from.

The system then:
- determines whether to use user-provided material or source material itself,
- creates learning units,
- stores them deterministically,
- presents them to the user,
- records user self-assessment against specific learning units,
- uses that stored history to guide future learning.

---

## Main design principle
The agent must never rely only on conversational memory to know what the user has learned.

Instead, it should use persistent storage and explicit retrieval of:
- prior learning units,
- prior question units,
- prior user interactions,
- topic history,
- difficulty / success patterns.

This avoids drift, forgetting, and vague personalization.

---

## Primary user flow

### 1. Session start
User opens chat with the agent.

Possible inputs:
- “I want to learn about accelerated GPUs.”
- a YouTube link,
- an article,
- a PDF or document,
- notes or pasted text,
- a request to go deeper on something already studied.

### 2. Intake + routing decision
The agent determines which of these cases applies:

#### Case A: User provides source material
The system extracts content from the provided source.

Examples:
- YouTube → transcript extraction
- article / webpage → text extraction
- PDF / doc → text extraction
- pasted text → direct parsing

#### Case B: User provides only a topic
The system sources or generates foundational material for that topic using strong retrieval / generation.

#### Case C: User asks to go deeper on an existing topic
The system retrieves prior stored learning history for that topic, analyzes what has already been covered, then expands deeper.

---

## Learning material generation flow

### 3. Curate source knowledge
From either extracted or sourced material, the agent creates a structured internal representation of what should be learned.

This should produce:
- topic title,
- subtopics,
- key concepts,
- important facts,
- relationships,
- possible misconceptions,
- depth level.

### 4. Create learning units
The agent converts curated knowledge into structured learning units.

At minimum, each concept should produce:

#### A. Learning card
A concise explanation card for a specific concept.

#### B. Question card
A paired recall/self-test card tied to that same concept.

The learning card teaches.  
The question card checks recall.

---

## Learning unit requirements
Each stored learning unit should have structured metadata, such as:
- unit_id,
- topic_id,
- concept_label,
- concept_summary,
- card_type (`learning` or `question`),
- source_reference,
- depth_level,
- created_at,
- related_unit_id.

Important:
- every question card should map cleanly to an underlying concept,
- every user interaction should be tied to a specific stored unit,
- each card should carry a concise summary of what it covers.

---

## Persistence model

### 5. Persist generated learning content
Generated cards are not temporary chat artifacts.

They should be stored persistently in a deterministic store.

What should be persisted:
- topic records,
- source records,
- curated concept records,
- learning cards,
- question cards,
- links between related cards,
- session metadata.

This matters because the generated cards themselves become part of the learner’s history.

### 6. Persist user interactions
When the user interacts with a question card, that interaction must also be stored.

For each interaction, capture at least:
- interaction_id,
- user_id,
- unit_id,
- topic_id,
- response status,
- difficulty signal,
- timestamp,
- session_id.

Suggested response states:
- got_it
- partially_got_it
- did_not_get_it

Suggested difficulty states:
- easy
- medium
- hard

These interaction records are the basis for future personalization.

---

## How the learning loop works

### 7. Teach phase
The system presents learning cards first.

Purpose:
- expose the user to the concept,
- make the user familiar with the material,
- establish a clear concept-to-card mapping.

### 8. Recall phase
The system then presents paired question cards.

The user is encouraged to explain the concept to themselves internally or aloud.

The user does not need to submit freeform text in v1.

Instead, after attempting recall, the user reports:
- whether they got it,
- whether they partially got it,
- or did not get it,
and optionally how hard it felt.

### 9. Evaluation phase
The agent evaluates the learner’s weak and strong areas not from chat memory, but from tool-based retrieval over stored interaction history.

This means the agent should explicitly retrieve:
- which units were missed,
- which concepts were marked hard,
- which concepts were consistently easy,
- which topics have partial mastery,
- what has already been covered.

### 10. Adaptation phase
Based on stored history, the agent decides what to do next:
- reinforce weak concepts,
- revisit missed concepts,
- generate simpler prerequisite material,
- move deeper into the same topic,
- connect related prior topics,
- move to a new topic.

---

## Cross-topic memory
The system should also maintain a history of what the learner has studied overall.

This enables:
- continuity over time,
- revisiting old themes,
- cross-pollination between topics,
- identifying recurring weaknesses,
- deeper topic expansion without redoing prior material blindly.

This history should include:
- topics studied,
- sources used,
- concepts covered,
- performance patterns,
- progression over time.

---

## Role of EverMem OS
EverMem OS should be treated as the long-term memory layer or part of the memory layer.

Potential use:
- store learner events,
- store topic history,
- store session summaries,
- store user progress signals,
- retrieve prior learning context,
- support continuity across sessions.

Important:
EverMem OS should support the agent’s memory and retrieval needs, but the app still needs a clear structured domain model for learning units and interactions.

So the design should not reduce everything to vague memory blobs.

---

## Suggested v1 scope

### In scope
- user enters topic or provides source
- routing between provided-source vs source-it-yourself
- content extraction / sourcing
- concept curation
- learning card creation
- paired question card creation
- persistent storage of cards
- persistent storage of user self-assessment
- retrieval-based learner state assessment
- simple adaptation for next step

### Out of scope for initial build
- freeform answer grading
- automatic judging of spoken explanations
- advanced spaced repetition optimization
- multimodal grading
- highly autonomous curriculum planning across months
- full production UI complexity

---

## Minimal viable loop
The minimum runnable artifact should be:

1. user provides a topic or source,
2. system creates structured learning cards + question cards,
3. cards are stored persistently,
4. user goes through a short set,
5. user marks recall outcome and difficulty,
6. interactions are stored,
7. agent retrieves stored records and summarizes what the user seems weak/strong at,
8. agent proposes the next learning step.

If this loop works end-to-end, the concept is proven.

---

## Key architectural modules

### A. Chat / session interface
Handles user conversation and session state.

### B. Intake router
Determines:
- provided source?
- topic-only?
- deepen existing topic?

### C. Source ingestion module
Extracts usable text from links, files, transcripts, or pasted content.

### D. Knowledge curation module
Turns raw material into structured concepts.

### E. Card generation module
Creates learning cards and paired question cards.

### F. Persistence module
Stores:
- topics,
- sources,
- cards,
- interactions,
- summaries.

### G. Learner-state retrieval module
Pulls performance data and prior history.

### H. Adaptation module
Chooses reinforcement / depth / progression.

### I. EverMem integration layer
Stores and retrieves long-term contextual memory.

---

## Critical implementation rules
- Do not rely on plain chat history as truth of learner state.
- All adaptation decisions should be grounded in retrieved stored records.
- Every question interaction must point to a specific stored learning concept.
- Learning content must be recoverable later.
- Topic progression must be inspectable, not implicit.

---

## Success criteria for v1
The system is successful if:
- it can generate usable learning material from a topic or source,
- it stores learning units in a structured way,
- it stores user feedback tied to those units,
- it can later retrieve that history and correctly describe what the learner struggled with,
- it can use that history to generate a sensible next step.

---

## Build sequence
1. define domain objects
2. define storage schema
3. define intake routing
4. implement source/topic ingestion
5. implement concept curation
6. implement card generation
7. implement interaction logging
8. implement retrieval-driven learner assessment
9. implement next-step adaptation
10. connect EverMem OS where appropriate

---

## Immediate next document
`SPEC.md`

The spec should translate this plan into:
- exact entities,
- tool boundaries,
- function responsibilities,
- storage schema,
- retrieval patterns,
- end-to-end flow,
- failure cases,
- v1 API / interface behavior.