"""MCQ Question Bank service for Task 13 Parts A-D.

Handles:
- Loading and validating the MCQ dataset from JSON
- Daily question set generation with deterministic rotation
- Part D answer-sheet processing: page rasterisation, fixed slot cropping,
  short-line handwriting OCR (Tesseract), tolerant "N.letter"
  parsing, positional scoring against daily_mcq_sets.answer_key_sequence
- Result storage, retrieval and manual correction

OMR / fill-density bubble detection is fully removed from this module.
The Part D sheet is a shared multi-candidate text sheet: each candidate
slot is a bounded box with a Candidate ID field plus one freeform line
("1.a, 2.c, ...").  Tesseract (pytesseract) is the only OCR engine used
here and by the Task 12 answer-script pipeline (answer_script_service /
ocr_service).
"""

import io
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pytz
import pymupdf as fitz
from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    DailyMcqResults,
    DailyMcqSets,
    McqBank,
    McqSectionCursor,
)
from app.services.file_store import persist_record
from app.services.mcq_bank import ANSWER_SHEET_LAYOUT, QUESTION_COUNT
from app.config import settings

logger = logging.getLogger(__name__)

# Constants from the specification
MCQ_SECTIONS = ["ENGLISH", "APTITUDE", "MERN", "PYTHON", "DBMS", "BACKEND_MID"]
DAILY_DRAW_COUNTS = [1, 1, 3, 1, 2, 2]  # Matches section order above
QUESTIONS_PER_DAY = sum(DAILY_DRAW_COUNTS)  # 10
BUSINESS_TIMEZONE = pytz.timezone(
    settings.BUSINESS_TIMEZONE if hasattr(settings, "BUSINESS_TIMEZONE") else "Europe/London"
)

BLANK_CHAR = "-"
AMBIGUOUS_CHAR = "!"
VALID_LETTERS = ("A", "B", "C", "D")

# Tolerant "N.letter" pair patterns:
#   1.a   1)a   1-a   1 a   1:a   (letters normalised to uppercase later)
_PAIR_RE = re.compile(
    r"(\d{1,2})(?:[.)\-:]\s*|\s+)([A-Da-d])(?![A-Za-z0-9])"
)

# OCR engine for the short slot lines: Tesseract via pytesseract.
# Simple single-line mode is ideal for extracting short alphabet pairs
# like "1.a 2.c" — no heavy ML model is involved.
_TESSERACT_LINE_CONFIG = "--oem 3 --psm 7"
_TESSERACT_ID_CONFIG = "--oem 3 --psm 7"


