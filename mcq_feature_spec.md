TASK 13 — Daily MCQ Question Bank, Round 1 (Batch/Non-LLM), Score-Gated Handoff to Existing Resume Flow

SCOPE NOTE: The resume-upload / Interview-creation / Round 2 pipeline is
already built and working — do not modify it beyond the one integration
point in Part E. Focus entirely on the new Round 1 mechanism below.

## PART A.0 — DATASET FORMAT: WHAT WAS MISUNDERSTOOD, WHAT MUST EXIST, WHAT RESULT IS EXPECTED

Read this section before touching Part A. A prior attempt at the dataset
file used the wrong shape twice, and this section exists so that doesn't
happen again.

### What went wrong

Two incorrect dataset formats were proposed at different points and must
NOT be used:

1. A "ten / twenty / thirty" column format — three generically-sized
   arrays (10/20/30 questions) with no section labels, and a daily draw
   rule of "1 from ten, 2 from twenty, 3 from thirty" (6 questions/day).
   This does not match this spec at all: it has the wrong number of
   questions per day (6, not 10), no mapping to the 6 real subject
   sections, and a different rotation rule than Part B specifies.

2. A generic `"columns": [[...], [...], [...]]` array-of-arrays format
   with arbitrary category labels per column (e.g. SQL/JS/Python) and
   "one question per column per day." This also does not match this
   spec: it has no fixed relationship to the 6 required sections or
   their required counts, and doesn't encode the 1/1/3/1/2/2 per-section
   daily draw defined in Part B.

Both of the above also carried over fields (`keywords`, `required_concepts`,
`important_phrases`, `answer`, `plain_answer`, `hr_answer`) from the
OLD per-resume LLM evaluation-key schema used elsewhere in this project.
Those fields do NOT belong in this dataset — MCQ scoring here is a plain
exact-letter match against `correct_option` (see Part D.4), never
concept/keyword/phrase evaluation. Including them adds dead weight the
loader has no use for and signals a misunderstanding of how this feature
scores answers.

### What must actually be created

The dataset file lives at `generated/mcq_bank/mcq_dataset.json` and MUST
use exactly this shape — a top-level `sections` object keyed by the 6
section names used in the `mcq_bank` table's CHECK constraint, each
holding an array of question objects with ONLY these fields:

```json
{
  "sections": {
    "ENGLISH": [
      {
        "sequence_index": 0,
        "question_text": "...",
        "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
        "correct_option": "B"
      }
    ],
    "APTITUDE": [ ... ],
    "MERN": [ ... ],
    "PYTHON": [ ... ],
    "DBMS": [ ... ],
    "BACKEND_MID": [ ... ]
  }
}
```

Field rules:

- `sequence_index` is 0-based and contiguous within its section (0, 1, 2,
  ... with no gaps) — this is what Part B's rotation logic increments
  through, so a gap or duplicate breaks the daily draw.
- `options` is always exactly 4 strings, each prefixed with its letter
  (`"A) "`, `"B) "`, `"C) "`, `"D) "`), consistent with how the existing
  document generator already renders MCQ options elsewhere in this
  project.
- `correct_option` is a single letter (`A`/`B`/`C`/`D`) matching one of
  the four options — never the full option text.
- No other fields. Do not add keywords, concepts, phrases, or any
  evaluation-key metadata to this file.

### Expected counts (unchanged from original Part A.2, restated for clarity)

```text
ENGLISH      10
APTITUDE     10
MERN         30
PYTHON       10
DBMS         20
BACKEND_MID  20
-------------------
TOTAL       100
```

### Expected result — what "done" looks like

A `generated/mcq_bank/mcq_dataset.json` file that:

1. Parses as valid JSON with the exact `sections` shape above — no
   alternate top-level key, no array-of-arrays, no generic column names.
2. Has exactly the six section keys listed above, each with exactly the
   question count shown, totaling 100.
3. Within each section, `sequence_index` values are 0-based and
   contiguous with no gaps or duplicates.
4. Every question has exactly 4 options and a `correct_option` that is
   one of `A`/`B`/`C`/`D` and corresponds to an actual option in that
   question's `options` array.
5. No fields beyond `sequence_index`, `question_text`, `options`,
   `correct_option` are present anywhere in the file.

The loader script (Part A.2 below) must validate all five of the above
and fail loudly — naming exactly which section/count/field failed — if
the file supplied doesn't match. Do not silently accept a malformed file
and proceed with whatever subset happens to parse.

A dataset file matching this exact shape has already been produced and
validated (100 questions, correct per-section counts, contiguous
sequence_index, valid correct_option/options pairing) — treat that file
as the reference for both content and shape when building/testing the
loader, not the two incorrect formats described above.

---

## Part A — Static MCQ question bank (100 questions, 6 sections)

