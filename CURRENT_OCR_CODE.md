# CURRENT OCR AND GRADING CODE IN MCQ SERVICE

## File: app/services/mcq_service.py

### Current OCR Configuration (Lines 67-68)
```python
# OCR engine for the short slot lines: Tesseract via pytesseract.
# Simple single-line mode is ideal for extracting short alphabet pairs
# like "1.a 2.c" — no heavy ML model is involved.
_TESSERACT_LINE_CONFIG = "--oem 3 --psm 7"
_TESSERACT_ID_CONFIG = "--oem 3 --psm 7"
```

### Current OCR Function (Lines 540-564)
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
        scale = max(1, int(80 / max(1, h))
        if scale > 1:
            crop = crop.resize((w * scale, h * scale), Image.LANCZOS)
        crop = ImageOps.autocontrast(crop)
        text = pytesseract.image_to_string(crop, config=config)
        return (text or "").strip()
    except Exception as e:
        logger.warning("Tesseract OCR failed for slot crop: %s", e)
        return ""
```

### Current Slot Cropping Function (Lines 518-537)
```python
def _crop_slot(gray: np.ndarray, box: Dict[str, float], pad_frac: float = 0.18) -> Image.Image:
    """Crop a normalized (x, y, w, h) box from a grayscale page, with padding."""
    h, w = gray.shape
    x0 = int(w * box["x"])
    y0 = int(h * box["y"])
    x1 = int(w * (box["x"] + box["w"]))
    y1 = int(h * (box["y"] + box["h"]))

    pad_x = int((x1 - x0) * pad_frac)
    pad_y = int((y1 - y0) * pad_frac)
    x0 = max(0, x0 - pad_x)
    y0 = max(0, y0 - pad_y)
    x1 = min(w, x1 + pad_x)
    y1 = min(h, y1 + pad_y)

    if x1 - x0 < 4 or y1 - y0 < 4:
        return Image.new("L", (8, 8), 255)

    crop = gray[y0:y1, x0:x1]
    return Image.fromarray(crop, mode="L")
```

### Current Answer Sheet Processing Pipeline (Lines 657-821)
The main function `process_mcq_answer_sheet_upload` uses the above OCR and cropping functions.

### Current Scoring Function (Lines 622-635)
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

### Current Usage in process_mcq_answer_sheet_upload (Lines ~716-764)
```python
for page_index, gray in enumerate(pages):
    for slot in ANSWER_SHEET_LAYOUT["slots"]:
        id_text = _ocr_slot_text(_crop_slot(gray, slot["id_box"]), _TESSERACT_ID_CONFIG)
        ans_text = _ocr_slot_text(_crop_slot(gray, slot["answers_box"]))

        candidate_id = _normalize_candidate_id(id_text)
        ans_text_clean = (ans_text or "").strip()

        # Unused slot: nothing written at all
        if not candidate_id and not ans_text_clean:
            continue

        raw_ocr_text = f"ID: {id_text.strip()}\nANSWERS: {ans_text_clean}"

        if ans_text_clean:
            sequence, detail, pairs = parse_answer_line(ans_text_clean, question_count)
            if not pairs:
                # Text was present but nothing parseable -> ILLEGIBLE
                row_status = "ILLEGIBLE"
                score = None
                sequence = "[ILLEGIBLE]"
                detail = [
                    {"question": q, "status": "ILLEGIBLE", "letter": None}
                    for q in range(1, question_count + 1)
                ]
            else:
                row_status = "OK"
                score = score_answer_sequence(sequence, answer_key_sequence)
        else:
            # ID present but answer line empty -> explicit all-blank
            row_status = "OK"
            sequence, detail, _ = parse_answer_line("", question_count)
            score = score_answer_sequence(sequence, answer_key_sequence)
```

## Issues Identified in Current Implementation:

1. **OCR Function Issues**:
   - Has a typo: `int(801, h)` should be `int(80 / max(1, h))`
   - Does deskewing happen before calling this? Yes, but the OCR function itself does additional upscaling and autocontrast
   - No confidence scoring is captured
   - No region-specific Tesseract configurations (uses same config for ID and answers)

2. **Processing Pipeline Issues**:
   - Relies on predefined `ANSWER_SHEET_LAYOUT` for slot coordinates
   - If the template doesn't match the actual scan/photo, OCR will fail
   - No image preprocessing (grayscale, deskew, binarize, denoise, upscale) is done before OCR
   - The OCR function does some upscaling and autocontrast, but not the full preprocessing pipeline

3. **Grading/Scoring**:
   - The `score_answer_sequence` function appears correct - it does actual comparison
   - However, if the OCR output is poor due to lack of preprocessing/ROI, scores will be wrong
   - No confidence-based handling - low confidence OCR results are still treated as if they were high confidence

## What Needs to be Fixed:
1. Add proper image preprocessing pipeline (grayscale, deskew, binarize, denoise, upscale)
2. Implement robust ROI detection (either template-based or line detection)
3. Use region-specific Tesseract configurations:
   - Candidate ID: digits only, `--psm 7`
   - Q1-Q5: single character A-D, `--psm 10` or `--psm 8`
   - Q6-Q10: letters+space, `--psm 7`
4. Capture and use OCR confidence scores
5. Implement confidence thresholding
6. Ensure grading uses actual comparison (which it already does, but depends on good OCR)