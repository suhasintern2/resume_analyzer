# Debug Report: MCQ Answer-Script PDF Upload/OCR/Scoring Pipeline Not Working

## Issue Summary
The MCQ feature as specified in Part D of `mcq_feature_spec.md` is **completely missing from the implementation**. What exists instead is a simplified text-based MCQ upload system that does not match the specification.

## Root Cause Analysis

### 1. Missing Database Tables
The following tables required by the MCQ feature specification do not exist:
- `mcq_bank` - Stores the question bank with sections, sequence_index, question_text, options, correct_option
- `mcq_section_cursor` - Tracks the daily draw position for each section
- `daily_mcq_sets` - Stores daily generated question sets and answer key sequences
- `daily_mcq_results` - Stores candidate results from uploaded answer sheets

**Verification**: Search of `./app/db/models.py` and Alembic migrations shows no references to these tables.

### 2. Missing Implementation of Core MCQ Functionality
The endpoints and processing pipeline described in Part D are absent:

**Specified in Part D (mcq_feature_spec.md)**:
- Upload endpoint accepting scanned PDF/image answer sheets
- OMR processing: deskew/normalize → crop name field → run OCR → measure fill density in 4 bubbles per question → build answer_sequence
- Scoring: positional match against `daily_mcq_sets.answer_key_sequence`
- Results view showing candidate_name + score + answer_sequence detail

**Actual Implementation in `/app/api/routes.py`**:
- `/mcq/day/{day}/upload` (POST) expects a plain text file with format:
  ```
  Candidate ID: 001
  Q1: [answer]
  Q2: [answer]
  ...
  ```
- No OMR/OCR processing
- No bubble sheet detection
- No daily answer key sequence concept
- No candidate name extraction via OCR

### 3. Mismatch Between Spec and Implementation
The existing MCQ system is a **completely different feature** that:
- Expects text uploads, not PDF/image scans
- Uses manual Q1:, Q2: format entry, not bubble sheets
- Does not use OMR or OCR for answer detection
- Does not implement the daily question bank or answer key sequence
- Does not store results in the specified table structure

## Specific Failure Points

When a user attempts to upload a PDF answer sheet with candidate name + bubble marks:

1. **Upload Reception**: The `/mcq/day/{day}/upload` endpoint rejects PDF files (expects text)
   - Would need to modify to accept multipart file uploads
   - Currently only processes `UploadFile` as text via `.read().decode()`

2. **File Processing**: No OMR pipeline invoked
   - No deskewing/normalization
   - No region cropping for name field or question bubbles
   - No OMR fill-density detection
   - No OCR for name field extraction

3. **Daily Question Lookup**: Would fail silently
   - No `daily_mcq_sets` table exists
   - No `_get_day_correct_answers()` function for MCQ feature
   - Lookup would return nothing or throw undefined function error

4. **Scoring**: Never executes
   - No answer sequence built from OMR results
   - No comparison against answer key sequence
   - No score calculation

5. **Result Storage**: Never happens
   - No `daily_mcq_results` table to insert into
   - No result viewing capability

## Evidence from Codebase

### Current MCQ Upload Endpoint (`/app/api/routes.py` lines 916-946):
```python
@router.post("/mcq/day/{day}/upload", response_model=MCQUploadResponse)
def upload_mcq_answers(day: int, files: list[UploadFile] = File(...)):
    """Upload completed MCQ answer sheets and get scores.
    
    Each file is parsed to extract candidate names and their answer
    sequences. Answers are compared against the correct answer key
    for the day and individual scores are returned.
    """
    # ... expects text files with "Candidate ID: 001\nQ1: [answer]" format
```

### Missing Components:
- No OMR service integration for bubble detection
- No OCR service for name field extraction  
- No daily question set generation/retrieval
- No result storage mechanism
- No proper error handling for missing data

## Conclusion

The MCQ answer-script PDF upload/OCR/scoring pipeline described in Part D of `mcq_feature_spec.md` is **not implemented at all**. The existing `/mcq/day/{day}/upload` endpoint implements a different, simpler text-based MCQ system that does not process PDF answer sheets, perform OMR/OCCR, or use the daily question bank concept.

To fix this, the complete MCQ feature as specified in Parts A-D of the specification needs to be implemented, including:
1. Database schema for MCQ tables
2. Daily question bank loading and rotation logic
3. OMR-based answer sheet processing pipeline
4. Result storage and viewing endpoints
5. Proper error handling and user feedback