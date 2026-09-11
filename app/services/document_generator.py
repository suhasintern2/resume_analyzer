from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from app.models.schemas import InterviewResult


def generate_docx(result: InterviewResult) -> bytes:
    doc = Document()

    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)

    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    title = doc.add_heading("Resume Interview Preparation", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    name_para = doc.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_para.add_run(f"Candidate: {result.candidate_name}")
    name_run.bold = True
    name_run.font.size = Pt(14)

    doc.add_paragraph()

    summary_heading = doc.add_heading("Profile Summary", level=2)
    doc.add_paragraph(result.summary)

    doc.add_paragraph()

    categories = {}
    for q in result.questions:
        cat = q.category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(q)

    for cat_name, questions in categories.items():
        doc.add_heading(f"{cat_name.upper()} QUESTIONS", level=2)

        for q in questions:
            q_para = doc.add_paragraph()
            q_run = q_para.add_run(f"{q.number}. {q.question}")
            q_run.bold = True
            q_run.font.size = Pt(11)

            a_label = doc.add_paragraph()
            a_label_run = a_label.add_run("Answer:")
            a_label_run.bold = True
            a_label_run.font.size = Pt(11)

            a_para = doc.add_paragraph(q.answer)
            a_para.paragraph_format.space_after = Pt(12)

    import io
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
