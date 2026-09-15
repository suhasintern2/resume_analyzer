"""Tests for Task 6 — retention/purge job (amendment §6).

Requires Postgres from docker-compose. Creates real rows + files; cleans up.
"""

import io
import os
from datetime import datetime, timedelta, timezone

import fitz
import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.db.models import Evaluation, File, Interview
from app.services import interview_service
from app.services.file_store import delete_stored_file
from app.services.retention_service import (
    find_expired_files,
    purge_expired_records,
)


def _pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Jane Smith\nSoftware Engineer\nSkills: React\n")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


@pytest.fixture
def track_files():
    """Collect (interview_id, file paths) and our own copies so teardown
    removes both the DB rows and any on-disk files still present."""
    made: list[str] = []
    paths: list[str] = []
    yield made, paths
    with SessionLocal() as session:
        for iv_id in made:
            iv = interview_service.get_interview(session, iv_id)
            if iv:
                session.delete(iv)
        session.commit()
    for p in paths:
        delete_stored_file(p)


def test_purge_deletes_only_evaluated_and_old(track_files):
    made, paths = track_files
    now = datetime.now(timezone.utc)

    def make_old(interview_id: str | None = None):
        with SessionLocal() as session:
            iv = interview_service.create_interview(
                session, content=_pdf_bytes(), ext="pdf",
            )
            session.flush()
            made.append(iv.interview_id)
            paths.append(
                session.scalar(
                    select(File).where(File.interview_id == iv.id)
                ).file_path
            )
            # Force updated_at into the past (old) and mark EVALUATED
            iv.status = "EVALUATED"
            iv.updated_at = now - timedelta(days=45)
            session.add(
                Evaluation(
                    interview_id=iv.id,
                    evaluator_version="1.0",
                    status="EVALUATED",
                    created_at=now - timedelta(days=45),
                    updated_at=now - timedelta(days=45),
                )
            )
            session.commit()
        return iv.id

    # 1) EVALUATED + old -> eligible for purge
    old_id = make_old()

    # 2) EVALUATED + recent -> NOT eligible
    with SessionLocal() as session:
        iv = interview_service.create_interview(
            session, content=_pdf_bytes(), ext="pdf",
        )
        session.flush()
        made.append(iv.interview_id)
        paths.append(
            session.scalar(select(File).where(File.interview_id == iv.id)).file_path
        )
        iv.status = "EVALUATED"
        session.commit()
        recent_id = iv.id

    # 3) old but still QUEUED/PROCESSING (mid-lifecycle) -> NOT eligible
    with SessionLocal() as session:
        iv = interview_service.create_interview(
            session, content=_pdf_bytes(), ext="pdf",
        )
        session.flush()
        made.append(iv.interview_id)
        paths.append(
            session.scalar(select(File).where(File.interview_id == iv.id)).file_path
        )
        iv.updated_at = now - timedelta(days=60)
        session.commit()
        queued_id = iv.id

    with SessionLocal() as session:
        eligible = find_expired_files(session, retention_days=30, now=now)
        eligible_ids = {iv.id for iv, _ in eligible}
        assert eligible_ids == {old_id}

        summary = purge_expired_records(session, retention_days=30, now=now)

    assert sum(len(v) for v in summary.values()) == 1

    # old/evaluated interview: file row + file deleted
    with SessionLocal() as session:
        assert session.scalar(
            select(File).where(File.interview_id == old_id)
        ) is None
        assert sum(len(v) for v in summary.values()) == 1
        # recent evaluated and queued untouched
        assert session.scalar(
            select(File).where(File.interview_id == recent_id)
        ) is not None
        assert session.scalar(
            select(File).where(File.interview_id == queued_id)
        ) is not None


def test_purge_honors_retention_floor(track_files):
    made, paths = track_files
    now = datetime.now(timezone.utc)

    with SessionLocal() as session:
        iv = interview_service.create_interview(
            session, content=_pdf_bytes(), ext="pdf",
        )
        session.flush()
        made.append(iv.interview_id)
        iv.status = "EVALUATED"
        iv.updated_at = now - timedelta(days=10)  # younger than 30d window
        session.commit()

    with SessionLocal() as session:
        eligible = find_expired_files(session, retention_days=30, now=now)
        assert eligible == []
        summary = purge_expired_records(session, retention_days=30, now=now)
        assert summary == {}

    with SessionLocal() as session:
        assert session.scalar(
            select(File).where(File.interview_id == iv.id)
        ) is not None


def test_purge_logs_and_keeps_evaluation_rows(track_files):
    made, paths = track_files
    now = datetime.now(timezone.utc)

    with SessionLocal() as session:
        iv = interview_service.create_interview(
            session, content=_pdf_bytes(), ext="pdf",
        )
        session.flush()
        made.append(iv.interview_id)
        iv.status = "EVALUATED"
        iv.updated_at = now - timedelta(days=40)
        ev = Evaluation(
            interview_id=iv.id,
            evaluator_version="1.0",
            status="EVALUATED",
            created_at=now - timedelta(days=40),
            updated_at=now - timedelta(days=40),
        )
        session.add(ev)
        session.commit()
        eval_id = ev.id
        interview_pk = iv.id

    summary = None
    with SessionLocal() as session:
        summary = purge_expired_records(session, retention_days=30, now=now)

    assert summary and len(summary) == 1

    # The interview + evaluation rows survive purge; only files rows go
    with SessionLocal() as session:
        assert session.get(Interview, interview_pk) is not None
        assert session.get(Evaluation, eval_id) is not None
        assert session.scalar(
            select(File).where(File.interview_id == interview_pk)
        ) is None


def test_retention_script_runs():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/retention_job.py"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    assert result.returncode == 0
    assert "purged" in result.stdout