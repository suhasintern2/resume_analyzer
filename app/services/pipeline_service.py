"""The worker's per-interview question-generation pipeline (Task 8 / Task 12).

Runs the stages built in Tasks 3/5/7 in order, committing ``status`` /
``processing_stage`` transitions on the ``interviews`` table after each step
so dashboards reflect real progress — job state is DB-persisted, never held
in-process.

Task 12 revision: BOTH rounds are generated in one pipeline run. Round 2
questions / evaluation keys / documents are produced upfront (round-2
delivery is then gated by the select-next-round *access* action, never by
generation). Both ``interview_rounds`` rows are marked ``QUESTIONS_READY``
when the pipeline completes.

Stage flow (``status`` stays ``PROCESSING`` during the three fine-grained
``processing_stage`` steps):

    claim -> PROCESSING + EXTRACTING -> GENERATING -> FORMATTING ->
    COMPLETED (stage None)

On any failure the worker marks the interview ``FAILED`` with a stored,
user-safe ``error_reason`` (stack traces are logged server-side only — see
``worker.mark_failed``).
"""

import logging
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import File, Interview
from app.services import interview_service
from app.services.document_service import generate_and_persist_documents
from app.services.evaluation_key_service import save_interview_evaluation_keys
from app.services.ocr_service import ocr_image
from app.services.pdf_extractor import extract_pdf_text
from app.services.contact_extractor import extract_contact_info
from app.services.question_generator import generate_interview_questions
from app.services.text_cleaner import clean_resume_text
from app.utils.helpers import truncate_resume_text, validate_resume_text

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """A domain error with a safe, user-facing message (no stack traces)."""


_RESUME_IMAGE_EXTS = (".jpg", ".jpeg", ".png")


def extract_resume_text(resume: File) -> str:
    """Read the stored resume record file and return cleaned, validated text.

    Reuses the existing MVP extraction logic: ``extract_pdf_text`` for PDFs
    and ``ocr_image`` for scans/photos, then ``clean_resume_text`` +
    ``validate_resume_text`` + ``truncate_resume_text``.
    """
    if not os.path.isfile(resume.file_path):
        raise PipelineError(f"Resume file is missing from storage: {resume.file_path}")

    ext = os.path.splitext(resume.file_path)[1].lower()
    if ext == ".pdf":
        raw = extract_pdf_text(resume.file_path)
    elif ext in _RESUME_IMAGE_EXTS:
        with open(resume.file_path, "rb") as fh:
            raw = ocr_image(fh.read())
    else:
        raise PipelineError(f"Unsupported resume file type: {ext or '(none)'}")

    cleaned = clean_resume_text(raw)
    if not validate_resume_text(cleaned):
        raise PipelineError(
            "Could not extract enough readable text from the resume."
        )
    return truncate_resume_text(cleaned)


def _set_stage(
    session: Session,
    interview: Interview,
    *,
    status: str,
    processing_stage: str | None,
) -> None:
    interview.status = status
    interview.processing_stage = processing_stage
    session.commit()
    logger.info(
        "Interview %s -> status=%s stage=%s",
        interview.interview_id, status, processing_stage,
    )


def run_pipeline(session: Session, interview: Interview) -> None:
    """Execute the question-generation pipeline for an already-claimed,
    already-``PROCESSING`` interview.

    Each transition is committed so a crash mid-pipeline leaves the row in a
    real, recoverable state (see ``worker.recover_interviews``).
    """
    # --- EXTRACTING -------------------------------------------------------
    _set_stage(session, interview, status="PROCESSING", processing_stage="EXTRACTING")
    resume = session.scalar(
        select(File).where(
            File.interview_id == interview.id, File.file_type == "RESUME",
        )
    )
    if resume is None:
        raise PipelineError("No resume record file found for this interview.")
    resume_text = extract_resume_text(resume)
    logger.info(
        "Interview %s extracted %d chars", interview.interview_id, len(resume_text),
    )
    interview.email, interview.phone = extract_contact_info(resume_text)

    # --- GENERATING (LLM + evaluation keys) --------------------------------
    _set_stage(session, interview, status="PROCESSING", processing_stage="GENERATING")

    # Generate questions for the single round
    result = generate_interview_questions(resume_text)
    interview.candidate_name = result.candidate_name

    # Save evaluation keys
    save_interview_evaluation_keys(
        session, interview_id=interview.id, result=result,
    )

    # --- FORMATTING (documents) ---
    _set_stage(session, interview, status="PROCESSING", processing_stage="FORMATTING")
    generate_and_persist_documents(
        session, interview=interview, result=result,
    )

    # --- COMPLETED ---------------------------------------------------------
    interview.status = "COMPLETED"
    interview.processing_stage = None
    interview.error_reason = None
    session.commit()
    logger.info(
        "Interview %s COMPLETED (questions ready)",
        interview.interview_id,
    )