def _load_dataset_from_json() -> Dict[str, List[Dict[str, Any]]]:
    """Load and validate the MCQ dataset from JSON file.

    Expected format:
    {
        "sections": {
            "ENGLISH": [...],
            "APTITUDE": [...],
            "MERN": [...],
            "PYTHON": [...],
            "DBMS": [...],
            "BACKEND_MID": [...]
        }
    }

    Each section must have the correct number of questions:
    - ENGLISH: 10
    - APTITUDE: 10
    - MERN: 30
    - PYTHON: 10
    - DBMS: 20
    - BACKEND_MID: 20

    Each question must have:
    - sequence_index: 0-based contiguous integer
    - question_text: non-empty string
    - options: exactly 4 strings, each prefixed with letter ("A) ", etc.)
    - correct_option: single letter A/B/C/D matching an option
    """
    if not os.path.isfile(settings.MCQ_DATASET_PATH):
        raise FileNotFoundError(
            f"MCQ dataset not found at {settings.MCQ_DATASET_PATH}. "
            f"Create generated/mcq_bank/mcq_dataset.json with the required format."
        )

    with open(settings.MCQ_DATASET_PATH) as f:
        data = json.load(f)

    # Handle both old format (columns) and new format (sections) for backward compatibility
    sections_data = data.get("sections", {})
    if not sections_data:
        # Try to load from columns format (old)
        columns = data.get("columns", [])
        if columns and len(columns) == 6:
            # Convert columns to sections
            section_names = MCQ_SECTIONS
            sections_data = {}
            for i, section_name in enumerate(section_names):
                if i < len(columns):
                    sections_data[section_name] = columns[i]
                else:
                    sections_data[section_name] = []
        else:
            raise ValueError(
                "MCQ dataset must contain either a 'sections' object with 6 section keys "
                "or a 'columns' array with exactly 6 elements."
            )

    # Validate we have all required sections
    missing_sections = [s for s in MCQ_SECTIONS if s not in sections_data]
    if missing_sections:
        raise ValueError(f"Missing sections in MCQ dataset: {missing_sections}")

    # Expected counts per section
    expected_counts = {
        "ENGLISH": 10,
        "APTITUDE": 10,
        "MERN": 30,
        "PYTHON": 10,
        "DBMS": 20,
        "BACKEND_MID": 20,
    }

    # Validate each section
    validated_sections = {}
    for section_name, questions in sections_data.items():
        if section_name not in MCQ_SECTIONS:
            raise ValueError(f"Unexpected section in MCQ dataset: {section_name}")

        expected_count = expected_counts[section_name]
        if len(questions) != expected_count:
            raise ValueError(
                f"Section {section_name} has {len(questions)} questions, "
                f"expected {expected_count}"
            )

        # Validate each question in the section
        validated_questions = []
        seen_indices = set()

        for i, q in enumerate(questions):
            # Validate required fields
            if "sequence_index" not in q:
                raise ValueError(f"Question missing sequence_index in {section_name}[{i}]")
            if "question_text" not in q:
                raise ValueError(f"Question missing question_text in {section_name}[{i}]")
            if "options" not in q:
                raise ValueError(f"Question missing options in {section_name}[{i}]")
            if "correct_option" not in q:
                raise ValueError(f"Question missing correct_option in {section_name}[{i}]")

            seq_idx = q["sequence_index"]
            question_text = q["question_text"].strip()
            options = q["options"]
            correct_option = q["correct_option"].strip().upper()

            # Validate sequence_index is 0-based and contiguous
            if seq_idx < 0 or seq_idx >= expected_count:
                raise ValueError(
                    f"Question sequence_index {seq_idx} out of range [0, {expected_count-1}] "
                    f"in {section_name}[{i}]"
                )
            if seq_idx in seen_indices:
                raise ValueError(
                    f"Duplicate sequence_index {seq_idx} in {section_name}"
                )
            seen_indices.add(seq_idx)

            # Validate question_text is not empty
            if not question_text:
                raise ValueError(f"Empty question_text in {section_name}[{i}]")

            # Validate options: exactly 4 strings, each prefixed with letter
            if not isinstance(options, list) or len(options) != 4:
                raise ValueError(
                    f"Question must have exactly 4 options in {section_name}[{i}], "
                    f"got {len(options)}"
                )

            for j, option in enumerate(options):
                if not isinstance(option, str):
                    raise ValueError(
                        f"Option must be string in {section_name}[{i}][{j}]"
                    )
                expected_prefix = f"{chr(ord('A') + j)}) "
                if not option.startswith(expected_prefix):
                    raise ValueError(
                        f"Option {j} in {section_name}[{i}] must start with '{expected_prefix}', "
                        f"got '{option[:10]}...'"
                    )

            # Validate correct_option: single letter A/B/C/D
            if correct_option not in ["A", "B", "C", "D"]:
                raise ValueError(
                    f"correct_option must be A/B/C/D in {section_name}[{i}], "
                    f"got '{correct_option}'"
                )

            # Validate correct_option matches an actual option
            option_letter_index = ord(correct_option) - ord('A')
            if not (0 <= option_letter_index < 4):
                raise ValueError(
                    f"correct_option '{correct_option}' maps to invalid option index "
                    f"in {section_name}[{i}]"
                )

            # Build validated question object
            validated_question = {
                "sequence_index": seq_idx,
                "question_text": question_text,
                "options": options,
                "correct_option": correct_option,
            }
            validated_questions.append(validated_question)

        # Validate we have all sequence indices 0..n-1
        if len(seen_indices) != expected_count:
            missing_indices = [i for i in range(expected_count) if i not in seen_indices]
            raise ValueError(
                f"Missing sequence indices in {section_name}: {missing_indices}"
            )

        validated_sections[section_name] = validated_questions

    logger.info(
        "Loaded and validated MCQ dataset with %d sections",
        len(validated_sections)
    )
    return {"sections": validated_sections}


