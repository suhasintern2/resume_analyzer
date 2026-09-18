"""MCQ Question Bank — dataset-driven question paper generation, download,
upload, and scoring (Task 13).

Reads questions from a JSON dataset file (generated/mcq_bank/mcq_dataset.json).
Each day corresponds to one index position across all columns.
The pipeline generates question papers, tracks correct answers, and scores
uploaded answer sheets.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.config import settings

logger = logging.getLogger(__name__)

DAYS = 10
CANDIDATES_PER_DAY = 5
QUESTION_COUNT = 10


def _load_dataset() -> dict[str, list[dict[str, Any]]]:
    """Load the MCQ dataset. Returns dict with 'columns' key, each column
    being a list of question dicts."""
    if not os.path.isfile(settings.MCQ_DATASET_PATH):
        raise FileNotFoundError(
            f"MCQ dataset not found at {settings.MCQ_DATASET_PATH}. "
            f"Create generated/mcq_bank/mcq_dataset.json with the required format."
        )
    with open(settings.MCQ_DATASET_PATH) as f:
        data = json.load(f)

    # Handle both old format (columns) and new format (sections)
    columns = data.get("columns", [])
    if not columns:
        # Try to load from sections format
        sections = data.get("sections", {})
        if sections:
            # Convert sections to columns - each section becomes a column
            columns = list(sections.values())
            logger.info("Loaded MCQ dataset from sections format with %d columns", len(columns))
        else:
            raise ValueError(
                "MCQ dataset has no columns or sections. "
                "The dataset must contain either a 'columns' array or a 'sections' object with question lists."
            )
    else:
        logger.info("Loaded MCQ dataset with %d columns", len(columns))

    return {"columns": columns}


def _get_day_questions(day: int) -> list[dict[str, Any]]:
    """Get questions for a specific day (1-indexed) using the spec's daily draw logic.

    Implements the rotation logic from Part B of the spec:
    - For each section, compute start index = ((day-1) * draw_count) % section_length
    - Draw draw_count questions from each section starting at start index (wrapping around)
    - Return questions in order: ENGLISH(1), APTITUDE(1), MERN(3), PYTHON(1), DBMS(2), BACKEND_MID(2)
    """
    dataset = _load_dataset()
    columns = dataset["columns"]  # List of sections in order: [ENGLISH, APTITUDE, MERN, PYTHON, DBMS, BACKEND_MID]

    # Draw counts per section as specified in the spec
    # ORDER: ENGLISH, APTITUDE, MERN, PYTHON, DBMS, BACKEND_MID
    draw_counts = [1, 1, 3, 1, 2, 2]

    questions = []

    for section_idx, (column, draw_count) in enumerate(zip(columns, draw_counts)):
        if not column:
            continue

        section_length = len(column)
        if section_length == 0:
            continue

        # Compute starting index for this section on this day
        # Formula: start_idx = ((day-1) * draw_count) % section_length
        start_idx = ((day - 1) * draw_count) % section_length

        # Draw 'draw_count' questions starting at start_idx, wrapping around if necessary
        for i in range(draw_count):
            idx = (start_idx + i) % section_length
            q = column[idx]

            # Map dataset fields to expected format
            q = dict(q)  # Create a copy to avoid modifying the original
            q["section_index"] = section_idx  # For debugging/tracing
            q["day"] = day

            # Convert dataset format to service format
            if "question_text" in q:
                q["question"] = q["question_text"]
            if "correct_option" in q:
                # Convert option letter (e.g., "B") to actual answer text
                options = q.get("options", [])
                correct_letter = q["correct_option"]
                if correct_letter and options:
                    # Map A->0, B->1, C->2, D->3
                    option_index = ord(correct_letter.upper()) - ord('A')
                    if 0 <= option_index < len(options):
                        q["correct_answer"] = options[option_index]
                    else:
                        q["correct_answer"] = correct_letter
                else:
                    q["correct_answer"] = correct_letter
            questions.append(q)

    # We should have exactly QUESTION_COUNT questions now (1+1+3+1+2+2=10)
    # But let's verify and handle any edge cases
    if len(questions) != QUESTION_COUNT:
        # This shouldn't happen if the dataset is correctly formatted, but let's be safe
        # If we have too few, pad with fillers
        while len(questions) < QUESTION_COUNT:
            questions.append({
                "number": len(questions) + 1,
                "category": "Fill",
                "question": "",
                "options": [],
                "correct_answer": "",
                "answer": "",
                "plain_answer": "",
                "hr_answer": "",
                "keywords": [],
                "required_concepts": [],
                "important_phrases": [],
            })
        # If we have too many, truncate
        questions = questions[:QUESTION_COUNT]

    # Re-number sequentially
    for i, q in enumerate(questions):
        q["number"] = i + 1

    return questions


def _get_day_correct_answers(day: int) -> list[str]:
    """Get the correct answer sequence for a specific day."""
    questions = _get_day_questions(day)
    return [q["correct_answer"] for q in questions]


def generate_question_paper(day: int, filepath: str | None = None) -> str:
    """Generate a printable MCQ question paper DOCX for a specific day.

    Contains 10 questions with checkbox options, blank answer lines,
    and 5 candidate ID sections. Returns the file path.
    """
    questions = _get_day_questions(day)

    # Validate we have real questions
    empty = [q for q in questions if not q.get("question") or q.get("category") == "Fill"]
    if len(empty) == QUESTION_COUNT:
        raise ValueError(
            f"No valid questions found for Day {day}. "
            f"Ensure {settings.MCQ_DATASET_PATH} has questions in each column "
            f"with at least {day} entries per column."
        )

    if filepath is None:
        os.makedirs(settings.MCQ_STORAGE_DIR, exist_ok=True)
        filepath = os.path.join(settings.MCQ_STORAGE_DIR, f"mcq_paper_day_{day}.docx")

    doc = Document()
    _apply_paper_base(doc)

    # Header
    title = doc.add_heading("VLOOKUP BUISNESS SOLUTION PTV LTD", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title.runs[0]
    title_run.font.size = Pt(16)
    title_run.bold = True

    # Subheading
    subheading = doc.add_heading("CANDIDATE ASSESSMENT ROUND 1", level=1)
    subheading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subheading_run = subheading.runs[0]
    subheading_run.font.size = Pt(14)
    subheading_run.bold = True

    doc.add_paragraph()

    # Questions
    for q in questions:
        q_para = doc.add_paragraph()
        q_run = q_para.add_run(f"Q{q['number']}. {q['question']}")
        q_run.bold = True
        q_run.font.size = Pt(12)
        q_para.paragraph_format.space_after = Pt(4)

        if q.get("options"):
            for opt in q["options"]:
                opt_para = doc.add_paragraph()
                opt_para.paragraph_format.left_indent = Inches(0.5)
                opt_para.paragraph_format.space_after = Pt(2)
                checkbox = opt_para.add_run("☐ ")
                checkbox.font.size = Pt(11)
                opt_run = opt_para.add_run(opt)
                opt_run.font.size = Pt(10)

        # Answer space - single line only
        ans_para = doc.add_paragraph()
        ans_para.paragraph_format.left_indent = Inches(0.5)
        ans_para.paragraph_format.space_after = Pt(2)
        ans_run = ans_para.add_run("Answer: ")
        ans_run.bold = True
        ans_run.font.size = Pt(10)
        ans_para.add_run("_" * 20).font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)
        ans_para.add_run(" (Write correct option only, e.g., A, B, C, D)")
        ans_para.add_run().font.size = Pt(8)
        ans_para.add_run().italic = True

        doc.add_paragraph()

    # Candidate sections (5 candidates) - using Candidate ID instead of name
    doc.add_page_break()
    header = doc.add_heading("Candidate Answer Sheet", level=1)
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for cand_idx in range(CANDIDATES_PER_DAY):
        cand_para = doc.add_paragraph()
        cand_para.paragraph_format.space_before = Pt(12)
        cand_para.paragraph_format.space_after = Pt(6)
        cand_run = cand_para.add_run(f"Candidate ID: {cand_idx + 1:03d} _______________")
        cand_run.bold = True
        cand_run.font.size = Pt(12)

        for q_num in range(1, QUESTION_COUNT + 1):
            ans_para = doc.add_paragraph()
            ans_para.paragraph_format.left_indent = Inches(0.5)
            ans_para.paragraph_format.space_after = Pt(2)
            ans_para.add_run(f"Q{q_num}: ").bold = True
            ans_para.add_run("_" * 20).font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)
            ans_para.add_run(" (Write correct option only)").font.size = Pt(8)
            ans_para.add_run().italic = True

    doc.save(filepath)
    logger.info("Generated question paper for day %d -> %s", day, filepath)
    return filepath


def generate_question_paper_docx(day: int) -> bytes:
    """Generate question paper DOCX as bytes for in-memory handling."""
    questions = _get_day_questions(day)

    doc = Document()
    _apply_paper_base(doc)

    # Header
    title = doc.add_heading("VLOOKUP BUISNESS SOLUTION PTV LTD", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title.runs[0]
    title_run.font.size = Pt(16)
    title_run.bold = True

    # Subheading
    subheading = doc.add_heading("CANDIDATE ASSESSMENT ROUND 1", level=1)
    subheading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subheading_run = subheading.runs[0]
    subheading_run.font.size = Pt(14)
    subheading_run.bold = True

    doc.add_paragraph()

    # Questions
    for q in questions:
        q_para = doc.add_paragraph()
        q_run = q_para.add_run(f"Q{q['number']}. {q['question']}")
        q_run.bold = True
        q_run.font.size = Pt(12)
        q_para.paragraph_format.space_after = Pt(4)

        if q.get("options"):
            for opt in q["options"]:
                opt_para = doc.add_paragraph()
                opt_para.paragraph_format.left_indent = Inches(0.5)
                opt_para.paragraph_format.space_after = Pt(2)
                checkbox = opt_para.add_run("☐ ")
                checkbox.font.size = Pt(11)
                opt_run = opt_para.add_run(opt)
                opt_run.font.size = Pt(10)

            # Answer space - single line only
            ans_para = doc.add_paragraph()
            ans_para.paragraph_format.left_indent = Inches(0.5)
            ans_para.paragraph_format.space_after = Pt(2)
            ans_run = ans_para.add_run("Answer: ")
            ans_run.bold = True
            ans_run.font.size = Pt(10)
            ans_para.add_run("_" * 20).font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)
            ans_para.add_run(" (Write correct option only, e.g., A, B, C, D)")
            ans_para.add_run().font.size = Pt(8)
            ans_para.add_run().italic = True

        doc.add_paragraph()

    # Candidate sections (5 candidates) - using Candidate ID instead of name
    doc.add_page_break()
    header = doc.add_heading("Candidate Answer Sheet", level=1)
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for cand_idx in range(CANDIDATES_PER_DAY):
        cand_para = doc.add_paragraph()
        cand_para.paragraph_format.space_before = Pt(12)
        cand_para.paragraph_format.space_after = Pt(6)
        cand_run = cand_para.add_run(f"Candidate ID: {cand_idx + 1:03d} _______________")
        cand_run.bold = True
        cand_run.font.size = Pt(12)

        for q_num in range(1, QUESTION_COUNT + 1):
            ans_para = doc.add_paragraph()
            ans_para.paragraph_format.left_indent = Inches(0.5)
            ans_para.paragraph_format.space_after = Pt(2)
            ans_para.add_run(f"Q{q_num}: ").bold = True
            ans_para.add_run("_" * 20).font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)
            ans_para.add_run(" (Write correct option only)").font.size = Pt(8)
            ans_para.add_run().italic = True

    buf = __import__("io").BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


def save_question_paper_to_db(day: int, session) -> str:
    """Generate and persist the question paper as a RECORD file.

    Returns the file path.
    """
    filepath = generate_question_paper(day)
    with open(filepath, "rb") as f:
        content = f.read()
    persist_record(
        content,
        interview_id=f"DAY_{day}",
        file_type="MCQ_SHEET",
        ext=".docx",
    )
    return filepath


def score_answer_sheet(
    day: int,
    correct_answers: list[str],
    candidate_answers: dict[str, list[str]],
) -> dict[str, Any]:
    """Score uploaded answer sheets for a specific day.

    Args:
        day: The day number (1-10)
        correct_answers: The correct answer sequence for the day
        candidate_answers: Dict of {candidate_identifier: [answers]} where
            answers is a list of strings (one per question) and candidate_identifier
            is typically in the format "Candidate 001", "Candidate 002", etc.

    Returns:
        Dict with individual scores and overall results
    """
    results = {}
    total_questions = len(correct_answers)

    for candidate_name, answers in candidate_answers.items():
        score = 0
        question_scores = []
        for q_idx in range(min(total_questions, len(answers))):
            given = answers[q_idx].strip().upper() if answers[q_idx] else ""
            correct = correct_answers[q_idx].strip().upper()
            if given == correct:
                score += 1
                question_scores.append({"question": q_idx + 1, "correct": True})
            else:
                question_scores.append({"question": q_idx + 1, "correct": False})

        percentage = round((score / total_questions) * 100, 1) if total_questions > 0 else 0
        results[candidate_name] = {
            "score": score,
            "max_score": total_questions,
            "percentage": percentage,
            "question_scores": question_scores,
        }

    return {
        "day": day,
        "total_questions": total_questions,
        "correct_answers": correct_answers,
        "candidates": results,
    }


def parse_uploaded_answer_sheet(text: str) -> dict[str, Any]:
    """Parse the uploaded answer sheet text to extract candidate IDs
    and their answer sequences.

    Expected format in the uploaded document:
    Candidate ID: 001
    Q1: [answer]
    Q2: [answer]
    ...
    Candidate ID: 002
    ...

    Returns:
        Dict with candidate IDs and their answer sequences
    """
    candidates: dict[str, list[str]] = {}
    current_candidate = None

    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Match candidate header: "Candidate ID: 001" or "Candidate ID: 001 _______________"
        cand_match = re.match(r"Candidate\s+ID:\s*(\d+)\s*:?\s*", line, re.IGNORECASE)
        if cand_match:
            candidate_id = f"Candidate {int(cand_match.group(1)):03d}"
            current_candidate = candidate_id
            if current_candidate not in candidates:
                candidates[current_candidate] = []
            continue

        # Match answer line: "Q1: answer" or just "answer"
        q_match = re.match(r"Q(\d+):\s*(.+)", line, re.IGNORECASE)
        if q_match and current_candidate is not None:
            answer = q_match.group(2).strip()
            # Pad the answers list if needed
            q_num = int(q_match.group(1))
            while len(candidates[current_candidate]) < q_num:
                candidates[current_candidate].append("")
            candidates[current_candidate][q_num - 1] = answer

    return {"candidates": candidates, "raw_text": text}


def _apply_paper_base(doc: Document) -> None:
    """Apply base formatting to the question paper document."""
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)
    font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)


def get_available_days() -> list[int]:
    """Get the list of available days (1-10) based on the dataset."""
    try:
        _load_dataset()
        return list(range(1, DAYS + 1))
    except FileNotFoundError:
        return []


def generate_mcq_answer_key(day: int, filepath: str | None = None) -> str:
    """Generate a printable MCQ answer key DOCX for a specific day.

    Shows the correct answer sequence for the day.
    Returns the file path.
    """
    questions = _get_day_questions(day)
    correct_answers = _get_day_correct_answers(day)

    if filepath is None:
        os.makedirs(settings.MCQ_STORAGE_DIR, exist_ok=True)
        filepath = os.path.join(settings.MCQ_STORAGE_DIR, f"mcq_answer_key_day_{day}.docx")

    doc = Document()
    _apply_paper_base(doc)

    # Header
    title = doc.add_heading("VLOOKUP BUISNESS SOLUTION PTV LTD", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title.runs[0]
    title_run.font.size = Pt(16)
    title_run.bold = True

    # Subheading
    subheading = doc.add_heading(f"DAY {day} ANSWER KEY", level=1)
    subheading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subheading_run = subheading.runs[0]
    subheading_run.font.size = Pt(14)
    subheading_run.bold = True

    doc.add_paragraph()

    # Answer key sequence
    answer_key_text = "".join(correct_answers)
    key_para = doc.add_paragraph()
    key_run = key_para.add_run(f"Answer Key Sequence: {answer_key_text}")
    key_run.bold = True
    key_run.font.size = Pt(14)
    key_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    key_para.paragraph_format.space_after = Pt(12)

    # Detailed answer key table
    doc.add_paragraph("Detailed Answer Key:", style='Heading 2')

    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'

    # Header row
    header_cells = table.rows[0].cells
    header_cells[0].text = "Question Number"
    header_cells[1].text = "Correct Answer"
    for cell in header_cells:
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True

    # Data rows
    for i, (question, answer) in enumerate(zip(questions, correct_answers), 1):
        row_cells = table.add_row().cells
        row_cells[0].text = f"Q{i}"
        row_cells[1].text = answer
        # Center align the answer cell
        for paragraph in row_cells[1].paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()
    instructions = doc.add_paragraph()
    instructions_run = instructions.add_run("Instructions: Compare candidate answer sheets to this key to score responses.")
    instructions_run.italic = True
    instructions_run.font.size = Pt(10)
    instructions.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.save(filepath)
    logger.info("Generated MCQ answer key for day %d -> %s", day, filepath)
    return filepath


def get_day_status(day: int) -> dict[str, Any]:
    """Get the status of a specific day: questions available, correct answers, etc."""
    try:
        questions = _get_day_questions(day)
        correct = _get_day_correct_answers(day)
        return {
            "day": day,
            "available": True,
            "questions": [q["question"] for q in questions],
            "question_count": len(questions),
            "correct_answers_available": bool(correct),
        }
    except FileNotFoundError:
        return {"day": day, "available": False}
