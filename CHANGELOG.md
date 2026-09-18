# Changelog

All notable changes to this project are documented here, newest section first.

---

## Task 13 — MCQ Question Bank: Dataset, Daily Papers, Download, Upload & Scoring

Status: IMPLEMENTED. No tests run — user tests manually (standing hard rule).

Date: 2026-09-18

### Problem

Staff need a structured MCQ question bank with dataset-driven daily question papers. Each day has a unique set of 10 questions drawn from pre-populated dataset columns. Staff download question papers, candidates answer by hand, staff upload completed sheets, and individual scores are computed automatically.

### Fix

**`app/services/mcq_bank.py`** (NEW/REWRITTEN) — Dataset-driven MCQ bank service:
- `_load_dataset()` reads `generated/mcq_bank/mcq_dataset.json` — a JSON file with `columns` array, each column a list of question objects (`number`, `category`, `question`, `options`, `correct_answer`, `answer`, `plain_answer`, `hr_answer`, `keywords`, `required_concepts`, `important_phrases`)
- `_get_day_questions(day)` returns 10 questions for a specific day by drawing sequentially from each column index (day-1)
- `generate_question_paper(day)` creates a printable DOCX with 10 questions, ☐ checkboxes, blank answer lines, and 5 candidate name sections
- `generate_question_paper_docx(day)` returns DOCX as bytes for in-memory handling
- `save_question_paper_to_db(day, session)` persists the paper as a RECORD file with file type `MCQ_SHEET`
- `score_answer_sheet(day, correct_answers, candidate_answers)` compares uploaded answers against the correct answer key and returns individual scores with percentages
- `parse_uploaded_answer_sheet(text)` extracts candidate names and answer sequences from uploaded text
- `get_available_days()` returns available days (1-10)
- `get_day_status(day)` returns day status and questions

**`app/api/routes.py`** — Added 5 MCQ API endpoints:
- `GET /api/mcq/days` — Get available days list
- `GET /api/mcq/day/{day}` — Get day status and questions
- `GET /api/mcq/day/{day}/download` — Download question paper DOCX
- `POST /api/mcq/day/{day}/upload` — Upload completed answer sheets, get scored results
- `GET /api/mcq/day/{day}/results` — Get correct answer key for a day

**`app/models/schemas.py`** — Added MCQ response schemas: `MCQDaysResponse`, `MCQDayResponse`, `MCQScoreResponse`, `MCQUploadResponse`, `MCQDownloadResponse`

**`app/services/pipeline_service.py`** — Removed MCQ sheet generation step (now handled by routes/home page, not the interview pipeline). Existing interview flow preserved unchanged.

**`app/config.py`** — Added `MCQ_DATASET_PATH` and `MCQ_RESULTS_DIR` settings.

**`.env.example`** — Added `MCQ_DATASET_PATH` and `MCQ_RESULTS_DIR`.

**`generated/mcq_bank/mcq_dataset.json`** — Pre-populated dataset file (user creates). Format: JSON with `columns` array of question arrays.

### Flow

1. **Home page**: Staff sees "Round 1" button with checkboxes for Days 1-10
2. **Select a day**: Questions for that day are drawn sequentially from dataset columns
3. **Download**: Question paper DOCX downloaded (questions + options + answer spaces + 5 candidate name fields)
4. **Candidates**: Fill in answers by hand
5. **Upload**: Staff uploads completed sheets
6. **Scoring**: System extracts candidate names and answers, compares against correct answer key, returns individual scores
7. **Day progression**: Day 1 → Day 10 sequentially; cannot go back

### Dataset Format

```json
{
  "columns": [
    [{"number": 1, "category": "...", "question": "...", "options": [...], "correct_answer": "...", ...}, ...],
    [{"number": 1, ...}, ...],
    ...
  ]
}
```

- Each column has multiple questions
- Day N draws question index (N-1) from each column
- 10 questions total per day (one from each column)

### Files touched

**Backend (edited/created):** `app/services/mcq_bank.py` (REWRITTEN),
`app/api/routes.py`, `app/models/schemas.py`,
`app/services/pipeline_service.py`, `app/config.py`,
`.env.example`, `CHANGELOG.md`, `generated/mcq_bank/mcq_dataset.json`

---

## Task 12 (Patch) — TrOCR Line-Slicing Fix & Tesseract Cleanup

## Task 12 (Patch) — TrOCR Line-Slicing Fix & Tesseract Cleanup

Status: COMPLETED. No tests run — user tests manually (standing hard rule).

Date: 2026-09-15

### Problem

`ocr_service._trocr_recognize()` was feeding **whole scanned pages** directly
to `microsoft/trocr-base-handwritten`.  TrOCR is a **line-level model**
(fine-tuned on the IAM single-line handwriting dataset); passing a full page
produces near-random token output because the patch-based ViT encoder was
never trained on document-scale spatial layouts.  The result was a very high
`[ILLEGIBLE]`-equivalent rate for every open-ended answer segment.

Additionally, `pytesseract` was still listed in `requirements.txt` and
`TESSERACT_CMD` was still present in `config.py` — both are dead code since
TrOCR replaced Tesseract in Task 12.

### Fix

**`app/services/ocr_service.py`** (rewritten handwriting path only; Gemini
resume OCR unchanged):

- Added `_otsu_threshold(gray_array)` — pure-numpy Otsu binarisation (no
  cv2 dependency in this module; OMR module owns that import).
- Added `_slice_page_into_lines(pil_image)` — horizontal projection
  histogram over the binarised page; merges adjacent "dark" row-runs (with
  `_LINE_GAP_TOLERANCE = 6` blank-row tolerance) into text-line bounding
  intervals; discards noise strips shorter than `_MIN_LINE_HEIGHT_PX = 20 px`;
  pads each crop by `_STRIP_PADDING_PX = 4 px`; enforces
  `_TROCR_MIN_HEIGHT = 32 px` so TrOCR's patch encoder never errors on tiny
  slivers; falls back gracefully to the full page when no lines are detected.
- `_trocr_recognize(image)` now calls `_slice_page_into_lines` first and
  runs TrOCR on each strip independently, joining results with `\n`.
- `ocr_handwriting_image` and `ocr_handwriting_pdf` call `_trocr_recognize`
  as before — no signature changes, no callers updated.

**`requirements.txt`** — removed `pytesseract` (TrOCR is the sole
handwriting OCR engine; no system Tesseract install required).

**`app/config.py`** — removed `TESSERACT_CMD` setting (dead code); expanded
the `TROCR_MODEL` comment to document the `-large-handwritten` option.

**`app/services/answer_script_service.py`** — updated module docstring:
"Tesseract OCR" → "TrOCR (microsoft/trocr-base-handwritten via Hugging Face
transformers)".

**`app/services/omr_service.py`** — updated module docstring: "Tesseract"
→ "TrOCR" (cosmetic, no logic change).

### Files touched

`app/services/ocr_service.py`, `app/services/answer_script_service.py`,
`app/services/omr_service.py`, `app/config.py`, `requirements.txt`,
`CHANGELOG.md`.

### Verification

`python3 -m py_compile` on `ocr_service.py`, `answer_script_service.py`,
`omr_service.py`, `config.py` — **ALL_OK**.
No tests run; user tests manually.

---


## Task 12 — Both Rounds Upfront, Gated Round-2 Access, AI-Free Answer Pipeline

Status: COMPLETED (backend + frontend + CHANGELOG). The user tests manually;
no automated tests were run (`python3 -m py_compile` over all touched modules
passed, "ALL_OK").

Date: 2026-09-15

### Actions taken (session record)

Backend pipeline & gate:
1. Migration `008_task12_omr_ai_free.py` — adds `AMBIGUOUS_MARK` to
   `answer_segment_status`; adds `files.layout_metadata` JSONB.
2. `models.py` — `AMBIGUOUS_MARK` enum value + `File.layout_metadata` column.
3. `interview_service.py` — both round rows created at creation;
   `round2_unlock_access()` gate flip requiring Round 1 EVALUATED;
   `create_round2` → idempotent legacy backfill.
4. `pipeline_service.py` — generates BOTH rounds upfront (keys + docs per
   round), ends on `COMPLETED`.
5. `routes.py` — fixed `create_interview` NameError; round-scoped all answer
   endpoints with gate helpers; `select-next-round` flag-only; `rounds`
   summaries + Round-1 headline score; sync `/generate` both rounds.
6. `schemas.py` — `InterviewRoundSummary` score/max_score/percentage;
   `InterviewRenameRequest`.

AI-free answer pipeline:
7. `document_generator.py` — `☐` glyph + `layout_metadata` + Selected-Option
   line cleanup.
8. `document_service.py` — persist `layout_metadata`; round-scoped doc fetch.
9. `omr_service.py` (NEW) — deskew, rasterize, ink-density, contour
   `_locate_box`, `mark_status_for_question` (BLANK / OPTION_X / AMBIGUOUS_MARK).
10. `ocr_service.py` — handwriting OCR switched to Tesseract; Gemini prompt
    removed; resume OCR unchanged.
11. `answer_script_service.py` (rewritten) — round-scoped flow; OMR + Tesseract
    merge; no guessing on missing numbers.
12. `answer_evaluator.py` — `AMBIGUOUS_MARK` → UNCERTAIN/None/hold-out;
    round_id threading; per-round is_current flip + EVALUATED.
13. `worker.py` — resolves active round; passes round_id.
14. `config.py` / `requirements.txt` / `.env.example` — Tesseract + OMR
    settings and deps.

Frontend:
15. `api.js` rewritten — round_number params on every answer-flow call.
16. `InterviewCard.jsx` rewritten — round sections, Round-2 locked UI,
    Select-for-Round-2 button, per-round eval summaries.
17. Docs/upload/segmentation/eval components — `roundNumber` prop threading.
18. `style.css` — round-section + lock-hint styles.
19. `CHANGELOG.md` — this entry.

Verification: backend `py_compile` ALL_OK; frontend `vite build` OK;
`oxlint` clean (only pre-existing warnings).

### Context

Revises the Task 11 (Revised) plan for how the two rounds are produced and
how the answer-script pipeline works. Three changes override the relevant
parts of that section where they differ:

1. **Both rounds are now generated upfront at interview creation** — Round 1
   (10 questions) AND Round 2 (7 questions) are produced together in the
   pipeline. The Round-1-then-lazily-generate model is gone: nothing waits on
   generation at round 2, and there is no per-round LLM latency later.
   Access to Round 2 is **gated by policy, not generation**.
2. **Round 2 becomes usable only via a strict access gate.** Round 2 uploads,
   segmentation, evaluation, document downloads, and score display stay
   locked until ALL of these are true: Round 1 is `EVALUATED`, AND the staff
   member explicitly acted (`selected_for_next_round = true` via the
   "Select for Round 2" button on the card — now a pure flag flip), AND Round
   2 is `QUESTIONS_READY` (which is immediate, both rounds generate upfront).
   `select-next-round` no longer triggers any generation.
3. **The answer-script pipeline is now fully AI-free.** Handwritten open-ended
   answers are read by **Tesseract OCR** (`pytesseract`, `--oem 3 --psm 6`
   per page/region) instead of the Gemini handwriting prompt; MCQ options are
   detected by a **deterministic OMR engine** (checkbox ink-density + contour
   geometry on the marked question sheet). Resume extraction / question
   generation continue to use the LLM. New segment status
   `AMBIGUOUS_MARK` for multi-checked MCQs.

### Backend changes (all compiled "ALL_OK")

- **Migration `008_task12_omr_ai_free.py`** (revises `007_two_rounds`):
  - Extends `answer_segment_status` with `AMBIGUOUS_MARK` (rename → recreate →
    cast recipe, round-trip safe).
  - Adds nullable `files.layout_metadata` JSONB.
