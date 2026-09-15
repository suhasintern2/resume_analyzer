"""Document generation for the interview pipeline.

``generate_docx`` (legacy synchronous download) is unchanged from the MVP and
continues to serve the three role views (interviewer / hr / candidate).

``generate_question_sheet`` and ``generate_answer_key`` are the two new RECORD
documents required by Task 7.  Both are persisted to disk via ``file_store``
and wired to ``files`` rows by the caller; they never return an in-memory
buffer that would disappear after the response.
"""

import io
import logging

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.models.schemas import InterviewResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers shared by all generation paths
# ---------------------------------------------------------------------------

CATEGORY_ORDER = [
    "MCQ",
    "Basic Technical",
    "Mid Technical (MERN)",
    "Resume Skills",
    "Project",
    "VlookUp Scenario",
]

_SECTION_LABELS: dict[str, str] = {
    "mcq":        "SECTION 1 — MULTIPLE CHOICE QUESTIONS (MCQs)",
    "basic":      "SECTION 2 — BASIC TECHNICAL QUESTIONS",
    "mern":       "SECTION 3 — MID TECHNICAL (MERN STACK)",
    "mid":        "SECTION 3 — MID TECHNICAL (MERN STACK)",
    "skill":      "SECTION 4 — RESUME SKILLS DEEP-DIVE",
    "project":    "SECTION 5 — PROJECT ARCHITECTURE",
    "scenario":   "SECTION 6 — VLOOKUP SCENARIOS (UK PROPERTY MANAGEMENT)",
    "vlookup":    "SECTION 6 — VLOOKUP SCENARIOS (UK PROPERTY MANAGEMENT)",
}


def _section_header(cat_name: str) -> str:
    """Section heading for a category, matching the original MVP's substring
    matching (e.g. 'MCQ' anywhere in the category yields SECTION 1)."""
    lowered = cat_name.lower()
    for needle, label in _SECTION_LABELS.items():
        if needle in lowered:
            return label
    return f"{cat_name.upper()} QUESTIONS"


def _sort_key(item: tuple) -> int:
    cat_name = item[0].lower()
    for idx, expected in enumerate(CATEGORY_ORDER):
        if expected.lower() in cat_name:
            return idx
    return 99


def _ordered_categories(result: InterviewResult) -> list[tuple[str, list]]:
    categories: dict[str, list] = {}
    for q in result.questions:
        categories.setdefault(q.category, []).append(q)
    return sorted(categories.items(), key=_sort_key)


def _apply_doc_base(doc: Document) -> None:
    """Set the shared font and page margins used by every generated DOCX."""
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


def _add_doc_header(
    doc: Document,
    *,
    title_text: str,
    candidate_name: str,
    notice_text: str | None = None,
    interview_id: str | None = None,
) -> None:
    """Write the company heading, candidate line, optional notice, and
    interview ID."""
    title = doc.add_heading(
        f"VlookUp Business Solutions\n{title_text}", level=0,
    )
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    if interview_id:
        id_para = doc.add_paragraph()
        id_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        id_run = id_para.add_run(f"Interview ID: {interview_id}")
        id_run.bold = True
        id_run.font.size = Pt(10)
        id_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    name_para = doc.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_para.add_run(f"Candidate: {candidate_name}")
    name_run.bold = True
    name_run.font.size = Pt(13)
    name_run.font.color.rgb = RGBColor(0x7A, 0xA0, 0x31)

    if notice_text:
        notice = doc.add_paragraph()
        notice.alignment = WD_ALIGN_PARAGRAPH.CENTER
        n_run = notice.add_run(notice_text)
        n_run.italic = True
        n_run.font.size = Pt(9.5)
        n_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    doc.add_paragraph()


# ---------------------------------------------------------------------------
# Legacy synchronous role-based generation (unchanged from MVP)
# ---------------------------------------------------------------------------

