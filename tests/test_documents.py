"""Tests for Task 7 — document generation wired to the new model.

Requires the Postgres instance from docker-compose to be running (interviews
are created against the real DB).  Sample interviews are cleaned up in
teardown, including their record files.
"""

import io
import os

import fitz
import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db import SessionLocal
from app.db.models import File, Interview
from app.models.schemas import InterviewResult, QuestionAnswer
from app.services import interview_service
from app.services.document_service import generate_and_persist_documents
from app.services.file_store import delete_stored_file

client = TestClient(app)


def _pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Jane Smith\nSoftware Engineer\nSkills: Python, Django, React\n"
        "Experience: Software Developer at TechCorp (2020-2023)",
    )
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _sample_result() -> InterviewResult:
    return InterviewResult(
        candidate_name="Jane Smith",
        summary="Full Stack developer with 4 years of React/Django experience.",
        questions=[
            QuestionAnswer(
                number=1,
                category="MCQ",
                question="Which database is document-based?",
                options=["A) MongoDB", "B) PostgreSQL", "C) SQLite", "D) Redis"],
                correct_option="A",
                answer="MongoDB stores data in flexible, JSON-like BSON documents.",
                hr_answer="MongoDB is a document database.",
                keywords=["document database", "BSON", "NoSQL"],
                required_concepts=[
                    {"name": "document model", "weight": 0.6},
                    {"name": "JSON-like storage", "weight": 0.4},
                ],
                important_phrases=["flexible schema", "JSON-like documents"],
            ),
            QuestionAnswer(
                number=2,
                category="Resume Skills",
                question="Explain the Django ORM to a junior developer.",
                options=None,
                correct_option=None,
                answer="The Django ORM maps Python classes to database tables and "
                "generates SQL from queries.",
                hr_answer="Django provides an easy way to work with a database.",
                keywords=["ORM", "mapping", "SQL", "queries"],
                required_concepts=[
                    {"name": "object-relational mapping", "weight": 0.5},
                    {"name": "query generation", "weight": 0.5},
                ],
                important_phrases=["maps classes to tables", "generates SQL"],
            ),
        ],
    )


def _docx_text(content: bytes) -> str:
    """Extract all paragraph text from a DOCX in memory."""
    buf = io.BytesIO(content)
    doc = Document(buf)
    return "\n".join(p.text for p in doc.paragraphs)


@pytest.fixture
def interview_ids():
    """Track interviews created by a test; delete them (and their record
    files) in teardown so the dev DB stays clean."""
    ids: list[str] = []
    yield ids
    if not ids:
        return
    with SessionLocal() as session:
        interviews = list(
            session.scalars(
                select(Interview).where(Interview.interview_id.in_(ids))
            ).all()
        )
        file_paths: list[str] = []
        for iv in interviews:
            files = session.scalars(
                select(File).where(File.interview_id == iv.id)
            ).all()
            file_paths.extend(f.file_path for f in files)
        for iv in interviews:
            session.delete(iv)
        session.commit()
    for path in file_paths:
        delete_stored_file(path)


