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

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            "Jane Smith\nSoftware Engineer\nSkills: Python, Django, React, PostgreSQL\n"
            "Experience: Software Developer at TechCorp (2020-2023)\n"
            "Projects: E-commerce Platform using Django and React",
        )
        doc.save(tmp.name)
        doc.close()

        try:
            with open(tmp.name, "rb") as f:
                response = client.post(
                    "/api/generate",
                    files={"file": ("resume.pdf", f, "application/pdf")},
                )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "result" in data
        finally:
            os.remove(tmp.name)