def generate_docx(result: InterviewResult, role: str = "interviewer") -> bytes:
    """
    Generate tailored DOCX interview documents based on target role:
    - 'interviewer': Technical keys and deep architectural answers
    - 'hr': Plain-English evaluation guide for non-technical recruiters
    - 'candidate': Questions and MCQ choices only (no answers)
    """
    doc = Document()
    _apply_doc_base(doc)

    role_titles = {
        "interviewer": "Technical Interviewer Evaluation Guide",
        "hr": "HR & Recruiter Assessment Guide (Non-Technical)",
        "candidate": "Candidate Interview Assessment Sheet",
    }
    document_title = role_titles.get(role, "Interview Preparation Guide")

    _add_doc_header(
        doc,
        title_text=document_title,
        candidate_name=result.candidate_name,
        notice_text=(
            "CONFIDENTIAL: Contains technical key answers and architecture benchmarks."
            if role == "interviewer"
            else "HR GUIDE: Contains plain-English indicators for non-technical evaluation."
            if role == "hr"
            else "Instructions: Complete MCQs and prepare to discuss your technical approach."
            if role == "candidate"
            else None
        ),
    )

    # Candidate Profile Summary (for interviewer and HR)
    if role != "candidate" and result.summary:
        doc.add_heading("Profile Summary", level=2)
        summary_para = doc.add_paragraph(result.summary)
        summary_para.paragraph_format.space_after = Pt(12)
        doc.add_paragraph()

    for cat_name, questions in _ordered_categories(result):
        header_text = _section_header(cat_name)

        cat_heading = doc.add_heading(header_text, level=2)
        cat_heading.paragraph_format.space_before = Pt(14)
        cat_heading.paragraph_format.space_after = Pt(6)

        for q in questions:
            q_para = doc.add_paragraph()
            q_run = q_para.add_run(f"Q{q.number}. {q.question}")
            q_run.bold = True
            q_run.font.size = Pt(11)
            q_para.paragraph_format.space_after = Pt(4)

            if q.options:
                for opt in q.options:
                    opt_para = doc.add_paragraph()
                    opt_para.paragraph_format.left_indent = Inches(0.25)
                    opt_para.paragraph_format.space_after = Pt(2)
                    opt_para.add_run(opt)

            if role == "candidate":
                if q.options:
                    ans_box = doc.add_paragraph()
                    ans_box.paragraph_format.left_indent = Inches(0.25)
                    ans_box.paragraph_format.space_after = Pt(10)
                    ans_run = ans_box.add_run("[   ] Selected Option: ________")
                    ans_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
                else:
                    note_para = doc.add_paragraph()
                    note_para.paragraph_format.left_indent = Inches(0.25)
                    note_para.paragraph_format.space_after = Pt(12)
                    note_run = note_para.add_run(
                        "Notes / Talking points:\n"
                        "_____________________________________________________________________\n"
                        "_____________________________________________________________________"
                    )
                    note_run.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
                    note_run.font.size = Pt(9.5)

            elif role == "hr":
                if q.correct_option:
                    key_p = doc.add_paragraph()
                    key_p.paragraph_format.left_indent = Inches(0.2)
                    key_p.paragraph_format.space_after = Pt(2)
                    k_run = key_p.add_run(f"Correct Option: {q.correct_option}")
                    k_run.bold = True
                    k_run.font.color.rgb = RGBColor(0x7A, 0xA0, 0x31)

                eval_label = doc.add_paragraph()
                eval_label.paragraph_format.left_indent = Inches(0.2)
                eval_label.paragraph_format.space_after = Pt(2)
                el_run = eval_label.add_run(
                    "What to Look For (Plain English Evaluation Guide):"
                )
                el_run.bold = True
                el_run.font.size = Pt(10)
                el_run.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)

                ans_text = q.hr_answer if q.hr_answer else q.answer
                ans_p = doc.add_paragraph()
                ans_p.paragraph_format.left_indent = Inches(0.2)
                ans_p.paragraph_format.space_after = Pt(12)
                ans_run = ans_p.add_run(ans_text)
                ans_run.font.size = Pt(10)

            else:  # role == "interviewer"
                if q.correct_option:
                    key_p = doc.add_paragraph()
                    key_p.paragraph_format.left_indent = Inches(0.2)
                    key_p.paragraph_format.space_after = Pt(2)
                    k_run = key_p.add_run(f"Correct Option: {q.correct_option}")
                    k_run.bold = True
                    k_run.font.color.rgb = RGBColor(0x7A, 0xA0, 0x31)

                ans_label = doc.add_paragraph()
                ans_label.paragraph_format.left_indent = Inches(0.2)
                ans_label.paragraph_format.space_after = Pt(2)
                al_run = ans_label.add_run("Technical Answer & Evaluation Benchmark:")
                al_run.bold = True
                al_run.font.size = Pt(10)
                al_run.font.color.rgb = RGBColor(0x48, 0x63, 0x1A)

                ans_p = doc.add_paragraph()
                ans_p.paragraph_format.left_indent = Inches(0.2)
                ans_p.paragraph_format.space_after = Pt(12)
                ans_run = ans_p.add_run(q.answer)
                ans_run.font.size = Pt(10)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Task 7 — New RECORD documents