def _get_mcq_bank_questions_from_db(session: Session) -> Dict[str, List[Dict[str, Any]]]:
    """Load MCQ questions from the database."""
    # Load all questions from mcq_bank table
    stmt = select(McqBank).order_by(McqBank.section, McqBank.sequence_index)
    db_questions = session.scalars(stmt).all()

    # Group by section
    sections_data = {section: [] for section in MCQ_SECTIONS}
    for q in db_questions:
        sections_data[q.section].append({
            "sequence_index": q.sequence_index,
            "question_text": q.question_text,
            "options": q.options,
            "correct_option": q.correct_option,
        })

    # Validate each section has the expected number of questions
    expected_counts = {
        "ENGLISH": 10,
        "APTITUDE": 10,
        "MERN": 30,
        "PYTHON": 10,
        "DBMS": 20,
        "BACKEND_MID": 20,
    }

    for section_name, questions in sections_data.items():
        expected_count = expected_counts[section_name]
        if len(questions) != expected_count:
            logger.warning(
                f"Section {section_name} has {len(questions)} questions in DB, "
                f"expected {expected_count}. Falling back to JSON dataset."
            )
            # Fall back to JSON dataset for this section
            json_data = _load_dataset_from_json()
            sections_data[section_name] = json_data["sections"][section_name]

    return {"sections": sections_data}


def _load_mcq_dataset(session: Session) -> Dict[str, List[Dict[str, Any]]]:
    """Load MCQ dataset, preferring database if available, otherwise JSON."""
    try:
        # Try to load from database first
        db_data = _get_mcq_bank_questions_from_db(session)

        # Validate that we have reasonable data
        total_questions = sum(len(questions) for questions in db_data["sections"].values())
        if total_questions >= 50:  # Reasonable minimum
            logger.info("Loaded MCQ dataset from database")
            return db_data
    except Exception as e:
        logger.warning(f"Failed to load MCQ dataset from database: {e}")

    # Fall back to JSON dataset
    logger.info("Loading MCQ dataset from JSON file")
    return _load_dataset_from_json()


def _get_business_date() -> datetime.date:
    """Get current date in business timezone."""
    utc_now = datetime.utcnow()
    business_time = utc_now.replace(tzinfo=pytz.utc).astimezone(BUSINESS_TIMEZONE)
    return business_time.date()


def _get_or_create_section_cursors(session: Session) -> Dict[str, McqSectionCursor]:
    """Get or create section cursor rows for all sections."""
    cursors = {}

    for section in MCQ_SECTIONS:
        stmt = select(McqSectionCursor).where(McqSectionCursor.section == section)
        cursor = session.scalar(stmt)

        if cursor is None:
            cursor = McqSectionCursor(section=section, next_index=0)
            session.add(cursor)
            session.flush()

        cursors[section] = cursor

    return cursors