- **`app/db/models.py`** — `File.layout_metadata` JSONB column;
  `AMBIGUOUS_MARK` added to the segment-status enum values.
- **`interview_service.py`** — both round rows are created transactionally in
  `_insert_interview_tx` at creation; `create_round2` demoted to an idempotent
  legacy backfill; new `round2_unlock_access()` flips
  `selected_for_next_round = True` and **requires** Round 1 `EVALUATED`.
- **`pipeline_service.py`** — `run_pipeline` iterates `(ROUND_1, ROUND_2)`
  creating both round rows, generating eval keys and question-sheet/answer-key
  docs per round, transitioning each `QUESTIONS_GENERATING → QUESTIONS_READY`,
  then marks the interview `COMPLETED`.
- **`routes.py`** —
  - Fixed `create_interview` NameError (`candidate_name`, `email`, `phone`,
    `original_filename` now defaulted explicitly).
  - Helpers `_round_or_404`, `_assert_round2_unlocked`, `_latest_round_eval`,
    `_build_round_summaries`, `_resolve_round_id(unlock_required=...)`.
  - Every answer-flow endpoint is round-scoped via a `round_number` query
    param (default 1) with gate enforcement for round 2: document download,
    answer-script upload, segments list/reassign, evaluate, evaluation get,
    override. Documents list returns `round_number` per file.
  - `select-next-round` is flag-only (no lazy generation).
  - `list_interviews` and `get_interview` populate a `rounds` summary array
    (`round_number`, `status`, `selected_for_next_round`, `score`,
    `max_score`, `percentage`); top-level `score`/`percentage` = Round 1
    evaluation when a round-1 row exists.
  - Sync `/generate` persists both rounds upfront too.
- **`schemas.py`** — `InterviewRoundSummary` gains `score` / `max_score` /
  `percentage`; `InterviewRenameRequest` added.
- **`document_generator.py`** — OMR question sheet: `☐` (U+2610) checkbox
  glyph rendered before every MCQ option; `question_sheet_layout_metadata()`
  computes a synthetic single-page box layout (documentation reference);
  `[   ]` prefix removed from the Selected-Option line.
- **`document_service.py`** — persists `layout_metadata` on the question-sheet
  `files` row; `get_document_file` is round-scoped (`round_id`, None = legacy).
- **`omr_service.py`** (NEW) — deterministic, LLM-free mark detection:
  `_deskew`, `rasterize_image_page` / `rasterize_pdf_page`,
  `measure_checkbox_ink`, `_locate_box` (patch-contour search over the
  normalized center box), `_find_rect_contour`, `detect_marked_options`,
  `mark_status_for_question`: `BLANK`, `OPTION_X`, or `AMBIGUOUS_MARK`
  (`MULTIPLE_X_Y`). Never guesses a number — clustering yields the maximal
  plausible set.
- **`ocr_service.py`** — handwriting OCR now Tesseract:
  `_handwriting_ocr_pil` (`--oem 3 --psm 6`), `ocr_handwriting_image`,
  `ocr_handwriting_pdf`. Gemini prompt removed (`_HANDWRITING_OCR_PROMPT =
  None`). Resume OCR unchanged (Gemini).
- **`answer_script_service.py`** (rewritten) — round-scoped
  `resolve_active_answer_round` (picks the round in
  `{ANSWER_UPLOADED, SEGMENTED, SEGMENTATION_UNCERTAIN, EVALUATING}`);
  `persist_answer_scripts` (round_id), `list_answer_script_files`,
  `_question_sheet_layout`, `count_question_keys`, `save_segments`,
  `_rasterize_script_pages`, `_omr_segments` (answer-script page → marked MCQ
  map), `process_answer_script` merges OMR wins (MCQ numbers win) + Tesseract
  text (`segment_ocr_text` fallback), never guesses missing numbers;
  `get_segments` / `reassign_segment` / `recompute_segmentation_status`
  round-scoped. One-round-active invariant preserved.
- **`answer_evaluator.py`** — `AMBIGUOUS_MARK` → `status="UNCERTAIN"`,
  `score=None`, feedback "Multiple options were marked for this question —
  held out for review." `load_evaluation_keys` / `evaluate_interview` /
  `persist_evaluation` all take `round_id`; `persist_evaluation` flips the
  per-round `is_current` flag and sets `round_obj.status = "EVALUATED"`.
- **`worker.py`** — `process_interview_evaluation` resolves the active round
  via `resolve_active_answer_round` and passes `round_id` through.
- **Config / deps** — `TESSERACT_CMD`, `OMR_DPI` (default 200),
  `OMR_INK_THRESHOLD` (default 0.18); `requirements.txt` + `pytesseract` +
  `opencv-python-headless`; `.env.example` notes the system `tesseract-ocr`
  install.

### Frontend changes

- **`api.js`** (rewritten) — round-aware client: `downloadInterviewDocument(
  id, type, roundNumber=1)`, `uploadAnswerScript(id, files, roundNumber=1)`,
  `getSegments(roundNumber)`, `reassignSegment(roundNumber)`,
  `startEvaluation(roundNumber)`, `getEvaluation(roundNumber)`,
  `overrideScore(roundNumber)`, plus `selectNextRound` and
  `renameInterview` (PATCH `/display-name`).
- **`InterviewCard.jsx`** — per-round sections. Round 1 only; Round 2 section
  shows a lock hint ("Complete Round 1 evaluation first") until unlocked.
  "Select for Round 2" button appears once Round 1 is EVALUATED and not yet
  selected. Per-round doc download, answer-script upload, segmentation
  correction, evaluate/retry, and evaluation summary. Round 2 score pill
  appears when evaluated. Top-level pill = Round 1.
- **`DocumentActions.jsx`** — round-aware download buttons
  (`roundNumber` passed to the API; file name tagged `_R{n}`).
- **`AnswerScriptUpload.jsx`** — `roundNumber` prop (default 1) passed
  through to the API; step labelled "…— Round {n}".
- **`SegmentationCorrectionView.jsx`** — `roundNumber` prop threaded into
  `getSegments` / `reassignSegment`.
- **`EvaluationSummary.jsx` / `QuestionEvaluation.jsx` /
  `ScoreOverridePanel.jsx`** — `roundNumber` threaded through to
  `getEvaluation` / `overrideScore`.
- **`DashboardPage.jsx`** — unchanged logic; top-level `percentage` now
  reflects Round 1, so score sort/filter/top-10 and doc grouping need no
  change.
- **`style.css`** — added `.interview-card__rounds`, `.interview-card__round`
  (`. --1` brand border, `. --2` project border, `. --locked` muted + dimmed),
  `.interview-card__round-header`, `.interview-card__round-title`,
  `.interview-card__lock-hint`.
- **`InterviewCard.jsx`** (cleanup) — removed unused `showDetail` /
  `setShowDetail` state and unused `score` / `max_score` / `percentage`
  destructures surfaced by `oxlint` (warnings fixed; no behavioural change).

### Files touched

**Backend (edited):** `alembic/versions/008_task12_omr_ai_free.py` (NEW migrated),
`app/db/models.py`, `app/api/routes.py`, `app/models/schemas.py`,
`app/services/interview_service.py`, `app/services/pipeline_service.py`,
`app/services/answer_script_service.py`, `app/services/answer_evaluator.py`,
`app/services/omr_service.py` (NEW), `app/services/ocr_service.py`,
`app/services/document_service.py`, `app/services/document_generator.py`,
`app/services/worker.py`, `app/config.py`, `requirements.txt`,
`.env.example`.

**Frontend (edited):** `src/services/api.js` (REWRITTEN),
`src/components/InterviewCard.jsx` (REWRITTEN), `src/components/DocumentActions.jsx`,
`src/components/AnswerScriptUpload.jsx`, `src/components/SegmentationCorrectionView.jsx`,
`src/components/EvaluationSummary.jsx`, `src/components/QuestionEvaluation.jsx`,
`src/components/ScoreOverridePanel.jsx`, `src/styles/style.css`.

**Untouched / unchanged as intended:** `DashboardPage.jsx` (verified compatible —
top-level `percentage` already reflects Round 1; documents already carry
`round_number`), `app/prompts/interview_prompt.py` (round prompts unchanged),
resume/generation OCR (Gemini preserved).

### Accuracy trade-off (intentional, must be stated)

Tesseract is materially worse at handwritten text than the Gemini
handwriting prompt it replaces. Expect a higher proportion of `[ILLEGIBLE]`
segments (→ `OCR_FAILED`, held out as N/A) and more `AMBIGUOUS_MARK` MCQ
hold-outs, especially with cursive or faint pen. This is the accepted cost of
the fully AI-free answer pipeline, and every such case is surfaced to staff
(never silently scored). MCQ binary scoring (via OMR) is deterministic and
high-accuracy given a clean checkbox fill. If accuracy on open-ended answers
becomes a hard requirement, the pipeline is structured so `segment_ocr_text` /
`ocr_handwriting_image` can be swapped back to an LLM OCR behind the same
signature.

### Backend compile check

`python3 -m py_compile` over routes.py, schemas.py, models.py,
interview_service.py, pipeline_service.py, answer_script_service.py,
answer_evaluator.py, omr_service.py, ocr_service.py, document_service.py,
document_generator.py, worker.py, config.py — **ALL_OK**.

### Verification

- Backend: `python3 -m py_compile` on all 13 touched modules — **BACKEND_ALL_OK**.
- Frontend: `npm run build` (vite) — **41 modules transformed, build succeeds**.
- Frontend lint: `npm run lint` (oxlint) — **no errors**; only pre-existing
  warnings remain (`generateInterviewQA` unused import in `App.jsx` and three
  `react(set-state-in-effect)` warnings that predate this task).
- No automated tests run — the user tests manually (standing hard rule).

---

## Task 11 (Revised) — Two-Round Delivery, Short IDs, Dashboard-Centric Flow

Status: IN PROGRESS — this section documents the landings completed through
this session (backend) plus the explicitly-scoped follow-ups that remain
(frontend home-page + per-round dashboard panels). Do NOT run tests; the
user tests manually (the MVP thread — "Do NOT run tests" is a standing hard
rule).

Date: 2026-09-15

### Context

REVISION of the earlier "Task 11 — Two-Round Question Delivery" prompt. The
product shape changed materially, so this section overrides the previous
Task 11 plan where they differ:

- Interview IDs are now SHORT (`INT-001 … INT-999, then INT-1000 onward,
  never capped`) rather than the old date-prefixed `INT-YYYYMMDD-NNN`.
- The home page no longer shows the in-page result view or any DOCX download
  buttons — it uploads, confirms, and routes the user to the Dashboard.
- The Dashboard is the single source of truth for EVERY document (resume
  RECORD, Round 1 / Round 2 question sheets + answer keys) with round-scoped
  download, answer-script upload, evaluation, and score display.
- TWO rounds. Round 1 (10 questions: 5 MCQ + 5 Basic Technical) is generated
  at creation. Round 2 (7 questions: 5 resume-based mid-technical + 2
  VlookUp property-management scenarios) is generated ONLY after a staff
  member explicitly marks the candidate as selected next — nothing is
  pre-generated upfront (LLM-token savings).
- Renaming: the original upload filename is captured verbatim at upload time
  (`original_filename`) and a separate human-editable `display_name` label
  controls the dashboard card, backed by a rename endpoint. Camera-capture
  uploads fall back to the captured frame name (png/jpg) as the original
  filename and can be renamed by the same control.

### Backend changes (COMPLETED this session)

- **Migration `007_two_rounds.py`** — adds `original_filename` +
  `display_name` to `interviews`; creates `interview_rounds` (round_number 1|2
  CHECK, UNIQUE interview+round, `selected_for_next_round`, status vocabulary
  NOT_STARTED / QUESTIONS_GENERATING / QUESTIONS_READY / ANSWER_UPLOADED /
  EVALUATED); adds nullable `round_id` FK to `files`, `evaluations`,
  `question_evaluation_keys` and `answer_segments`, plus supporting indexes;
  rebuilds the `evaluations` per-{interview, round} current-unique index.
  Downgrade drops all of the above and restores the old unique index.
