"""Tests for Task 8 — job queue & worker (DB-persisted state, crash recovery).

Requires the Postgres instance from docker-compose to be running.  The worker
is driven explicitly (``process_next_job`` / ``recover_interviews``) — the
background loop is disabled under tests via tests/conftest.py.  The LLM is
stubbed at the pipeline boundary so the e2e path runs without any network.
Sample interviews are cleaned up in teardown, including their record files.
"""

import io
import os

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db import SessionLocal
from app.db.models import File, Interview, QuestionEvaluationKey
from app.models.schemas import InterviewResult, QuestionAnswer
from app.services import interview_service, pipeline_service
from app.services.worker import (
    claim_next_interview,
    process_next_job,
    recover_interviews,
    run_startup_recovery,
)
from app.services.file_store import delete_stored_file

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


def _sample_result() -> InterviewResult:
    return InterviewResult(
        candidate_name="Jane Smith",
        summary="Full Stack developer with 4 years of React/Django experience.",
        questions=[
            QuestionAnswer(
                number=1,
                category="Basic Technical",
                question="What is the difference between HTTP and HTTPS?",
                options=None,
                correct_option=None,
                answer="HTTPS is HTTP with TLS encryption for secure transport.",
                hr_answer="HTTPS keeps communication secure.",
                keywords=["TLS", "encryption", "secure"],
                required_concepts=[
                    {"name": "transport layer security", "weight": 0.7},
                    {"name": "data encryption", "weight": 0.3},
                ],
                important_phrases=["secure transport"],
            ),
            QuestionAnswer(
                number=2,
                category="Resume Skills",
                question="Explain the Django ORM to a junior developer.",
                options=None,
                correct_option=None,
                answer="The Django ORM maps Python classes to database tables.",
                hr_answer="Django makes database work easier.",
                keywords=["ORM", "mapping", "SQL"],
                required_concepts=[
                    {"name": "object-relational mapping", "weight": 0.6},
                    {"name": "query generation", "weight": 0.4},
                ],
                important_phrases=["maps classes to tables"],
            ),
        ],
    )


@pytest.fixture
def interview_ids():
    """Track interviews created by a test; delete them (and their record
    files) in teardown so the dev DB stays clean.  Child rows (files,
    evaluation keys, concepts) are removed by the DB ON DELETE CASCADE."""
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
            file_paths.extend(
                session.scalars(select(File.file_path).where(File.interview_id == iv.id))
            )
            session.delete(iv)
        session.commit()
    for path in file_paths:
        delete_stored_file(path)


