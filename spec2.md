# RESUME INTERVIEW PLATFORM — UPGRADE MASTER CONTEXT

> ## ⚠️ AUTHORITATIVE AMENDMENT
>
> This context is amended by **"SPEC 2 AMENDMENT — DATABASE, DATA INTEGRITY & CONCURRENCY FIXES"** (see Appendix A at the end of this document). The amendment is not a new project — it is a set of corrections layered on top of this context and implemented in the **same** implementation pass.
>
> **Where this context and the amendment conflict, THE AMENDMENT WINS.**
>
> Summary of what the amendment overrides:
>
> * Database: **PostgreSQL required** (overrides the SQLite-for-MVP allowance in §32). No SQLite in any form.
> * Interview IDs: race-free generation via DB (INSERT → derive `INT-YYYYMMDD-NNN` → UPDATE), UNIQUE constraint enforced at DB level, never client-generated (§3/§5 of the original).
> * Schema: clean record design with integer PKs as real FKs, evaluation **history** (new row per re-evaluation, `is_current` flag), status enums/CHECK constraints (§3).
> * Job processing: state lives in Postgres (not in-memory), startup recovery of stuck rows, `FOR UPDATE SKIP LOCKED` for worker claiming (§4).
> * Auth: **required** — every `/api/interviews*` and document-download route requires an authenticated staff session; `interview_id` is not a bearer credential (§5).
> * File lifecycle: scratch files deleted after use; **record files never auto-deleted** by request cleanup; separate scheduled retention job (`RETENTION_DAYS`) (§6).
> * Handwriting OCR: distinct prompt that outputs `[BLANK]` / `[ILLEGIBLE]` / transcribed text per region (§7).
> * Segmentation: mismatch ⇒ `SEGMENTATION_UNCERTAIN` + mandatory manual-correction UI before evaluation (§8).
> * Scoring: shared reference corpus for TF-IDF/BM25; server-side normalization of LLM concept weights (§9).
> * New capability: per-question manual score override with required reason, stored auditable (§10).
> * Async processing: frontend changes go beyond a dashboard — rework upload flow to QUEUED→POLLING; duplicate-submission protection keyed off server-side interview state, not a client button flag (§11).
> * "Do not" additions and acceptance-criteria additions (§12, §13).

---

## 0. ROLE

You are an experienced full-stack engineer taking over an **existing working Resume Interview Q&A Generator MVP**.

Your task is to **upgrade the existing application in place**.

Do NOT rebuild the application from scratch.

Do NOT unnecessarily rewrite working functionality.

First inspect the existing repository, understand the current architecture and implementation, identify what already exists, and then implement the upgrade described below.

The application already has:

* Resume upload
* PDF/image processing
* Resume text extraction
* OCR
* LLM-based interview question generation
* Question + sample answer generation
* Result display
* Document generation/download
* Existing frontend
* **React frontend migration already completed**

The current task is to add the next major capability:

> **Generate interview sheets → interviewee writes answers manually → staff uploads completed answer sheet → system extracts answers → evaluates answers WITHOUT using an LLM → calculates scores → displays evaluation results in a dashboard.**

The upgraded system must also support multiple staff members uploading resumes and answer scripts, with every interview tracked using a unique Interview ID.

---

# 1. IMPORTANT PROJECT PRINCIPLE

The existing MVP is already functional.

The objective now is:

```text
UPGRADE EXISTING SYSTEM
NOT
REBUILD EXISTING SYSTEM
```

Preserve working functionality unless a change is required by the new architecture.

Before making changes:

1. Inspect the repository.
2. Inspect the existing backend.
3. Inspect the existing React frontend.
4. Inspect existing API routes.
5. Inspect existing models/schemas.
6. Inspect existing services.
7. Inspect existing document-generation logic.
8. Inspect existing LLM integration.
9. Identify current storage behavior.
10. Identify whether persistence already exists.
11. Identify what can be reused.
12. Produce a short implementation plan.
13. Then implement incrementally.

Do not assume the original MVP structure is still exactly as described in the old specification.

The actual repository is the source of truth.

---

# 2. CURRENT SYSTEM

The current application is a Resume Interview Q&A Generator.

Existing primary flow:

```text
Staff
  ↓
Upload Resume
  ↓
Validate File
  ↓
Extract Resume Text
  ↓
Clean Text
  ↓
LLM
  ↓
Generate Interview Questions
  ↓
Generate Sample Answers
  ↓
Display Result
  ↓
Download / Print
```

The React migration has already been completed.

The upgrade should extend this system rather than replace it.

---

# 3. NEW BUSINESS FLOW

The upgraded application must support the following lifecycle:

```text
Resume Upload
      ↓
Generate Interview
      ↓
Assign Interview ID
      ↓
Process Resume
      ↓
Generate Questions
      ↓
Generate Sample Answers
      ↓
Generate Evaluation Key
      ↓
Generate Interview Sheet(s)
      ↓
Staff Downloads / Prints Sheet
      ↓
Interviewee Manually Writes Answers
      ↓
Staff Receives Completed Answer Sheet
      ↓
Staff Uploads Answer Sheet
      ↓
System Associates Answer Sheet With Interview ID
      ↓
OCR / Text Extraction
      ↓
Answer Segmentation
      ↓
Deterministic Answer Evaluation
      ↓
Score Calculation
      ↓
Question-Level Results
      ↓
Overall Score
      ↓
Dashboard
```

---

# 4. CRITICAL AI REQUIREMENT

There are now two separate stages.

## Stage A — Interview Generation

LLM IS ALLOWED.

```text
Resume
  ↓
LLM
  ↓
Questions
Sample Answers
Evaluation Key
```

## Stage B — Answer Evaluation

LLM IS NOT ALLOWED.

```text
Completed Answer Sheet
  ↓
OCR
  ↓
Text Processing
  ↓
Deterministic Evaluation Engine
  ↓
Score
```

The answer-checking mechanism must NOT call:

* OpenAI
* Gemini
* Anthropic
* Any LLM
* Any generative AI model
* Any semantic LLM evaluator

The evaluator must be deterministic and reproducible.

For the same answer and answer key, it should produce the same result.

---

# 5. MAIN NEW FEATURE: INTERVIEW ID

Every uploaded resume must receive a unique Interview ID.

Example:

```text
INT-20260914-001
INT-20260914-002
INT-20260914-003
```

Recommended format:

```text
INT-YYYYMMDD-NNN
```

or another collision-safe equivalent.

The ID must be generated by the backend.

Never trust a client-generated ID.

The Interview ID becomes the primary reference for the complete interview lifecycle.

Example:

```text
INT-20260914-001

├── Resume
├── Extracted resume information
├── Generated questions
├── Sample answers
├── Evaluation key
├── Interview question sheet
├── Answer key
├── Uploaded answer script
├── Evaluation result
└── Score
```

The system must never depend on the original resume filename as the primary identifier.

---

# 6. DASHBOARD

Add a prominent:

```text
Dashboard
```

button to the React application.

When clicked, open the dashboard.

The dashboard is the operational interface for staff.

It should show all interview jobs and their current state.

Example:

```text
INTERVIEW DASHBOARD

Interview ID       Status          Actions

INT-20260914-001   Processing       Processing...
INT-20260914-002   Completed        Resume
                                    Questions
                                    Answer Key
                                    Upload Answers

INT-20260914-003   Evaluated        Resume
                                    Questions
                                    Answer Key
                                    Answer Script
                                    View Score
```

---

# 7. DASHBOARD INTERVIEW CARD

Prefer a clean card/table design.

Each interview should display:

```text
Interview ID
Candidate Name
Created Time
Current Status
Processing Stage
Available Documents
Answer Script Upload
Evaluation Status
Score
```

Example:

```text
┌──────────────────────────────────────────────────────┐
│ INT-20260914-002                                     │
│ Candidate: Rahul Sharma                              │
│                                                      │
│ Status: Completed                                    │
│                                                      │
│ Resume Processing       ✓                            │
│ Question Generation     ✓                            │
│ Document Generation     ✓                            │
│ Answer Evaluation       ○ Not Started               │
│                                                      │
│ [Resume] [Question Sheet] [Answer Key]               │
│                                                      │
│ Upload Completed Answer Script                       │
│ [ Choose File ]                                      │
│ [ Evaluate Answers ]                                 │
└──────────────────────────────────────────────────────┘
```

After evaluation:

```text
┌──────────────────────────────────────────────────────┐
│ INT-20260914-002                                     │
│ Candidate: Rahul Sharma                              │
│                                                      │
│ Evaluation: ✓ Complete                               │
│                                                      │
│ Score: 78 / 100                                      │
│ Percentage: 78%                                      │
│                                                      │
│ [ View Detailed Evaluation ]                         │
└──────────────────────────────────────────────────────┘
```

---

# 8. DOCUMENTS

For each completed interview, the dashboard should provide download access to the relevant generated documents.

At minimum support:

```text
1. Resume / extracted resume information where currently supported
2. Interview Question Sheet
3. Answer Key / Sample Answers
```

If the existing application already produces specific documents, reuse those implementations.

Do not duplicate document-generation logic.

The interview question sheet is the document that will be given to the interviewee.

The answer key is used internally for evaluation and should not normally be given to the interviewee.

---

# 9. INTERVIEW QUESTION SHEET

The generated interview sheet must be suitable for printing.

Example:

```text
RESUME INTERVIEW

Interview ID: INT-20260914-002
Candidate: Rahul Sharma

--------------------------------------------

QUESTION 1

What is Django ORM?

ANSWER:

____________________________________________

____________________________________________

____________________________________________

____________________________________________


QUESTION 2

Explain your e-commerce project architecture.

ANSWER:

____________________________________________

____________________________________________

____________________________________________

____________________________________________
```