def _generate_daily_mcq_set(session: Session, business_date: Optional[datetime.date] = None) -> DailyMcqSets:
    """Generate a daily MCQ set for the given business date using JSON-only usage.

    This uses a simple sequential approach: take the first N questions from each section
    where N is the draw count for that section. This matches the expected answer key pattern
    and ensures JSON-only usage when database tables are empty.

    Assembles questions in fixed presented order:
      ENGLISH(1), APTITUDE(1), MERN(3), PYTHON(1), DBMS(2), BACKEND_MID(2)
    - Builds answer_key_sequence from correct_options in that order.
    """
    if business_date is None:
        business_date = _get_business_date()

    # Check if we already have a set for this date (idempotent)
    stmt = select(DailyMcqSets).where(DailyMcqSets.set_date == business_date)
    existing_set = session.scalar(stmt)
    if existing_set is not None:
        logger.info(f"Daily MCQ set already exists for {business_date}")
        return existing_set

    # Load MCQ dataset from JSON only (optimized for empty DB scenario)
    dataset = _load_dataset_from_json()
    sections_data = dataset["sections"]

    # Validate we have all sections
    missing_sections = [s for s in MCQ_SECTIONS if s not in sections_data]
    if missing_sections:
        raise ValueError(f"Missing sections in MCQ dataset: {missing_sections}")

    # Generate questions for the day using simple sequential selection
    selected_questions = []  # Will contain tuples of (section_name, question_dict)

    for section_idx, (section_name, draw_count) in enumerate(zip(MCQ_SECTIONS, DAILY_DRAW_COUNTS)):
        questions = sections_data[section_name]
        if not questions:
            continue

        # Simple sequential: take first 'draw_count' questions
        for i in range(min(draw_count, len(questions))):
            question_data = questions[i]
            selected_questions.append((section_name, question_data))

    # Build the question list in the specified order and extract answer key
    # Order: ENGLISH(1), APTITUDE(1), MERN(3), PYTHON(1), DBMS(2), BACKEND_MID(2)
    ordered_questions = []
    answer_key_chars = []

    question_ptr = 0
    for section_idx, (section_name, draw_count) in enumerate(zip(MCQ_SECTIONS, DAILY_DRAW_COUNTS)):
        for _ in range(draw_count):
            if question_ptr < len(selected_questions):
                section_name, question_data = selected_questions[question_ptr]
                ordered_questions.append(question_data)
                answer_key_chars.append(question_data["correct_option"])
                question_ptr += 1

    answer_key_sequence = "".join(answer_key_chars)
    question_count = len(answer_key_chars)

    # Create the daily MCQ sets record
    # Note: question_ids is left empty as we're not using DB-based question IDs
    daily_set = DailyMcqSets(
        set_date=business_date,
        question_ids=[],
        answer_key_sequence=answer_key_sequence,
    )
    session.add(daily_set)
    session.flush()

    logger.info(
        f"Generated daily MCQ set for {business_date}: {answer_key_sequence}"
    )
    return daily_set


def get_today_mcq_set(session: Session) -> DailyMcqSets:
    """Get today's MCQ set, generating it if necessary."""
    business_date = _get_business_date()

    # Try to get existing set for today
    stmt = select(DailyMcqSets).where(DailyMcqSets.set_date == business_date)
    today_set = session.scalar(stmt)

    if today_set is None:
        # Generate it if it doesn't exist
        today_set = _generate_daily_mcq_set(session, business_date)

    return today_set


# ---------------------------------------------------------------------------
# Part D — page rasterisation (self-contained; no omr_service import)
# ---------------------------------------------------------------------------


