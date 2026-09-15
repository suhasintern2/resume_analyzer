"""Tests for Task 9 — answer-script upload, handwriting OCR & segmentation.

Requires the Postgres instance from docker-compose to be running.  The LLM is
stubbed: ``ocr_handwriting_image/pdf`` are monkeypatched to return canned
marked-up text, and the question-generation pipeline is stubbed the same way
as in test_worker (so an interview can reach COMPLETED without any network).
Sample interviews are cleaned up in teardown, including their record files.
"""

import io
import os

import fitz
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.main import app
from app.db import SessionLocal
from app.db.models import AnswerSegment, File, Interview
from app.models.schemas import InterviewResult, QuestionAnswer
from app.services import answer_script_service, interview_service, pipeline_service
from app.services.answer_segmentation import segment_ocr_text
from app.services.file_store import delete_stored_file
from app.services.worker import (
    claim_next_answer_script,
    process_next_job,
    recover_interviews,
    run_startup_recovery,
)

client = TestClient(app)


def _pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Jane Smith\nSoftware Engineer\n"
        "Professional Summary: Full Stack developer with four years of "
        "experience building web applications using Python, Django, React, "
        "PostgreSQL and MongoDB. Led a team of three developers and shipped "
        "production features for a UK property management platform.\n"
        "Skills: Python, Django, React, PostgreSQL, REST APIs, Docker, AWS\n"
        "Experience: Software Developer at TechCorp (2020-2023)\n"
        "Projects: E-commerce Platform using Django and React, Real-time "
        "dashboard for internal analytics.\n"
        "Education: BSc Computer Science",
    )
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _png_bytes(text: str = "x") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), color=(255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _sample_result() -> InterviewResult:
    return InterviewResult(
        candidate_name="Jane Smith",
        summary="Full Stack developer with 4 years of React/Django experience.",
        questions=[
            QuestionAnswer(
                number=n,
                category="Resume Skills",
                question=f"Question {n} text?",
                options=None,
                correct_option=None,
                answer="Sample answer",
                hr_answer="hr",
                keywords=["k"],
                required_concepts=[{"name": "c", "weight": 1.0}],
                important_phrases=["p"],
            )
            for n in (1, 2)
        ],
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


def _create_completed(interview_ids, monkeypatch) -> str:
    """Create an interview and drive it through the (stubbed) pipeline."""
    monkeypatch.setattr(
        pipeline_service, "generate_interview_questions", lambda text: _sample_result()
    )
    resp = client.post(
        "/api/interviews",
        files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    interview_id = resp.json()["interview_id"]
    interview_ids.append(interview_id)
    for _ in range(50):
        status = _status_of(interview_id)[0]
        if status not in {"QUEUED", "PROCESSING"}:
            break
        process_next_job()
    assert _status_of(interview_id)[0] == "COMPLETED"
    return interview_id


def _status_of(interview_id: str) -> tuple[str, str | None]:
    with SessionLocal() as session:
        iv = interview_service.get_interview(session, interview_id)
        assert iv is not None
        return iv.status, iv.processing_stage


def _upload(interview_id: str, *files, name="script.pdf", content_type="application/pdf"):
    return client.post(
        f"/api/interviews/{interview_id}/answer-script",
        files=[("files", (name, content, content_type)) for content in files],
    )


# ── pure segmentation logic ──────────────────────────────────────────────


def test_segmentation_matches_all_questions_cleanly():
    ocr_text = (
        "Question 1: React is a JavaScript UI library.\n"
        "Question 2: The Django ORM maps classes to tables."
    )
    segments, matched = segment_ocr_text(ocr_text, question_count=2)
    assert matched is True
    assert [s.question_number for s in segments] == [1, 2]
    assert all(s.status == "TRANSCRIBED" for s in segments)
    assert segments[0].content == "React is a JavaScript UI library."
    assert segments[1].content == "The Django ORM maps classes to tables."


def test_segmentation_supports_short_markers_and_preamble():
    ocr_text = (
        "Candidate answers\n"
        "Q1) Python\n"
        "Q2: JavaScript"
    )
    segments, matched = segment_ocr_text(ocr_text, question_count=2)
    assert matched is True
    assert segments[0].question_number is None  # unnumbered preamble kept for review
    assert [s.question_number for s in segments[1:]] == [1, 2]


def test_segmentation_flags_missing_marker_as_uncertain():
    # Q2's marker is missing entirely — must NOT be guessed to be Q2.
    ocr_text = "Question 1: first\nQuestion 3: third"
    segments, matched = segment_ocr_text(ocr_text, question_count=3)
    assert matched is False
    assert [s.question_number for s in segments] == [1, 3]


def test_segmentation_flags_duplicate_marker_as_uncertain():
    ocr_text = "Question 2: a duplicate\nQuestion 2: repeated again"
    segments, matched = segment_ocr_text(ocr_text, question_count=2)
    assert matched is False
    assert [s.question_number for s in segments] == [2, 2]


def test_segmentation_blank_marker_is_not_dropped_or_text():
    ocr_text = (
        "Question 1: [BLANK]\n"
        "Question 2: He wrote [BLANK] in the sandbox."
    )
    segments, matched = segment_ocr_text(ocr_text, question_count=2)
    assert matched is True
    assert segments[0].status == "BLANK"
    assert segments[0].content == ""
    # Marker inside real text stays TRANSCRIBED, marker preserved verbatim.
    assert segments[1].status == "TRANSCRIBED"
    assert segments[1].content == "He wrote [BLANK] in the sandbox."


def test_segmentation_illegible_marker():
    ocr_text = "Question 1: [ILLEGIBLE]\nQuestion 2: readable text"
    segments, matched = segment_ocr_text(ocr_text, question_count=2)
    assert matched is True
    assert segments[0].status == "ILLEGIBLE"
    assert segments[1].status == "TRANSCRIBED"


def test_segmentation_blank_marker_not_conflated_with_illegible():
    segments, matched = segment_ocr_text(
        "Question 1: [BLANK]\nQuestion 2: [ILLEGIBLE]", question_count=2,
    )
    assert matched is True
    assert segments[0].status == "BLANK"
    assert segments[1].status == "ILLEGIBLE"


# ── upload endpoint ──────────────────────────────────────────────────────


def test_upload_persists_answer_script_files(interview_ids, monkeypatch):
    interview_id = _create_completed(interview_ids, monkeypatch)
    resp = _upload(
        interview_id,
        b"%PDF-1.4 fake pdf content here for validation",
        name="answers.pdf",
        content_type="application/pdf",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["status"] == "ANSWER_UPLOADED"
    assert body["files_uploaded"] == 1

    with SessionLocal() as session:
        iv = interview_service.get_interview(session, interview_id)
        types = set(
            session.scalars(select(File.file_type).where(File.interview_id == iv.id))
        )
        assert "ANSWER_SCRIPT" in types
        script = session.scalar(
            select(File).where(
                File.interview_id == iv.id, File.file_type == "ANSWER_SCRIPT",
            )
        )
        assert os.path.isfile(script.file_path)


def test_upload_accepts_multiple_images_and_replaces(interview_ids, monkeypatch):
    interview_id = _create_completed(interview_ids, monkeypatch)

    first = _upload(
        interview_id,
        _png_bytes(), _png_bytes(),
        name="page1.png", content_type="image/png",
    )
    assert first.status_code == 200
    assert first.json()["files_uploaded"] == 2

    # Re-upload: previous pages are wiped, not accumulated.
    second = _upload(
        interview_id,
        _png_bytes(),
        name="new.png", content_type="image/png",
    )
    assert second.status_code == 200
    assert second.json()["files_uploaded"] == 1

    with SessionLocal() as session:
        iv = interview_service.get_interview(session, interview_id)
        scripts = list(
            session.scalars(
                select(File).where(
                    File.interview_id == iv.id, File.file_type == "ANSWER_SCRIPT",
                )
            )
        )
        assert len(scripts) == 1


def test_upload_rejects_invalid_extension(interview_ids, monkeypatch):
    interview_id = _create_completed(interview_ids, monkeypatch)
    resp = _upload(
        interview_id,
        b"hello", name="answers.txt", content_type="text/plain",
    )
    assert resp.status_code == 400


def test_upload_rejects_when_interview_not_ready(interview_ids, monkeypatch):
    # An interview still QUEUED (pipeline not run) has no questions yet.
    resp = client.post(
        "/api/interviews",
        files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    interview_id = resp.json()["interview_id"]
    interview_ids.append(interview_id)

    resp = _upload(interview_id, _png_bytes(), name="a.png", content_type="image/png")
    assert resp.status_code == 409


def test_upload_rejects_unknown_interview():
    resp = _upload("INT-19990101-001", _png_bytes(), name="a.png", content_type="image/png")
    assert resp.status_code == 404


# ── worker-driven OCR segmentation ───────────────────────────────────────


def test_worker_segments_uploaded_scripts(interview_ids, monkeypatch):
    interview_id = _create_completed(interview_ids, monkeypatch)

    # Two scanned pages, each contributing answers for different questions;
    # the joined text must still align cleanly to Q1..Q2.
    ocr_texts = iter([
        "Question 1: Python is great.",
        "Question 2: Django ORM.",
    ])
    monkeypatch.setattr(
        answer_script_service, "ocr_handwriting_image", lambda data: next(ocr_texts)
    )
    monkeypatch.setattr(
        answer_script_service, "ocr_handwriting_pdf", lambda path: next(ocr_texts)
    )

    _upload(
        interview_id,
        _png_bytes(), _png_bytes(),
        name="script.png", content_type="image/png",
    )
    resp = client.get(f"/api/interviews/{interview_id}/segments")  # no segments yet
    assert resp.status_code == 409

    # Worker OCRs + segments -> SEGMENTED (markers matched 1..2).
    assert process_next_job() is True
    assert _status_of(interview_id) == ("SEGMENTED", None)

    resp = client.get(f"/api/interviews/{interview_id}/segments")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SEGMENTED"
    assert body["matched"] is True
    assert [s["question_number"] for s in body["segments"]] == [1, 2]
    assert {s["content"] for s in body["segments"]} == {
        "Python is great.", "Django ORM.",
    }
    assert all(s["status"] == "TRANSCRIBED" for s in body["segments"])


def test_worker_marks_failed_when_no_question_keys(interview_ids, monkeypatch):
    # Upload answer scripts to an interview with zero evaluation keys: the
    # segmentation must fail rather than guess, and the worker marks FAILED.
    resp = client.post(
        "/api/interviews",
        files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    interview_id = resp.json()["interview_id"]
    interview_ids.append(interview_id)

    # Manually move it to COMPLETED-ish without keys: simplest faithful route
    # is to let the worker pipeline run with a stub that produces questions,
    # then delete the keys to simulate an inconsistent DB.
    with SessionLocal() as session:
        iv = interview_service.get_interview(session, interview_id)
        iv.status = "COMPLETED"
        session.commit()

    _upload(interview_id, _png_bytes(), name="a.png", content_type="image/png")
    assert process_next_job() is True
    assert _status_of(interview_id)[0] == "FAILED"


def test_recovery_resets_stage_for_answer_uploaded(interview_ids, monkeypatch):
    interview_id = _create_completed(interview_ids, monkeypatch)
    _upload(interview_id, _png_bytes(), name="a.png", content_type="image/png")

    # Crash right after claim: ANSWER_UPLOADED with a stage set.
    with SessionLocal() as session:
        iv = interview_service.get_interview(session, interview_id)
        assert iv.status == "ANSWER_UPLOADED"
        claimed = claim_next_answer_script(session)
        assert claimed is not None and claimed.interview_id == interview_id
    assert _status_of(interview_id) == ("ANSWER_UPLOADED", "EXTRACTING_ANSWERS")

    # Recovery clears the stage so the answer-script claim can retry.
    assert run_startup_recovery() == 1
    assert _status_of(interview_id) == ("ANSWER_UPLOADED", None)

    monkeypatch.setattr(
        answer_script_service, "ocr_handwriting_image",
        lambda data: "Question 1: ok\nQuestion 2: ok",
    )
    monkeypatch.setattr(
        answer_script_service, "ocr_handwriting_pdf",
        lambda data: "Question 1: ok\nQuestion 2: ok",
    )
    assert process_next_job() is True
    assert _status_of(interview_id) == ("SEGMENTED", None)


# ── manual override ──────────────────────────────────────────────────────


def test_manual_reassign_preserves_original_and_recomputes_status(
    interview_ids, monkeypatch,
):
    interview_id = _create_completed(interview_ids, monkeypatch)

    # OCR that mis-labels Q1 as Q2 -> duplicate Q2, Q1 missing -> UNCERTAIN.
    monkeypatch.setattr(
        answer_script_service, "ocr_handwriting_image",
        lambda data: "Question 2: alpha\nQuestion 2: beta",
    )
    monkeypatch.setattr(
        answer_script_service, "ocr_handwriting_pdf",
        lambda data: "Question 2: alpha\nQuestion 2: beta",
    )
    _upload(interview_id, _png_bytes(), name="a.png", content_type="image/png")
    assert process_next_job() is True
    assert _status_of(interview_id) == ("SEGMENTATION_UNCERTAIN", None)

    resp = client.get(f"/api/interviews/{interview_id}/segments")
    assert resp.status_code == 200
    segments = resp.json()["segments"]
    assert resp.json()["matched"] is False
    assert [s["question_number"] for s in segments] == [2, 2]

    # Correct the first block to Q1 -> set is {1, 2} exactly -> SEGMENTED.
    first_id = segments[0]["id"]
    resp = client.post(
        f"/api/interviews/{interview_id}/segments/{first_id}/reassign",
        json={"question_number": 1},
    )
    assert resp.status_code == 200
    assert resp.json()["segment"]["is_manual_override"] is True
    assert resp.json()["segment"]["question_number"] == 1
    assert resp.json()["segment"]["original_question_number"] == 2
    assert resp.json()["matched"] is True

    # Reassignment is auditable and the status recomputed.
    resp = client.get(f"/api/interviews/{interview_id}/segments")
    nums = sorted(s["question_number"] for s in resp.json()["segments"])
    assert nums == [1, 2]
    overridden = [s for s in resp.json()["segments"] if s["is_manual_override"]]
    assert len(overridden) == 1
    assert overridden[0]["original_question_number"] == 2


def test_reassign_validates_question_number(interview_ids, monkeypatch):
    interview_id = _create_completed(interview_ids, monkeypatch)
    monkeypatch.setattr(
        answer_script_service, "ocr_handwriting_image",
        lambda data: "Question 1: one\nQuestion 2: two",
    )
    monkeypatch.setattr(
        answer_script_service, "ocr_handwriting_pdf",
        lambda data: "Question 1: one\nQuestion 2: two",
    )
    _upload(interview_id, _png_bytes(), name="a.png", content_type="image/png")
    assert process_next_job() is True

    seg_id = client.get(f"/api/interviews/{interview_id}/segments").json()["segments"][0]["id"]
    resp = client.post(
        f"/api/interviews/{interview_id}/segments/{seg_id}/reassign",
        json={"question_number": 0},
    )
    assert resp.status_code == 400

    resp = client.post(
        f"/api/interviews/{interview_id}/segments/{seg_id}/reassign",
        json={"question_number": 1},
    )
    assert resp.status_code == 200