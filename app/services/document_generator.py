import io
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from app.models.schemas import InterviewResult


def generate_docx(result: InterviewResult, role: str = "interviewer") -> bytes:
    """
    Generate tailored DOCX interview documents based on target role:
    - 'interviewer': Technical keys and deep architectural answers
    - 'hr': Plain-English evaluation guide for non-technical recruiters
    - 'candidate': Questions and MCQ choices only (no answers)
    """
    doc = Document()

    # Base font setup
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)
    font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

    # Page Margins
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    role_titles = {
        "interviewer": "Technical Interviewer Evaluation Guide",
        "hr": "HR & Recruiter Assessment Guide (Non-Technical)",
        "candidate": "Candidate Interview Assessment Sheet",
    }
    document_title = role_titles.get(role, "Interview Preparation Guide")

    # Document Header
    title = doc.add_heading(f"VlookUp Business Solutions\n{document_title}", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Candidate Meta
    name_para = doc.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_para.add_run(f"Candidate: {result.candidate_name}")
    name_run.bold = True
    name_run.font.size = Pt(13)
    name_run.font.color.rgb = RGBColor(0x7A, 0xA0, 0x31)

    # Role specific banner/notice
    if role == "interviewer":
        notice = doc.add_paragraph()
        notice.alignment = WD_ALIGN_PARAGRAPH.CENTER
        n_run = notice.add_run("CONFIDENTIAL: Contains technical key answers and architecture benchmarks.")
        n_run.italic = True
        n_run.font.size = Pt(9.5)
        n_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    elif role == "hr":
        notice = doc.add_paragraph()
        notice.alignment = WD_ALIGN_PARAGRAPH.CENTER
        n_run = notice.add_run("HR GUIDE: Contains plain-English indicators for non-technical evaluation.")
        n_run.italic = True
        n_run.font.size = Pt(9.5)
        n_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    elif role == "candidate":
        notice = doc.add_paragraph()
        notice.alignment = WD_ALIGN_PARAGRAPH.CENTER
        n_run = notice.add_run("Instructions: Complete MCQs and prepare to discuss your technical approach.")
        n_run.italic = True
        n_run.font.size = Pt(9.5)
        n_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    doc.add_paragraph()

    # Candidate Profile Summary (for interviewer and HR)
    if role != "candidate" and result.summary:
        doc.add_heading("Profile Summary", level=2)
        summary_para = doc.add_paragraph(result.summary)
        summary_para.paragraph_format.space_after = Pt(12)
        doc.add_paragraph()

    # Order of categories
    CATEGORY_ORDER = [
        "MCQ",
        "Basic Technical",
        "Mid Technical (MERN)",
        "Resume Skills",
        "Project",
        "VlookUp Scenario",
    ]

    categories = {}
    for q in result.questions:
        cat = q.category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(q)

    def sort_key(item):
        cat_name = item[0]
        for idx, expected in enumerate(CATEGORY_ORDER):
            if expected.lower() in cat_name.lower():
                return idx
        return 99

    ordered = sorted(categories.items(), key=sort_key)

    for cat_name, questions in ordered:
        header_text = f"{cat_name.upper()} QUESTIONS"
        if "mcq" in cat_name.lower():
            header_text = "SECTION 1 — MULTIPLE CHOICE QUESTIONS (MCQs)"
        elif "basic" in cat_name.lower():
            header_text = "SECTION 2 — BASIC TECHNICAL QUESTIONS"
        elif "mern" in cat_name.lower() or "mid" in cat_name.lower():
            header_text = "SECTION 3 — MID TECHNICAL (MERN STACK)"
        elif "skill" in cat_name.lower():
            header_text = "SECTION 4 — RESUME SKILLS DEEP-DIVE"
        elif "project" in cat_name.lower():
            header_text = "SECTION 5 — PROJECT ARCHITECTURE"
        elif "scenario" in cat_name.lower() or "vlookup" in cat_name.lower():
            header_text = "SECTION 6 — VLOOKUP SCENARIOS (UK PROPERTY MANAGEMENT)"

        cat_heading = doc.add_heading(header_text, level=2)
        cat_heading.paragraph_format.space_before = Pt(14)
        cat_heading.paragraph_format.space_after = Pt(6)

        for q in questions:
            # Question prompt
            q_para = doc.add_paragraph()
            q_run = q_para.add_run(f"Q{q.number}. {q.question}")
            q_run.bold = True
            q_run.font.size = Pt(11)
            q_para.paragraph_format.space_after = Pt(4)

            # Render MCQ options if present
            if q.options:
                for opt in q.options:
                    opt_para = doc.add_paragraph()
                    opt_para.paragraph_format.left_indent = Inches(0.25)
                    opt_para.paragraph_format.space_after = Pt(2)
                    opt_para.add_run(opt)

            # Role-Specific Content
            if role == "candidate":
                # Candidate gets NO answers
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
                    note_run = note_para.add_run("Notes / Talking points:\n_____________________________________________________________________\n_____________________________________________________________________")
                    note_run.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
                    note_run.font.size = Pt(9.5)

            elif role == "hr":
                # HR gets Plain-English guide
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
                el_run = eval_label.add_run("What to Look For (Plain English Evaluation Guide):")
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
                # Technical interviewer gets deep technical answers
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
