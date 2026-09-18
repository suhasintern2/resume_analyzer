"""Document generation for the interview pipeline.

``generate_docx`` (legacy synchronous download) is unchanged from the MVP and
continues to serve the three role views (interviewer / hr / candidate).

``generate_question_sheet`` and ``generate_answer_key`` are the two new RECORD
documents required by Task 7.  Both are persisted to disk via ``file_store``
and wired to ``files`` rows by the caller; they never return an in-memory
buffer that would disappear after the response.

``generate_pdf`` produces a temporary PDF for the given role and interview,
stored on disk until explicitly deleted by the mark-as-done flow.
"""

import io
import logging
import os

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from fpdf import FPDF

from app.models.schemas import InterviewResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Category ordering for the new 9-question structure (no MCQs)
# ---------------------------------------------------------------------------

CATEGORY_ORDER = [
    "Tech Stack",
    "Experience",
    "Project",
    "Application Scenario",
    "VlookUp Challenge",
]

_SECTION_LABELS: dict[str, str] = {
    "tech stack": "SECTION 1 — TECH STACK QUESTIONS",
    "experience": "SECTION 2 — EXPERIENCE-BASED QUESTIONS",
    "project": "SECTION 3 — PROJECT-BASED QUESTIONS",
    "application scenario": "SECTION 4 — REAL-WORLD APPLICATION SCENARIO",
    "vlookup challenge": "SECTION 5 — VLOOKUP CHALLENGE SCENARIOS",
}


def _section_header(cat_name: str) -> str:
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