# ---------------------------------------------------------------------------

# Task 12 — OMR checkbox glyph printed in front of every MCQ option. The
# candidate fills the box on the paper; the OMR pass detects its ink density.
OMR_CHECKBOX_GLYPH = "\u2610"  # ☐ BALLOT BOX

# Synthetic single-page layout model used only to describe the *intended*
# geometry of the printable question sheet (normalized 0..1 coordinates).
# The OMR detector reads the actual scanned pages (contours + printed text);
# these estimates document the reference layout for a generated sheet.
_LAYOUT_VERSION = 1
_PAGE_MODEL = {
    "height_unit": 0.075,      # rows consumed per question block
    "first_block_y": 0.22,     # below the header / candidate line
    "checkbox_x": 0.07,        # printed checkbox horizontal (normalized)
    "checkbox_w": 0.022,
    "checkbox_h": 0.014,
    "option_row_step": 0.02,   # vertical step between option rows
    "option_first_y": 0.008,
}


def question_sheet_layout_metadata(result: InterviewResult) -> dict | None:
    """Return OMR layout metadata for a question sheet, or None when the sheet
    contains no MCQ (nothing OMR-scannable).

    Structure:
    ``{"version": 1, "mode": "checkbox-omr", "pages": [{"index": 0,
      "questions": [{"number": N, "options": [{"label": "A", "box": {...}}]}]}]}``

    All ``box`` coordinates are normalized (0..1) page units.  Only questions
    with option lists get checkbox boxes; open-ended questions have none (they
    are OCR-answered, never OMR).
    """
    mcq_numbers = [q.number for q in result.questions if q.options]
    if not mcq_numbers:
        logger.info(
            "Question sheet has no MCQ questions — layout_metadata omitted",
        )
        return None

    questions_meta: list[dict] = []
    block_index = 0
    for q in result.questions:
        if not q.options:
            continue
        options_meta: list[dict] = []
        base_y = (
            _PAGE_MODEL["first_block_y"]
            + block_index * _PAGE_MODEL["height_unit"]
        )
        for label, option_text in enumerate(q.options, start=1):
            letter = _option_letter(label, option_text)
            options_meta.append({
                "label": letter,
                "box": {
                    "x": _PAGE_MODEL["checkbox_x"],
                    "y": base_y + _PAGE_MODEL["option_first_y"]
                        + (label - 1) * _PAGE_MODEL["option_row_step"],
                    "w": _PAGE_MODEL["checkbox_w"],
                    "h": _PAGE_MODEL["checkbox_h"],
                },
            })
        questions_meta.append({
            "number": q.number,
            "options": options_meta,
        })
        block_index += 1

    return {
        "version": _LAYOUT_VERSION,
        "mode": "checkbox-omr",
        "pages": [{"index": 0, "questions": questions_meta}],
    }