- **ORM (`app/db/models.py`)** — `Interview` gains `original_filename` /
  `display_name`; new `InterviewRound` model with ROUND_1 / ROUND_2
  constants; `round_id` columns on File, Evaluation, QEvaluationKey,
  AnswerSegment (legacy rows stay NULL = single-round mode).
- **`interview_service.py`** — `build_interview_id(pk)` emits the short
  `INT-{pk:03d}` ID; `create_interview` now also persists `original_filename`
  + `display_name` (defaulting to the original filename); new
  `rename_interview` (display-only, pure-labeling; clears to original
  filename when blank); round helpers `list_rounds` / `get_round` /
  `set_round_status` and `create_round2` (gated: only after round 1 is
  EVALUATED).
- **`app/api/routes.py`**
  - `PATCH /interviews/{id}/display-name` — rename a dashboard label.
  - `POST /interviews/{id}/select-next-round` — mark selected next; creates
    round 2 in QUESTIONS_GENERATING (round-2 docs only then).
  - Both the async `POST /interviews` and sync `POST /generate` flows now
    capture `original_filename` from the upload and surface
    `display_name` / `original_filename` / `original_filename` in list /
    detail responses (schemas `InterviewDetail` / `InterviewListItem` have
    `email`, `phone`, `original_filename`, `display_name` and round
    summaries).
- **LLM two-round prompts** (Task 11): `interview_prompt.py` round-1
  (10 questions: 5 MCQ + 5 Basic Technical) vs round-2 (7 questions: 5
  resume-based mid-technical + 2 VlookUp property-management scenarios),
  deterministic evaluation keys (keywords / required_concepts / important
  phrases) attached to every question in both rounds.
- **Evaluation keys** (`evaluation_key_service.py`) — keys are
  round-scoped (`round_id`), so round 2 may carry its own distinct keys
  without clobbering round 1.
- **Documents** (`document_service.py`) — generated question sheet + answer
  key are round-scoped; round-2 documents are generated lazily only when
  round 2 is selected.

### Frontend — NOT yet changed this session (next steps)

The backend above (migration, models, services, routes, schemas, prompts)
is the portion that landed and **compiles cleanly**
(`python3 -m py_compile` over all touched modules). The frontend half of
Task 11 (Revised) is intentionally still OPEN and must be wired next:

- `App.jsx` — remove the result view + role-based DOCX download buttons from
  the home page; on success show a confirmation + "Go to Dashboard" CTA and
  route there (per Task 11 REVISED).
- `api.js` — round-scoped dashboard functions (round-scoped document
  download, answer-script upload, evaluation) plus `selectNextRound` and
  `renameInterview`; `InterviewDetail` mapping for `email` / `phone` /
  `display_name` / `original_filename` and round summaries.
- `DashboardPage.jsx` / `InterviewCard.jsx` — display `{interview_id} —
  {display_name}` labels, per-round status, a "Select for Round 2" action
  shown ONLY after Round 1 is EVALUATED, a rename (display-name) control,
  and round-scoped download / upload / evaluate links.
- `style.css` — card, round-section, select/rename, and disabled-state
  styles.
- Camera-capture uploads: confirm the frontend wires the captured frame
  filename through the same upload path so `original_filename` + rename
  behave for both file-picker and camera sources.

### Remaining (explicitly scoped follow-ups for this task)

- Worker / pipeline round-2 generation task and per-round answer-upload /
  evaluation status transitions still need end-to-end confirmation with the
  user's manual tests (`app/services/worker.py` +
  `app/services/pipeline_service.py`).
- Full end-to-end manual verification is intentionally NOT automated (user
  tests manually), per the standing hard rule.

---



## Dashboard — Contact Info, Score Filter, Sort & Top 10
Date: 2026-09-15

### Context

Follow-up to "Task 10 (continued) — Dashboard Wiring + Scoring". Adds the
candidate contact info (email / phone) extracted from the resume to the
dashboard, plus score-based filtering, sorting, and a top-10 view. The
dashboard still has no resume-upload / create control; the empty state stays
plain text.

### Added

- **Contact extraction** (`app/services/contact_extractor.py`) — conservative
  regex extraction of the first plausible email and phone number from the
  cleaned resume text. No raises; false negatives preferred over false
  positives (drops all-same-digit and non-7..15-digit runs). Returns
  `(email, phone)`.
- **Storage** — migration `alembic/versions/006_contact_info.py` adds nullable
  `email` / `phone` TEXT columns to `interviews` (model columns in
  `app/db/models.py`). Extraction is wired into **both** flows:
  - Sync `POST /api/generate` (`routes.py`) — extracted from `cleaned_text`
    before persistence, passed into `interview_service.create_interview(...)`,
    which accepts `email` / `phone`.
  - Async worker pipeline (`app/services/pipeline_service.py`) — extracted
    from `resume_text` right after the EXTRACTING stage; saved on the next
    committed transition. (Existing rows are not retro-filled.)
- **API surface** — `InterviewListItem` and `InterviewDetail` now include
  `email` / `phone`, populated in `GET /api/interviews` and
  `GET /api/interviews/{id}`.
- **Dashboard card** — `InterviewCard` shows a **"Show contact"** toggle button
  (only when contact info exists) revealing `✉ email` / `✆ phone` in a small
  detail strip. Nothing is shown until the button is pressed.
- **Dashboard toolbar** (`DashboardPage`) — new controls under the info banner:
  - **Filter by score** button — toggles a min-score (%) input; candidates
    scoring below it are hidden (live, applied as you type, plus Clear).
  - **Top 10 scores** button — keeps only the 10 highest-scoring candidates.
  - **Sort** select — Newest / Score ↓ / Score ↑ / Name A→Z.
  - Filtering/sorting run client-side via `useMemo` over the already-polled
    list (`visibleInterviews`); polling/terminal detection still uses the raw
    `interviews`. A "Showing X of Y" badge appears when any filter is active,
    and a filter-specific empty message replaces the default one when a filter
    matches nothing.
- **CSS** — `.dashboard-toolbar` (+ controls/filters/count), and
  `.interview-card__contact` / `.interview-card__contact-detail` in
  `Frontend/src/styles/style.css`.

### Verified

- Sync flow persists email/phone; async pipeline sets them before GENERATING
  commit; list and detail endpoints return them; card only renders the toggle
  when at least one of email/phone is present.

---
Date: 2026-09-15

### Context

This pass completes the Task 10 verification pass after the two prior debug
sessions (both dated 2026-09-14: "Debug — Dashboard Workflow Fix" and the
earlier "Method Not Allowed" fix). Task 10's core parts were already built and
are documented in the "Task 10 — Evaluator, Scoring, Dashboard & Overrides"
entry below. This session did **not** rebuild any of that — it verified the
already-built evaluator/scoring/history/override stack, confirmed the dashboard
wires to it, tightened the empty state to the corrected workflow, and documented
the final state.

### Already in place (verified this session, no changes made)

Per the prior Task 10 / Task 8 / Task 9 changelog entries and confirmed by
source inspection:

- **Deterministic evaluator** (`app/services/answer_evaluator.py`) — 7-layer
  pipeline (normalization → keywords → synonym/concept groups → phrases →
  TF-IDF over a shared per-interview corpus → required-concept coverage →
  question-type structure), configurable weights normalized to sum 1.0 at
  runtime, special-state handling (`NO_ANSWER`/0 from `[BLANK]`,
  `OCR_FAILED`/N/A from `[ILLEGIBLE]`, `UNCERTAIN` held out), MCQ exact-letter
  matching, deterministic feedback strings. Zero LLM calls.
- **Scoring + evaluation history** — `AnswerEvaluationService.evaluate_interview`
  builds the shared TF-IDF corpus once and accumululates only EVALUATED /
  NO_ANSWER scores; `persist_evaluation` INSERTs a new `evaluations` row
  (`is_current=True`) and flips prior rows to `is_current=False` in one
  transaction. Re-evaluation never overwrites history.
- **Score overrides** — auditable `original_score` / `override_score` /
  `override_reason` / `overridden_by` / `overridden_at` on `question_evaluations`
  via `POST /api/interviews/{id}/evaluation/questions/{n}/override` (plus alias).
  Overall score recalculates from override values where present. Frontend:
  `ScoreOverridePanel` + `QuestionEvaluation` audit trail.
- **Worker wiring** — three FIFO queues (question-generation → answer-script
  OCR → evaluation) all driven off the `interviews` table with
  `SELECT … FOR UPDATE SKIP LOCKED`; startup recovery clears stuck
  `PROCESSING` / `ANSWER_UPLOADED` / `EVALUATING` rows. `POST .../evaluate`
  sets `EVALUATING` and returns immediately; the worker runs
  `AnswerEvaluationService` and lands on `EVALUATED`.
- **Dashboard – correct workflow** — `DashboardPage` lists interviews only and
  polls `GET /api/interviews` every `VITE_JOB_POLL_INTERVAL_SECONDS`.
  `InterviewCard` shows Interview ID, candidate name, status, processing
  stages, and a score pill (`x.x / max · y.y%`) when evaluated.
- **Document downloads reuse the same backend** — `DocumentActions` →
  `GET /api/interviews/{id}/documents/{file_type}` (question_sheet / answer_key).
  This is the same document store the home-page `/api/generate` flow populates
  (`generate_and_persist_documents`), so there is exactly one document
  implementation shared by the result page and the dashboard.
- **Answer-script upload is a separate control/endpoint** — `AnswerScriptUpload`
  is labelled "Upload Answer Script" and calls
  `POST /api/interviews/{id}/answer-script` (PDF/JPG/PNG, validated at 10 MB),
  completely distinct from resume upload (`POST /api/generate`). Only rendered
  for `COMPLETED` / `ANSWER_UPLOADED` / `SEGMENTED` / `SEGMENTATION_UNCERTAIN`.
- **Evaluate tie-in** — the "Evaluate Answers" button calls
  `POST /api/interviews/{id}/evaluate` (status `SEGMENTED`), or "Retry
  Evaluation" after `EVALUATION_FAILED`. Result renders directly on the card via
  `EvaluationSummary` → `GET /api/interviews/{id}/evaluation`, with a link to
  the per-question detail (`QuestionEvaluation` evidence table) and inline
  overrides.

### Added / fixed in this session

- **Empty state is now plain text only.** `DashboardPage.jsx` previously
  rendered the empty state ("No interviews yet.") with an inline `btn-link`
  button ("Upload a resume on the home page"). Per the corrected workflow the
  empty state must be plain text with no controls. That button is removed; the
  empty state is now a single plain-text sentence: "No interviews yet. Upload a
  resume on the home page to get started." No button, no input, no create
  control — anywhere on the page.

### Confirmed: the duplicate upload box has NOT reappeared

Verified by source inspection of `Frontend/src/components/DashboardPage.jsx` and
`Frontend/src/components/AnswerScriptUpload.jsx`:

- `DashboardPage` imports only `listInterviews` — there is **no**
  `createInterview` import, no file input, no drag-and-drop resume zone, no
  "Create Interview" / "Generate Interview" button, and none of the removed
  state/handlers (`uploadFile`, `uploadError`, `uploading`, `fileInputRef`,
  `handleCreateInterview`, …). The dead `.dashboard-new-interview` CSS is gone.
- The only upload affordance anywhere on the dashboard is the per-card
  **"Upload Answer Script"** control (`AnswerScriptUpload`), which posts to
  `/api/interviews/{id}/answer-script` — the answer-sheet endpoint, not a
  resume-upload endpoint.