The sheet should contain:

* Interview ID
* Candidate name
* Questions
* Clearly identifiable question numbers
* Space for handwritten answers

The answer areas should be clearly separated.

---

# 10. ANSWER SHEET UPLOAD

Staff must be able to upload the completed answer script from the dashboard.

Supported formats should initially follow the existing upload capabilities:

```text
.pdf
.jpg
.jpeg
.png
```

Maximum file size should remain configurable.

Recommended default:

```text
10 MB
```

The backend must validate:

* Extension
* MIME type where available
* File size
* File readability

Never trust frontend validation alone.

---

# 11. ANSWER SCRIPT PROCESSING

After upload:

```text
Answer Script
      ↓
File Validation
      ↓
Determine PDF/Image
      ↓
Text Extraction / OCR
      ↓
Clean Text
      ↓
Identify Answer Regions
      ↓
Associate Answer With Question
      ↓
Evaluate
      ↓
Calculate Score
```

For image and scanned PDF answer sheets, OCR will be required.

The system should reuse the existing OCR infrastructure where possible.

Do not build a second unrelated OCR implementation.

---

# 12. HANDWRITTEN ANSWER OCR

> **AMENDED BY SPEC 2 AMENDMENT §7 (wins on conflict).** Do not reuse the resume OCR prompt verbatim. Add a distinct handwriting system instruction.

The answer script is expected to potentially contain handwritten answers.

This is an important limitation.

Do not assume handwriting OCR is perfect.

Reuse the existing `ocr_service.py` module/abstraction, but use a **separate handwriting-OCR system instruction** tuned for handwriting.

The handwriting OCR step must explicitly classify each answer region into one of three states, **from the OCR step itself** (not inferred later from character count):

```text
[BLANK]          - no handwriting detected in the region
[ILLEGIBLE]      - handwriting present but not confidently readable
<transcribed text> - normal case: handwriting was read
```

The system must:

* Detect insufficient OCR output
* Detect unreadable answers
* Avoid silently giving a zero when OCR failed
* Show an appropriate status
* Allow staff to identify the problem

For example:

```text
Question 4
Status: Unable to read answer
Reason: Insufficient OCR text
```

This is preferable to:

```text
Question 4
Score: 0
```

because OCR failure and an incorrect answer are not the same thing. Downstream evaluation branches on the exact `[BLANK]` / `[ILLEGIBLE]` / transcribed signal to separate "No Answer" (score 0) from "OCR failure" (score N/A), per §49–§52.

---

# 13. ANSWER SEGMENTATION

> **AMENDED BY SPEC 2 AMENDMENT §8 (wins on conflict).** Marker-based segmentation is expected to fail when a candidate writes past the allotted space, skips a question, or uses a spare sheet.

Because the application generated the original question sheet, it already knows:

```text
Question 1
Question 2
Question 3
...
```

Use this information.

Do not rely entirely on OCR to determine which question an answer belongs to.

The generated answer sheet should have strong structural markers.

For example:

```text
QUESTION 1
ANSWER 1

QUESTION 2
ANSWER 2
```

The answer script should be associated with its Interview ID.

The evaluator should then map:

```text
Question 1 → Answer 1
Question 2 → Answer 2
Question 3 → Answer 3
```

where possible.

**If the number of detected question markers does not match the expected question count for that interview, mark the whole answer set `SEGMENTATION_UNCERTAIN` rather than guessing** — never silently produce a potentially incorrect score.

If segmentation is uncertain, the dashboard must show a **manual-correction view** where staff can view the raw OCR'd text blocks for the uncertain interview and manually assign each block to the correct question number **before evaluation runs**. This manual override is mandatory; the deterministic evaluator's accuracy depends on correct segmentation.

---

# 14. ANSWER EVALUATION ENGINE

Create a dedicated service.

Suggested conceptual name:

```text
DeterministicAnswerEvaluator
```

or:

```text
AnswerEvaluationService
```

Do not call it simply:

```text
KeywordMatcher
```

because the evaluation system must be more sophisticated than literal keyword counting.

---

# 15. EVALUATION ENGINE GOAL

The evaluator should determine:

> How well does the candidate's answer cover the important concepts expected by the answer key?

It should not require the candidate to reproduce the sample answer word-for-word.

Example expected answer:

```text
Django ORM allows developers to interact with database records
using Python models rather than writing SQL for every operation.
```

Candidate answer:

```text
Django provides a model abstraction that lets Python code work
with database data without manually writing SQL queries.
```

This should score highly.

A literal string comparison would fail.

---

# 16. RECOMMENDED EVALUATION STRATEGY

Use a multi-layer deterministic approach.

```text
Candidate Answer
      ↓
Normalization
      ↓
Tokenization
      ↓
Keyword Matching
      ↓
Synonym / Concept Group Matching
      ↓
Phrase Matching
      ↓
TF-IDF / BM25 Similarity
      ↓
Required Concept Coverage
      ↓
Question-Type Rules
      ↓
Weighted Score
```

No LLM.

---

# 17. LAYER 1 — TEXT NORMALIZATION

Normalize both candidate answer and evaluation key.

Perform operations such as:

* Lowercase
* Normalize whitespace
* Normalize punctuation
* Remove irrelevant formatting
* Normalize common word forms where practical
* Tokenize

Do not aggressively alter technical terminology.

For example:

```text
PostgreSQL
Postgres
```

may be treated as related through an explicit synonym mapping.

But do not create uncontrolled automatic substitutions.

---

# 18. LAYER 2 — KEYWORD MATCHING

Each question should have relevant keywords.

Example:

```json
{
  "keywords": [
    "django",
    "orm",
    "database",
    "model",
    "sql",
    "query"
  ]
}
```

Calculate keyword coverage.

However:

DO NOT give the majority of the score to exact keywords.

Keyword matching is only one component.

---

# 19. LAYER 3 — SYNONYM / CONCEPT GROUPS

Support manually defined concept groups.

Example:

```json
{
  "database": [
    "database",
    "db",
    "data store"
  ],
  "authentication": [
    "authentication",
    "auth",
    "login",
    "user authentication"
  ],
  "api": [
    "api",
    "application programming interface",
    "endpoint",
    "http service"
  ]
}
```

Prefer question-specific concept groups where possible.

Do not attempt to create a universal ontology for every technology.

The goal is a practical MVP evaluator.

---

# 20. LAYER 4 — PHRASE MATCHING

Important phrases can provide stronger evidence than individual keywords.

Example:

```text
object relational mapper
database abstraction
client-server communication
stateless architecture
password hashing
```

Match normalized phrases.

Allow partial variants where practical.

---

# 21. LAYER 5 — TF-IDF / BM25

> **AMENDED BY SPEC 2 AMENDMENT §9 (wins on conflict).** A 2-document corpus (sample answer vs. candidate answer) makes IDF weighting degenerate. Build a shared reference corpus **once at generation time** from all sample answers and concept/phrase text for that interview's question set, and compute similarity against that corpus. Do not compute IDF from just the single question pair.

Use a deterministic text similarity mechanism.

Preferred simple options:

```text
TF-IDF + cosine similarity
```

or:

```text
BM25
```

Do not introduce embeddings unless there is a proven need.

Do not introduce a vector database.

For this scale, local deterministic text similarity is sufficient.

The similarity score should be treated as supporting evidence rather than absolute correctness.

---

# 22. LAYER 6 — REQUIRED CONCEPT COVERAGE

> **AMENDED BY SPEC 2 AMENDMENT §9–§10 (wins on conflict).** Naming caveat: "concept coverage" is lexical/synonym matching with a different label — it is NOT meaning-based matching, and neither the UI nor staff communication should overstate it. Compensate operationally with the manual score-override capability (§47a) and the per-question score-override API.

This should be one of the strongest components.

For each question, define important concepts.

Example:

```json
{
  "required_concepts": [
    "database interaction",
    "Python models",
    "SQL abstraction"
  ]
}
```

Evaluate whether the candidate answer addresses those concepts.

Concepts can have weights.

Example:

```json
{
  "concepts": [
    {
      "name": "database interaction",
      "weight": 0.30
    },
    {
      "name": "Python models",
      "weight": 0.30
    },
    {
      "name": "SQL abstraction",
      "weight": 0.25
    },
    {
      "name": "query generation",
      "weight": 0.15
    }
  ]
}
```

**LLM-generated concept weights:** do not hard-fail validation if a question's concept weights don't sum exactly to 1.0 — LLMs are unreliable at exact arithmetic. Normalize weights server-side after parsing (divide each by their sum). Only fail validation if weights are missing or non-numeric.

---

# 23. QUESTION-SPECIFIC EVALUATION

Different question types should be evaluated differently.

## Technical

Look for:

* Correct terminology
* Core concepts
* Technical relationships
* Appropriate explanation

## Project

Look for:

* Purpose
* Candidate role
* Architecture
* Technologies
* Implementation
* Database/API
* Challenges
* Results

## Problem Solving

Look for:

* Problem identification
* Investigation
* Reasoning
* Solution
* Validation/result

## Behavioral

Look for:

* Situation
* Task
* Action
* Result

Do not require exact STAR wording.

The concepts are what matter.

---

# 24. RECOMMENDED INITIAL SCORING MODEL

Use a 100-point total.

For each question, normalize the score to 0–10.

Recommended initial weighting:

```text
Required Concept Coverage     40%
Keyword Coverage              25%
Phrase / Synonym Matching     15%
TF-IDF/BM25 Similarity         10%
Question-Type Structure        10%
```

