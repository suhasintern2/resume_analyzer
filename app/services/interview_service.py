"""Interview creation, lookup, rename, and round helpers.

Interview ID generation is race-free per amendment §2 and Task 3: the row is
INSERTed first (Postgres assigns the SERIAL PK inside the transaction), the
human-readable ``INT-{serial}`` ID is derived from that PK (Task 11 — the
serial is zero-padded to at least 3 digits, e.g. INT-001 … INT-999, then
INT-1000 onwards, never capped), and the row is UPDATE'd with it before
commit. The UNIQUE constraint on ``interviews.interview_id`` is the final
safety net; a small retry loop treats any violation as a transient collision.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import File, Interview, InterviewRound, ROUND_1, ROUND_2
from app.services.file_store import delete_stored_file, persist_record

logger = logging.getLogger(__name__)

_MAX_INSERT_ATTEMPTS = 3


def build_interview_id(interview_pk: int) -> str:
    """Short display ID: INT-{serial}, zero-padded to at least 3 digits.

    INT-001 … INT-999, then INT-1000 onward — never truncated, never padded
    beyond what the number needs.
    """
    return f"INT-{interview_pk:03d}"


def _insert_interview_tx(
    session: Session,
    *,
    candidate_name: str | None,
    content: bytes,
    ext: str,
    file_type: str,
    email: str | None = None,
    phone: str | None = None,
    original_filename: str | None = None,
    display_name: str | None = None,
) -> tuple[Interview, str]:
    """INSERT → derive ID → persist RECORD file under interview dir → wire files row.

    The record file is written inside the same transaction as the row, so a
    failed/rolled-back insert leaves no orphaned file behind. Returns
    ``(interview, relative_file_path)``.
    """
    # ``interview_id`` is NOT NULL, so the row needs a value at INSERT time.
    # We insert a unique, server-side, never-committed placeholder, and
    # overwrite it with the PK-derived ID below — still INSERT-first,
    # derive-from-PK, UPDATE-before-commit, all in this one transaction.
    interview = Interview(
        candidate_name=candidate_name,
        email=email,
        phone=phone,
        original_filename=original_filename,
        display_name=display_name or original_filename,
        status="QUEUED",
        interview_id=f"PENDING-{uuid.uuid4().hex}",
    )
    session.add(interview)
    session.flush()  # Postgres assigns the real SERIAL PK here

    interview.interview_id = build_interview_id(interview.id)

    # Persist into <UPLOAD_DIR>/<interview_id>/ — the interview_id is only
    # known after the row is flushed, which is why the file is written here.
    file_path = persist_record(
        content,
        interview_id=interview.interview_id,
        file_type=file_type,
        ext=ext,
    )

    session.add(
        File(
            interview_id=interview.id,
            file_type=file_type,
            file_path=file_path,
        )
    )

    # Round 1 AND Round 2 exist from the moment the interview is created
    # (Task 12 revision — both rounds are generated upfront in the worker).
    # Round 2's content is delivered only after the select-next-round access
    # gate is met (round 1 EVALUATED + selected_for_next_round=true).
    for _round_number in (ROUND_1, ROUND_2):
        _round = InterviewRound(
            interview_id=interview.id,
            round_number=_round_number,
            status="NOT_STARTED",
            selected_for_next_round=None,
        )
        session.add(_round)
    session.flush()

    return interview, file_path


def create_interview(
    session: Session,
    *,
    content: bytes,
    ext: str,
    candidate_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    original_filename: str | None = None,
) -> Interview:
    """Persist the resume as a record file and create the QUEUED interview.

    ``original_filename`` is captured exactly as received at upload time and
    is a pure display/labeling concern — the stored record file keeps its
    safe server-generated uuid4 name. ``display_name`` defaults to it.

    On a DB failure the just-written record file is removed again so we
    never leave an orphaned on-disk file or a ``files`` row whose interview
    does not exist. The (very unlikely) IntegrityError retry path cleans up
    the file from the failed attempt before trying again.
    """
    attempts = 0
    while True:
        pending_path: str | None = None
        try:
            with session.begin():
                _interview, pending_path = _insert_interview_tx(
                    session,
                    candidate_name=candidate_name,
                    content=content,
                    ext=ext,
                    file_type="RESUME",
                    email=email,
                    phone=phone,
                    original_filename=original_filename,
                )
                return _interview
        except IntegrityError as e:
            # The transaction rolled back, so any record file written by
            # this attempt is orphaned — remove it before retrying.
            if pending_path:
                delete_stored_file(pending_path)
            attempts += 1
            if attempts >= _MAX_INSERT_ATTEMPTS:
                raise
            logger.warning(
                "interview_id collision on insert, retry %d/%d: %s",
                attempts, _MAX_INSERT_ATTEMPTS - 1, e,
            )
        except Exception:
            if pending_path:
                delete_stored_file(pending_path)
            raise


def get_interview(session: Session, interview_id: str) -> Interview | None:
    return session.scalar(
        select(Interview).where(Interview.interview_id == interview_id)
    )


def rename_interview(
    session: Session,
    interview: Interview,
    *,
    display_name: str,
) -> Interview:
    """Update the dashboard label for an interview. Pure display concern."""
    interview.display_name = display_name.strip()
    session.commit()
    logger.info(
        "Renamed interview %s display_name -> %s",
        interview.interview_id, interview.display_name,
    )
    return interview


# ---------------------------------------------------------------------------
# Round helpers (Task 11)
# ---------------------------------------------------------------------------

def get_round(
    session: Session,
    *,
    interview_pk: int,
    round_number: int,
) -> InterviewRound | None:
    return session.scalar(
        select(InterviewRound).where(
            InterviewRound.interview_id == interview_pk,
            InterviewRound.round_number == round_number,
        )
    )


def _ensure_round_for_legacy(
    session: Session,
    interview: Interview,
    *,
    round_number: int,
) -> InterviewRound | None:
    """Return a round row for the interview.

    New interviews always have round 1 from creation; round 2 is created only
    by select-next-round. Pre-Task-11 legacy interviews have neither — for them
    round 1 is handled in "legacy mode" (no round row, round_id NULL) and round
    2 never exists. Returns ``None`` only for legacy round 1 or a nonexistent
    round 2.
    """
    round_obj = get_round(session, interview_pk=interview.id, round_number=round_number)
    if round_obj is not None or round_number != ROUND_1:
        return round_obj
    has_any = session.scalar(
        select(InterviewRound).where(InterviewRound.interview_id == interview.id)
    )
    if has_any is not None:
        # A modern interview should always have round 1; treat missing as 404.
        return None
    # Legacy interview (created before Task 11) — operate round-1 only,
    # safely, without back-filling a round row.
    return None


def list_rounds(
    session: Session,
    *,
    interview_pk: int,
) -> list[InterviewRound]:
    return list(
        session.scalars(
            select(InterviewRound)
            .where(InterviewRound.interview_id == interview_pk)
            .order_by(InterviewRound.round_number)
        ).all()
    )


def set_round_status(
    session: Session,
    round_obj: InterviewRound,
    *,
    status: str,
) -> None:
    round_obj.status = status
    session.commit()


def create_round2(
    session: Session,
    interview: Interview,
) -> InterviewRound:
    """Ensure a round-2 row exists (Task 12 revision).

    Modern interviews have both round rows from creation; this is now only a
    safety net for legacy pre-Task-12 rows.  When the round already exists it
    is returned unchanged (idempotent) instead of raising.
    """
    existing = get_round(session, interview_pk=interview.id, round_number=ROUND_2)
    if existing is not None:
        return existing
    round2 = InterviewRound(
        interview_id=interview.id,
        round_number=ROUND_2,
        status="NOT_STARTED",
        selected_for_next_round=None,
    )
    session.add(round2)
    session.flush()
    session.commit()
    logger.info(
        "Interview %s: round 2 row created (legacy backfill, NOT_STARTED)",
        interview.interview_id,
    )
    return round2


def round2_unlock_access(
    session: Session,
    interview: Interview,
) -> InterviewRound:
    """Select the candidate for Round 2 (access-gate action, Task 12).

    Round 2 questions are generated upfront at creation, so this action only
    flips the access flag on round 1 — it never triggers generation.
    Enforces the gate before flipping: round 1 must be EVALUATED.
    """
    r1 = get_round(session, interview_pk=interview.id, round_number=ROUND_1)
    if r1 is None:
        raise ValueError(
            f"Interview {interview.interview_id} has no round-1 row."
        )
    if r1.status != "EVALUATED":
        raise ValueError(
            "Round 1 must be fully evaluated before this candidate can "
            "be selected for Round 2."
        )
    r1.selected_for_next_round = True
    round2 = create_round2(session, interview)
    session.commit()
    logger.info(
        "Interview %s: unlocked round 2 access (round-1 selected_for_next_round=True)",
        interview.interview_id,
    )
    return round2