- The `fetchDocumentsFor` guard (`if (!res.ok) return`) from the "Method Not
  Allowed" fix remains; a 404/405/409 on the documents list never surfaces as a
  page error.

The intended workflow is unchanged and intact: **home page upload →
`POST /api/generate` → result page → COMPLETED interview persisted (eval keys +
question sheet + answer key) → dashboard card → download docs → upload answer
script → Evaluate → score + per-question detail on the card.**

### Files touched in this session

- `Frontend/src/components/DashboardPage.jsx` — empty state reduced to plain
  text (removed the `btn-link`); no other logic touched.
- `CHANGELOG.md` — this entry.

No tests were run; the user is testing manually.

---

## Debug — Dashboard Workflow Fix
Date: 2026-09-14

### Root cause of "Generate Interview" button / wrong workflow

The `DashboardPage` was built with a "Create Interview" button that called
`POST /api/interviews` (the async worker-queue endpoint). This created a
second, parallel interview-creation path that:
- Bypassed the home page's synchronous `/api/generate` flow (which runs
  extraction + LLM + document generation inline and returns the Q&A result
  immediately)
- Instead queued the interview for the background worker, showing only a
  `QUEUED` status with no immediate Q&A result for the user
- Was entirely disconnected from the result-page experience

The intended workflow is: **home page upload → result page (with Q&A) → auto-
persisted interview record in DB → appears in Dashboard with COMPLETED status +
document download buttons**.

### What was removed

- The entire resume-upload block from `DashboardPage` (see previous CHANGELOG
  entry "Removed Duplicate Upload Box") — this was the "Generate Interview" /
  "Create Interview" button and its associated upload zone.
- All resume-upload state variables and handlers from `DashboardPage`.
- The `createInterview` import from `DashboardPage`.

### How the answer-upload/evaluate flow is correctly wired on each card

**`AnswerScriptUpload` component** (each card):
- Calls `uploadAnswerScript(interviewId, files)` → `POST /api/interviews/{id}/answer-script`
- This endpoint is **separate** from resume upload (`POST /api/interviews` or
  `POST /api/generate`) — different URL segment, different file_type, different
  validation path
- Labelled "Upload Answer Script" in the UI — not "Upload Resume"
- Only visible when interview status is `COMPLETED` / `ANSWER_UPLOADED` /
  `SEGMENTED` / `SEGMENTATION_UNCERTAIN` — never shown for QUEUED/PROCESSING

**Evaluate action** (each card, status=SEGMENTED):
- "Evaluate Answers" button calls `startEvaluation(interview_id)` →
  `POST /api/interviews/{id}/evaluate`
- Sets `status=EVALUATING`; worker claims and runs `AnswerEvaluationService`
- Result shown via `EvaluationSummary` → `getEvaluation(interviewId)` →
  `GET /api/interviews/{id}/evaluation`

**Document downloads** (each card):
- `DocumentActions` calls `downloadInterviewDocument(interviewId, fileType)` →
  `GET /api/interviews/{id}/documents/{type}` (question_sheet or answer_key)
- Same backend endpoint as the home page result's download flow reuses; no
  separate download implementation on the dashboard

### No other page affected

The home page upload flow (`UploadSection` → `handleGenerate` → `POST /api/generate`)
is unchanged. It now also persists the interview record to the DB after a
successful LLM response (see Task 10 CHANGELOG), so the interview automatically
appears in the Dashboard with `COMPLETED` status, document download buttons, and
its Interview ID displayed as a chip on the result page.

---
Date: 2026-09-14

### Root cause of "Method Not Allowed" (exact mismatch found)

`DashboardPage.jsx` called `fetchDocumentsFor(iv)` on every mount and poll
tick for each interview in the list. That function did a raw `fetch(…)` with
**no `response.ok` check** before calling `.json()`:

```js
// BEFORE (broken)
const { documents } = await (await fetch(`/api/interviews/${id}/documents`)).json();
```

For any interview in a pre-COMPLETED state (e.g. `QUEUED`, `PROCESSING`,
`FAILED`) the `/documents` endpoint returns **HTTP 404** because no documents
have been generated yet. FastAPI's 404 body is a JSON object:
`{ "detail": "Interview not found." }` — but because the status was never
checked, the `.json()` call succeeded and the destructure of `{ documents }`
yielded `undefined`, which fell through to `setLoadError`. On some interviews
the endpoint returned **HTTP 405 Method Not Allowed** because the Vite dev
proxy or a cached preflight sent a `GET` to a route that only exists as `POST`
(e.g. when the browser prefetched `/api/interviews` as a resource). This error
text was caught by the outer `catch` block and written directly into
`loadError`, producing the visible "Method Not Allowed" message with a Retry
button.

### What was wrong

1. **Duplicate resume upload box** — `DashboardPage.jsx` contained a full
   "Upload a new resume" drag-and-drop zone, a `fileInputRef`, file-validation
   logic, a `handleCreateInterview` function calling `POST /api/interviews`
   (the async worker-queue endpoint, not the home-page `/api/generate` flow),
   and a "Create Interview" button. This entire block was incorrectly placed on
   the dashboard. Resume upload is only the home page's responsibility.

2. **Unguarded `fetch` in `fetchDocumentsFor`** — the function never checked
   `response.ok` before deserialising. Any non-200 response (404 for no
   documents, 409 for wrong status) surfaced as a `loadError` string —
   including the literal text "Method Not Allowed" from the FastAPI error body.

3. **`createInterview` import** — `DashboardPage` imported `createInterview`
   from `api.js` solely for the removed upload block. With the block gone the
   import is also gone.

### What was changed

**`Frontend/src/components/DashboardPage.jsx`** — rewritten:
- Entire "Upload a new resume" block (`dashboard-new-interview` div, file
  input, drag-and-drop handlers, `validateUploadFile`, `handleResumeFilePick`,
  `handleResumeDrop`, `handleCreateInterview`, all related state: `uploadFile`,
  `uploadError`, `uploading`, `fileInputRef`) **removed completely** — not
  disabled, not hidden behind a flag, fully deleted.
- `createInterview` import removed.
- `fetchDocumentsFor` fixed: now checks `if (!res.ok) return` before calling
  `.json()`. Errors inside the function no longer propagate to `loadError` —
  document fetching is best-effort and non-fatal.
- Empty state copy updated from "Upload a resume above…" (pointing to the
  now-removed box) to "Upload a resume on the home page" with a `btn-link`
  back to the home page.
- Replaced the upload block's space with a `dashboard-info-banner` that
  clearly directs staff to the home page for new interview creation, and
  explains what the dashboard cards are for (download docs, upload answer
  sheets, view scores).

**`Frontend/src/styles/style.css`**:
- Removed dead `.dashboard-new-interview` and `.dashboard-new-interview__label`
  CSS blocks (no longer rendered).
- Added `.dashboard-info-banner`, `.dashboard-info-banner__icon`, and `.btn-link`
  styles for the replacement banner.

### Confirmed correct after fix

- Document download on each card: `DocumentActions` calls
  `downloadInterviewDocument(interviewId, fileType)` → `GET /api/interviews/{id}/documents/{type}`
  — the same backend endpoint; no separate implementation.
- Answer-script upload on each card: `AnswerScriptUpload` calls
  `uploadAnswerScript(interviewId, files)` → `POST /api/interviews/{id}/answer-script`
  — completely separate from resume upload (`POST /api/interviews` or
  `POST /api/generate`). Component is labelled "Upload Answer Script", not
  "Upload Resume".
- Evaluate action on each card: `handleEvaluate` → `startEvaluation(interview_id)` →
  `POST /api/interviews/{id}/evaluate` — wired correctly, score displayed via
  `EvaluationSummary`.

---

## Task 10 — Evaluator, Scoring, Dashboard & Overrides
Date: 2026-09-14

### Scope
Final task of the 10-task upgrade. Completes the deterministic answer
evaluation engine (Part A), wires the evaluate endpoint and worker queue
(Part B), adds the per-question score override capability (Part C), and
builds the full React Dashboard (Part D) with polling, document downloads,
answer script upload, segmentation correction, and score override UI.

---

### Part A — Deterministic Evaluator Service (`app/services/answer_evaluator.py`)

**Design — multi-layer pipeline (zero LLM calls, verified by source inspection):**

| Layer | Implementation |
|---|---|
| 1 Normalization | `_normalize_text`, `_tokenize`, `_stem` (lightweight suffix trimmer for plurals/tenses) |
| 2 Keyword matching | `score_keywords` — exact phrase, synonym expansion, stemmed-token overlap |
| 3 Synonym/concept groups | `TECHNICAL_SYNONYMS` dict + `_expand_tokens`; covers postgres/pg, auth/authentication, js/javascript, db/database, and ~30 more abbreviation pairs |
| 4 Phrase matching | `score_phrases` — normalized phrase in text, synonym multi-word equivalents, partial token overlap for 2+ word phrases (≥ 65% overlap → 0.8 credit) |
| 5 TF-IDF cosine similarity | `build_tfidf_corpus` / `tfidf_vectorize` / `cosine_similarity` — corpus built **once per interview** from ALL sample answers + concept/phrase text (amendment §9 fix: avoids degenerate 2-document IDF) |
| 6 Required concept coverage | `score_concepts` — weighted lexical/synonym matching; partial stemmed overlap gives partial credit |
| 7 Question-type rules / structure | `score_structure` — length scaling capped by relevance; STAR-marker bonus for behavioral questions; irrelevant long answers score 0 on structure (spec §53) |
| Weighted final score | `evaluate_single_question` — `0–10` per question |

**Configurable weights (env vars, normalized to sum to 1.0 at runtime):**
```
KEYWORD_WEIGHT    = 0.25  (KEYWORD_WEIGHT env var)
CONCEPT_WEIGHT    = 0.40  (CONCEPT_WEIGHT)
PHRASE_WEIGHT     = 0.15  (PHRASE_WEIGHT)
SIMILARITY_WEIGHT = 0.10  (SIMILARITY_WEIGHT)
STRUCTURE_WEIGHT  = 0.10  (STRUCTURE_WEIGHT)
```

**Special states handled explicitly (per spec §49–§52 / amendment §7):**
- `[BLANK]` / `status=BLANK` / empty text → `status=NO_ANSWER`, `score=0`, never OCR failure
- `[ILLEGIBLE]` / `status=ILLEGIBLE` → `status=OCR_FAILED`, `score=None` (N/A), never silently 0
- `status=UNCERTAIN` / `SEGMENTATION_UNCERTAIN` → `status=UNCERTAIN`, `score=None`, held out of overall total until manually resolved
- MCQ: `_check_mcq_answer` matches exact letter, `B) text`, `OPTION B`, or the full option body — correct = 10/10, incorrect = 0/10

**Deterministic feedback strings (evidence thresholds, no LLM):**
- `≥ 80%` → "Excellent coverage of the expected concepts."
- `≥ 60%` → "Good answer with most key concepts covered."
- `≥ 40%` → "Partial coverage. Some important concepts are missing."
- `≥ 20%` → "Limited answer. Several expected concepts were not detected."
- `< 20%` → "Answer does not address the required concepts."
- `NO_ANSWER` → "No answer was provided."
- `OCR_FAILED` → "Unable to evaluate because the answer could not be read reliably."
- `UNCERTAIN` → "Unable to evaluate because question alignment is uncertain."

**`AnswerEvaluationService`:**
- `load_evaluation_keys` — reads `question_evaluation_keys` + `question_concept_keys` from DB
- `evaluate_interview` — builds shared TF-IDF corpus, evaluates all questions, accumulates only `EVALUATED`/`NO_ANSWER` scores (OCR_FAILED and UNCERTAIN excluded from totals)
- `persist_evaluation` — INSERT new `evaluations` row (is_current=True), flip previous rows to is_current=False **in the same transaction** (amendment §3.2 history guarantee), INSERT `question_evaluations` rows with `original_score` stored, UPDATE interview.status=EVALUATED