Example:

```text
Concept Coverage:       8/10
Keyword Coverage:       7/10
Phrase Matching:        8/10
Similarity:             7/10
Structure:              9/10
```

Final:

```text
0.40 × 8
+ 0.25 × 7
+ 0.15 × 8
+ 0.10 × 7
+ 0.10 × 9
= 7.75 / 10
```

If there are 20 questions:

```text
775 / 1000
= 77.5 / 100
```

The exact weighting should remain configurable so it can be tuned after testing.

> **AMENDED BY SPEC 2 AMENDMENT §10 (wins on conflict).** Add per-question **manual score override**:
>
> * Staff can view the deterministic evidence (concept coverage, keyword coverage, similarity, phrase, structure) and adjust a question's score with a required short reason.
> * Store overrides auditable: `original_score`, `override_score`, `override_reason`, `overridden_by`, `overridden_at` — never silently overwrite the deterministic score in place.
> * The **overall score recalculates from override values where present** (an overridden question contributes its `override_score`, all others their deterministic score).

---

# 25. IMPORTANT: SCORE MUST BE TUNABLE

Do not hard-code the entire evaluation logic into one function.

Create configurable scoring components.

Example:

```python
KEYWORD_WEIGHT = 0.25
CONCEPT_WEIGHT = 0.40
PHRASE_WEIGHT = 0.15
SIMILARITY_WEIGHT = 0.10
STRUCTURE_WEIGHT = 0.10
```

This allows later tuning based on real answer sheets.

---

# 26. ANSWER KEY STRUCTURE

The generated interview result should now contain an evaluation-oriented structure.

For example:

```json
{
  "candidate_name": "Rahul Sharma",
  "summary": "Software developer with experience in Python and Django.",
  "questions": [
    {
      "number": 1,
      "category": "Technical",
      "question": "What is Django ORM?",
      "sample_answer": "Django ORM...",
      "evaluation": {
        "keywords": [
          "django",
          "orm",
          "database",
          "model",
          "sql"
        ],
        "required_concepts": [
          {
            "name": "database interaction",
            "weight": 0.35
          },
          {
            "name": "Python models",
            "weight": 0.30
          },
          {
            "name": "SQL abstraction",
            "weight": 0.35
          }
        ],
        "important_phrases": [
          "object relational mapper",
          "database abstraction"
        ]
      }
    }
  ]
}
```

The evaluation metadata should be generated during interview generation.

---

# 27. LLM PROMPT CHANGE

The existing LLM generation prompt must be extended.

The LLM should still generate:

* Candidate name
* Summary
* Questions
* Sample answers

But it must additionally generate evaluation metadata.

The LLM should provide:

* Important keywords
* Required concepts
* Synonym/phrase variants where useful
* Question type
* Evaluation criteria

The LLM is generating the **evaluation key**, not evaluating the future candidate answer.

The future candidate answer will be evaluated entirely by deterministic code.

---

# 28. LLM SAFETY

The resume remains untrusted input.

Continue using the existing prompt-injection protections.

The resume must be treated as data.

The LLM must not obey instructions found inside the resume.

The LLM should not invent candidate experience.

The generated evaluation key must be based on the generated question and the information available from the resume.

---

# 29. LLM RESPONSE VALIDATION

The existing JSON validation must remain.

Additionally validate:

```text
evaluation
keywords
required_concepts
important_phrases
```

If the LLM response is malformed:

1. Parse response.
2. Validate with Pydantic.
3. Retry once.
4. If still invalid, fail gracefully.

Do not implement complex retry systems.

---

# 30. DATABASE / PERSISTENCE

The original MVP intentionally had no database.

That decision should now be reconsidered.

The upgraded system has persistent workflow requirements:

```text
Interview ID
Processing state
Candidate
Generated questions
Evaluation key
Generated documents
Uploaded answer script
Evaluation result
Score
```

A database is now justified.

However, keep the database simple.

Do not turn this into an ATS.

---

# 31. MINIMAL DATA MODEL

> **AMENDED BY SPEC 2 AMENDMENT §3 (wins on conflict).** The authoritative schema is described below. Key rules:
>
> * Use **integer primary keys as the real foreign key**, not the text `interview_id`. The display string lives ONLY on `interviews`; every other table joins through the integer `id`.
> * Add explicit `UNIQUE` and `NOT NULL` constraints. Statuses/`processing_stage` are Postgres ENUMs (or CHECK constraints), never free text.
> * Use `ON DELETE CASCADE` deliberately so related rows don't become orphaned.

Authoritative schema:

```sql
interviews (
  id              SERIAL PRIMARY KEY,
  interview_id    TEXT UNIQUE NOT NULL,      -- human-readable, display only
  candidate_name  TEXT,
  status          TEXT NOT NULL,
  processing_stage TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
)

files (
  id              SERIAL PRIMARY KEY,
  interview_id    INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
  file_type       TEXT NOT NULL,   -- resume | question_sheet | answer_key | answer_script
  file_path       TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
)

evaluations (
  id              SERIAL PRIMARY KEY,
  interview_id    INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
  evaluator_version TEXT NOT NULL,
  total_score     NUMERIC,
  max_score       NUMERIC,
  percentage      NUMERIC,
  status          TEXT NOT NULL,
  is_current      BOOLEAN NOT NULL DEFAULT true,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
)

question_evaluations (
  id              SERIAL PRIMARY KEY,
  evaluation_id   INTEGER NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
  question_number INTEGER NOT NULL,
  score           NUMERIC,
  max_score       NUMERIC,
  keyword_score   NUMERIC,
  concept_score   NUMERIC,
  phrase_score    NUMERIC,
  similarity_score NUMERIC,
  structure_score NUMERIC,
  status          TEXT NOT NULL,   -- EVALUATED | NO_ANSWER | OCR_FAILED | UNCERTAIN
  feedback        TEXT
)
```

**Evaluation history, not overwrite:** every re-evaluation run INSERTS a new `evaluations` row (with its own `evaluator_version`); it never updates the previous row's scores in place. Exactly one row per interview has `is_current = true` at any time, flipped in the same transaction that inserts the new row. The dashboard always displays the `is_current` evaluation; past evaluations remain queryable for audit.

**Manual score override** (per amendment §10): store `original_score`, `override_score`, `override_reason`, `overridden_by`, `overridden_at` as an auditable field on `question_evaluations` (or a linked override table). Never overwrite the deterministic score in place.

Do not store unnecessary personal information.

---

# 32. DATABASE TECHNOLOGY

> **AMENDED BY SPEC 2 AMENDMENT §1 (wins on conflict).**

```text
REQUIRED DATABASE: PostgreSQL
```

Reasons (do not relitigate this in implementation):

* Interview ID generation must be collision-safe under concurrent staff uploads ⇒ real transactional guarantees, not read-then-increment logic.
* Multiple staff poll and write simultaneously; SQLite's single-writer behavior is not acceptable for this access pattern.
* The system stores personal candidate data with a multi-day lifecycle; it needs proper constraints, not a file-based DB.

Do not introduce MongoDB. Do not introduce a document store. Relational + Postgres only.

**Do not use SQLite, in any form, for this upgrade.**