def _create_interview_with_documents(interview_ids):
    """Create an interview via the API and generate+persist both documents
    through the Task 7 service function."""
    resp = client.post(
        "/api/interviews",
        files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    interview_id = resp.json()["interview_id"]
    interview_ids.append(interview_id)

    result = _sample_result()
    with SessionLocal() as session:
        interview = interview_service.get_interview(session, interview_id)
        assert interview is not None
        generate_and_persist_documents(
            session, interview=interview, result=result,
        )
        session.commit()
    return interview_id


def test_question_sheet_contains_no_answers_or_keywords(interview_ids):
    interview_id = _create_interview_with_documents(interview_ids)

    with SessionLocal() as session:
        interview = interview_service.get_interview(session, interview_id)
        file_row = session.scalar(
            select(File).where(
                File.interview_id == interview.id,
                File.file_type == "QUESTION_SHEET",
            )
        )
        assert file_row is not None
        assert os.path.isfile(file_row.file_path)
        with open(file_row.file_path, "rb") as fh:
            sheet_text = _docx_text(fh.read())

    # The sheet must show the questions...
    assert "Which database is document-based?" in sheet_text
    assert "Explain the Django ORM to a junior developer." in sheet_text
    assert "Interview ID: " in sheet_text and interview_id in sheet_text
    assert "Candidate: Jane Smith" in sheet_text

    # ...but must NOT contain answers, keywords, concepts, or phrases.
    assert "MongoDB stores data in flexible" not in sheet_text
    assert "Sample Answer" not in sheet_text
    assert "Correct Option" not in sheet_text
    assert "Keywords" not in sheet_text
    assert "Required Concepts" not in sheet_text
    assert "Important Phrases" not in sheet_text
    # Evaluation-key terms that never belong on a candidate's sheet
    for forbidden in ["document database", "JSON-like", "flexible schema"]:
        assert forbidden not in sheet_text


def test_answer_key_contains_answer_and_evaluation_key_metadata(interview_ids):
    interview_id = _create_interview_with_documents(interview_ids)

    with SessionLocal() as session:
        interview = interview_service.get_interview(session, interview_id)
        file_row = session.scalar(
            select(File).where(
                File.interview_id == interview.id,
                File.file_type == "ANSWER_KEY",
            )
        )
        assert file_row is not None
        assert os.path.isfile(file_row.file_path)
        with open(file_row.file_path, "rb") as fh:
            key_text = _docx_text(fh.read())

    # Question + sample answer
    assert "Which database is document-based?" in key_text
    assert "MongoDB stores data in flexible, JSON-like BSON documents." in key_text
    assert "Sample Answer" in key_text
    # Evaluation-key metadata: keywords, concepts (with weight), phrases
    assert "Keywords: " in key_text
    assert "document database, BSON, NoSQL" in key_text
    assert "Required Concepts: " in key_text
    assert "JSON-like storage (40%)" in key_text
    assert "document model (60%)" in key_text
    assert "Important Phrases: " in key_text
    assert '"flexible schema"' in key_text
    assert "Interview ID: " in key_text and interview_id in key_text


def test_both_documents_are_downloadable_by_interview_id(interview_ids):
    interview_id = _create_interview_with_documents(interview_ids)

    for file_type in ("question_sheet", "answer_key"):
        resp = client.get(
            f"/api/interviews/{interview_id}/documents/{file_type}"
        )
        assert resp.status_code == 200
        assert (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            in resp.headers["content-type"]
        )
        assert len(resp.content) > 1000
        # Valid DOCX (opening it must not raise)
        text = _docx_text(resp.content)
        assert text

    # List endpoint reports both generated documents
    list_resp = client.get(f"/api/interviews/{interview_id}/documents")
    assert list_resp.status_code == 200
    types = {d["file_type"] for d in list_resp.json()["documents"]}
    assert types == {"question_sheet", "answer_key"}


def test_download_rejects_invalid_file_type(interview_ids):
    interview_id = _create_interview_with_documents(interview_ids)

    resp = client.get(f"/api/interviews/{interview_id}/documents/resume")
    assert resp.status_code == 400
    assert "Invalid file type" in resp.json()["detail"]


def test_download_rejects_unknown_interview():
    resp = client.get("/api/interviews/INT-19990101-001/documents/question_sheet")
    assert resp.status_code == 404


def test_download_404_when_document_not_generated(interview_ids):
    # Create an interview but DO NOT generate documents.
    resp = client.post(
        "/api/interviews",
        files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    interview_id = resp.json()["interview_id"]
    interview_ids.append(interview_id)

    resp = client.get(
        f"/api/interviews/{interview_id}/documents/question_sheet"
    )
    assert resp.status_code == 404