def _create_queued(interview_ids) -> str:
    resp = client.post(
        "/api/interviews",
        files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    interview_id = resp.json()["interview_id"]
    interview_ids.append(interview_id)
    return interview_id


def _status_of(interview_id: str) -> tuple[str, str | None]:
    with SessionLocal() as session:
        iv = interview_service.get_interview(session, interview_id)
        assert iv is not None
        return iv.status, iv.processing_stage


def _drain_until_terminal(interview_id: str, cap: int = 100) -> None:
    """Keep running worker iterations until the interview leaves the
    in-flight states (any pre-existing QUEUED rows get processed first)."""
    for _ in range(cap):
        status, _ = _status_of(interview_id)
        if status not in {"QUEUED", "PROCESSING"}:
            return
        process_next_job()
    raise AssertionError(f"interview {interview_id} did not reach a terminal state")


def test_worker_end_to_end_reaches_completed(interview_ids, monkeypatch):
    monkeypatch.setattr(
        pipeline_service, "generate_interview_questions", lambda text: _sample_result()
    )
    iid = _create_queued(interview_ids)

    _drain_until_terminal(iid)

    with SessionLocal() as session:
        iv = interview_service.get_interview(session, iid)
        assert iv is not None
        assert iv.status == "COMPLETED"
        assert iv.processing_stage is None
        assert iv.error_reason is None
        assert iv.candidate_name == "Jane Smith"

        # Evaluation keys persisted per question
        keys = list(
            session.scalars(
                select(QuestionEvaluationKey).where(
                    QuestionEvaluationKey.interview_id == iv.id
                )
            )
        )
        assert len(keys) == 2

        # Both RECORD documents + the resume exist in the files table and on disk
        types = set(
            session.scalars(select(File.file_type).where(File.interview_id == iv.id))
        )
        assert types == {"RESUME", "QUESTION_SHEET", "ANSWER_KEY"}
        for f in session.scalars(select(File).where(File.interview_id == iv.id)):
            assert os.path.isfile(f.file_path)


def test_worker_failure_marks_failed_and_continues(interview_ids, monkeypatch):
    calls = {"n": 0}

    def flaky(text):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated mid-pipeline boom")
        return _sample_result()

    monkeypatch.setattr(pipeline_service, "generate_interview_questions", flaky)

    first = _create_queued(interview_ids)
    second = _create_queued(interview_ids)

    _drain_until_terminal(first)
    _drain_until_terminal(second)

    with SessionLocal() as session:
        iv1 = interview_service.get_interview(session, first)
        assert iv1.status == "FAILED"
        assert iv1.processing_stage is None
        assert iv1.error_reason and "RuntimeError" in iv1.error_reason
        assert "simulated mid-pipeline boom" in iv1.error_reason
        # No stack traces in the stored reason
        assert "Traceback" not in iv1.error_reason

        # The loop kept going: the next job succeeded even though a prior one
        # failed — pipeline failure must not crash the worker.
        iv2 = interview_service.get_interview(session, second)
        assert iv2.status == "COMPLETED"
        assert iv2.error_reason is None

    assert calls["n"] == 2


def test_startup_recovery_resets_inflight_and_reprocesses(interview_ids, monkeypatch):
    monkeypatch.setattr(
        pipeline_service, "generate_interview_questions", lambda text: _sample_result()
    )
    iid = _create_queued(interview_ids)

    # Simulate a crash mid-pipeline: a row stuck in PROCESSING/GENERATING
    # committed before the worker died.
    with SessionLocal() as session:
        iv = interview_service.get_interview(session, iid)
        iv.status = "PROCESSING"
        iv.processing_stage = "GENERATING"
        session.commit()
    assert _status_of(iid) == ("PROCESSING", "GENERATING")

    # Startup recovery re-queues it
    assert run_startup_recovery() == 1
    assert _status_of(iid) == ("QUEUED", None)

    # And the worker picks it back up -> reprocessed to COMPLETED
    _drain_until_terminal(iid)
    with SessionLocal() as session:
        iv = interview_service.get_interview(session, iid)
        assert iv.status == "COMPLETED"
        assert len(
            list(
                session.scalars(
                    select(QuestionEvaluationKey).where(
                        QuestionEvaluationKey.interview_id == iv.id
                    )
                )
            )
        ) == 2


def test_recover_interviews_resets_claim_crash_then_picks_oldest(interview_ids):
    first = _create_queued(interview_ids)
    second = _create_queued(interview_ids)

    # Crash right after claim: status=PROCESSING with NO processing_stage
    with SessionLocal() as session:
        iv = interview_service.get_interview(session, first)
        iv.status = "PROCESSING"
        iv.processing_stage = "EXTRACTING"
        session.commit()

    # Recovery handles both a stage-less claim-crash (second stays QUEUED; it
    # is not an in-flight state) and stage-carrying rows.
    with SessionLocal() as session:
        count = recover_interviews(session)
    assert count == 1
    assert _status_of(first) == ("QUEUED", None)

    # Claim always takes the oldest QUEUED first, and flips it to PROCESSING;
    # a second claim finds nothing left.
    with SessionLocal() as session:
        claimed = claim_next_interview(session)
        assert claimed is not None and claimed.interview_id == first
        assert claimed.status == "PROCESSING"
        second_claim = claim_next_interview(session)
        assert second_claim is not None and second_claim.interview_id == second
        third_claim = claim_next_interview(session)
        assert third_claim is None


def test_recover_interviews_leaves_terminal_rows_alone(interview_ids):
    iid = _create_queued(interview_ids)
    with SessionLocal() as session:
        iv = interview_service.get_interview(session, iid)
        iv.status = "EVALUATED"  # a terminal state for a different pipeline
        session.commit()

    assert run_startup_recovery() == 0
    assert _status_of(iid) == ("EVALUATED", None)