def _write_question_to_pdf(
    pdf: FPDF,
    q,
    role: str,
    show_answer: bool = True,
) -> None:
    """Write a single question block to an FPDF instance."""
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Q{q.number}. {q.question}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if role == "hr" or role == "interviewer":
        if show_answer:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, f"Answer: {q.answer}")
            pdf.ln(2)
            if q.hr_answer:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(0x64, 0x74, 0x8B)
                pdf.multi_cell(0, 6, f"HR Guide: {q.hr_answer}")
                pdf.set_text_color(0, 0, 0)
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, f"Your answer:")
            pdf.ln(2)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(0x64, 0x74, 0x8B)
            for _ in range(6):
                pdf.cell(0, 5, "_" * 80, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, f"Your answer:")
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0x64, 0x74, 0x8B)
        for _ in range(6):
            pdf.cell(0, 5, "_" * 80, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    pdf.ln(8)


def _write_question_to_docx(
    doc: Document,
    q,
    role: str,
    show_answer: bool = True,
) -> None:
    """Write a single question block to a DOCX document."""
    q_para = doc.add_paragraph()
    q_run = q_para.add_run(f"Q{q.number}. {q.question}")
    q_run.bold = True
    q_run.font.size = Pt(11)
    q_para.paragraph_format.space_after = Pt(4)

    if role == "candidate":
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

    else:  # interviewer
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
            _write_question_to_docx(doc, q, role)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Task 7 — New RECORD documents (question sheet + answer key)
# ---------------------------------------------------------------------------

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

            options = getattr(q, "options", None) or []
            if options:
                for opt in options:
                    opt_para = doc.add_paragraph()
                    opt_para.paragraph_format.left_indent = Inches(0.25)
                    opt_para.paragraph_format.space_after = Pt(2)
                    opt_run = opt_para.add_run(f"☐ {opt}")
                    opt_run.font.size = Pt(10)

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
            q_para = doc.add_paragraph()
            q_run = q_para.add_run(f"Q{q.number}. {q.question}")
            q_run.bold = True
            q_run.font.size = Pt(11)
            q_para.paragraph_format.space_after = Pt(4)

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

            kw_p = doc.add_paragraph()
            kw_p.paragraph_format.left_indent = Inches(0.2)
            kw_p.paragraph_format.space_after = Pt(2)
            kw_label = kw_p.add_run("Keywords: ")
            kw_label.bold = True
            kw_label.font.size = Pt(10)
            kw_label.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
            kw_text = kw_p.add_run(", ".join(q.keywords))
            kw_text.font.size = Pt(10)

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


# ---------------------------------------------------------------------------
# PDF generation (temporary, auto-deleted on mark-as-done)
# ---------------------------------------------------------------------------

def generate_pdf(
    result: InterviewResult,
    *,
    role: str,
    interview_id: str,
    output_dir: str,
) -> str:
    """Generate a PDF file for the given role and interview.

    Returns the absolute file path of the generated PDF.
    The PDF is a temporary file stored under ``output_dir``.
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"interview_{interview_id}_{role}.pdf"
    filepath = os.path.join(output_dir, filename)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title page
    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 20, "VlookUp Business Solutions", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    title_map = {
        "interviewer": "Technical Interviewer Evaluation Guide",
        "hr": "HR & Recruiter Assessment Guide",
        "candidate": "Candidate Interview Assessment Sheet",
    }
    pdf.set_font("Helvetica", "", 16)
    pdf.cell(0, 15, title_map.get(role, "Interview Kit"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Candidate: {result.candidate_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, f"Interview ID: {interview_id}", new_x="LMARGIN", new_y="NEXT")
    if result.summary:
        pdf.ln(5)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, f"Summary: {result.summary}")
    pdf.add_page()

    # Questions
    for cat_name, questions in _ordered_categories(result):
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(0x1F, 0x29, 0x37)
        pdf.cell(0, 10, _section_header(cat_name), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
        pdf.set_text_color(0, 0, 0)

        for q in questions:
            _write_question_to_pdf(pdf, q, role, show_answer=(role != "candidate"))

    pdf.output(filepath)
    logger.info(
        "Generated PDF for interview %s, role=%s -> %s",
        interview_id, role, filepath,
    )
    return filepath


def delete_pdf(filepath: str | None) -> None:
    """Delete a temporary PDF file."""
    if not filepath:
        return
    try:
        os.remove(filepath)
        logger.info("Deleted temporary PDF: %s", filepath)
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.warning("Could not delete PDF %s: %s", filepath, e)


# ---------------------------------------------------------------------------
# OMR layout metadata for the printed question sheet (Task 12)
# ---------------------------------------------------------------------------

def question_sheet_layout_metadata(result: InterviewResult) -> dict:
    """Compute a synthetic single-page box layout for OMR on the question sheet.

    Returns a dict with a ``pages`` key listing page layouts, each containing
    ``index`` and ``questions``. Each question has ``number`` and ``options``
    (list of ``{label, box}`` where ``box`` holds normalized 0..1 page
    coordinates ``{x, y, w, h}`` for the checkbox).
    """
    questions = result.questions
    page_height = 11.0  # inches (Letter)
    page_width = 8.5
    margin = 0.8
    usable_width = page_width - 2 * margin
    usable_height = page_height - 2 * margin

    estimated_line_height = 0.35  # inches per question+option line
    questions_per_page = max(1, int(usable_height / estimated_line_height))

    pages = []
    for page_idx in range(0, len(questions), questions_per_page):
        page_questions = []
        for i, q in enumerate(questions[page_idx:page_idx + questions_per_page]):
            abs_idx = page_idx + i
            y_norm = (margin + i * estimated_line_height) / page_height
            options = getattr(q, "options", None) or []
            option_entries = []
            for opt_idx, opt in enumerate(options):
                opt_y = y_norm + 0.05 + opt_idx * 0.08
                option_entries.append({
                    "label": opt,
                    "box": {
                        "x": 0.02,
                        "y": max(0.0, min(opt_y, 0.95)),
                        "w": 0.06,
                        "h": 0.05,
                    },
                })
            page_questions.append({
                "number": q.number,
                "options": option_entries,
            })
        pages.append({
            "index": page_idx // questions_per_page,
            "questions": page_questions,
        })

    return {"pages": pages}