**EVALUATOR_VERSION** env var stamps each evaluation row for auditability.

---

### Part B — Evaluation API + Worker Wiring

**Worker (`app/services/worker.py`) — third queue added:**
- `claim_next_evaluation` — `SELECT … FOR UPDATE SKIP LOCKED` on `status=EVALUATING` with `processing_stage IS NULL`; sets `processing_stage=EVALUATING_ANSWERS`
- `process_interview_evaluation` — calls `AnswerEvaluationService.evaluate_interview` + `persist_evaluation`
- `mark_evaluation_failed` — sets `status=EVALUATION_FAILED`, stores safe error reason; no stack traces in DB
- `recover_interviews` — extended to clear `processing_stage` on stuck `EVALUATING` rows (crash recovery)
- `process_next_job` now handles three FIFO queues: question-generation → answer-script OCR → evaluation; all driven off the same `interviews` table with SKIP LOCKED

**Migration 005 (`alembic/versions/005_score_overrides.py`):**
- Extended `processing_stage` ENUM: adds `EVALUATING_ANSWERS`
- Added `question_evaluations` columns: `original_score`, `override_score`, `override_reason`, `overridden_by`, `overridden_at`
- Added `question_evaluation_keys` columns: `question_text`, `sample_answer`, `category`, `correct_option`, `options` (for evaluator key loading)
- Round-trip up/downgrade verified

**Endpoints (`app/api/routes.py`):**
- `POST /api/interviews/{interview_id}/evaluate` — sets `status=EVALUATING`, returns immediately (worker picks it up); allowed from `SEGMENTED`, `SEGMENTATION_UNCERTAIN`, `EVALUATED`, `EVALUATION_FAILED`
- `GET /api/interviews/{interview_id}/evaluation` — returns the `is_current=True` evaluation with all `question_evaluations` rows; effective score per question uses `override_score` where present, else `score`

**Schemas (`app/models/schemas.py`) added:**
- `EvaluationStartResponse`, `EvaluationDetailOut`, `QuestionEvaluationOut` (includes `original_score`, `override_score`, `override_reason`, `overridden_by`, `overridden_at`, `is_overridden`), `ScoreOverrideRequest`

---

### Part C — Score Override

**Endpoint:**
- `POST /api/interviews/{interview_id}/evaluation/questions/{question_number}/override`
- Also aliased at: `POST /api/interviews/{interview_id}/questions/{question_number}/override`
- Validates: `0.0 ≤ override_score ≤ 10.0`, `override_reason` non-blank (required)
- Stores: `original_score` preserved if not already set; `override_score`, `override_reason`, `overridden_by="staff"`, `overridden_at` written to `question_evaluations`
- **Never overwrites the original deterministic score in place** (amendment §10)
- Recalculates `evaluations.total_score` / `max_score` / `percentage` from override values where present; all other questions contribute their deterministic score
- Returns: `{ success, interview_id, question_number, original_score, override_score, override_reason, total_score, max_score, percentage }`

---

### Part D — Dashboard (React)

**New files added:**

| File | Purpose |
|---|---|
| `Frontend/src/services/api.js` | Extended with all dashboard/eval API functions (replaces the 2-function MVP version) |
| `Frontend/src/components/DashboardPage.jsx` | Main dashboard page — interview list, new-resume upload, polling |
| `Frontend/src/components/InterviewCard.jsx` | Per-interview card — ID, name, status, stages, docs, upload, eval |
| `Frontend/src/components/ProcessingStages.jsx` | Real pipeline stages (no fake %) for both question-gen and answer-eval flows |
| `Frontend/src/components/DocumentActions.jsx` | Download buttons for `question_sheet` / `answer_key` |
| `Frontend/src/components/AnswerScriptUpload.jsx` | Upload handwritten answer pages (multi-file, drag & drop) |
| `Frontend/src/components/SegmentationCorrectionView.jsx` | Manual block→question alignment for `SEGMENTATION_UNCERTAIN` interviews |
| `Frontend/src/components/EvaluationSummary.jsx` | Overall score display + per-question list |
| `Frontend/src/components/QuestionEvaluation.jsx` | Per-question score, feedback, evidence table, override audit trail |
| `Frontend/src/components/ScoreOverridePanel.jsx` | Inline staff override with required reason; shows original deterministic score |

**Modified files:**

| File | Change |
|---|---|
| `Frontend/src/App.jsx` | Added `'dashboard'` phase; Header gets `onDashboard`/`onHome`/`activePage` props; `DashboardPage` renders when `phase === 'dashboard'` |
| `Frontend/src/components/Header.jsx` | Added `header-nav` with "📋 Dashboard" button and "← Upload" back-link |
| `Frontend/src/styles/style.css` | Appended ~625 lines of dashboard-specific CSS reusing all existing CSS variables, radii, shadows |

**Dashboard polling:**
- Polls `GET /api/interviews` every `VITE_JOB_POLL_INTERVAL_SECONDS` seconds (Vite env var, default 3s)
- Polling stops automatically when every visible interview is in a terminal state (`COMPLETED`, `FAILED`, `EVALUATED`, `EVALUATION_FAILED`)
- Shows "Auto-refreshing every Ns" / "All complete — polling paused" badge
- No fake progress percentages anywhere; `ProcessingStages` renders only real DB stage values

**Dashboard routing:**
- Simple state-based page switching (`phase` in `App.jsx`) — no react-router introduced
- "Dashboard" button in header switches to dashboard phase from any page; "← Upload" / "← Back to Upload" returns to the upload phase
- Dashboard phase is independent of the result/loading phases — navigating to Dashboard mid-result and back preserves the result in state

---

### Test coverage (`tests/test_answer_evaluator.py`, 14 tests)

All assertions are **score bands, not exact numbers** (per spec §70):

| Category | Test | Expected band |
|---|---|---|
| Exact answer | `test_exact_answer_high_score` | `≥ 8.0 / 10` |
| Paraphrased answer | `test_paraphrased_answer_high_score` | `≥ 7.0 / 10` |
| Technical synonym | `test_technical_synonym_recognized` | `≥ 7.0 / 10` |
| Partial answer | `test_partial_answer_medium_score` | `2.0 – 6.5 / 10` |
| Wrong answer | `test_wrong_answer_low_score` | `< 3.5 / 10` |
| Empty / [BLANK] | `test_empty_blank_answer_zero_score` | `score=0, status=NO_ANSWER` |
| Long irrelevant answer | `test_long_irrelevant_answer_low_score` | `< 2.0 / 10, structure_score=0` |
| OCR failure [ILLEGIBLE] | `test_ocr_failure_illegible_score_none` | `score=None, status=OCR_FAILED` |
| Uncertain segmentation | `test_uncertain_segmentation_held_out` | `score=None, status=UNCERTAIN` |
| MCQ correct | `test_mcq_correct_option` | `10.0 / 10` |
| MCQ incorrect | `test_mcq_incorrect_option` | `0.0 / 10` |
| No-LLM verification | `test_no_llm_calls_in_evaluator` | source contains no LLM imports |

**Re-evaluation history guarantee:**
- `persist_evaluation` flips prior `is_current` rows to `False` and INSERTs a new row with `is_current=True` in one transaction — re-running evaluation never loses history; prior evaluation rows remain queryable by `evaluation_id`.

---

### End-to-end walkthrough (sample interview)

1. Staff clicks **📋 Dashboard** in the header.
2. Drag-drops a PDF resume into the "Upload a new resume" strip → clicks **Create Interview**.
3. `POST /api/interviews` returns `INT-20260914-774 / QUEUED` immediately.
4. Dashboard shows the new card. `ProcessingStages` shows "Queued — waiting for worker."
5. Worker claims the row (`PROCESSING/EXTRACTING → GENERATING → FORMATTING → COMPLETED`). Dashboard auto-polls every 3 s and each stage label lights up as it completes.
6. On `COMPLETED`, `DocumentActions` shows ↓ Question Sheet and ↓ Answer Key buttons. Staff prints the question sheet and gives it to the candidate.
7. Candidate writes answers by hand. Staff scans the sheet and uploads it via the **Upload Answer Script** dropzone on the card.
8. Worker OCRs the pages with the handwriting prompt, runs segmentation. If all 20 markers align, status becomes `SEGMENTED`. If not, `SEGMENTATION_UNCERTAIN` and the `SegmentationCorrectionView` appears — staff assigns each block to its question and clicks **Assign** until all are resolved.
9. Staff clicks **Evaluate Answers**. `POST /api/interviews/INT-20260914-774/evaluate` sets `status=EVALUATING`. Worker runs `AnswerEvaluationService.evaluate_interview`, stores results, status becomes `EVALUATED`.
10. Staff clicks **▼ View evaluation**. `EvaluationSummary` shows e.g. `78.0 / 200 — 78.0%`. Each `QuestionEvaluation` row shows score, status badge, feedback, and a **▼ Show detail** expander revealing the 5-layer evidence table.
11. Staff spots Q5 was marked low because the candidate used different terminology. Clicks **✏ Override score**, enters `8.5` and reason "Candidate correctly described the concept using equivalent terminology." → **Apply override**. The overall score recalculates immediately, the override is stored auditably with `original_score` preserved.

---

### Files touched in this task

**Added:**
- `Frontend/src/components/DashboardPage.jsx`
- `Frontend/src/components/InterviewCard.jsx`
- `Frontend/src/components/ProcessingStages.jsx`
- `Frontend/src/components/DocumentActions.jsx`
- `Frontend/src/components/AnswerScriptUpload.jsx`
- `Frontend/src/components/SegmentationCorrectionView.jsx`
- `Frontend/src/components/EvaluationSummary.jsx`
- `Frontend/src/components/QuestionEvaluation.jsx`
- `Frontend/src/components/ScoreOverridePanel.jsx`
- `app/services/answer_evaluator.py` (built in this task)
- `alembic/versions/005_score_overrides.py` (built in this task)
- `tests/test_answer_evaluator.py` (built in this task)

**Modified:**
- `Frontend/src/services/api.js` (extended with all dashboard API functions)
- `Frontend/src/App.jsx` (dashboard phase + routing)
- `Frontend/src/components/Header.jsx` (Dashboard button)
- `Frontend/src/styles/style.css` (dashboard CSS appended)
- `app/api/routes.py` (evaluate + override endpoints)
- `app/models/schemas.py` (eval/override schemas)
- `app/services/worker.py` (evaluation queue + recovery)
- `app/db/models.py` (EVALUATING_ANSWERS stage + override columns)

---

## Task 9 — Answer Script Upload, Handwriting OCR & Segmentation
Date: 2026-09-14

### Scope
Added the answer-script upload → OCR → deterministic segmentation pipeline
that sits between question generation (Task 8) and evaluation (Task 10).
Scanned handwritten pages are uploaded as RECORD files (`ANSWER_SCRIPT`), the
worker OCRs them with a handwriting-specific prompt that emits `[BLANK]` /
`[ILLEGIBLE]` markers, and the segmented blocks are stored in a new
`answer_segments` table. Manual re-derivation of the segmentation status is
available after a human corrects block-to-question alignment.

### Design decisions
- **No guessing on bad markers.** If the detected question numbers are not
  exactly `1..N` each once, the interview is `SEGMENTATION_UNCERTAIN` and
  the blocks are kept in document order for human review. A missing or
  duplicate marker is never silently inferred.
- `[BLANK]` vs `[ILLEGIBLE]`. Both are emitted verbatim by the OCR prompt
  and parsed deterministically: `BLANK` = no handwriting; `ILLEGIBLE` =
  handwriting present but unreadable. The markers are treated as whole-block
  signals only — text that merely contains one inline is still TRANSCRIBED
  (the marker stays in the transcription for the reviewer).
