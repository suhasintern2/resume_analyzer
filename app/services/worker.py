"""Background worker loop + startup recovery (Task 8).

Job state lives 100% in the ``interviews`` table (``status`` +
``processing_stage`` + ``error_reason``); nothing is held in memory.  A
lightweight polling loop (no Celery/Kafka/Redis) claims the next QUEUED
interview with Postgres ``SELECT ... FOR UPDATE SKIP LOCKED`` so it stays
correct even if more than one worker process is ever run.
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.db.models import Interview
from app.services import answer_script_service
from app.services.pipeline_service import run_pipeline
from app.services.answer_script_service import process_answer_script
from app.services.answer_evaluator import AnswerEvaluationService

logger = logging.getLogger(__name__)

# Statuses this pipeline can leave behind if the process dies mid-flight. All
# of them are safe to re-queue (see module docstring of pipeline_service and
# the Task 8 CHANGELOG retry-safety decision): the pipeline never persists
# partial artifacts that a re-run would corrupt.
_INFLIGHT_STATUSES = ("PROCESSING",)

# Re-queued interviews keep their prior failure reason cleared.
_MAX_ERROR_REASON_LENGTH = 500


def claim_next_interview(session: Session) -> Interview | None:
    """Atomically claim the oldest QUEUED interview, oldest first.

    ``SELECT ... FOR UPDATE SKIP LOCKED`` lets concurrent workers each grab a
    distinct row without blocking each other; the committed
    ``status=PROCESSING`` transition then makes the claim durable.
    """
    stmt = (
        select(Interview)
        .where(Interview.status == "QUEUED")
        .order_by(Interview.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    interview = session.scalar(stmt)
    if interview is None:
        return None
    interview.status = "PROCESSING"
    interview.processing_stage = None
    session.commit()
    logger.info(
        "Claimed interview %s (pk=%d)", interview.interview_id, interview.id,
    )
    return interview


def claim_next_answer_script(session: Session) -> Interview | None:
    """Atomically claim the oldest ANSWER_UPLOADED interview for OCR.

    Same SKIP LOCKED discipline as the pipeline claim.  ``processing_stage``
    is NULL because the pipeline flow never touches these rows; it is set to
    EXTRACTING_ANSWERS here as the in-flight marker, and cleared by recovery
    on crash.
    """
    stmt = (
        select(Interview)
        .where(
            Interview.status == "ANSWER_UPLOADED",
            Interview.processing_stage.is_(None),
        )
        .order_by(Interview.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    interview = session.scalar(stmt)
    if interview is None:
        return None
    interview.processing_stage = "EXTRACTING_ANSWERS"
    session.commit()
    logger.info(
        "Claimed answer script for %s (pk=%d)",
        interview.interview_id, interview.id,
    )
    return interview


def claim_next_evaluation(session: Session) -> Interview | None:
    """Atomically claim the oldest EVALUATING interview for deterministic evaluation.

    Same SKIP LOCKED discipline as pipeline/script claims. processing_stage is
    set to EVALUATING_ANSWERS as the in-flight marker, and cleared on crash recovery.
    """
    stmt = (
        select(Interview)
        .where(
            Interview.status == "EVALUATING",
            Interview.processing_stage.is_(None),
        )
        .order_by(Interview.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    interview = session.scalar(stmt)
    if interview is None:
        return None
    interview.processing_stage = "EVALUATING_ANSWERS"
    session.commit()
    logger.info(
        "Claimed evaluation for %s (pk=%d)",
        interview.interview_id, interview.id,
    )
    return interview


def process_interview_evaluation(session: Session, interview: Interview) -> None:
    """Execute deterministic evaluation for an interview's active round and persist results."""
    round_obj = answer_script_service.resolve_active_answer_round(session, interview)
    round_id = round_obj.id if round_obj is not None else None
    eval_data = AnswerEvaluationService.evaluate_interview(
        session, interview, round_id=round_id,
    )
    AnswerEvaluationService.persist_evaluation(
        session, interview, eval_data, round_id=round_id,
    )


def mark_evaluation_failed(
    session: Session, interview: Interview, exc: Exception,
) -> None:
    """Persist status=EVALUATION_FAILED + a safe error reason."""
    if interview is None:
        return
    interview.status = "EVALUATION_FAILED"
    interview.processing_stage = None
    interview.error_reason = safe_error_message(exc)
    session.commit()
    logger.error(
        "Interview %s EVALUATION_FAILED: %s",
        interview.interview_id, interview.error_reason,
    )


def safe_error_message(exc: Exception) -> str:
    """Build a stored, user-safe failure reason — never a stack trace.

    Kept short; the full traceback is only ever written to server logs.
    """
    detail = str(exc).strip() or exc.__class__.__name__
    return f"{exc.__class__.__name__}: {detail}"[: _MAX_ERROR_REASON_LENGTH]