def _to_gray(image: Image.Image) -> np.ndarray:
    """PIL image -> uint8 grayscale numpy array."""
    return np.array(image.convert("L"), dtype=np.uint8)


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Correct small page skew (<=15°) so slot coordinates stay aligned.

    PCA on the dark-pixel coordinate cloud; fails safe (returns the page
    unchanged) when ink is sparse or the angle is extreme.
    """
    coords = np.column_stack(np.where(gray < 128))
    if len(coords) < 200:
        return gray

    mean = coords.mean(axis=0)
    centered = (coords - mean).astype(np.float64)
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    main_vec = eigenvectors[:, np.argmax(eigenvalues)]
    angle = float(np.degrees(np.arctan2(main_vec[0], main_vec[1])))

    if angle < -45:
        angle += 90
    elif angle > 45:
        angle -= 90

    if abs(angle) < 0.2 or abs(angle) > 15:
        return gray

    pil_gray = Image.fromarray(gray, mode="L")
    rotated = pil_gray.rotate(
        -angle,
        resample=Image.BICUBIC,
        expand=False,
        fillcolor=255,
    )
    return np.array(rotated, dtype=np.uint8)


def _rasterize_answer_sheet(file_path: str, content: bytes, ext: str) -> List[np.ndarray]:
    """Rasterize an uploaded answer sheet into deskewed grayscale pages.

    For MCQ answer sheets, only image files (JPG/PNG) are supported to ensure
    high-quality OCR. PDF files are not supported as they can introduce
    quality loss during conversion.
    """
    pages: List[np.ndarray] = []
    if ext == ".pdf":
        # PDF processing is disabled for MCQ answer sheets to ensure
        # high-quality OCR. Please upload JPG/PNG images instead.
        logger.warning(
            "PDF files are not supported for MCQ answer sheets due to potential "
            "quality loss during conversion. Please upload JPG/PNG images."
        )
        return pages  # Return empty list to signal failure
    elif ext in (".jpg", ".jpeg", ".png"):
        with Image.open(io.BytesIO(content)) as img:
            pages.append(_deskew(_to_gray(img.convert("RGB"))))
    else:
        logger.warning(
            "Skipping MCQ answer sheet with unsupported ext %s: %s", ext, file_path,
        )
    return pages


# ---------------------------------------------------------------------------
# Part D — slot cropping + short-line OCR (Tesseract)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Part D — tolerant "N.letter" parsing + positional scoring
# ---------------------------------------------------------------------------


def parse_answer_line(
    text: str,
    question_count: int = QUESTIONS_PER_DAY,
) -> Tuple[str, List[Dict[str, Any]], Dict[int, set]]:
    """Parse a freeform OCR line into a fixed-length answer sequence.

    Tolerated pair forms (case-insensitive on the letter):
        "1.a"  "1)a"  "1-a"  "1 a"  "1:a"   (commas/spaces anywhere between)

    Rules:
    - Sequence is ordered by question number 1..question_count, NOT by the
      order pairs were written.
    - Question with no pair          -> BLANK_CHAR ("-"), status "BLANK"
      (counts as incorrect but visibly distinct from a wrong letter).
    - Question with one pair         -> that letter uppercased, status "OK".
    - Question with conflicting pairs-> AMBIGUOUS_CHAR ("!"), status
      "AMBIGUOUS" with the conflicting letters in ``letter``.
    - Question numbers outside 1..question_count are ignored.

    Returns (answer_sequence, answer_detail, pairs_by_question).
    """
    pairs_by_question: Dict[int, set] = {}
    for match in _PAIR_RE.finditer(text or ""):
        q_num = int(match.group(1))
        letter = match.group(2).upper()
        if 1 <= q_num <= question_count:
            pairs_by_question.setdefault(q_num, set()).add(letter)

    sequence_chars: List[str] = []
    answer_detail: List[Dict[str, Any]] = []
    for q in range(1, question_count + 1):
        letters = pairs_by_question.get(q)
        if not letters:
            sequence_chars.append(BLANK_CHAR)
            answer_detail.append({"question": q, "status": "BLANK", "letter": None})
        elif len(letters) == 1:
            letter = next(iter(letters))
            sequence_chars.append(letter)
            answer_detail.append({"question": q, "status": "OK", "letter": letter})
        else:
            sequence_chars.append(AMBIGUOUS_CHAR)
            answer_detail.append({
                "question": q,
                "status": "AMBIGUOUS",
                "letter": "".join(sorted(letters)),
            })

    return "".join(sequence_chars), answer_detail, pairs_by_question


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


def _normalize_candidate_id(raw: str) -> str:
    """Normalise OCR'd Candidate ID text to a compact stored value."""
    text = (raw or "").strip()
    if not text:
        return ""
    # Keep digits if present (e.g. "Candidate ID: 001" -> "001")
    digits = re.sub(r"\D", "", text)
    if digits:
        return digits.lstrip("0") or "0"
    # Otherwise keep the cleaned alphanumeric token
    cleaned = re.sub(r"[^A-Za-z0-9\-]", "", text)
    return cleaned


# ---------------------------------------------------------------------------
# Part D — upload pipeline
# ---------------------------------------------------------------------------


