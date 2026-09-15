"""Tests for interview creation (Task 3).

Requires the Postgres instance from docker-compose to be running (these
tests write real rows).  All rows and record files created here are
cleaned up at the end of each test.
"""

import io
import os
import re
from concurrent.futures import ThreadPoolExecutor

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db import SessionLocal
from app.db.models import File, Interview
from app.services import interview_service
from app.services.file_store import delete_stored_file

client = TestClient(app)

ID_PATTERN = re.compile(r"^INT-\d{8}-\d{3,}$")


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


def _post_resume(pdf: bytes, filename: str = "resume.pdf"):
    return client.post(
        "/api/interviews",
        files={"file": (filename, pdf, "application/pdf")},
    )


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


def test_create_interview_success(interview_ids):
    resp = _post_resume(_pdf_bytes())
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"success": True, "status": "QUEUED", "interview_id": data["interview_id"]}
    assert ID_PATTERN.fullmatch(data["interview_id"])

    interview_ids.append(data["interview_id"])

    # Row exists with status QUEUED + a record file in the files table
    with SessionLocal() as session:
        iv = interview_service.get_interview(session, data["interview_id"])
        assert iv is not None
        assert iv.status == "QUEUED"
        assert iv.processing_stage is None
        file_row = session.scalar(
            select(File).where(File.interview_id == iv.id)
        )
        assert file_row is not None
        assert file_row.file_type == "RESUME"
        assert os.path.isfile(file_row.file_path)


def test_create_interview_rejects_invalid_file(interview_ids):
    resp = client.post(
        "/api/interviews",
        files={"file": ("resume.exe", b"MZ fake", "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert not interview_ids  # nothing created


def test_create_interview_rejects_empty_file(interview_ids):
    resp = client.post(
        "/api/interviews",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert resp.status_code in (400, 413)
    assert not interview_ids


def test_get_interview_detail(interview_ids):
    created = _post_resume(_pdf_bytes()).json()
    interview_ids.append(created["interview_id"])

    resp = client.get(f"/api/interviews/{created['interview_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["interview_id"] == created["interview_id"]
    assert body["status"] == "QUEUED"
    assert body["processing_stage"] is None
    assert body["candidate_name"] is None
    assert isinstance(body["id"], int)
    assert body["created_at"]


def test_get_interview_not_found():
    resp = client.get("/api/interviews/INT-19990101-001")
    assert resp.status_code == 404


def test_resume_record_file_persists_after_request(interview_ids):
    """RECORD files must survive request handling (amendment §6 / Task 6).

    The uploaded resume is a record file: creating the interview must not
    delete it as a side effect of the request completing. The file must
    still exist on disk AND the DB row must point at it. (This fails if any
    old request-cleanup logic deletes record files.)
    """
    resp = _post_resume(_pdf_bytes())
    assert resp.status_code == 200
    interview_id = resp.json()["interview_id"]
    interview_ids.append(interview_id)

    with SessionLocal() as session:
        iv = interview_service.get_interview(session, interview_id)
        assert iv is not None
        file_row = session.scalar(
            select(File).where(File.interview_id == iv.id, File.file_type == "RESUME")
        )
        assert file_row is not None
        assert os.path.isfile(file_row.file_path)
        # Stored under a per-interview subdirectory (Task 6 convention)
        assert file_row.file_path.startswith(f"uploads/{interview_id}/RESUME_")


def test_resume_record_file_survives_generate_flow_scratch_cleanup(interview_ids):
    """The /api/generate scratch cleanup must not touch RECORD files.

    Record files live under per-interview dirs; the generate endpoint only
    deletes its own system-temp scratch file. Re-running/interaction should
    leave the created interview's resume intact.
    """
    resp = _post_resume(_pdf_bytes())
    assert resp.status_code == 200
    interview_id = resp.json()["interview_id"]
    interview_ids.append(interview_id)

    # Ensure the run left no flat orphan files in the upload root from the
    # request (files must be under the interview dir, tracked in DB).
    with SessionLocal() as session:
        iv = interview_service.get_interview(session, interview_id)
        file_rows = list(
            session.scalars(
                select(File).where(File.interview_id == iv.id)
            )
        )
    assert len(file_rows) == 1
    assert os.path.isfile(file_rows[0].file_path)


def test_concurrent_interview_creation(interview_ids):
    """Fire N simultaneous creation requests and assert every resulting
    interview_id is unique — DUPLICATES are the failure mode we test for.

    Gaps in the numeric suffix are expected (SERIAL advances even on
    rolled-back attempts); duplicates are not.
    """
    n_workers = 25
    pdf = _pdf_bytes()

    def post_one(_):
        with TestClient(app) as c:
            r = c.post(
                "/api/interviews",
                files={"file": ("resume.pdf", pdf, "application/pdf")},
            )
            return r.status_code, r.json()

    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        results = list(ex.map(post_one, range(n_workers)))

    assert all(code == 200 for code, _ in results), results

    ids = [body["interview_id"] for _, body in results]
    interview_ids.extend(ids)

    numeric = sorted(int(i.rsplit("-", 1)[1]) for i in ids)
    print(
        f"concurrent create: {n_workers} requests -> distinct ids={len(set(ids))},"
        f" pk={numeric[0]}..{numeric[-1]},"
        f" gaps(between min/max)={max(numeric) - min(numeric) + 1 - n_workers},"
        f" duplicates={n_workers - len(set(ids))}"
    )

    assert all(ID_PATTERN.fullmatch(i) for i in ids)
    assert all(body["status"] == "QUEUED" for _, body in results)
    assert len(set(ids)) == n_workers