def mark_failed(
    session: Session, interview: Interview, exc: Exception,
) -> None:
    """Persist status=FAILED + a safe error reason (no stack traces)."""
    if interview is None:
        return
    interview.status = "FAILED"
    interview.processing_stage = None
    interview.error_reason = safe_error_message(exc)
    session.commit()
    logger.error(
        "Interview %s FAILED: %s",
        interview.interview_id, interview.error_reason,
    )


def process_next_job() -> bool:
    """Claim and process up to one job. Returns True if a job ran.

    Two queues share one loop, both driven off the ``interviews`` table:
    the question-generation pipeline (QUEUED -> COMPLETED) and the answer-
    script OCR/segmentation pipeline (ANSWER_UPLOADED -> SEGMENTED /
    SEGMENTATION_UNCERTAIN).  A failure inside a job marks that interview
    FAILED and returns True (loop keeps going); a failure *claiming* returns
    False so the loop sleeps and retries.
    """
    with SessionLocal() as session:
        # 1) Question-generation queue.
        try:
            interview = claim_next_interview(session)
        except Exception:
            logger.exception("Worker claim failed; will retry")
            return False
        if interview is not None:
            try:
                run_pipeline(session, interview)
            except Exception as e:
                # Full traceback goes to server logs only; the DB stores a safe
                # one-line reason. The loop continues for subsequent jobs.
                logger.exception(
                    "Pipeline failed for interview %s", interview.interview_id,
                )
                mark_failed(session, interview, e)
            return True

        # 2) Answer-script queue.
        try:
            interview = claim_next_answer_script(session)
        except Exception:
            logger.exception("Worker answer-script claim failed; will retry")
            return False
        if interview is not None:
            try:
                process_answer_script(session, interview)
            except Exception as e:
                logger.exception(
                    "Answer script failed for interview %s", interview.interview_id,
                )
                session.rollback()
                mark_failed(session, interview, e)
            return True

        # 3) Evaluation queue.
        try:
            interview = claim_next_evaluation(session)
        except Exception:
            logger.exception("Worker evaluation claim failed; will retry")
            return False
        if interview is None:
            return False
        try:
            process_interview_evaluation(session, interview)
        except Exception as e:
            logger.exception(
                "Evaluation failed for interview %s", interview.interview_id,
            )
            session.rollback()
            mark_evaluation_failed(session, interview, e)
        return True


def recover_interviews(session: Session) -> int:
    """Startup recovery: reset any in-flight row back to a claimable state.

    Three kinds of rows can be left by a crash:
    - ``PROCESSING`` (pipeline EXTRACTING/GENERATING/FORMATTING, or a bare
      claim) -> re-queued for the question-generation pipeline;
    - ``ANSWER_UPLOADED`` with a non-null ``processing_stage`` (a claim made
      by the answer-script pipeline before its OCR/segmentation finished) ->
      stage cleared so the answer-script claim picks it up again;
    - ``EVALUATING`` with a non-null ``processing_stage`` (a claim made by the
      evaluator before persistence finished) -> stage cleared so the evaluation
      claim picks it up again.
    """
    rows = list(
        session.scalars(
            select(Interview).where(Interview.status.in_(_INFLIGHT_STATUSES))
        ).all()
    )
    for iv in rows:
        iv.status = "QUEUED"
        iv.processing_stage = None
        logger.info("Recovered interview %s: PROCESSING -> QUEUED", iv.interview_id)

    script_rows = list(
        session.scalars(
            select(Interview).where(
                Interview.status == "ANSWER_UPLOADED",
                Interview.processing_stage.is_not(None),
            )
        ).all()
    )
    for iv in script_rows:
        iv.processing_stage = None
        logger.info(
            "Recovered interview %s: ANSWER_UPLOADED stage cleared",
            iv.interview_id,
        )

    eval_rows = list(
        session.scalars(
            select(Interview).where(
                Interview.status == "EVALUATING",
                Interview.processing_stage.is_not(None),
            )
        ).all()
    )
    for iv in eval_rows:
        iv.processing_stage = None
        logger.info(
            "Recovered interview %s: EVALUATING stage cleared",
            iv.interview_id,
        )

    total = len(rows) + len(script_rows) + len(eval_rows)
    if total:
        session.commit()
    return total


def run_startup_recovery() -> int:
    """Recovery entrypoint for the app lifespan (runs in a worker thread)."""
    with SessionLocal() as session:
        count = recover_interviews(session)
    if count:
        logger.info("Startup recovery re-queued %d interview(s)", count)
    return count


async def run_worker_forever() -> None:
    """Polling loop: claim+process one job, then sleep — until cancelled.

    The blocking pipeline runs in a worker thread via ``asyncio.to_thread`` so
    it never stalls the FastAPI event loop.
    """
    logger.info(
        "Worker loop starting (poll interval %.1fs)",
        settings.WORKER_POLL_INTERVAL_SECONDS,
    )
    while True:
        try:
            await asyncio.to_thread(process_next_job)
        except Exception:
            logger.exception("Worker iteration crashed; continuing")
        await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)