Use a standard driver/ORM appropriate to the existing backend (e.g. SQLAlchemy + `asyncpg`/`psycopg`, or the project's existing convention if one already exists). Inspect the repository first — reuse any existing DB access pattern.

### Local Postgres setup

Provide a `docker-compose` service (e.g.):

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: resume
      POSTGRES_PASSWORD: resume
      POSTGRES_DB: resume
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

or clear local setup instructions (e.g. `brew install postgresql` / `apt install postgresql`, `createdb resume`). Configure via `DATABASE_URL` (e.g. `postgresql+asyncpg://resume:resume@localhost:5432/resume`).

---

# 33. JOB PROCESSING

Multiple staff members may upload resumes concurrently.

Example:

```text
Staff A → Resume A
Staff B → Resume B
Staff C → Resume C
Staff D → Resume D
```

All uploads must be accepted without one browser request blocking the others.

However, the heavy processing does not need to happen concurrently.

For the MVP, use a simple job queue.

Conceptually:

```text
                 ┌──────────────┐
Resume A ───────►│              │
Resume B ───────►│     QUEUE    │
Resume C ───────►│              │
Resume D ───────►│              │
                 └──────┬───────┘
                        │
                        ▼
                 Processing Worker
                        │
                        ▼
                     Job A
                        │
                        ▼
                     Job B
                        │
                        ▼
                     Job C
```

---

# 34. IMPORTANT CONCURRENCY REQUIREMENT

Interpret the requirement as:

### Concurrent uploads

Multiple staff members can submit jobs.

### Controlled processing

The heavy resume processing can be performed sequentially:

```text
Job A → processing
Job B → queued
Job C → queued
```

This is intentionally simple.

Do not immediately introduce:

* Celery
* Kafka
* RabbitMQ
* Redis
* Kubernetes
* distributed workers

unless the existing deployment or testing proves they are necessary.

---

# 35. ONE WORKER

> **AMENDED BY SPEC 2 AMENDMENT §4 (wins on conflict).** Job state lives in the database, not memory.

For the MVP, a single processing worker is acceptable.

Example:

```text
Queue
 ↓
Worker
 ↓
Process one job
 ↓
Mark completed
 ↓
Process next job
```

**Explicit requirements from the amendment:**

* Job status is a column on `interviews` (`status`, `processing_stage`) persisted in Postgres — **never** held only in an in-process Python variable, dict, or in-memory queue.
* On application startup, run a **recovery step**: any interview whose status is a non-terminal processing state (e.g. `PROCESSING`, `EXTRACTING`, `GENERATING`, `EVALUATING`) left over from before the restart must be reset to `QUEUED` (for interview generation) or `FAILED` with a clear reason (if it cannot be safely resumed). A stuck row that never resolves is not acceptable.
* Use `SELECT ... FOR UPDATE SKIP LOCKED` (a standard Postgres pattern) if the worker needs to safely claim the next queued job — especially if more than one worker process is ever run. This guarantees no two workers double-process the same interview.

The queue must persist job status sufficiently that the dashboard can show:

```text
Queued
Processing
Completed
Failed
```

---

# 36. PROCESSING STATUS

Use explicit states, enforced as Postgres ENUM types (or CHECK constraints), not free text.

Recommended:

```text
QUEUED
PROCESSING
EXTRACTING
GENERATING
FORMATTING
COMPLETED
FAILED
```

Answer evaluation:

```text
ANSWER_UPLOADED
EVALUATING
EVALUATED
EVALUATION_FAILED
```

Additional answer-per-region statuses produced by the handwriting OCR / segmentation stages:

```text
EVALUATED
NO_ANSWER        (from [BLANK], score 0)
OCR_FAILED       (from [ILLEGIBLE], score N/A)
UNCERTAIN        (manual staff decision required)
SEGMENTATION_UNCERTAIN
```

The exact enum names may follow the existing project conventions.

---

# 37. PROCESSING ROUND UI

The user specifically wants a visual "processing round."

This should be a visual representation of actual stages.

Example:

```text
INT-20260914-002

Processing

✓ Resume uploaded
✓ Resume text extracted
● Generating interview questions
○ Generating documents
○ Finalizing
```

After completion:

```text
✓ Resume uploaded
✓ Resume text extracted
✓ Generating interview questions
✓ Generating documents
✓ Processing complete
```

Do NOT show fake percentages.

Avoid:

```text
73%
84%
91%
```

unless actual measurable progress exists.

---

# 38. FRONTEND POLLING

The React dashboard should update job status automatically.

For the MVP, use polling.

Example:

```text
GET /api/interviews
```

and/or:

```text
GET /api/interviews/{interview_id}/status
```

Poll every reasonable interval, such as:

```text
2–5 seconds
```

Stop polling when the job reaches:

```text
COMPLETED
FAILED
```

Do not introduce WebSockets unless there is a real requirement.

Polling is simpler and sufficient for ~200 interviews.

---

# 39. API DESIGN

> **AMENDED BY SPEC 2 AMENDMENT §5 (wins on conflict).** Authentication is REQUIRED, not optional:
>
> * Add a basic staff login (session or token-based — do not over-engineer; no SSO/OAuth for the MVP, but it must exist).
> * **Every `/api/interviews*` route requires an authenticated staff session.**
> * Document-download routes must check the requesting session is authenticated — not just that the caller supplied a valid `interview_id`. Do not treat `interview_id` as a bearer credential.

Preserve existing endpoints.

Add endpoints as needed.

Recommended:

```http
GET /api/health
```

Existing health endpoint.

---

## Create interview

```http
POST /api/interviews
```

Upload resume. Authenticated staff only.

Response:

```json
{
  "success": true,
  "interview_id": "INT-20260914-001",
  "status": "QUEUED"
}
```

If the existing `/api/generate` endpoint already performs this functionality, evolve it carefully rather than creating unnecessary duplicate endpoints.

---

# 40. LIST INTERVIEWS

```http
GET /api/interviews
```

Authenticated staff only.

Response:

```json
{
  "interviews": [
    {
      "interview_id": "INT-20260914-001",
      "candidate_name": "Rahul Sharma",
      "status": "PROCESSING",
      "processing_stage": "GENERATING",
      "score": null
    }
  ]
}
```

---

# 41. INTERVIEW STATUS

```http
GET /api/interviews/{interview_id}
```

Return:

* Interview ID
* Candidate name
* Status
* Processing stage
* Available documents
* Answer evaluation status
* Score

---

# 42. ANSWER SCRIPT UPLOAD

Authenticated staff only.

Recommended:

```http
POST /api/interviews/{interview_id}/answer-script
```

Input:

```text
multipart/form-data
file
```

The uploaded answer script is a **record file** (see §56) — never auto-deleted by request-cleanup logic.

Response:

```json
{
  "success": true,
  "interview_id": "INT-20260914-001",
  "status": "ANSWER_UPLOADED"
}
```

---

# 43. START EVALUATION

Recommended:

```http
POST /api/interviews/{interview_id}/evaluate
```

This should start deterministic answer evaluation.

Response:

```json
{
  "success": true,
  "interview_id": "INT-20260914-001",
  "status": "EVALUATING"
}
```

Do not make the browser wait unnecessarily for the full evaluation.

---

# 44. EVALUATION RESULT

```http
GET /api/interviews/{interview_id}/evaluation
```

Example:

```json
{
  "interview_id": "INT-20260914-001",
  "total_score": 78,
  "max_score": 100,
  "percentage": 78,
  "questions": [
    {
      "number": 1,
      "score": 8,
      "max_score": 10,
      "status": "EVALUATED"
    }
  ]
}
```

---

# 45. DOCUMENT DOWNLOAD

Reuse existing document endpoints where possible.

The dashboard should expose download buttons for available documents.

Do not create duplicate document generation code.

> **AMENDED BY SPEC 2 AMENDMENT §5 (wins on conflict).** Document-download routes must check the requesting session is authenticated, not simply that the caller supplied a valid `interview_id`. Do not treat `interview_id` as a bearer credential.

---

# 46. ANSWER EVALUATION RESULT UI

The dashboard should display an overall score.

Example:

```text
INTERVIEW RESULT

Candidate:
Rahul Sharma

Interview ID:
INT-20260914-001

Score:

78 / 100

78%
```

Then question-level breakdown:

```text
Question 1
Score: 8/10

Question 2
Score: 7/10

Question 3
Score: 9/10
```

---

# 47. DETAILED EVALUATION

Provide a detailed view.

Example:

```text
Question 1
What is Django ORM?

Score: 8/10

Concept Coverage:
✓ Database interaction
✓ Python models
✓ SQL abstraction

Keyword Coverage:
✓ Django
✓ ORM
✓ database
✓ model

Similarity:
0.81
```

The detailed feedback should be generated from deterministic evidence.

Do not ask an LLM to write feedback.

### Manual score override view

> **AMENDED BY SPEC 2 AMENDMENT §10 (wins on conflict).** From the detailed evaluation view, staff can view the deterministic evidence (concept coverage, keyword coverage, similarity, phrase, structure) and adjust a question's score with a **required short reason**. The override is stored auditable (`original_score`, `override_score`, `override_reason`, `overridden_by`, `overridden_at`) and never overwrites the deterministic score in place. The overall score recalculates from override values where present.

---

# 48. DETERMINISTIC FEEDBACK

Generate simple feedback based on score/evidence.

Examples:

```text
Excellent coverage of the expected concepts.
```

```text
Good answer with most key concepts covered.
```

```text
Partial coverage. Some important concepts are missing.
```

```text
Limited answer. Several expected concepts were not detected.
```

```text
Unable to evaluate because the answer could not be read reliably.
```

Do not fabricate qualitative explanations.

---

# 49. OCR FAILURE VS WRONG ANSWER

These are different states.

Wrong answer:

```text
Answer successfully extracted
Evaluation completed
Score: 2/10
```

OCR failure:

```text
Answer extraction failed
Score: N/A
```

Do not convert extraction failures into zero scores.

---

# 50. PARTIAL ANSWERS

If a candidate answers only part of a question:

```text
Question:
Explain REST APIs and their stateless nature.

Candidate:
REST APIs allow applications to communicate over HTTP.
```

The evaluator should detect:

```text
HTTP/API communication ✓
Statelessness ✗
```

and award partial credit.

---

# 51. EMPTY ANSWER

If the answer region is blank:

```text
Status: No Answer
Score: 0/10
```

This is different from OCR failure.

---

# 52. VERY SHORT ANSWER

If the candidate provides very little text:

```text
Status: Evaluated
```

The scoring system should naturally produce a low score based on concept coverage.

Do not automatically assign zero simply because the answer is short.

---

# 53. VERY LONG ANSWER

Long answers should not automatically receive higher scores.

The system should score based on relevant concept coverage.

Extra irrelevant text should not increase the score significantly.

---

# 54. DOCUMENT GENERATION

Reuse the existing `python-docx` implementation if present.

The system should generate at least:

```text
Interview Question Sheet
Answer Key / Sample Answers
```

The question sheet is for the interviewee.

The answer key is internal.

If the existing application already generates multiple scripts, preserve that behavior and expose the relevant documents through the dashboard.

---

# 55. FILE STORAGE

Temporary processing files should not be publicly accessible.

Use safe generated filenames.

Never directly use user-provided filenames as filesystem paths.

Example:

```text
uuid4().pdf
uuid4().png
```

Associate them with the Interview ID in the database.

---

# 56. CLEANUP

> **AMENDED BY SPEC 2 AMENDMENT §6 (wins on conflict).** Do not let old request-cleanup code silently delete files the dashboard still needs. Separate "scratch" from "record":

* **Scratch files** (raw upload buffer before extraction, intermediate OCR render images): delete immediately after use, as before.
* **Record files** (resume, question sheet, answer key, answer script, generated evaluation report): persist on disk (or object storage) with the path stored in the `files` table, and **never auto-deleted by request-cleanup logic**.

Do not delete a file that the dashboard is expected to download.

Add an explicit, **separate retention job** (e.g. a daily scheduled task) that purges record files and their DB rows after a defined retention period post-evaluation, configurable via env var (e.g. `RETENTION_DAYS=30`). This is a deliberate, **logged, scheduled** operation — not a side effect of request handling.

---

# 57. SECURITY

Continue enforcing:

* Backend-only API keys
* File type validation
* MIME validation
* File size limits
* Safe filenames
* No public upload directory
* No stack traces in frontend
* No API keys in frontend
* Minimal logging

---

# 58. PRIVACY

Resumes and answer scripts contain personal information.

Do not log:

* Full resume contents
* Full handwritten answer contents
* Phone numbers
* Email addresses
* Candidate personal information unnecessarily
* Full generated answer content

Log only operational metadata.

Example:

```text
Interview ID
File size
File type
Processing stage
Processing duration
Success/failure
```

---

# 59. LOGGING

Useful logs:

```text
Interview created: INT-...
Resume extraction started
Resume extraction completed
Resume character count
LLM generation started
LLM generation completed
Document generation completed
Answer script uploaded
Answer OCR started
Answer evaluation started
Answer evaluation completed
Processing duration
```

Do not log sensitive content.

---

# 60. ERROR HANDLING

Expected errors:

```text
Invalid file
File too large
Unreadable PDF
OCR failure
Insufficient resume text
LLM failure
LLM timeout
Malformed LLM response
Answer script OCR failure
Answer segmentation failure
Evaluation failure
Document generation failure
```

Return user-friendly messages.

Do not expose stack traces.

---

# 61. ANSWER EVALUATION ERROR EXAMPLE

Instead of:

```text
IndexError: list index out of range
```

show:

```text
We could not reliably read the answer script. Please upload a clearer scan.
```

---

# 62. FRONTEND ARCHITECTURE

The React frontend already exists.

Do not migrate again.

Inspect the current components and follow existing conventions.

The upgrade should add reusable components such as:

```text
Dashboard
InterviewCard
InterviewStatus
ProcessingStages
DocumentActions
AnswerScriptUpload
EvaluationSummary
QuestionEvaluation
```

Use the existing routing/state-management approach if one already exists.

Do not introduce Redux or another state-management library unless the current application genuinely requires it.

---

# 63. DASHBOARD UX

The dashboard should be optimized for staff operations.

Primary workflow:

```text
Open Dashboard
      ↓
See Interview IDs
      ↓
See Processing Status
      ↓
Download Completed Scripts
      ↓
Conduct Interview
      ↓
Upload Answer Script
      ↓
Evaluate
      ↓
View Score
```

The workflow should be obvious without requiring technical knowledge.

---

# 64. PROCESSING TABLE/CARDS

Recommended columns:

```text
Interview ID
Candidate
Created
Status
Stage
Documents
Answer Script
Evaluation
Score
```

Use visual status indicators:

```text
Queued
Processing
Completed
Failed
Evaluating
Evaluated
```

Do not rely only on color; include text.

---

# 65. CONCURRENT STAFF WORKFLOW

Example:

```text
Staff A uploads Resume A
→ INT-001
→ QUEUED

Staff B uploads Resume B
→ INT-002
→ QUEUED

Staff C uploads Resume C
→ INT-003
→ QUEUED
```

Dashboard:

```text
INT-001   Processing
INT-002   Queued
INT-003   Queued
```

Worker:

```text
INT-001 → complete
INT-002 → processing
INT-003 → queued
```

All staff can continue using the dashboard.

---

# 66. JOB IDENTITY

Never associate a job based only on:

```text
filename
```

Always use:

```text
interview_id
```

The uploaded answer script must explicitly belong to:

```text
/interviews/{interview_id}/answer-script
```

or equivalent backend logic.

---

# 67. DUPLICATE SUBMISSIONS

> **AMENDED BY SPEC 2 AMENDMENT §11 (wins on conflict).** With async processing, the upload request returns immediately, so duplicate-submission protection can no longer rely on disabling a button for the duration of one in-flight HTTP request. Protection must be **keyed off server-side interview state** — e.g. disable "Generate" if an interview with the same source resume / staff session is already `QUEUED` or `PROCESSING` — not a client-side flag that a page refresh clears.

The UI must prevent accidental repeated submissions.

During resume generation:

```text
Generate button disabled (while a QUEUED/PROCESSING job exists for the same source/staff)
```

During answer evaluation:

```text
Evaluate button disabled (while the answer set is EVALUATING or already EVALUATED for the current key)
```

Backend should also protect against duplicate processing.

Frontend-only protection is insufficient.

---

# 68. RE-EVALUATION

The system should allow staff to re-run deterministic evaluation if necessary.

Because evaluation is deterministic, re-evaluation should produce the same result unless:

* Evaluation rules changed
* Answer key changed
* OCR output changed

> **AMENDED BY SPEC 2 AMENDMENT §3.2 (wins on conflict).** Re-evaluation **INSERTs a new `evaluations` row** (with its own `evaluator_version`); it does NOT update the previous row's scores in place. The new row becomes `is_current = true` in the same transaction. Past evaluations remain queryable for audit.

Do not call an LLM.

---

# 69. EVALUATION VERSIONING

Consider storing a simple evaluator version:

```text
evaluator_version: "1.0"
```

This is useful because scoring rules may be tuned later.

If scoring weights change, you can identify which evaluation version produced a score.

Store `evaluator_version` on the `evaluations` table (amendment §3 schema) so each historical evaluation records the exact engine that produced it.

Do not build a complicated version-management system.

---

# 70. TESTING THE EVALUATOR

This is one of the most important parts of the upgrade.

Create test cases for:

### Exact answer

Expected:

```text
High score
```

### Paraphrased answer

Expected:

```text
High score
```

### Partial answer

Expected:

```text
Medium score
```

### Wrong answer

Expected:

```text
Low score
```

### Empty answer

Expected:

```text
0
```

### Irrelevant answer

Expected:

```text
Low score
```

### Correct answer with different wording

Expected:

```text
High score
```

### OCR failure

Expected:

```text
N/A / extraction failure
```

### Technical synonym

Expected:

```text
Correctly recognized
```

---

# 71. TEST DATA

Create a deterministic test dataset.

For example:

```text
Question:
What is Django ORM?

Expected concepts:
- database interaction
- models
- SQL abstraction

Answer A:
Django ORM allows Python models to interact with database records.

Expected:
High score

Answer B:
Django is a Python web framework.

Expected:
Low/medium score

Answer C:
I like Django because it is fast.

Expected:
Low score

Answer D:
Django ORM provides an abstraction over SQL and allows developers
to work with database records through Python models.

Expected:
Very high score
```

---

# 72. DO NOT OPTIMIZE BASED ON ONE TEST

The evaluator should be tested against multiple examples.

Aim for:

```text
20–50 manually evaluated answers
```

before deciding that the scoring algorithm is good.

Compare:

```text
Human-assigned score
vs
System score
```

Tune weights accordingly.

---

# 73. EVALUATION QUALITY TARGET

The goal is not mathematical perfection.

The goal is:

```text
Consistent
Explainable
Deterministic
Reasonably accurate
Fast
Cheap
```

For this internal MVP, an explainable deterministic system is preferable to a mysterious AI score.

---

# 74. PERFORMANCE

Expected workload:

```text
~200 candidates
Monday + Tuesday
```

Likely low/moderate concurrency.

The application does not need infrastructure for thousands of simultaneous users.

Answer evaluation should be lightweight and fast once OCR is complete.

---

# 75. DO NOT INTRODUCE UNNECESSARY INFRASTRUCTURE

Do NOT add unless proven necessary:

```text
Kubernetes
Kafka
RabbitMQ
Celery
Redis
Microservices
Vector database
Embedding service
LLM evaluator
WebSocket infrastructure
Complex distributed workers
```

Keep the system understandable.

---

# 76. RECOMMENDED ARCHITECTURE

The upgraded system should conceptually become:

```text
                         React
                           │
                           ▼
                        FastAPI
                           │
            ┌──────────────┼───────────────┐
            │              │               │
            ▼              ▼               ▼
       Interview API    Dashboard       Documents
            │
            ▼
        Job Queue
            │
            ▼
     Processing Worker
            │
       ┌────┴─────┐
       ▼          ▼
   Extraction     LLM
       │          │
       └────┬─────┘
            ▼
       Evaluation Key
            │
            ▼
       Question Sheet
            │
            ▼
       Interviewee
            │
            ▼
      Written Answers
            │
            ▼
      Answer Upload
            │
            ▼
        OCR / Text
            │
            ▼
   Deterministic Evaluator
            │
       ┌────┴──────────┐
       ▼               ▼
 Question Scores    Overall Score
       │               │
       └──────┬────────┘
              ▼
          Dashboard
```

---

# 77. FOLDER STRUCTURE

Do not blindly replace the current project structure.

Adapt the existing structure.

A reasonable target structure could be:

```text
app/
├── main.py
│
├── api/
│   ├── routes.py
│   ├── interview_routes.py
│   ├── dashboard_routes.py
│   └── evaluation_routes.py
│
├── services/
│   ├── pdf_extractor.py
│   ├── ocr_service.py
│   ├── text_cleaner.py
│   ├── llm_service.py
│   ├── question_generator.py
│   ├── document_generator.py
│   ├── interview_service.py
│   ├── job_service.py
│   ├── answer_extractor.py
│   ├── answer_segmenter.py
│   ├── answer_evaluator.py
│   ├── scoring_service.py
│   └── evaluation_key_service.py
│
├── models/
│   ├── schemas.py
│   ├── interview.py
│   ├── evaluation.py
│   └── question_evaluation.py
│
├── prompts/
│   └── interview_prompt.py
│
├── utils/
│   ├── file_validation.py
│   ├── text_utils.py
│   └── helpers.py
│
└── ...
```

Frontend:

```text
frontend/
└── src/
    ├── components/
    │   ├── Dashboard.jsx
    │   ├── InterviewCard.jsx
    │   ├── ProcessingStages.jsx
    │   ├── DocumentActions.jsx
    │   ├── AnswerUpload.jsx
    │   ├── EvaluationSummary.jsx
    │   └── QuestionEvaluation.jsx
    │
    ├── pages/
    │   ├── Home.jsx
    │   └── DashboardPage.jsx
    │
    ├── services/
    │   └── api.js
    │
    └── ...
```

Use the actual project's conventions instead of forcing this exact structure.

---

# 78. ENVIRONMENT VARIABLES

Preserve existing environment variables.

Add configuration where required.

Possible:

```env
MAX_FILE_SIZE_MB=4
MAX_RESUME_CHARACTERS=50000
LLM_TIMEOUT_SECONDS=60

# Database (amendment §1 — PostgreSQL required)
DATABASE_URL=postgresql+asyncpg://resume:resume@localhost:5432/resume

# Staff auth (amendment §5)
STAFF_USERNAME=staff
STAFF_PASSWORD_HASH=<argon2/bcrypt hash, not plaintext>
SESSION_SECRET=

# Record-file retention (amendment §6)
RETENTION_DAYS=30

KEYWORD_WEIGHT=0.25
CONCEPT_WEIGHT=0.40
PHRASE_WEIGHT=0.15
SIMILARITY_WEIGHT=0.10
STRUCTURE_WEIGHT=0.10

JOB_POLL_INTERVAL_SECONDS=3
```

Do not expose secrets to React.

---

# 79. DEPLOYMENT

The system should remain deployable as a simple application.

Preferred:

```text
React
   ↓
FastAPI
   ↓
PostgreSQL          (amendment §1 — required, via docker-compose or local service)
   ↓
OCR
   ↓
LLM API
```

A single server is sufficient for the expected workload unless actual testing proves otherwise.

---

# 80. IMPORTANT DATABASE DECISION

The original MVP's "no database" rule is no longer mandatory.

The upgraded application has persistent workflow state.

Therefore:

```text
No database
```

should NOT be treated as an immutable requirement.

However:

```text
No unnecessary database complexity
```

remains a requirement.

Use the smallest reliable persistence layer compatible with the existing deployment.

> **AMENDED BY SPEC 2 AMENDMENT §1 (wins on conflict).** The smallest reliable persistence layer is **PostgreSQL** (mandatory). "No database" and any SQLite allowance are overridden.

---

# 81. UI DESIGN

Preserve the current React UI style.

The dashboard should feel like part of the existing application.

Do not redesign the entire website.

Add:

* Dashboard button
* Dashboard page
* Interview cards/table
* Processing status
* Document actions
* Answer upload
* Evaluation results

Maintain:

* Existing typography
* Existing spacing
* Existing colors
* Existing branding
* Existing responsive behavior

unless there is a clear usability reason to change them.

---

# 82. PROCESSING VISUAL

Use actual stages.

Example:

```text
Resume Processing

✓ Upload
✓ Extraction
● Question Generation
○ Document Generation
○ Complete
```

For answer evaluation:

```text
Answer Evaluation

✓ Answer uploaded
✓ OCR extraction
● Evaluating answers
○ Calculating score
```

Then:

```text
✓ Evaluation complete
```

---

# 83. MOBILE

The primary use case is desktop staff usage.

Still ensure the dashboard is usable on:

* Desktop
* Laptop
* Tablet
* Mobile

Do not over-engineer mobile UI.

---

# 84. SECURITY OF DOCUMENT DOWNLOADS

> **AMENDED BY SPEC 2 AMENDMENT §5 (wins on conflict).** Download routes require an authenticated staff session. Authorization is NOT satisfied by merely supplying a valid `interview_id` — the requesting session must be authenticated, and downloads must be scoped to the authenticated staff member / authorized set of interviews.

Generated documents should not be publicly exposed.

Downloads should be served through backend routes that validate the Interview ID/file association.

Do not allow:

```text
/download?filename=../../etc/passwd
```

or equivalent path traversal.

Never construct paths directly from untrusted user input.

---

# 85. API ERROR RESPONSES

Use a consistent structure.

Example:

```json
{
  "success": false,
  "error": {
    "code": "ANSWER_OCR_FAILED",
    "message": "We could not reliably read the uploaded answer script."
  }
}
```

Frontend should display `message`.

Internal debugging details should remain in server logs.

---

# 86. ACCEPTANCE CRITERIA

The upgrade is complete when:

## Interview Generation

* [ ] Existing resume upload still works
* [ ] Existing PDF extraction still works
* [ ] Existing OCR still works
* [ ] Existing LLM generation still works
* [ ] Interview ID is automatically generated
* [ ] Questions are generated
* [ ] Sample answers are generated
* [ ] Evaluation metadata is generated
* [ ] Question sheet is generated
* [ ] Answer key is generated

## Dashboard

* [ ] Dashboard button exists
* [ ] Dashboard opens successfully
* [ ] Interviews are listed
* [ ] Interview IDs are visible
* [ ] Candidate names are visible
* [ ] Processing status is visible
* [ ] Processing stage is visible
* [ ] Completed documents have download buttons

## Processing

* [ ] Multiple staff can submit uploads
* [ ] Uploads receive unique IDs
* [ ] Jobs enter queue
* [ ] Worker processes jobs
* [ ] Dashboard shows queued jobs
* [ ] Dashboard shows processing jobs
* [ ] Dashboard shows completed jobs
* [ ] Dashboard shows failed jobs
* [ ] No fake progress percentage is shown
* [ ] Actual processing stages are displayed

## Answer Upload

* [ ] Answer script can be uploaded
* [ ] Answer script is associated with Interview ID
* [ ] PDF/image answer sheets are supported
* [ ] OCR is triggered where necessary
* [ ] OCR failure is detected
* [ ] Empty answers are detected
* [ ] Answer regions are associated with questions

## Answer Evaluation

* [ ] No LLM is used
* [ ] Text is normalized
* [ ] Keywords are matched
* [ ] Synonym/concept groups are supported
* [ ] Important phrases are matched
* [ ] TF-IDF/BM25 similarity is supported
* [ ] Required concepts are evaluated
* [ ] Question-specific rules are supported
* [ ] Partial answers receive partial credit
* [ ] Wrong answers receive low scores
* [ ] Empty answers receive zero
* [ ] OCR failures do not automatically receive zero
* [ ] Scores are deterministic
* [ ] Evaluation weights are configurable

## Results

* [ ] Overall score is shown
* [ ] Percentage is shown
* [ ] Question-level scores are shown
* [ ] Evaluation evidence is shown
* [ ] Evaluation status is shown
* [ ] Staff can inspect detailed results

## Amendment acceptance criteria (SPEC 2 AMENDMENT §13)

* [ ] Postgres is the database, with proper FK/UNIQUE/CHECK constraints enforced at the schema level
* [ ] Interview ID generation is verified race-free under concurrent load (test with simultaneous submissions)
* [ ] A crashed/restarted worker correctly recovers stuck interviews on startup, verified by test
* [ ] Staff authentication is required on every interview/document/evaluation route
* [ ] OCR output explicitly distinguishes blank vs. illegible vs. transcribed text
* [ ] Segmentation mismatches surface a manual-correction UI rather than guessing
* [ ] Re-evaluation creates a new evaluation record and preserves history
* [ ] Staff can override an individual question score with a logged reason
* [ ] A defined, scheduled retention/purge job exists for record files and rows past the retention window

---

# 87. IMPORTANT IMPLEMENTATION ORDER

Do not attempt to build everything simultaneously.

Implement in this order:

> **AMENDMENT MAPPING (SPEC 2 AMENDMENT):** the phases below remain, but carry the amendment's mandates with them:
>
> * Phase 2 (Data model) → Postgres schema of amendment §3, ENUMs/CHECK constraints, FK + UNIQUE + NOT NULL + CASCADE; evaluation history with `is_current`.
> * Phase 3 (Interview ID) → race-free generation of amendment §2 (INSERT → derive `INT-YYYYMMDD-NNN` → UPDATE in one transaction; UNIQUE constraint on `interview_id`; never client-generated).
> * Phase 4 (Evaluation key) → concept-weight normalization per amendment §9.
> * Phase 5 (Evaluator) → shared reference corpus for TF-IDF/BM25 per amendment §9; per-question manual score override per §10.
> * Phase 6 (Answer OCR) → handwriting OCR with `[BLANK]`/`[ILLEGIBLE]`/transcribed per §7; segmentation uncertainty + manual-correction UI per §8.
> * Phase 8 (Job queue) → DB-backed state + startup recovery + `FOR UPDATE SKIP LOCKED` per §4.
> * New: Phase for staff auth (amendment §5) — required before any interview route ships.
> * New: Phase for file lifecycle/retention (amendment §6) — scratch vs record + `RETENTION_DAYS` job.

## Phase 1 — Repository audit

Inspect existing code.

Understand:

```text
Frontend
Backend
APIs
Models
Storage
LLM
OCR
Documents
```

Do not modify code yet unless necessary.

---

## Phase 2 — Data model

Implement:

```text
Interview
Job Status
Processing Stage
Evaluation
Question Evaluation
File references
```

---

## Phase 3 — Interview ID

Add:

```text
INT-YYYYMMDD-NNN
```

and associate all interview resources with it.

---

## Phase 4 — Evaluation key

Modify the LLM generation output to include:

```text
keywords
concepts
phrases
question type
```

Validate the schema.

---

## Phase 5 — Deterministic evaluator

Build and unit test:

```text
normalization
keyword matching
concept matching
phrase matching
TF-IDF/BM25
scoring
```

Do this before building the full dashboard.

---

## Phase 6 — Answer OCR

Reuse the existing OCR infrastructure.

Implement:

```text
answer extraction
answer segmentation
```

---

## Phase 7 — Evaluation API

Implement:

```text
answer upload
evaluation
result retrieval
```

---

## Phase 8 — Job queue

Implement:

```text
QUEUED
PROCESSING
COMPLETED
FAILED
```

with one worker.

---

## Phase 9 — Dashboard backend

Implement interview listing and status APIs.

---

## Phase 10 — React dashboard

Build:

```text
Dashboard
Interview Cards/Table
Processing Stages
Document Downloads
Answer Upload
Evaluation Results
```

---

## Phase 11 — Polling

Automatically refresh dashboard state.

---

## Phase 12 — End-to-end testing

Test complete lifecycle:

```text
Resume
 ↓
Interview ID
 ↓
Processing
 ↓
Question Sheet
 ↓
Manual Answer
 ↓
Answer Upload
 ↓
OCR
 ↓
Evaluation
 ↓
Score
 ↓
Dashboard
```

---

# 88. DO NOT DO THESE THINGS

Do not:

* Rebuild the existing application from scratch.
* Replace the existing React migration.
* Introduce an LLM into answer evaluation.
* Use embeddings unnecessarily.
* Build RAG.
* Build an AI agent.
* Add candidate authentication.
* Build an ATS.
* Build candidate ranking.
* Add voice/video interviews.
* Add payment systems.
* Add Kubernetes.
* Add Kafka.
* Add complex distributed infrastructure.
* Create fake progress percentages.
* Store full resume text in logs.
* Expose API keys.
* Use filename as interview identity.
* Treat OCR failure as a wrong answer.
* Give high scores purely because many keywords occur.
* Require exact answer wording.
* Generate evaluation feedback with an LLM.

**Additions from SPEC 2 AMENDMENT §12 (authoritative):**

* Use SQLite, in any form, for this upgrade.
* Generate interview IDs by reading-then-incrementing outside a transaction.
* Store the text `interview_id` as a foreign key anywhere other than the `interviews` table itself.
* Overwrite a previous evaluation's row when re-evaluating.
* Ship any staff-facing API route without an authentication check.
* Infer OCR failure vs. blank answer from character count alone.
* Treat "concept coverage" as semantically equivalent to true meaning-based matching — it is lexical matching with a different label, and staff-facing UI/communication should not overstate it.
* Delete a "record" file (resume, question sheet, answer key, answer script) as a side effect of normal request processing.

---

# 89. CRITICAL DESIGN PRINCIPLE FOR ANSWER CHECKING

The evaluator must answer:

> "Did the candidate demonstrate the important concepts required to answer this question?"

It must NOT answer:

> "How similar are these two strings?"

Text similarity is only one signal.

The primary signal should be concept coverage.

---

# 90. CRITICAL DESIGN PRINCIPLE FOR SCALABILITY

The requirement is approximately:

```text
200 candidates
```

not:

```text
200 simultaneous LLM requests
```

Therefore:

```text
Concurrent uploads
+
Queued processing
+
Single worker
```

is acceptable for the initial upgraded version.

If actual testing shows the worker becomes a bottleneck, optimize later.

---

# 91. CRITICAL DESIGN PRINCIPLE FOR EXPLAINABILITY

Every score should be explainable.

Example:

```text
Question 5
Score: 7.5 / 10

Concept coverage: 80%
Keyword coverage: 70%
Phrase matching: 60%
Similarity: 78%
Structure: 80%
```

This allows staff to understand why a candidate received a score.

Do not produce an unexplained:

```text
Score: 78
```

---

# 92. FINAL TARGET SYSTEM

The completed upgrade should provide:

```text
                 STAFF
                   │
                   ▼
              React App
                   │
          ┌────────┴────────┐
          │                 │
          ▼                 ▼
      Resume Upload      Dashboard
          │                 │
          ▼                 │
    Interview ID            │
          │                 │
          ▼                 │
        Queue               │
          │                 │
          ▼                 │
     Processing Worker      │
          │                 │
     ┌────┴────┐            │
     ▼         ▼            │
  Extract     LLM           │
     │         │            │
     └────┬────┘            │
          ▼                 │
     Evaluation Key         │
          │                 │
          ▼                 │
    Question Sheet          │
          │                 │
          ▼                 │
      Interviewee           │
          │                 │
      Writes Answers        │
          │                 │
          ▼                 │
    Answer Script           │
          │                 │
          ▼                 │
       Upload ──────────────┘
          │
          ▼
         OCR
          │
          ▼
    Answer Segmentation
          │
          ▼
 Deterministic Evaluator
          │
    ┌─────┴──────┐
    ▼            ▼
Question Scores  Overall Score
    │            │
    └──────┬─────┘
           ▼
       Dashboard
```

---

# 93. FINAL SUCCESS CRITERIA

The upgraded platform is successful if a staff member can:

```text
1. Upload a candidate resume.
2. Receive a unique Interview ID.
3. See the interview in the dashboard.
4. See its processing status.
5. Wait while it moves through real processing stages.
6. Download the generated interview question sheet.
7. Download the internal answer key.
8. Give the question sheet to the interviewee.
9. Receive the handwritten answer sheet.
10. Upload the answer sheet against the Interview ID.
11. Let the system OCR the answers.
12. Let the deterministic evaluator assess them.
13. Receive a score without any LLM call.
14. View question-level scoring.
15. View the overall score.
16. Process multiple staff submissions through the queue.
```

The system should remain:

```text
Simple
Fast
Deterministic where possible
Explainable
Low cost
Maintainable
Easy to deploy
```

The most important new technical component is the:

```text
DETERMINISTIC ANSWER EVALUATION ENGINE
```

Build and validate that carefully before adding unnecessary infrastructure.

# END OF CONTEXT

---

# APPENDIX A — SPEC 2 AMENDMENT (AUTHORITATIVE ON CONFLICT)

> This appendix is the verbatim "SPEC 2 AMENDMENT — DATABASE, DATA INTEGRITY & CONCURRENCY FIXES". It amends this context during the **same** implementation pass. Where it conflicts with the content above, **this appendix wins**. All amendment callouts throughout this document reference sections below.

## 0. PURPOSE OF THIS AMENDMENT

This document amends the "RESUME INTERVIEW PLATFORM — UPGRADE MASTER CONTEXT" spec.

Do NOT treat this as a new project. Treat it as corrections layered on top of the existing upgrade spec, applied during the same implementation pass.

Where this amendment conflicts with the original upgrade spec, THIS AMENDMENT WINS.

Read both documents fully before writing any code.

---

## 1. DATABASE ENGINE — MANDATORY CHANGE

The original spec allowed "SQLite for a single-server MVP." This is now overridden.

```text
REQUIRED DATABASE: PostgreSQL
```

Reasons (do not relitigate this in implementation):

* Interview ID generation must be collision-safe under concurrent staff uploads. This requires real transactional guarantees, not read-then-increment logic.
* Multiple staff will be polling and writing simultaneously. SQLite's single-writer behavior is not acceptable for this access pattern.
* This system now stores personal candidate data with a multi-day lifecycle. It needs proper constraints, not a file-based DB.

Do not introduce MongoDB. Do not introduce a document store. Relational + Postgres only.

Use a standard driver/ORM appropriate to the existing backend (e.g. SQLAlchemy + `asyncpg`/`psycopg`, or the project's existing convention if one already exists). Inspect the repository first — if any DB access pattern already exists, follow it.

Provide a `docker-compose` service or clear local setup instructions for Postgres, since the original deployment had no database at all.

---

## 2. INTERVIEW ID GENERATION — MUST BE RACE-FREE

Do not generate `INT-YYYYMMDD-NNN` by reading the last row and incrementing in application code. Under concurrent uploads (which this system explicitly supports), that pattern will produce duplicate or skipped IDs.

Required approach:

```text
1. INSERT the interview row first, letting Postgres assign a real
   auto-incrementing primary key (SERIAL / IDENTITY).
2. Derive the human-readable interview_id from that primary key
   inside the same transaction, e.g.:
   INT-{created_date:YYYYMMDD}-{id:03d}
3. UPDATE the row with the derived interview_id in the same
   transaction before committing.
```

Alternative acceptable approach: a Postgres sequence per day combined with a unique constraint + retry-on-conflict loop. Either way, uniqueness must be enforced at the database level with a UNIQUE constraint on `interview_id` — never assumed safe purely because application code "checked first."

Never generate or accept an interview ID from the client.

---

## 3. SCHEMA — CLEAN RECORD DESIGN

Replace the schema sketch in the original spec with the following principles. This is not optional polish — it is required for data integrity.

### 3.1 Use integer primary keys as the real foreign key, not the text ID

```sql
interviews (
  id              SERIAL PRIMARY KEY,
  interview_id    TEXT UNIQUE NOT NULL,      -- human-readable, display only
  candidate_name  TEXT,
  status          TEXT NOT NULL,
  processing_stage TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
)

files (
  id              SERIAL PRIMARY KEY,
  interview_id    INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
  file_type       TEXT NOT NULL,   -- resume | question_sheet | answer_key | answer_script
  file_path       TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
)

evaluations (
  id              SERIAL PRIMARY KEY,
  interview_id    INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
  evaluator_version TEXT NOT NULL,
  total_score     NUMERIC,
  max_score       NUMERIC,
  percentage      NUMERIC,
  status          TEXT NOT NULL,
  is_current      BOOLEAN NOT NULL DEFAULT true,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
)

question_evaluations (
  id              SERIAL PRIMARY KEY,
  evaluation_id   INTEGER NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
  question_number INTEGER NOT NULL,
  score           NUMERIC,
  max_score       NUMERIC,
  keyword_score   NUMERIC,
  concept_score   NUMERIC,
  phrase_score    NUMERIC,
  similarity_score NUMERIC,
  structure_score NUMERIC,
  status          TEXT NOT NULL,   -- EVALUATED | NO_ANSWER | OCR_FAILED | UNCERTAIN
  feedback        TEXT
)
```

Rules:

* `interview_id` (the display string) lives ONLY on the `interviews` table. Every other table joins through the integer `id`. Never duplicate the text ID as a join key elsewhere.
* Add explicit `UNIQUE` and `NOT NULL` constraints wherever the original spec implied one informally — do not leave integrity enforcement to application code alone.
* Use `ON DELETE CASCADE` deliberately so an interview's related rows don't become orphaned if a record is ever removed.

### 3.2 Evaluation history, not overwrite

The original spec mentions `evaluator_version` and "re-evaluation" but never says what happens to the previous evaluation. Fix this:

* Every re-evaluation run INSERTS a new row into `evaluations` (with its own `evaluator_version`), it does NOT update the previous row's scores in place.
* Exactly one evaluation row per interview has `is_current = true` at any time. Flipping that flag happens in the same transaction that inserts the new evaluation row.
* The dashboard always displays the `is_current` evaluation, but past evaluations remain queryable for audit purposes.

### 3.3 Status values are enums, not free text

Define `status` and `processing_stage` as Postgres `ENUM` types (or CHECK constraints), not arbitrary strings. This prevents a typo in application code from silently producing an interview stuck in an unrecognized state that the dashboard can't render.

---

## 4. JOB PROCESSING — STATE LIVES IN THE DATABASE, NOT IN MEMORY

The original spec's "one worker" description is ambiguous about implementation. Make this explicit:

* Job status is a column on `interviews` (`status`, `processing_stage`), persisted in Postgres — never held only in an in-process Python variable, dict, or in-memory queue.
* On application startup, run a recovery step: any interview whose status is a non-terminal processing state (e.g. `PROCESSING`, `EXTRACTING`, `GENERATING`, `EVALUATING`) left over from before the restart must be reset to `QUEUED` (for interview generation) or `FAILED` with a clear reason (if it cannot be safely resumed). A stuck row that never resolves is not acceptable.
* Use `SELECT ... FOR UPDATE SKIP LOCKED` (a standard Postgres pattern) if you need the worker to safely claim the next queued job, especially if you ever run more than one worker process. This guarantees no two workers double-process the same interview.

---

## 5. AUTHENTICATION — REQUIRED, NOT OPTIONAL

The original spec has no authentication anywhere, despite being a multi-staff system handling personal candidate data and internal-only answer keys, with sequential, guessable interview IDs.

Add:

* A basic staff login (session or token-based — do not over-engineer, this does not need SSO/OAuth for the MVP, but it must exist).
* Every `/api/interviews*` route requires an authenticated staff session.
* Document download routes must check the requesting session is authenticated, not just that the caller supplied a valid `interview_id`. Do not treat `interview_id` as a bearer credential.

---

## 6. FILE LIFECYCLE — SEPARATE "SCRATCH" FROM "RECORD"

The original MVP deleted all temp files after each request. This upgrade needs the opposite for lifecycle files. Do not let old cleanup code silently delete files the dashboard still needs.

* **Scratch files** (raw upload buffer before extraction, intermediate OCR render images): delete immediately after use, as before.
* **Record files** (resume, question sheet, answer key, answer script, generated evaluation report): persist on disk (or object storage) with the path stored in the `files` table, and never auto-deleted by request-cleanup logic.
* Add an explicit, separate retention job (e.g. a daily task) that purges record files and their DB rows after a defined retention period post-evaluation (recommend configurable via env var, e.g. `RETENTION_DAYS=30`). This must be a deliberate, logged, scheduled operation — not a side effect of request handling.

---

## 7. OCR FOR HANDWRITING — DO NOT REUSE THE RESUME PROMPT VERBATIM

Reuse the `ocr_service.py` module/abstraction, but add a distinct system instruction for answer-sheet OCR. The resume OCR prompt is tuned for printed text and technical vocabulary; handwriting recognition needs different guidance.

The handwriting OCR prompt must explicitly instruct the model to output one of three states per answer region, not just raw text:

```text
[BLANK]       - no handwriting detected in the region
[ILLEGIBLE]   - handwriting present but not confidently readable
<transcribed text> - normal case
```

This distinction must come from the OCR step itself, not be inferred later from character count. Downstream evaluation logic branches on this exact signal to correctly separate "No Answer" (score 0) from "OCR failure" (score N/A) per the original spec's own Section 49–52 requirement — which cannot be honestly satisfied without this.

---

## 8. ANSWER SEGMENTATION — MANUAL OVERRIDE REQUIRED

Marker-based segmentation (`QUESTION 1` / `ANSWER 1`) will fail whenever a candidate writes past the allotted space, skips a question, or uses a spare sheet. Add:

* A concrete check: if the number of detected question markers does not match the expected question count for that interview, mark the whole answer set `SEGMENTATION_UNCERTAIN` rather than guessing.
* A manual-correction view in the dashboard where staff can view the raw OCR'd text blocks for an uncertain interview and manually assign each block to the correct question number before evaluation runs. This does not exist anywhere in the original spec and must be added — the deterministic evaluator's accuracy depends on segmentation being correct first.

---

## 9. SCORING ENGINE — TWO CORRECTIONS

* **TF-IDF/BM25 corpus size**: a 2-document corpus (sample answer vs. candidate answer) makes IDF weighting degenerate. Build a shared reference corpus once at generation time from all sample answers and concept/phrase text for that interview's question set, and compute similarity against that. Do not compute IDF from just the single question pair.
* **LLM-generated concept weights**: do not hard-fail validation if a question's concept weights don't sum exactly to 1.0 — LLMs are unreliable at exact arithmetic. Normalize weights server-side (divide each by their sum) after parsing, and only fail validation if weights are missing or non-numeric.

---

## 10. MANUAL SCORE OVERRIDE — ADD THIS CAPABILITY

Without embeddings or an LLM, "concept coverage" reduces to lexical/synonym matching and will systematically under-score correct paraphrased answers that don't hit predefined vocabulary. This is a known ceiling, not a bug to eliminate — compensate for it operationally:

* Add a `score_override` capability at the question level: staff can view the deterministic evidence (concept coverage, keyword coverage, similarity) and adjust a question's score with a required short reason.
* Store overrides as their own auditable field (`original_score`, `override_score`, `override_reason`, `overridden_by`, `overridden_at`) — never silently overwrite the deterministic score in place.
* The overall score recalculates from override values where present.

---

## 11. ASYNC PROCESSING — FRONTEND IMPACT IS LARGER THAN THE ORIGINAL SPEC IMPLIES

The original spec says "don't redesign the UI, just add a dashboard." Correct this expectation:

* The existing upload flow is synchronous (auto-submit → wait → render, with a stepper driven by real elapsed time). Moving to `QUEUED → PROCESSING → COMPLETED` requires reworking that flow to poll and reflect state that can now span minutes, not just the addition of a separate dashboard page.
* Duplicate-submission protection can no longer rely on disabling a button for the duration of one in-flight HTTP request, since the request now returns immediately. Protection must be keyed off server-side interview state (e.g. disable "Generate" if an interview with the same source resume/staff session is already `QUEUED` or `PROCESSING`), not a client-side flag that a page refresh clears.

---

## 12. WHAT NOT TO DO (ADDITIONS TO THE ORIGINAL SPEC'S LIST)

In addition to the original spec's "do not" list, also do not:

* Use SQLite, in any form, for this upgrade.
* Generate interview IDs by reading-then-incrementing outside a transaction.
* Store the text `interview_id` as a foreign key anywhere other than the `interviews` table itself.
* Overwrite a previous evaluation's row when re-evaluating.
* Ship any staff-facing API route without an authentication check.
* Infer OCR failure vs. blank answer from character count alone.
* Treat "concept coverage" as semantically equivalent to true meaning-based matching — it is lexical matching with a different label, and staff-facing UI/communication should not overstate it.
* Delete a "record" file (resume, question sheet, answer key, answer script) as a side effect of normal request processing.

---

## 13. ACCEPTANCE CRITERIA ADDITIONS

Add to the original spec's acceptance checklist:

* [ ] Postgres is the database, with proper FK/UNIQUE/CHECK constraints enforced at the schema level
* [ ] Interview ID generation is verified race-free under concurrent load (test with simultaneous submissions)
* [ ] A crashed/restarted worker correctly recovers stuck interviews on startup, verified by test
* [ ] Staff authentication is required on every interview/document/evaluation route
* [ ] OCR output explicitly distinguishes blank vs. illegible vs. transcribed text
* [ ] Segmentation mismatches surface a manual-correction UI rather than guessing
* [ ] Re-evaluation creates a new evaluation record and preserves history
* [ ] Staff can override an individual question score with a logged reason
* [ ] A defined, scheduled retention/purge job exists for record files and rows past the retention window

# END OF AMENDMENT