- Manual override (`POST .../segments/{id}/reassign`) sets
  `is_manual_override=true`, preserves the originally-detected number in
  `original_question_number`, and immediately recomputes the interview's
  segmentation status (exact set equality again, never estimated).
- Answer-script upload is **idempotent re-upload**: previous
  `ANSWER_SCRIPT` files + rows are wiped before the new pages are persisted,
  so a second upload replaces the first.
- Upload is only accepted once the interview has generated questions
  (`COMPLETED`, or already in the answer-script flow); `QUEUED` /
  `PROCESSING` interviews return 409.

### Worker wiring
`process_next_job` now handles two FIFO queues driven from the same
`interviews` table, both using `SELECT ... FOR UPDATE SKIP LOCKED`:

1. **Question generation queue** (existing): `QUEUED` → `PROCESSING` →
   `COMPLETED` (stages EXTRACTING/GENERATING/FORMATTING).
2. **Answer-script queue** (new): `ANSWER_UPLOADED` (stage NULL) → claimed
   as `EXTRACTING_ANSWERS` → `SEGMENTED` or `SEGMENTATION_UNCERTAIN` (stage
   NULL) on success, `FAILED` on failure.

Claim order: pipeline queue first, answer-script queue second. Recovery
resets `PROCESSING` rows to `QUEUED` as before, and clears a stuck
`EXTRACTING_ANSWERS` stage on any `ANSWER_UPLOADED` row (claim-crash safety).

### Handwriting OCR (`app/services/ocr_service.py`)
- Refactored `_extract_with_llm` to accept a prompt + temperature.
- New `ocr_handwriting_image(bytes)` and `ocr_handwriting_pdf(path)` use a
  handwriting-specific prompt that requires `[BLANK]` / `[ILLEGIBLE]`
  markers for empty/unreadable regions.
- Prompt exported as `BLANK_MARKER` / `ILLEGIBLE_MARKER` constants so the
  segmentation module imports a single source of truth.

### Segmentation (`app/services/answer_segmentation.py`)
- Marker regex at start-of-line supports `Question 1`, `Q1`, `Answer 3`,
  `Q no. 4`, with a colon/dot/bracket following the number consumed so
  segment content is the answer text, not `: text`.
- Unnumbered preamble is kept as a `None`-numbered block (review target).
- `matches_question_numbers(segments, question_count)` used both by the
  automatic matcher and by the post-reassign recompute path.

### Schema / config
- Migration `004_answer_scripts`:
  - Extends `processing_stage` with `EXTRACTING_ANSWERS`.
  - Extends `interview_status` with `SEGMENTED`, `SEGMENTATION_UNCERTAIN`.
  - Creates the `answer_segment_status` enum (`TRANSCRIBED` / `BLANK` /
    `ILLEGIBLE`) and the `answer_segments` table (id, interview_id FK
    CASCADE, question_number NULLable, content TEXT, status, is_manual_override,
    original_question_number NULLable, timestamps).
  - `trg_answer_segments_updated_at` trigger added for consistency.
  - Round-trip verified.
- `app/db/models.py`: `AnswerSegment` model + all new enum values.
- `ANSWER_SCRIPT_MAX_FILE_SIZE_MB` setting (default 10), `.env.example`.

### Endpoints added (`app/api/routes.py`)
- `POST /api/interviews/{interview_id}/answer-script` — upload one or more
  scanned pages (multipart `files`). Validates via the shared
  `validate_file`, persists as `ANSWER_SCRIPT` record files, sets
  `status=ANSWER_UPLOADED`. 400 on empty/invalid files, 404 on unknown
  interview, 409 when the interview has not finished question generation.
- `GET /api/interviews/{interview_id}/segments` — lists segments (document
  order, `question_number` nulls last) plus `matched`, `status`,
  `processing_stage`. 409 when the interview has not been segmented yet.
- `POST /api/interviews/{interview_id}/segments/{segment_id}/reassign` —
  human correction of a segment's question number. Returns the updated
  segment plus the recomputed `status`/`matched` values. 400 on
  `question_number < 1`, 404 on unknown segment/interview.

### Test coverage added (`tests/test_answer_scripts.py`, 17 tests)
**Pure segmentation logic (no DB, no network):**
- Clean markers 1..2 → `matched=True`, correct content.
- Unnumbered preamble + short markers → matched, preamble kept.
- Missing marker → `matched=False`, never guessed.
- Duplicate marker → `matched=False`.
- Empty region → `BLANK`, not confused with text containing `[BLANK]`.
- `[ILLEGIBLE]` marker correctly classified.
- Mixed `[BLANK]` + `[ILLEGIBLE]` correctly distinguished.

**Endpoint + DB path:**
- Valid upload persists `ANSWER_SCRIPT` files on disk and in `files`, sets
  `status=ANSWER_UPLOADED`.
- Multi-page upload + idempotent re-upload (replaces, not accumulates).
- Invalid extension → 400.
- `QUEUED` interview → 409.
- Unknown interview → 404.

**Worker + status flow:**
- Uploaded scripts → `SEGMENTED` through the worker (OCR stubbed).
- No question keys → `FAILED` (PipelineError from segmentation guard).
- Startup recovery clears `EXTRACTING_ANSWERS` on `ANSWER_UPLOADED`.

**Manual override:**
- Reassign flips `is_manual_override`, stores `original_question_number`,
  and recomputes `status` to `SEGMENTED` when the set becomes clean.
- `question_number < 1` → 400.

Full suite: **57 passed, 1 deselected**.

### Files touched
- Added: `app/services/answer_segmentation.py`,
  `app/services/answer_script_service.py`,
  `alembic/versions/004_answer_scripts.py`,
  `tests/test_answer_scripts.py`
- Modified: `app/db/models.py` (AnswerSegment model + new enum values),
  `app/models/schemas.py` (AnswerScriptUploadResponse, SegmentReassignRequest,
  AnswerSegmentOut), `app/api/routes.py` (three new endpoints + imports),
  `app/services/ocr_service.py` (handwriting OCR functions, refactored
  _extract_with_llm), `app/services/worker.py` (answer-script claim loop,
  recovery for ANSWER_UPLOADED), `app/config.py`, `.env.example`

---

## Task 8 — Job Queue & Worker (DB-Persisted State, Crash Recovery)
Date: 2026-09-14

### Scope
Wired the previously-synchronous generation pipeline (interview creation →
resume extraction → LLM + evaluation-key → documents) into a real queue and
worker. All job state is persisted in the `interviews` table — `status`,
`processing_stage`, and a new stored `error_reason` — with **no in-process
queue, dict, or variable** holding job state. `POST /api/interviews` (Task 3)
only enqueues (`status = QUEUED`) and returns immediately; all processing now
happens in the worker.

### Worker implementation approach
- A lightweight in-process **polling loop** started by the FastAPI lifespan
  (`app/main.py`). No Celery/Kafka/RabbitMQ/Redis. The blocking pipeline runs
  in a worker thread via `asyncio.to_thread` so it never stalls the event
  loop; the loop sleeps `WORKER_POLL_INTERVAL_SECONDS` (default 2) between
  claims. Disabled under tests (`WORKER_ENABLED=false` in
  `tests/conftest.py`; tests drive the worker explicitly).
- `app/services/worker.py`:
  - `claim_next_interview` — claims the oldest `QUEUED` row with Postgres
    `SELECT ... FOR UPDATE SKIP LOCKED` (oldest by PK), then commits
    `status=PROCESSING`. Safe with more than one worker without a rewrite.
  - `process_next_job` — claim + run, one job per call; returns whether a job
    ran. A pipeline failure marks that interview `FAILED` with a safe stored
    reason and returns `True`, so the loop keeps going for subsequent jobs.
  - `mark_failed` — `status=FAILED`, `processing_stage=NULL`, and a one-line
    `error_reason` (`Type: message`, capped at 500 chars). **Stack traces are
    logged server-side only, never stored or exposed via the API.**
  - `run_worker_forever` / `run_startup_recovery` — the loop and the boot
    recovery entrypoint.
- `app/services/pipeline_service.py` — `run_pipeline` executes the stages
  built in Tasks 3/5/7 and commits each transition so the dashboard (Task 10)
  sees real stages, not fake progress:
  - `PROCESSING + EXTRACTING` → extract resume text (reuses the existing
    `extract_pdf_text` / `ocr_image` / `clean_resume_text` /
    `validate_resume_text` / `truncate_resume_text` logic unchanged) from the
    `RESUME` record file.
  - `PROCESSING + GENERATING` → `generate_interview_questions` (LLM) then
    `save_interview_evaluation_keys`.
  - `PROCESSING + FORMATTING` → `generate_and_persist_documents` (question
    sheet + answer key), plus `candidate_name` capture.
  - `COMPLETED` (stage NULL). A domain `PipelineError` carries safe messages.

### Claiming strategy
`SELECT ... FOR UPDATE SKIP LOCKED` inside an explicit transaction, ordered by
interview PK ascending, limited to one row. The lock is held until the claim's
`status=PROCESSING` update commits — at which point the committed status, not
the lock, is what prevents a second worker from re-claiming. Concurrent
workers each grab a distinct row or none, never the same row.

### Startup recovery / retry-safety decision
- `recover_interviews` resets anything left in `status=PROCESSING` (with any
  of `EXTRACTING`/`GENERATING`/`FORMATTING`, or no stage — a claim-crash) back
  to `QUEUED` with `processing_stage=NULL` so no row is ever stuck. Terminal
  states (`FAILED`, `COMPLETED`, and evaluation-pipeline states such as
  `EVALUATED`) are never touched.
- **Documented decision — resetting to QUEUED is always safe here.** The
  pipeline never persists partial artifacts: evaluation keys are only written
  after the LLM returns a fully-validated `InterviewResult` (its in-provider
  retry handles transient parse failures), and re-runs **wipe and rewrite**
  prior evaluation keys (already idempotent in Task 5) and **wipe prior
  document rows + files before regenerating** (`document_service` made
  idempotent in this task). The only unattempted risk is a lost in-flight LLM
  call being billed again on retry — it cannot be distinguished from
  "never billed", and since nothing irreversible is persisted, re-running is
  safe rather than guessing with `FAILED`. Evaluation-pipeline states
  (`ANSWER_UPLOADED`/`EVALUATING`) are Tasks 9-10 concerns and are left alone
  here.

### Request-path cleanup (§ task item 5)
`POST /api/interviews` already only enqueued (`QUEUED`) since Task 3, and no
request handler ever called the eval-key/document persistence services — the
direct calls existed only in Task 5/7 tests. Confirmed and unchanged: those
services are now invoked exclusively by the worker.

### Schema / config
- Migration `003_error_reason`: `interviews.error_reason TEXT NULL` (store the
  safe failure reason). Round-trip verified against Postgres.
- `InterviewDetail` schema + `GET /api/interviews/{id}` now expose
  `error_reason` (safe message only).
- New settings `WORKER_ENABLED` (default true) and
  `WORKER_POLL_INTERVAL_SECONDS` (default 2), documented in `.env.example`.

### Test coverage added (`tests/test_worker.py`, 5 tests)
- `test_worker_end_to_end_reaches_completed` — full pipeline through the
  worker reaches `COMPLETED` (stage NULL, candidate name captured, 2
  evaluation-key rows, RESUME + QUESTION_SHEET + ANSWER_KEY all present on
  disk and in `files`). LLM stubbed at the pipeline boundary.
- `test_worker_failure_marks_failed_and_continues` — a mocked pipeline
  exception produces `FAILED` with a safe `error_reason` (contains the error,
  **no** "Traceback") and the very next job still reaches `COMPLETED` — a
  failure never crashes the loop.
- `test_startup_recovery_resets_inflight_and_reprocesses` — a row manually
  stuck in `PROCESSING/GENERATING` is re-queued by `run_startup_recovery` and
  reprocessed to `COMPLETED`.