def _option_letter(index: int, option_text: str) -> str:
    """Derive the printed option letter (``A``/``B``/...) from the option text
    when the generator emitted it (``A) ...``), else from its ordinal index."""
    stripped = option_text.strip()
    if len(stripped) >= 1 and stripped[0].isalpha():
        return stripped[0].upper()
    return chr(ord("A") + index - 1)

def generate_question_sheet(
    result: InterviewResult,
    *,
    interview_id: str,
) -> bytes:
    """Interview Question Sheet — printable document given to the interviewee.

    Contains numbered questions with ample blank space for handwritten answers.
    Deliberately contains **no** answers, keywords, concepts, or any
    evaluation-key content.
    """
    doc = Document()
    _apply_doc_base(doc)
    _add_doc_header(
        doc,
        title_text="Interview Question Sheet",
        candidate_name=result.candidate_name,
        notice_text=(
            "Answer each question in the space provided. "
            "Do not write on any other part of this sheet."
        ),
        interview_id=interview_id,
    )

    for cat_name, questions in _ordered_categories(result):
        header_text = _section_header(cat_name)
        cat_heading = doc.add_heading(header_text, level=2)
        cat_heading.paragraph_format.space_before = Pt(14)
        cat_heading.paragraph_format.space_after = Pt(6)

        for q in questions:
            q_para = doc.add_paragraph()
            q_run = q_para.add_run(f"Q{q.number}. {q.question}")
            q_run.bold = True
            q_run.font.size = Pt(11)
            q_para.paragraph_format.space_after = Pt(4)

            if q.options:
                for opt in q.options:
                    opt_para = doc.add_paragraph()
                    opt_para.paragraph_format.left_indent = Inches(0.25)
                    opt_para.paragraph_format.space_after = Pt(2)
                    # Task 12 — leading OMR checkbox glyph the candidate fills
                    # on paper (detected by ink density, no AI involved).
                    glyph = opt_para.add_run(f"{OMR_CHECKBOX_GLYPH}  ")
                    glyph.font.size = Pt(12)
                    opt_para.add_run(opt)

                ans_box = doc.add_paragraph()
                ans_box.paragraph_format.left_indent = Inches(0.25)
                ans_box.paragraph_format.space_after = Pt(10)
                ans_run = ans_box.add_run("Selected Option: ________")
                ans_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
            else:
                blank = doc.add_paragraph()
                blank.paragraph_format.left_indent = Inches(0.25)
                blank.paragraph_format.space_after = Pt(4)
                blank_run = blank.add_run("Your answer:")
                blank_run.bold = True
                blank_run.font.size = Pt(10)
                blank_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

                for _ in range(6):
                    line = doc.add_paragraph()
                    line.paragraph_format.left_indent = Inches(0.25)
                    line.paragraph_format.space_after = Pt(2)
                    line.add_run("_" * 85).font.color.rgb = RGBColor(
                        0xCB, 0xD5, 0xE1,
                    )

                doc.add_paragraph()

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    logger.info(
        "Generated question sheet for interview %s (%d questions)",
        interview_id, len(result.questions),
    )
    return buffer.getvalue()