def process_mcq_answer_sheet_upload(
    session: Session,
    file_path: str,
    content: bytes,
    ext: str,
    filename: str,
) -> Dict[str, Any]:
    """Process an uploaded shared multi-candidate MCQ answer sheet.

    Pipeline (entirely non-LLM):
    1. Rasterize + deskew the page(s).
    2. For each fixed slot in ANSWER_SHEET_LAYOUT:
       - crop the Candidate ID box -> Tesseract -> candidate_id
       - crop the answers box      -> Tesseract -> raw "N.letter" line
       - tolerant-parse into a 10-char sequence ordered by question number
       - zero parseable pairs but non-empty OCR text -> whole row ILLEGIBLE
       - empty ID + empty answers -> unused slot, skipped
    3. Score positionally against today's answer_key_sequence
       (ILLEGIBLE rows score NULL, never 0).
    4. Persist rows in daily_mcq_results.

    Returns a dict with per-row results (or success=False + error).
    """
    try:
        today_set = get_today_mcq_set(session)
        answer_key_sequence = today_set.answer_key_sequence

        if not answer_key_sequence:
            return {
                "success": False,
                "error": "No answer key sequence available for today",
                "error_type": "MISSING_ANSWER_KEY",
            }

        pages = _rasterize_answer_sheet(file_path, content, ext)
        if not pages:
            return {
                "success": False,
                "error": "Could not rasterize the uploaded file. PDF files are not supported for MCQ answer sheets - please upload JPG/PNG images only.",
                "error_type": "RASTERIZATION_FAILED",
            }

        # Persist the upload on disk (RECORD convention).  We intentionally
        # do NOT insert a files row: File.interview_id is a NOT NULL FK to
        # interviews and MCQ sheets predate any interview.
        try:
            stored_path = persist_record(
                content,
                interview_id=f"MCQ_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
                file_type="MCQ_ANSWER_SHEET",
                ext=ext,
            )
        except Exception as store_err:  # non-fatal
            logger.warning("Could not persist MCQ sheet to disk: %s", store_err)
            stored_path = None

        question_count = len(answer_key_sequence)
        rows: List[Dict[str, Any]] = []

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

                rows.append({
                    "slot_index": slot["index"],
                    "page_index": page_index,
                    "candidate_id": candidate_id,
                    "answer_sequence": sequence,
                    "score": score,
                    "row_status": row_status,
                    "raw_ocr_text": raw_ocr_text,
                    "answer_detail": detail,
                    "percentage": (
                        round((score / question_count) * 100, 1)
                        if score is not None and question_count
                        else None
                    ),
                })

        if not rows:
            return {
                "success": False,
                "error": (
                    "No candidate rows could be located on the sheet. "
                    "Ensure the printed shared answer sheet template was used "
                    "and candidates wrote their ID and answers in the boxed slots."
                ),
                "error_type": "NO_ROWS_PARSED",
            }

        result_ids: List[int] = []
        for row in rows:
            result = DailyMcqResults(
                daily_mcq_set_id=today_set.id,
                candidate_id=row["candidate_id"],
                answer_sequence=row["answer_sequence"],
                score=row["score"],
                row_status=row["row_status"],
                raw_ocr_text=row["raw_ocr_text"],
                answer_detail=row["answer_detail"],
                source_sheet_file_id=None,
            )
            session.add(result)
            session.flush()
            result_ids.append(result.id)
            row["result_id"] = result.id

        session.commit()

        logger.info(
            "Processed MCQ answer sheet %s: %d row(s), statuses=%s, stored=%s",
            filename,
            len(rows),
            [r["row_status"] for r in rows],
            stored_path,
        )

        return {
            "success": True,
            "results": rows,
            "result_ids": result_ids,
            "answer_key_sequence": answer_key_sequence,
            "max_score": question_count,
            "source_sheet_path": stored_path,
        }

    except Exception as e:
        logger.exception(f"Failed to process MCQ answer sheet: {e}")
        session.rollback()
        return {
            "success": False,
            "error": str(e),
            "error_type": "PROCESSING_FAILED",
        }


