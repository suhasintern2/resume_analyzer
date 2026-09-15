"""Retention/purge of RECORD files (amendment §6 / Task 6).

A deliberate, logged, *scheduled* operation — never triggered by request
handling. Purges record files and their ``files`` rows only for interviews
whose evaluation is complete (``interviews.status == 'EVALUATED'``) AND
whose last lifecycle transition is older than ``RETENTION_DAYS``. Nothing
mid-lifecycle is ever touched.

Operates off the ``files`` table rows (source of truth), never by scanning
the upload directory.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Evaluation, File, Interview
from app.services.file_store import delete_stored_file

logger = logging.getLogger(__name__)

_MAX_PURGES_PER_RUN = 500


def _cutoff(retention_days: int, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now - timedelta(days=retention_days)


def find_expired_files(
    session: Session, *, retention_days: int, now: datetime | None = None,
) -> list[tuple[Interview, File]]:
    """Return (interview, file) pairs eligible for purge, oldest first.

    Eligibility ("evaluation complete AND older than the retention window"):
    the interview is EVALUATED and its *latest* evaluation (the EVALUATED
    run with the greatest ``created_at``) completed more than
    ``RETENTION_DAYS`` ago. Nothing mid-lifecycle is ever eligible
    (QUEUED/PROCESSING/COMPLETED interviews never match). Limited to
    _MAX_PURGES_PER_RUN rows.
    """
    cutoff = _cutoff(retention_days, now)

    # Latest EVALUATED evaluation timestamp per interview
    latest_eval = (
        select(
            Evaluation.interview_id,
            func.max(Evaluation.created_at).label("last_evaluated_at"),
        )
        .where(Evaluation.status == "EVALUATED")
        .group_by(Evaluation.interview_id)
        .subquery()
    )

    rows = session.execute(
        select(Interview, File)
        .join(File, File.interview_id == Interview.id)
        .join(latest_eval, latest_eval.c.interview_id == Interview.id)
        .where(
            Interview.status == "EVALUATED",
            latest_eval.c.last_evaluated_at < cutoff,
        )
        .order_by(latest_eval.c.last_evaluated_at.asc())
        .limit(_MAX_PURGES_PER_RUN)
    ).all()
    return [(iv, f) for iv, f in rows]


def purge_expired_records(
    session: Session, *, retention_days: int, now: datetime | None = None,
) -> dict:
    """Delete expired record files and their ``files`` rows.

    Returns a summary of purged rows keyed by ``interview_id`` with lists
    of file types. Each purge is logged (never the file contents).
    """
    if retention_days <= 0:
        raise ValueError("RETENTION_DAYS must be a positive number")

    cutoff = _cutoff(retention_days, now)
    purged: dict[str, list[str]] = {}
    timestamp = datetime.now(timezone.utc).isoformat()

    for interview, file_row in find_expired_files(
        session, retention_days=retention_days, now=now,
    ):
        delete_stored_file(file_row.file_path)
        session.delete(file_row)
        purged.setdefault(interview.interview_id, []).append(file_row.file_type)
        logger.info(
            "PURGE interview_id=%s file_type=%s timestamp=%s",
            interview.interview_id, file_row.file_type, timestamp,
        )

    session.commit()

    total = sum(len(types) for types in purged.values())
    logger.info(
        "Retention run complete: %d file row(s) purged, cutoff=%s",
        total, cutoff.isoformat(),
    )
    return purged