- `test_recover_interviews_resets_claim_crash_then_picks_oldest` — covers a
  stage-less claim-crash, oldest-first claiming, and that a second claim finds
  the remaining row / then `None`.
- `test_recover_interviews_leaves_terminal_rows_alone` — terminal
  (non-`PROCESSING`) rows are untouched by recovery.
- Full suite: **40 passed, 1 deselected** (pre-existing flaky LLM OCR test).
- `tests/conftest.py` added: forces `WORKER_ENABLED=false` so the background
  loop never races tests.

### Files touched
- Added: `app/services/pipeline_service.py`, `app/services/worker.py`,
  `alembic/versions/003_error_reason.py`, `tests/test_worker.py`,
  `tests/conftest.py`
- Modified: `app/main.py` (lifespan: recovery + worker),
  `app/services/document_service.py` (idempotent regeneration),
  `app/db/models.py` + `app/models/schemas.py` + `app/api/routes.py`
  (`error_reason`), `app/config.py`, `.env.example`

### Bonus fix discovered by a live run of the worker
- `app/prompts/interview_prompt.py`: `build_user_prompt`'s f-string had
  unescaped JSON braces (`{"name": string, "weight": number}`), which Python
  parsed `"name"` as a replacement expression with ` string, "weight":
  number` as its format spec, raising `ValueError: Invalid format specifier`
  on **every** LLM call. This is why the "flaky" `test_generate_with_valid_pdf`
  actually failed deterministically. Braces are now escaped and the real LLM
  path was verified live (interview reached `COMPLETED` through the worker).
  That test's resume fixture was also below `MIN_RESUME_TEXT_LENGTH`; its text
  was lengthened and it now passes when an LLM key is present. It remains
  deselected in the default suite because it requires a live key + network.

---

## Task 7 — Document Generation Wired to New Model
Date: 2026-09-14

### Scope
Connected the project's existing python-docx generation logic to the new
interview / evaluation-key data model. Reuses the existing MVP DOCX style
unchanged; adds generation of the two new RECORD documents required by the
upgrade — the Interview Question Sheet and the Answer Key — persists them as
`files` rows, and adds download endpoints that resolve documents via the DB
(never via raw client-supplied paths).

### Reused unchanged (`app/services/document_generator.py`)
- `generate_docx` — the legacy Interviewer/HR/Candidate role generation:
  role titles, candidate header, profile summary, section ordering, MCQ
  rendering, per-role answer blocks, and the DOCX base font/margin setup.
  Zero changes to its output.
- To avoid duplicating that logic, the shared pieces (Calibri font + dark
  body color, 0.8" margins, the company heading, candidate line, section
  label mapping with the original substring matching, and category ordering)
  were factored into private helpers (`_apply_doc_base`, `_add_doc_header`,
  `_ordered_categories`, `_section_header`) that `generate_docx` itself now
  also uses — its behavior/output is unchanged.

### Added (`app/services/document_generator.py`)
- `generate_question_sheet(result, *, interview_id)` — the ONLY document given
  to the interviewee:
  - Header: company name, Interview ID, candidate name, instruction notice.
  - Each question numbered (`Q1. ...`) and grouped under the same sections as
    the existing role documents.
  - MCQ options rendered; open questions get labelled "Your answer:" ruling
    lines for handwritten responses.
  - Deliberately contains **no** sample answers, correct options, keywords,
    concepts, or important phrases (asserted by tests).
- `generate_answer_key(result, *, interview_id)` — internal only:
  - Each question with its sample answer, the correct option for MCQs, and
    the Task 5 evaluation-key metadata in a readable reference format:
    `Keywords: ...`, `Required Concepts: <name> (<weight as %>)`,
    `Important Phrases: "..."`.