def generate_answer_key(
    result: InterviewResult,
    *,
    interview_id: str,
) -> bytes:
    """Internal Answer Key — never exposed to the interviewee.

    Contains each question with its sample answer **and** the evaluation-key
    metadata from Task 5 (keywords, required_concepts with normalised weights,
    important_phrases) in a readable internal-reference format.
    """
    doc = Document()
    _apply_doc_base(doc)
    _add_doc_header(
        doc,
        title_text="Answer Key (Internal — Confidential)",
        candidate_name=result.candidate_name,
        notice_text=(
            "INTERNAL USE ONLY — contains sample answers and evaluation-key "
            "metadata.  Do not share with the interviewee."
        ),
        interview_id=interview_id,
    )

    for cat_name, questions in _ordered_categories(result):
        header_text = _section_header(cat_name)
        cat_heading = doc.add_heading(header_text, level=2)
        cat_heading.paragraph_format.space_before = Pt(14)
        cat_heading.paragraph_format.space_after = Pt(6)

        for q in questions:
            # Question
            q_para = doc.add_paragraph()
            q_run = q_para.add_run(f"Q{q.number}. {q.question}")
            q_run.bold = True
            q_run.font.size = Pt(11)
            q_para.paragraph_format.space_after = Pt(4)

            if q.options:
                for opt in q.options:
                    opt_para = doc.add_paragraph()
                    opt_para.paragraph_format.left_indent = Inches(0.25)
                    opt_para.paragraph_format.space_after = Pt(2)
                    opt_para.add_run(opt)

            # Correct option (if MCQ)
            if q.correct_option:
                key_p = doc.add_paragraph()
                key_p.paragraph_format.left_indent = Inches(0.2)
                key_p.paragraph_format.space_after = Pt(2)
                k_run = key_p.add_run(f"Correct Option: {q.correct_option}")
                k_run.bold = True
                k_run.font.color.rgb = RGBColor(0x7A, 0xA0, 0x31)

            # Sample answer
            ans_label = doc.add_paragraph()
            ans_label.paragraph_format.left_indent = Inches(0.2)
            ans_label.paragraph_format.space_after = Pt(2)
            al_run = ans_label.add_run("Sample Answer:")
            al_run.bold = True
            al_run.font.size = Pt(10)
            al_run.font.color.rgb = RGBColor(0x48, 0x63, 0x1A)

            ans_p = doc.add_paragraph()
            ans_p.paragraph_format.left_indent = Inches(0.2)
            ans_p.paragraph_format.space_after = Pt(8)
            ans_run = ans_p.add_run(q.answer)
            ans_run.font.size = Pt(10)

            # Keywords
            kw_p = doc.add_paragraph()
            kw_p.paragraph_format.left_indent = Inches(0.2)
            kw_p.paragraph_format.space_after = Pt(2)
            kw_label = kw_p.add_run("Keywords: ")
            kw_label.bold = True
            kw_label.font.size = Pt(10)
            kw_label.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
            kw_text = kw_p.add_run(", ".join(q.keywords))
            kw_text.font.size = Pt(10)

            # Required concepts with weights
            if q.required_concepts:
                con_p = doc.add_paragraph()
                con_p.paragraph_format.left_indent = Inches(0.2)
                con_p.paragraph_format.space_after = Pt(2)
                con_label = con_p.add_run("Required Concepts: ")
                con_label.bold = True
                con_label.font.size = Pt(10)
                con_label.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
                con_text = con_p.add_run(
                    ", ".join(
                        f"{c.name} ({c.weight:.0%})"
                        for c in q.required_concepts
                    )
                )
                con_text.font.size = Pt(10)

            # Important phrases
            ph_p = doc.add_paragraph()
            ph_p.paragraph_format.left_indent = Inches(0.2)
            ph_p.paragraph_format.space_after = Pt(2)
            ph_label = ph_p.add_run("Important Phrases: ")
            ph_label.bold = True
            ph_label.font.size = Pt(10)
            ph_label.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
            ph_text = ph_p.add_run(
                "; ".join(f'"{p}"' for p in q.important_phrases)
            )
            ph_text.font.size = Pt(10)

            doc.add_paragraph()

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    logger.info(
        "Generated answer key for interview %s (%d questions)",
        interview_id, len(result.questions),
    )
    return buffer.getvalue()
