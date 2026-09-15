import os
import io
import tempfile
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_page():
    response = client.get("/")
    assert response.status_code == 200


def test_reject_invalid_file():
    response = client.post(
        "/api/generate",
        files={"file": ("test.exe", b"fake content", "application/octet-stream")},
    )
    assert response.status_code == 400


def test_reject_empty_file():
    response = client.post(
        "/api/generate",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code in (400, 422)


def test_generate_with_valid_pdf():
    import fitz

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            "Jane Smith\nSoftware Engineer\n"
            "Professional Summary: Full Stack developer with four years of "
            "experience building web applications using Python, Django, React, "
            "PostgreSQL and MongoDB. Led a team of three developers.\n"
            "Skills: Python, Django, React, PostgreSQL, REST APIs, Docker, AWS\n"
            "Experience: Software Developer at TechCorp (2020-2023)\n"
            "Projects: E-commerce Platform using Django and React",
        )
        doc.save(tmp_path)
        doc.close()

        with open(tmp_path, "rb") as f:
            response = client.post(
                "/api/generate",
                files={"file": ("resume.pdf", f, "application/pdf")},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "result" in data
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_download_docx_all_roles():
    payload = {
        "candidate_name": "Test Candidate",
        "summary": "Full Stack developer",
        "questions": [
            {
                "number": 1,
                "category": "MCQ",
                "question": "Which database is document-based?",
                "options": ["A) MongoDB", "B) PostgreSQL", "C) SQLite", "D) Redis"],
                "correct_option": "A",
                "answer": "MongoDB stores data in flexible, JSON-like BSON documents.",
                "hr_answer": "MongoDB is a document database.",
                "keywords": ["document database", "BSON", "NoSQL"],
                "required_concepts": [
                    {"name": "document model", "weight": 0.6},
                    {"name": "JSON-like storage", "weight": 0.4},
                ],
                "important_phrases": ["flexible schema", "JSON-like documents"],
            }
        ]
    }

    for role in ["interviewer", "hr", "candidate"]:
        response = client.post(f"/api/download/docx?role={role}", json=payload)
        assert response.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in response.headers["content-type"]
        assert len(response.content) > 1000