1. New table `mcq_bank`:
```sql
   mcq_bank (
     id              SERIAL PRIMARY KEY,
     section         TEXT NOT NULL CHECK (section IN
                       ('ENGLISH','APTITUDE','MERN','PYTHON','DBMS','BACKEND_MID')),
     sequence_index  INTEGER NOT NULL,   -- 0-based position within its section,
                                          -- used for deterministic rotation, not random order
     question_text   TEXT NOT NULL,
     options         JSONB NOT NULL,     -- 4 options
     correct_option  TEXT NOT NULL,      -- e.g. 'A'/'B'/'C'/'D'
     UNIQUE (section, sequence_index)
   )
```
2. Expected counts per section: ENGLISH 10, APTITUDE 10, MERN 30, PYTHON 10,
   DBMS 20, BACKEND_MID 20 (100 total). Do NOT generate/invent the actual
   question content yourself — build a loader (JSON import script, per
   Part A.0's exact schema above) that ingests the supplied dataset file,
   validates the per-section counts, sequence_index contiguity, and
   option/correct_option consistency described in Part A.0, and fails
   loudly — naming the specific violation — if any check doesn't pass.
   Seed with a small placeholder set (2–3 dummy questions per section,
   in the same Part A.0 shape) only so the pipeline is testable end-to-end
   before the real dataset file is loaded.

## Part B — Deterministic daily rotation (no randomness, no re-draw on repeat calls)

1. New table `mcq_section_cursor`:
```sql
   mcq_section_cursor (
     section    TEXT PRIMARY KEY,
     next_index INTEGER NOT NULL DEFAULT 0   -- next sequence_index to draw
   )
```
2. Daily draw counts per section (fixed, per confirmed distribution):
   ENGLISH 1, APTITUDE 1, MERN 3, PYTHON 1, DBMS 2, BACKEND_MID 2 → 10 total.
3. New table `daily_mcq_sets`:
```sql
   daily_mcq_sets (
     id                  SERIAL PRIMARY KEY,
     set_date            DATE NOT NULL UNIQUE,   -- business-timezone date, see below
     question_ids        INTEGER[] NOT NULL,     -- 10 mcq_bank ids, in presented order
     answer_key_sequence TEXT NOT NULL,           -- e.g. "BACDABCADB", same order as question_ids
     created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
   )
```
4. Generation logic (idempotent per calendar date):
   - Use a fixed business timezone for "today" (Europe/London) — do not use
     server/UTC time, since a server-UTC boundary can silently shift which
     calendar day a late-evening request lands on relative to the actual
     business day. Make the timezone configurable via env var
     (BUSINESS_TIMEZONE), defaulting to Europe/London.
   - On the FIRST request for a given business date: for each section, pull
     `sequence_index` in [next_index, next_index + draw_count) modulo that
     section's total question count (wrapping around), advance
     `mcq_section_cursor.next_index` by draw_count (mod total) in the same
     transaction, assemble the 10 questions in a fixed presented order
     (ENGLISH, APTITUDE, MERN×3, PYTHON, DBMS×2, BACKEND_MID×2), build
     `answer_key_sequence` from their correct_options in that order, and
     insert the `daily_mcq_sets` row.
   - On ANY subsequent request for the SAME business date: return the
     existing `daily_mcq_sets` row unchanged. Do NOT advance the cursor
     again or redraw — this must be safe to call repeatedly in one day
     without desyncing from a sheet that's already been printed.
   - Wrap the draw in a transaction with row-level locking on the cursor
     rows (SELECT ... FOR UPDATE) to avoid a race if two requests land at
     the same moment on the first call of the day.
5. Note for your own verification (not code, just confirm this holds):
   with these draw counts, every section's rotation realigns to its start
   every 10 business days (30/3, 20/2, 20/2, 10/1, 10/1, 10/1) — if your
   modulo math doesn't produce that, something's wrong.

## Part C — Daily question-sheet document (one per day, not per candidate)

1. Generate ONE printable document per `daily_mcq_sets` row containing all
   10 questions with their 4 options each, no answer key, no candidate
   name field (this sheet is generic/shared for the day — reuse the
   existing document-generation module/conventions from document_generator.py).
2. Store it as a RECORD file (per the existing file-lifecycle convention)
   linked to `daily_mcq_sets.id`, not to any interview — it predates any
   interview existing.
3. Add a dashboard-level (not per-card) action: "Download Today's Round 1
   MCQ Sheet" — triggers/fetches today's `daily_mcq_sets` row (generating
   it via Part B's idempotent logic if it doesn't exist yet for today) and
   serves the document. This button is visible regardless of how many
   interviews exist, since Round 1 no longer depends on any interview
   record existing yet.

## Part D — Shared multi-candidate answer sheet: AI-free extraction + scoring

1. Design a printable answer-sheet template with a fixed grid: ~10 row
   slots, each row = a blank handwritten Name field + 10 question columns,
   each question column showing 4 bubble/checkbox marks (A/B/C/D) at known,
   fixed print coordinates — same principle as the earlier OMR approach,
   just repeated per row instead of per full-page question. Store the
   coordinate layout metadata alongside the template so the scanned sheet
   can be interpreted against exact known positions.
