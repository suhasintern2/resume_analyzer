# MCQ OCR Pipeline Fix Plan

## Issue Summary
The user reports the current OCR pipeline for candidate answer sheets is broken because:
1. Raw Tesseract is run on the whole page with no preprocessing or region targeting
2. This produces garbage output like "OK / ---------- / 0 / 10 / 0% / Correct / SO" and "ILLEGIBLE"
3. The grading step appears to hardcode "Correct" regardless of actual comparison

## Current Implementation Location
Based on previous examination, the OCR and answer sheet processing is in:
- File: `app/services/mcq_service.py`
- Functions:
  - `_ocr_slot_text` (lines ~540-564): Current Tesseract OCR call
  - `_crop_slot` (lines ~518-537): Crops regions for OCR
  - `process_mcq_answer_sheet_upload` (lines ~657-821): Main processing pipeline
  - Score calculation: Uses `score_answer_sequence` function (lines ~622-635)

## Current OCR Implementation (to be replaced)
From previous examination of mcq_service.py:

```python
def _ocr_slot_text(crop: Image.Image, config: str = _TESSERACT_LINE_CONFIG) -> str:
    """OCR one cropped slot with Tesseract in single-line mode.
    
    Upscales and auto-contrasts first — short handwritten alphabet pairs
    ("1.a 2.c") read far more reliably this way.  Returns "" on any failure
    (caller decides how to interpret empty text).
    """
    try:
        import pytesseract
    except ImportError:
        logger.error("pytesseract not installed — cannot OCR MCQ answer sheets")
        return ""

    try:
        # Upscale for better recognition of small handwriting.
        w, h = crop.size
        scale = max(1, int(80 / max(1, h)))
        if scale > 1:
            crop = crop.resize((w * scale, h * scale), Image.LANCZOS)
        crop = ImageOps.autocontrast(crop)
        text = pytesseract.image_to_string(crop, config=config)
        return (text or "").strip()
    except Exception as e:
        logger.warning("Tesseract OCR failed for slot crop: %s", e)
        return ""

# Config constants:
_TESSERACT_LINE_CONFIG = "--oem 3 --psm 7"
_TESSERACT_ID_CONFIG = "--oem 3 --psm 7"
```

## Grading Function Location
The scoring happens in:
- `score_answer_sequence` function (lines ~622-635):
```python
def score_answer_sequence(
    answer_sequence: str,
    answer_key_sequence: str,
) -> int:
    """Positional char-by-char comparison. No fuzzy matching.

    Only an exact A/B/C/D letter in the expected position counts.
    BLANK ("-",) / AMBIGUOUS ("!") always count as incorrect.
    """
    score = 0
    for given, correct in zip(answer_sequence or "", answer_key_sequence or ""):
        if given == correct and given in VALID_LETTERS:
            score += 1
    return score
```

This function appears correct - it does actual comparison, not hardcoded "Correct". However, the user claims there's hardcoding, so I need to verify where the actual grading happens in the upload pipeline.

Looking at `process_mcq_answer_sheet_upload`:
- Line ~743: `score = score_answer_sequence(sequence, answer_key_sequence)`
- This looks correct.

Let me re-examine the user's complaint about "garbage like 'OK / ---------- / 0 / 10 / 0% / Correct / SO' and 'ILLEGIBLE'" - this sounds like it might be coming from a different endpoint or different part of the system.

Actually, looking back at the routes.py file, there's an older MCQ endpoint at lines ~79-101 that had a different implementation:

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

This older endpoint (which the DEBUG_MCQ_PIPELINE.md mentioned) does expect text uploads, not PDF/image processing. And it might have the hardcoded "Correct" issue.

But the user's current message talks about "scanned/photographed candidate answer sheets" and "uploaded as an image, not PDF", which matches the newer system in mcq_service.py that processes PDF/JPG/PNG files.

Let me proceed with the assumption that we need to fix the OCR pipeline in mcq_service.py's `process_mcq_answer_sheet_upload` function and related OCR helpers.

## Fix Approach
Based on the user's detailed instructions, I need to:

**STEP 1**: Show current broken code (OCR call and grading function)
**STEP 2**: Implement image preprocessing (grayscale, deskew, binarize, denoise, upscale)
**STEP 3**: Implement ROI extraction per answer blank (using template coordinates or line detection)
**STEP 4**: OCR each cropped region with targeted Tesseract config
**STEP 5**: Implement confidence thresholding
**STEP 6**: Fix grading (ensure actual comparison, not hardcoded)
**STEP 7**: Maintain output schema consistency
**STEP 8**: Verify with test samples

Let me first show the current code as requested in STEP 1.