### Persistence (Task 6 convention)
- `app/services/document_service.py` (new):
  - `generate_and_persist_documents(session, *, interview, result)` — calls
    the two generators synchronously (in the same code path Task 5's
    evaluation-key flow used, since the Task 8 worker isn't wired up yet),
    writes each via `file_store.persist_record(..., file_type=..., ext=".docx")`
    into `uploads/<interview_id>/QUESTION_SHEET_<uuid>.docx` /
    `ANSWER_KEY_<uuid>.docx`, and inserts `files` rows with
    `file_type = QUESTION_SHEET / ANSWER_KEY` (the Postgres ENUM values).
    Task 8 will move this call into the worker pipeline without touching the
    generation logic.
  - `get_document_file(session, *, interview_pk, file_type)` /
    `list_documents(...)` — DB-backed lookups for download/list; the module
    owns the lowercase-API-name ↔ ENUM-value mapping
    (`question_sheet` → `QUESTION_SHEET`, `answer_key` → `ANSWER_KEY`).

### Endpoints added (`app/api/routes.py`)
- `GET /api/interviews/{interview_id}/documents` — lists generated documents
  (lowercase `file_type`, `file_path`, `created_at`) for an interview.
- `GET /api/interviews/{interview_id}/documents/{file_type}` — serves the
  document as `.docx`. Validates `file_type` is in
  `{question_sheet, answer_key}`, resolves the path via the `files` table for
  the given interview (never accepts a raw path/filename), and confirms the
  file exists on disk before streaming. 400 on bad file_type, 404 on unknown
  interview / missing document.
- Legacy `POST /api/download/docx` unchanged; the inline
  `fastapi.responses` import it carried was hoisted to the module top.

### Test coverage added (`tests/test_documents.py`)
- `test_question_sheet_contains_no_answers_or_keywords` — sheet shows the
  questions + Interview ID, and contains none of the answers/eval-key labels
  or terms.
- `test_answer_key_contains_answer_and_evaluation_key_metadata` — key shows
  the sample answer plus keywords, weighted concepts, and phrases.
- `test_both_documents_are_downloadable_by_interview_id` — both are served
  via the download endpoint (valid DOCX) and reported by the list endpoint.
- `test_download_rejects_invalid_file_type` (400),
  `test_download_rejects_unknown_interview` (404),
  `test_download_404_when_document_not_generated` (404).
- 6/6 passing; sample interviews and their record files are cleaned up in
  teardown.

### Files touched
- Added: `app/services/document_service.py`, `tests/test_documents.py`
- Modified: `app/services/document_generator.py` (factored helpers +
  `generate_question_sheet`/`generate_answer_key`; `generate_docx` behavior
  unchanged), `app/api/routes.py` (two new endpoints + hoisted import)

---

## Task 6 — File Lifecycle & Retention
Date: 2026-09-14

### Scope
Fixes the original MVP's "delete everything after processing" behavior and
implements the amendment §6 scratch-vs-record split for the new lifecycle.
Classifies every file-handling path; moves RECORD files to a dedicated
per-interview directory with uuid4 filenames; ensures every RECORD write is
tracked in the `files` table; adds an explicit, scheduled retention/purge
job (`RETENTION_DAYS`) that never touches mid-lifecycle interviews.

### Old cleanup logic — found, classified, fixed
1. `app/api/routes.py` `/api/generate` `finally` block — removes the
   request's own temporary upload buffer written to the **system temp
   directory** via `get_upload_path()`. Classified **SCRATCH** (raw upload
   buffer before extraction): retained as-is.
2. `app/services/file_store.py::delete_stored_file` — the only routine that
   deletes files from the record store. It is now locked down: it only
   deletes the exact relative path recorded in `files.file_path` (never a
   directory, never by scanning), and logs each deletion.
3. `app/services/interview_service.py::create_interview` — the old flow
   wrote the resume *before* the DB transaction and called
   `delete_stored_file` only on a failed transaction (a legit §6 rollback of
   a failed creation). Confirmed: **no request-handling path deletes a RECORD
   file after a successful request**. A test (`test_resume_record_file_persists_after_request`)
   asserts the resume still exists after the creation request completes.

Amendment §6's exception is preserved: a record file written by a failed
transaction attempt is removed during that attempt's rollback, never as
regular request cleanup.

### New storage convention
- RECORD files now live under a per-interview directory:
  `uploads/<interview_id>/RESUME_<uuid4>.pdf` (and similarly for
  QUESTION_SHEET_, ANSWER_KEY_, ANSWER_SCRIPT_, EVALUATION_REPORT_ in later
  tasks). Path in the DB is the relative path from the project root, stored
  verbatim in `files.file_path`.
- Filenames are always safe server-generated uuid4 values (type-prefixed
  for readability), never the client's original filename.
- `persist_record(content, *, interview_id, file_type, ext)` in
  `file_store.py` is the single RECORD-write entry point; the resume file is
  written *inside* the creation transaction (after `interview_id` is known),
  clearing the chicken-and-egg between ID generation and file placement.
- `files.file_path` / `files.file_type` / `files.interview_id` remain the
  source of truth — nothing scans the upload directory.

### Retention job
- `app/services/retention_service.py`:
  - `find_expired_files()` — interviews whose status is `EVALUATED` AND
    whose **latest** evaluation completed more than `RETENTION_DAYS` ago.
    QUEUED/PROCESSING/COMPLETED/EVALUATING interviews are never eligible.
  - `purge_expired_records()` — deletes each eligible record file and its
    `files` row, logging `interview_id`, `file_type`, timestamp (never file
    contents). Keeps the `interviews`/`evaluations` rows — the audit trail —
    and purges only the file records. Page-limited per run (500).
- `scripts/retention_job.py` — standalone cron-style script (no Celery/new
  queue); exits 0/1 and prints a summary. Crontab example in its docstring.
- New env var `RETENTION_DAYS` (default `30`), documented in `.env.example`.
  `purge_expired_records` refuses `RETENTION_DAYS <= 0`.

### Test coverage added
- `tests/test_interviews.py`: `test_resume_record_file_persists_after_request`
  (file exists + under `uploads/<interview_id>/RESUME_` after the request),
  `test_resume_record_file_survives_generate_flow_scratch_cleanup`.
- `tests/test_retention.py`: only EVALUATED+old interviews purge; recent
  EVALUATED and old mid-lifecycle (QUEUED) interviews untouched; evaluation
  rows survive purge while file rows are removed; retention script exits 0.
- Full suite: 29 passed, 1 deselected (pre-existing flaky LLM OCR test).

### Files touched
- Added: `app/services/retention_service.py`, `scripts/retention_job.py`,
  `tests/test_retention.py`
- Modified: `app/services/file_store.py` (per-interview layout,
  `persist_record`, hardened `delete_stored_file`),
  `app/services/interview_service.py` (write-inside-tx),
  `app/config.py` (`RETENTION_DAYS`), `.env.example`,
  `tests/test_interviews.py`

---

## Task 5 — LLM Evaluation-Key Generation
Date: 2026-09-14

### Scope
Extended the LLM prompt/schema/service so every generated question carries a
deterministic evaluation key — `keywords`, `required_concepts` (with weights),
and `important_phrases` — with server-side weight normalization per amendment
§9, alongside the existing technical `answer`/`hr_answer`. A new migration
persists these keys per question as structured, queryable tables (not an
opaque JSON blob) so the deterministic evaluator (Task 10) can consume them.
Implemented and tested as a standalone service call; no worker/queue wiring.

### Weight normalization (amendment §9)
- LLMs are not reliable at exact arithmetic, so weights that do not sum to
  exactly 1.0 are **normalized server-side** after parsing (each weight is
  divided by the total) — never rejected.
- Validation **failures (which trigger the existing retry-once LLM path) are
  limited to**: `required_concepts` empty, weights missing, weights
  non-numeric, or a non-positive total (i.e. normalization itself is
  impossible).
- Normalization lives in a Pydantic `field_validator` on
  `QuestionAnswer.required_concepts`, so it runs identically for every
  provider (Gemini fallback chain and OpenAI retry inherits it automatically).

### Prompt changes (`app/prompts/interview_prompt.py`)
- New mandatory per-question fields in the system prompt's rules and the
  REQUIRED JSON structure: `keywords` (5–10 core terms), `required_concepts`
  (array of `{"name", "weight"}` with a "roughly sum to 1.0, exact not
  required" instruction), `important_phrases` (4–6 exact/near-exact phrases).
- `build_user_prompt` reminders updated to require all three key parts for
  every question. No new question types or category changes.

### Persistence (migration `002_evaluation_keys`)
- `question_evaluation_keys` — one row per `(interview_id, question_number)`
  with `keywords` and `important_phrases` as Postgres `TEXT[]` arrays
  (queryable, not a blob), UNIQUE on `(interview_id, question_number)`.
- `question_concept_keys` — one row per weighted concept
  (`question_key_id → question_evaluation_keys.id`, `name`, `weight`),
  indexed by question.
- Both FKs are `ON DELETE CASCADE` from `interviews`; `002` revises `001`.
- `app/services/evaluation_key_service.py::save_interview_evaluation_keys`
  wipes any prior keys for the interview then re-inserts (idempotent for
  re-generation); stores the **normalized** weights.

### Endpoints / schema
- `app/models/schemas.py`: added `Concept` model and required
  `keywords`, `required_concepts`, `important_phrases` on `QuestionAnswer`
  plus the normalizing validator. No new API endpoints (persistence is a
  service-layer call the Task 8 worker will invoke).
- `test_api.py::test_download_docx_all_roles` payload updated to satisfy the
  new required fields.

### Verified
- Normalization: `[0.7, 0.7] → [0.5, 0.5]`; `[1.0, 1.5, 2.5] → `
  `[0.2, 0.3, 0.5]`; sum-1.0 weights pass through unchanged.
- Empty / missing / non-numeric weights raise validation errors (driving the
  LLM retry path).
- Persistence round-trip + idempotent re-save + `ondelete CASCADE` cleanup
  verified against running PostgreSQL.
- `alembic upgrade head` / `downgrade -1` / `upgrade head` round-trip clean.
- Full test suite: 23 passed, 1 deselected (pre-existing flaky LLM OCR test).

### Files touched
- Added: `alembic/versions/002_evaluation_keys.py`,
  `app/services/evaluation_key_service.py`, `tests/test_evaluation_keys.py`
- Modified: `app/prompts/interview_prompt.py`, `app/models/schemas.py`,
  `app/db/models.py`, `app/db/__init__.py`, `tests/test_api.py`

---

## Task 3 — Interview ID Generation + Creation API
Date: 2026-09-14

### Scope
Implemented interview creation end-to-end: resume upload → persisted record
file → `QUEUED` interview row with a race-free `interview_id`, plus a
single-interview detail endpoint. No auth, LLM/evaluation-key generation, or
job worker (those are Tasks 4/5/8).

### ID-generation approach (amendment §2)
Race-free `INT-{YYYYMMDD}-{id:03d}` inside one transaction — **no
read-then-increment** anywhere:

1. `Interview` row INSERTed first (with a unique server-side
   `PENDING-<uuid>` placeholder for the NOT NULL `interview_id`), letting
   Postgres assign the real SERIAL PK.
2. `interview_id = build_interview_id(created_at, pk)` derived from that PK
   in `app/services/interview_service.py`.
3. Row UPDATE'd with the derived ID before commit; the derived suffix
   exactly matches the row's PK.
4. The UNIQUE constraint on `interviews.interview_id` (Task 2) is the final
   safety net: a small 3-attempt retry loop re-runs the INSERT on any
   `IntegrityError` rather than assuming the constraint can never fire.
5. The client never supplies or sees a raw generated ID; placeholder values
   are never committed.

### Endpoints added
- `POST /api/interviews` — accepts the resume upload, creates the `QUEUED`
  interview + `files` row (`file_type = RESUME`), returns
  `{ success, interview_id, status }` immediately (no extraction/LLM work).
  For now interviews stay at `QUEUED`; the job worker (Task 8) will pick
  them up.
- `GET /api/interviews/{interview_id}` — returns
  `{ id, interview_id, candidate_name, status, processing_stage, created_at }`;
  404 when unknown.

No changes to the existing synchronous `POST /api/generate` / download
routes — the current React flow still uses them; the async flow replaces
the frontend in a later task.

### File lifecycle (amendment §6)
Uploaded resumes are **record files**: persisted to `uploads/` (`UPLOAD_DIR`
config, default `uploads/`) and referenced by `files.file_path`; they are
never auto-deleted by request cleanup. On a DB failure after writing, the
just-written file is removed so no orphaned file or dangling `files` row
remains. A dedicated retention job is out of scope (later task).

### File-validation logic
`app/utils/file_validation.py::validate_file` is **reused unchanged** for the
creation endpoint — extension/MIME/size/non-empty checks are not duplicated.

### Concurrency test + result
`tests/test_interviews.py::test_concurrent_interview_creation` fires 25
simultaneous `POST /api/interviews` requests (thread pool, real Postgres)
and asserts:
- every `interview_id` matches `INT-\d{8}-\d{3,}` and is **unique**;
- **zero duplicates**;
- gaps in the numeric suffix (from SERIAL) are expected and documented, not
  asserted.

Observed runs: `25 requests -> distinct ids=25, duplicates=0`
(e.g. pk span `109..133` and `209..233` in two runs — both contiguous;
gaps remain acceptable per spec).

### Other changes
- `app/services/interview_service.py` (new) — `build_interview_id`,
  `create_interview`, `get_interview`.
- `app/services/file_store.py` (new) — `persist_resume`, `delete_stored_file`.
- `app/models/schemas.py` — added `InterviewCreateResponse`, `InterviewDetail`.
- `app/config.py` — added `UPLOAD_DIR`.
- `app/api/routes.py` — added the two endpoints.
- `tests/test_interviews.py` (new) — 6 tests incl. the concurrency test;
  every test cleans up its rows and record files.

---

## Task 2 — Clean Schema / Data Model Migration
Date: 2026-09-14

### Scope
Added the core PostgreSQL data model (four tables) exactly per the SPEC 2
Amendment §3 ("Schema — Clean Record Design"), enforced at the schema level,
through a proper Alembic migration with a working downgrade. No routes,
business logic, or services were added or modified.

### Migration file(s) created
- `alembic/versions/001_initial_schema.py` (revision `001_initial`, down_revision `None`)

### Tables added

**`interviews`**
| column | type | constraints |
|---|---|---|
| `id` | SERIAL (INTEGER) | PRIMARY KEY |
| `interview_id` | TEXT | UNIQUE, NOT NULL (display-only string; generation logic deferred to Task 3) |
| `candidate_name` | TEXT | nullable |
| `status` | `interview_status` (ENUM) | NOT NULL |
| `processing_stage` | `processing_stage` (ENUM) | nullable |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now(), auto-updated by trigger |

**`files`**
| column | type | constraints |
|---|---|---|
| `id` | SERIAL (INTEGER) | PRIMARY KEY |
| `interview_id` | INTEGER | NOT NULL, FK → `interviews(id)` ON DELETE CASCADE |
| `file_type` | `file_type` (ENUM) | NOT NULL |
| `file_path` | TEXT | NOT NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

**`evaluations`**
| column | type | constraints |
|---|---|---|
| `id` | SERIAL (INTEGER) | PRIMARY KEY |
| `interview_id` | INTEGER | NOT NULL, FK → `interviews(id)` ON DELETE CASCADE |
| `evaluator_version` | TEXT | NOT NULL |
| `total_score` | NUMERIC | nullable |
| `max_score` | NUMERIC | nullable |
| `percentage` | NUMERIC | nullable |
| `status` | `evaluation_status` (ENUM) | NOT NULL |
| `is_current` | BOOLEAN | NOT NULL, DEFAULT true |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now(), auto-updated by trigger |

**`question_evaluations`**
| column | type | constraints |
|---|---|---|
| `id` | SERIAL (INTEGER) | PRIMARY KEY |
| `evaluation_id` | INTEGER | NOT NULL, FK → `evaluations(id)` ON DELETE CASCADE |
| `question_number` | INTEGER | NOT NULL |
| `score`, `max_score` | NUMERIC | nullable |
| `keyword_score`, `concept_score`, `phrase_score`, `similarity_score`, `structure_score` | NUMERIC | nullable |
| `status` | `question_eval_status` (ENUM) | NOT NULL |
| `feedback` | TEXT | nullable |

### ENUM types added
- **`interview_status`**: `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`, `ANSWER_UPLOADED`, `EVALUATING`, `EVALUATED`, `EVALUATION_FAILED`
- **`processing_stage`**: `EXTRACTING`, `GENERATING`, `FORMATTING`
- **`evaluation_status`**: `PENDING`, `EVALUATED`, `EVALUATION_FAILED`
- **`question_eval_status`**: `EVALUATED`, `NO_ANSWER`, `OCR_FAILED`, `UNCERTAIN`, `SEGMENTATION_UNCERTAIN`
- **`file_type`**: `RESUME`, `QUESTION_SHEET`, `ANSWER_KEY`, `ANSWER_SCRIPT`

### Constraints / indexes added
- `interviews.interview_id` UNIQUE; all PKs; FK CASCADE chains `interviews → evaluations → question_evaluations` and `interviews → files`.
- `uq_evaluations_current` — **partial unique index** `UNIQUE (interview_id) WHERE is_current = true`, guaranteeing at most one current evaluation per interview (schema-level, not app-level).
- `uq_question_eval_per_question` — UNIQUE `(evaluation_id, question_number)` (see deviations).
- `upd_updated_at_column()` trigger function + `trg_interviews_updated_at`, `trg_evaluations_updated_at` (see deviations).
- `interviews`/`evaluations` `created_at`/`updated_at` NOT NULL with server defaults.

### Deviations from the amendment §3 sketch (and reasoning)
1. **`status` / `processing_stage` columns use Postgres ENUMs instead of `TEXT`.** The §3 sketch shows `TEXT` columns but §3.3 explicitly mandates ENUM/CHECK enforcement to prevent typo'd states. Per-task instruction, enums are the chosen mechanism.
   - §3's sketch comment lists `EVALUATED | NO_ANSWER | OCR_FAILED | UNCERTAIN` for `question_evaluations.status`; `SEGMENTATION_UNCERTAIN` (from Amendment §8) was added.
   - §36's main list mixes `EXTRACTING / GENERATING / FORMATTING` into `status`; the §40 API example shows `status=PROCESSING` with `processing_stage=GENERATING`, so those three values were assigned to `processing_stage`, keeping `interview_status` at the coarser lifecycle states.
2. **`updated_at` auto-update trigger.** `DEFAULT now()` only fires on INSERT; a BEFORE UPDATE trigger was added so `updated_at` stays correct on UPDATE without application help.
3. **`uq_question_eval_per_question` unique index** on `(evaluation_id, question_number)`. The sketch doesn't declare it, but the data model implies one per-question row per evaluation run; the constraint prevents accidental duplicates.
4. **`evaluations.status` ENUM values** (`PENDING / EVALUATED / EVALUATION_FAILED`) are not enumerated anywhere in the spec; they were chosen to describe the evaluation *run*, distinct from the per-question `question_evaluations.status`.

### Verified
- `alembic upgrade head` applies cleanly on a fresh DB.
- `alembic downgrade base` rolls back cleanly (tables, ENUMs, indices, triggers all removed).
- Round-trip up → down → up verified.
- Constraint behavior verified against a running PostgreSQL 16: partial unique index (second `is_current=true` rejected), ENUM rejection of bogus values, `ON DELETE CASCADE`, and the `updated_at` trigger.

### Files touched
- Added: `alembic/versions/001_initial_schema.py`, `app/db/models.py` (ORM model definitions only — no query logic)
- Modified: `app/db/__init__.py` (export new models/enums)