2. Upload endpoint accepts one scanned sheet (PDF or image) containing
   up to ~10 candidates' rows, associated with today's `daily_mcq_sets`
   (or a specified date if uploading a backlog day).
3. Processing pipeline, entirely AI-free (reuse the OpenCV-based
   deskew/crop/fill-density approach from the earlier OMR MCQ work):
   - Deskew/normalize the page.
   - For each row: crop the Name field region and run it through the
     existing non-LLM handwriting-OCR engine (whichever you set up
     already — Tesseract/PaddleOCR/TrOCR) to get candidate_name text.
   - For each of the 10 question columns in that row: measure fill
     density in each of the 4 bubble regions against the calibrated
     threshold (identical logic to the earlier per-question MCQ
     detection) to determine the marked option, building a 10-character
     answer_sequence string in question-presented order.
   - Per-question edge cases within a row: zero marks above threshold →
     record as a specific "no mark" character (not silently wrong-but-
     unflagged) in the stored sequence detail; multiple marks above
     threshold → record as "ambiguous" similarly. Both still count as
     incorrect for scoring, but must be visible in the row's detail view
     for staff to spot-check, not silently indistinguishable from a
     genuinely wrong answer.
4. Score: compare each row's answer_sequence character-by-character
   against `daily_mcq_sets.answer_key_sequence` for that date — simple
   string/positional comparison, count matches. No fuzzy matching needed,
   these are single-character option letters.
5. New table `daily_mcq_results`:
```sql
   daily_mcq_results (
     id                SERIAL PRIMARY KEY,
     daily_mcq_set_id  INTEGER NOT NULL REFERENCES daily_mcq_sets(id),
     candidate_name    TEXT NOT NULL,       -- OCR'd, may need manual correction
     answer_sequence   TEXT NOT NULL,
     score             INTEGER NOT NULL,    -- out of 10
     source_sheet_file_id INTEGER REFERENCES files(id),
     created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
   )
```
6. Add a manual-correction affordance for candidate_name specifically
   (name-field OCR will be the least reliable part of this pipeline) —
   let staff edit an OCR'd name inline before finalizing results, reusing
   the existing manual-correction UI pattern from the earlier segmentation
   work.

## Part E — Results view + the ONE integration point with the existing flow

1. New "Today's Round 1 Results" view: list of `daily_mcq_results` for a
   given date (default today), sortable by score, showing candidate_name
   + score + answer_sequence detail (with no-mark/ambiguous flags visible).
2. Per-row action: "Select for Interview" — this is the ONLY touch-point
   with the existing, already-built resume-upload/Interview-creation flow.
   When triggered:
   - Route/hand off to the existing resume-upload entry point, pre-filling
     the candidate name from this result row (staff can still edit it —
     OCR'd names aren't fully trusted).
   - Once that existing flow creates the Interview record, set a new
     nullable `interviews.daily_mcq_result_id` FK back to this
     `daily_mcq_results` row (add via migration), for traceability.
3. Retire the OLD Round-1 LLM-generation path: the existing interview-
   creation pipeline must STOP generating/evaluating its own MCQ + Basic
   Technical questions per-resume — that entire mechanism is superseded
   by this feature. Instead, when an interview is created with a linked
   `daily_mcq_result_id`, populate that interview's `interview_rounds`
   round_number = 1 row directly from the linked daily result (status =
   EVALUATED, score copied over) rather than running any generation/OCR/
   evaluate cycle for round 1. Round 2 (resume-based mid-tech + VlookUp
   scenario, LLM-generated) is UNCHANGED — still generated per-interview
   as already built.
4. If an interview is somehow created without a linked daily_mcq_result_id
   (e.g. a manual/legacy path), leave round 1 in a NOT_STARTED-equivalent
   state rather than erroring — but flag this as an edge case you found,
   don't silently paper over it.

## Documentation & output

Document every change in CHANGELOG.md — append a dated section titled
"Task 13 — Daily MCQ Bank, Batch Round 1, Score-Gated Handoff" listing:
new tables, the rotation/idempotency mechanism, the answer-sheet template
and OMR/OCR pipeline, the results view, the retirement of old per-resume
Round-1 generation, the new interviews.daily_mcq_result_id linkage, and
the dataset-loader validation added per Part A.0.

Output a summary covering: confirmation the daily draw is idempotent
(same set returned on repeated calls same day) and correctly rotates the
next day, the business-timezone setting used, how a row's no-mark/
ambiguous marks surface to staff, confirmation the old per-resume Round 1
LLM generation path has been removed/retired (not left dormant alongside
the new one), and confirmation the loader correctly rejects a
malformed/wrong-shape dataset file (naming what's wrong) rather than
silently accepting it.

Do NOT run tests. I will test manually myself.