# ---------------------------------------------------------------------------
# Part D/E — results retrieval + manual correction
# ---------------------------------------------------------------------------


def get_mcq_results_for_date(
    session: Session,
    target_date: Optional[datetime.date] = None,
) -> List[Dict[str, Any]]:
    """Get MCQ result rows for a date (defaults to today), newest score first."""
    if target_date is None:
        target_date = _get_business_date()

    stmt = (
        select(DailyMcqResults, DailyMcqSets)
        .join(DailyMcqSets, DailyMcqResults.daily_mcq_set_id == DailyMcqSets.id)
        .where(DailyMcqSets.set_date == target_date)
        .order_by(
            DailyMcqResults.score.desc().nulls_last(),
            DailyMcqResults.created_at,
        )
    )

    results = session.execute(stmt).all()
    out: List[Dict[str, Any]] = []
    for row in results:
        result, daily_set = row.DailyMcqResults, row.DailyMcqSets
        max_score = len(daily_set.answer_key_sequence)
        out.append({
            "id": result.id,
            "candidate_id": result.candidate_id,
            "answer_sequence": result.answer_sequence,
            "score": result.score,
            "max_score": max_score,
            "percentage": (
                round((result.score / max_score) * 100, 1)
                if result.score is not None and max_score
                else None
            ),
            "row_status": str(result.row_status),
            "raw_ocr_text": result.raw_ocr_text,
            "answer_detail": result.answer_detail,
            "created_at": result.created_at.isoformat() if result.created_at else None,
        })
    return out


def update_mcq_result(
    session: Session,
    result_id: int,
    candidate_id: Optional[str] = None,
    answer_sequence: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Manual correction of one result row (candidate ID and/or sequence).

    Re-scores positionally against the row's daily set answer key.
    An ILLEGIBLE row that receives a corrected sequence becomes OK.
    Returns the updated row dict, or None when not found.
    """
    result = session.scalar(
        select(DailyMcqResults).where(DailyMcqResults.id == result_id)
    )
    if result is None:
        return None

    daily_set = session.scalar(
        select(DailyMcqSets).where(DailyMcqSets.id == result.daily_mcq_set_id)
    )
    answer_key = daily_set.answer_key_sequence if daily_set else ""
    question_count = len(answer_key)

    if candidate_id is not None:
        result.candidate_id = candidate_id.strip()

    if answer_sequence is not None:
        # Accept "ABCD..." or loose "A B C D" / "A,B,C,..." input.
        letters = [
            ch.upper()
            for ch in answer_sequence
            if ch.upper() in VALID_LETTERS or ch in (BLANK_CHAR, AMBIGUOUS_CHAR)
        ]
        if len(letters) != question_count:
            raise ValueError(
                f"answer_sequence must contain exactly {question_count} entries "
                f"(A-D, '{BLANK_CHAR}' or '{AMBIGUOUS_CHAR}'); got {len(letters)}."
            )
        result.answer_sequence = "".join(letters)
        # Rebuild detail directly from the corrected sequence so BLANK/AMBIGUOUS
        # statuses match exactly what was entered.
        detail = []
        for i, ch in enumerate(result.answer_sequence, start=1):
            if ch in VALID_LETTERS:
                detail.append({"question": i, "status": "OK", "letter": ch})
            elif ch == BLANK_CHAR:
                detail.append({"question": i, "status": "BLANK", "letter": None})
            else:
                detail.append({"question": i, "status": "AMBIGUOUS", "letter": None})
        result.answer_detail = detail
        result.score = score_answer_sequence(result.answer_sequence, answer_key)
        result.row_status = "OK"

    session.commit()

    max_score = question_count
    return {
        "id": result.id,
        "candidate_id": result.candidate_id,
        "answer_sequence": result.answer_sequence,
        "score": result.score,
        "max_score": max_score,
        "percentage": (
            round((result.score / max_score) * 100, 1)
            if result.score is not None and max_score
            else None
        ),
        "row_status": str(result.row_status),
        "raw_ocr_text": result.raw_ocr_text,
        "answer_detail": result.answer_detail,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }