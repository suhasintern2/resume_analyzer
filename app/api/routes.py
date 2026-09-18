import os
import time
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import Response
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.db import get_db, SessionLocal
from app.db.models import (
    AnswerSegment,
    Evaluation,
    Interview,
    QuestionEvaluation,
)
from app.utils.file_validation import validate_file
from app.utils.helpers import get_upload_path, validate_resume_text, truncate_resume_text
from app.services.pdf_extractor import extract_pdf_text
from app.services.ocr_service import ocr_image
from app.services.text_cleaner import clean_resume_text
from app.services.contact_extractor import extract_contact_info
from app.services.question_generator import generate_interview_questions
from app.services.document_generator import generate_docx
from app.services import interview_service
from app.services import answer_script_service
from app.services.document_service import (
    DOCUMENT_FILE_TYPES,
    db_to_file_type,
    generate_and_persist_documents,
    generate_interview_pdfs,
    get_pdf_paths,
    get_document_file,
    list_documents,
    delete_interview_pdfs,
    store_pdf_paths,
    reconstruct_interview_result,
)
from app.services.interview_service import mark_as_done
from app.services.evaluation_key_service import save_interview_evaluation_keys
from app.services.mcq_bank import (
    _get_day_questions,
    _get_day_correct_answers,
    generate_question_paper,
    generate_mcq_answer_key,
    score_answer_sheet,
    parse_uploaded_answer_sheet,
    get_available_days,
    get_day_status,
)
from app.models.schemas import (
    GenerateResponse,
    InterviewResult,
    InterviewCreateResponse,
    InterviewDetail,
    InterviewListItem,
    InterviewListResponse,
    InterviewRenameRequest,
    AnswerScriptUploadResponse,
    SegmentReassignRequest,
    EvaluationStartResponse,
    EvaluationDetailOut,
    QuestionEvaluationOut,
    ScoreOverrideRequest,
    MarkAsDoneResponse,
    MCQDaysResponse,
    MCQDayResponse,
    MCQScoreResponse,
    MCQUploadResponse,
    MCQDownloadResponse,
)
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/interviews", response_model=InterviewCreateResponse)
def create_interview(
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
):
    """Create a QUEUED interview from an uploaded resume (async flow).

    Reuses the existing MVP file validation. Interview ID is generated
    race-free inside the transaction (see interview_service). No resume
    extraction or LLM call happens here — that is the job worker's job.
    """
    ext = validate_file(file, settings.MAX_FILE_SIZE_MB)
    content = file.file.read()

    interview = interview_service.create_interview(
        session,
        content=content,
        ext=ext,
        candidate_name=None,
        email=None,
        phone=None,
        original_filename=file.filename,
    )

    logger.info(
        "Created interview %s (status=%s, pk=%d)",
        interview.interview_id,
        interview.status,
        interview.id,
    )
    return InterviewCreateResponse(
        success=True,
        interview_id=interview.interview_id,
        status=interview.status,
    )


@router.get("/interviews", response_model=InterviewListResponse)
def list_interviews(session: Session = Depends(get_db)):
    """List all interviews ordered by creation date descending.
    Includes the latest evaluation score if evaluated.
    """
    interviews = list(
        session.scalars(
            select(Interview).order_by(Interview.id.desc())
        ).all()
    )
    items: list[InterviewListItem] = []
    for iv in interviews:
        # Get the current evaluation for this interview
        curr_eval = session.scalar(
            select(Evaluation).where(
                Evaluation.interview_id == iv.id,
                Evaluation.is_current.is_(True),
            )
        )
        items.append(
            InterviewListItem(
                id=iv.id,
                interview_id=iv.interview_id,
                candidate_name=iv.candidate_name,
                email=iv.email,
                phone=iv.phone,
                status=iv.status,
                processing_stage=iv.processing_stage,
                error_reason=iv.error_reason,
                score=float(curr_eval.total_score) if curr_eval and curr_eval.total_score is not None else None,
                max_score=float(curr_eval.max_score) if curr_eval and curr_eval.max_score is not None else None,
                percentage=float(curr_eval.percentage) if curr_eval and curr_eval.percentage is not None else None,
                created_at=iv.created_at,
                updated_at=iv.updated_at,
            )
        )
    return InterviewListResponse(interviews=items)


@router.get("/interviews/{interview_id}", response_model=InterviewDetail)
def get_interview(interview_id: str, session: Session = Depends(get_db)):
    """Return the current row for a single interview."""
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    return InterviewDetail(
        id=interview.id,
        interview_id=interview.interview_id,
        candidate_name=interview.candidate_name,
        email=interview.email,
        phone=interview.phone,
        status=interview.status,
        processing_stage=interview.processing_stage,
        error_reason=interview.error_reason,
        created_at=interview.created_at,
    )


@router.patch("/interviews/{interview_id}/display-name")
def update_interview_display_name(
    interview_id: str,
    body: InterviewRenameRequest,
    session: Session = Depends(get_db),
):
    """Rename the dashboard label for an interview (Task 11).

    ``display_name`` is a pure display concern — the stored record file, the
    interview_id and the candidate's own resume content are never touched.
    The rename is deliberately kept in the API (not the DB row) so the
    original upload name is preserved and only the label shown in the
    Dashboard / document file names changes. Clears to ``original_filename``
    when the incoming value would otherwise be blank.
    """
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    cleaned = body.display_name.strip() if body.display_name else ""
    if not cleaned:
        cleaned = interview.original_filename or interview.interview_id
    interview = interview_service.rename_interview(
        session, interview, display_name=cleaned,
    )
    return {
        "success": True,
        "interview_id": interview_id,
        "display_name": interview.display_name,
        "original_filename": interview.original_filename,
    }


@router.get("/interviews/{interview_id}/documents")
def list_interview_documents(interview_id: str, session: Session = Depends(get_db)):
    """List available generated documents for an interview.

    Only returns documents that have been generated (question_sheet,
    answer_key) — does not include the RESUME upload.
    """
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    files = list_documents(session, interview_pk=interview.id)
    return {
        "interview_id": interview_id,
        "documents": [
            {
                "file_type": db_to_file_type(f.file_type),
                "file_path": f.file_path,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in files
        ],
    }


@router.get("/interviews/{interview_id}/documents/{file_type}")
def download_interview_document(
    interview_id: str,
    file_type: str,
    session: Session = Depends(get_db),
):
    """Download a generated document by file_type."""
    if file_type not in DOCUMENT_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file_type}'. "
            f"Allowed: {', '.join(sorted(DOCUMENT_FILE_TYPES))}",
        )

    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    file_row = get_document_file(
        session, interview_pk=interview.id, file_type=file_type,
    )
    if file_row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No '{file_type}' document found for interview {interview_id}.",
        )

    if not os.path.isfile(file_row.file_path):
        logger.error(
            "Document file missing on disk: interview=%s file_type=%s path=%s",
            interview_id, file_type, file_row.file_path,
        )
        raise HTTPException(
            status_code=404,
            detail=f"Document file for '{file_type}' is missing from storage.",
        )

    with open(file_row.file_path, "rb") as fh:
        content = fh.read()

    type_labels = {
        "question_sheet": "QuestionSheet",
        "answer_key": "AnswerKey",
    }
    label = type_labels.get(file_type, file_type)
    filename = f"VlookUp_{label}_{interview_id}.docx"

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/interviews/{interview_id}/answer-script", response_model=AnswerScriptUploadResponse)
def upload_answer_script(
    interview_id: str,
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_db),
):
    """Upload scanned handwritten answer-script pages for an interview.

    Only valid once the interview has finished question generation
    (COMPLETED) or is already in the answer-script flow.  Re-uploading
    replaces the previous pages.  Persisted as RECORD ANSWER_SCRIPT files;
    OMR/OCR/segmentation is the job worker's job (status -> ANSWER_UPLOADED).
    """
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    _ALLOWED_UPLOAD_STATUSES = {
        "COMPLETED", "ANSWER_UPLOADED", "SEGMENTED", "SEGMENTATION_UNCERTAIN",
    }
    if interview.status not in _ALLOWED_UPLOAD_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Answer scripts can only be uploaded once an interview has "
                f"generated its questions (current status: {interview.status})."
            ),
        )

    if not files:
        raise HTTPException(status_code=400, detail="No answer script files were uploaded.")

    scripts: list[tuple[bytes, str]] = []
    for upload in files:
        ext = validate_file(upload, settings.ANSWER_SCRIPT_MAX_FILE_SIZE_MB)
        scripts.append((upload.file.read(), ext))

    count = answer_script_service.persist_answer_scripts(
        session, interview=interview, scripts=scripts,
    )
    logger.info(
        "Uploaded %d answer script page(s) for %s (status=%s)",
        count, interview.interview_id, interview.status,
    )
    return AnswerScriptUploadResponse(
        success=True,
        interview_id=interview.interview_id,
        status=interview.status,
        files_uploaded=count,
    )


def _segment_json(segment) -> dict:
    return {
        "id": segment.id,
        "question_number": segment.question_number,
        "original_question_number": segment.original_question_number,
        "content": segment.content,
        "status": str(segment.status),
        "is_manual_override": segment.is_manual_override,
        "created_at": segment.created_at.isoformat() if segment.created_at else None,
        "updated_at": segment.updated_at.isoformat() if segment.updated_at else None,
    }


@router.get("/interviews/{interview_id}/segments")
def get_answer_segments(
    interview_id: str,
    session: Session = Depends(get_db),
):
    """List the segmented answer blocks for an interview, for review."""
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    # For simplicity, we'll just get all segments for this interview
    # In a single round system, we don't need to filter by round
    segments = answer_script_service.get_segments(
        session, interview_pk=interview.id,
    )

    # In a single round system, we don't need to track round-specific status
    return {
        "interview_id": interview_id,
        "status": "SEGMENTED",  # Placeholder - in reality we'd need to track this differently
        "processing_stage": interview.processing_stage,
        "matched": True,  # Placeholder
        "segments": [_segment_json(s) for s in segments],
    }


@router.post("/interviews/{interview_id}/segments/{segment_id}/reassign")
def reassign_segment(
    interview_id: str,
    segment_id: int,
    body: SegmentReassignRequest,
    session: Session = Depends(get_db),
):
    """Manually correct a segment's question alignment.

    Records the originally-detected number and the manual override, then
    re-derives the segmentation status from the corrected set.
    """
    if body.question_number < 1:
        raise HTTPException(
            status_code=400, detail="question_number must be a positive integer.",
        )

    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    segment = session.scalar(
        select(AnswerSegment).where(
            AnswerSegment.id == segment_id,
            AnswerSegment.interview_id == interview.id,
        )
    )
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not found for this interview.")

    answer_script_service.reassign_segment(
        session, segment, new_question_number=body.question_number,
    )
    aligned = answer_script_service.recompute_segmentation_status(
        session, interview=interview,
    )
    return {
        "interview_id": interview_id,
        "status": interview.status,
        "matched": aligned,
        "segment": _segment_json(segment),
    }


@router.post("/interviews/{interview_id}/evaluate", response_model=EvaluationStartResponse)
def evaluate_interview_endpoint(
    interview_id: str,
    session: Session = Depends(get_db),
):
    """Trigger deterministic answer evaluation for an interview via background worker."""
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    # In a single round system, we evaluate the interview directly
    interview.status = "EVALUATING"
    interview.processing_stage = None
    interview.error_reason = None
    session.commit()

    logger.info(
        "Enqueued interview %s for evaluation",
        interview.interview_id,
    )
    return EvaluationStartResponse(
        success=True,
        interview_id=interview.interview_id,
        status=interview.status,
    )


@router.get("/interviews/{interview_id}/evaluation", response_model=EvaluationDetailOut)
def get_interview_evaluation(
    interview_id: str,
    session: Session = Depends(get_db),
):
    """Retrieve the current evaluation result for an interview."""
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    # Get the current evaluation for this interview
    curr_eval = session.scalar(
        select(Evaluation).where(
            Evaluation.interview_id == interview.id,
            Evaluation.is_current.is_(True),
        )
    )
    if curr_eval is None:
        raise HTTPException(
            status_code=404,
            detail=f"No evaluation found for interview {interview_id}.",
        )

    q_evals = list(
        session.scalars(
            select(QuestionEvaluation)
            .where(QuestionEvaluation.evaluation_id == curr_eval.id)
            .order_by(QuestionEvaluation.question_number)
        ).all()
    )

    questions_out: list[QuestionEvaluationOut] = []
    for q in q_evals:
        eff_score = (
            float(q.override_score)
            if q.override_score is not None
            else (float(q.score) if q.score is not None else None)
        )
        questions_out.append(
            QuestionEvaluationOut(
                id=q.id,
                question_number=q.question_number,
                score=eff_score,
                original_score=(
                    float(q.original_score)
                    if q.original_score is not None
                    else (float(q.score) if q.score is not None else None)
                ),
                override_score=float(q.override_score) if q.override_score is not None else None,
                override_reason=q.override_reason,
                overridden_by=q.overridden_by,
                overridden_at=q.overridden_at,
                is_overridden=q.override_score is not None,
                max_score=float(q.max_score) if q.max_score is not None else None,
                keyword_score=float(q.keyword_score) if q.keyword_score is not None else None,
                concept_score=float(q.concept_score) if q.concept_score is not None else None,
                phrase_score=float(q.phrase_score) if q.phrase_score is not None else None,
                similarity_score=float(q.similarity_score) if q.similarity_score is not None else None,
                structure_score=float(q.structure_score) if q.structure_score is not None else None,
                status=str(q.status),
                feedback=q.feedback,
            )
        )

    return EvaluationDetailOut(
        interview_id=interview.interview_id,
        evaluation_id=curr_eval.id,
        evaluator_version=curr_eval.evaluator_version,
        total_score=float(curr_eval.total_score) if curr_eval.total_score is not None else None,
        max_score=float(curr_eval.max_score) if curr_eval.max_score is not None else None,
        percentage=float(curr_eval.percentage) if curr_eval.percentage is not None else None,
        status=str(curr_eval.status),
        is_current=curr_eval.is_current,
        created_at=curr_eval.created_at,
        questions=questions_out,
    )


@router.post(
    "/interviews/{interview_id}/evaluation/questions/{question_number}/override",
)
@router.post(
    "/interviews/{interview_id}/questions/{question_number}/override",
)
def override_question_score(
    interview_id: str,
    question_number: int,
    body: ScoreOverrideRequest,
    session: Session = Depends(get_db),
):
    """Override a question score with an auditable reason.
    Recalculates the overall score from override values where present.
    Never overwrites the original deterministic score in place.
    """
    if body.override_score < 0.0 or body.override_score > 10.0:
        raise HTTPException(
            status_code=400,
            detail="override_score must be between 0.0 and 10.0.",
        )
    if not body.override_reason or not body.override_reason.strip():
        raise HTTPException(
            status_code=400,
            detail="override_reason is required and cannot be blank.",
        )

    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    # Get the current evaluation for this interview
    curr_eval = session.scalar(
        select(Evaluation).where(
            Evaluation.interview_id == interview.id,
            Evaluation.is_current.is_(True),
        )
    )
    if curr_eval is None:
        raise HTTPException(status_code=404, detail=f"No current evaluation for interview {interview_id}.")

    q_eval = session.scalar(
        select(QuestionEvaluation).where(
            QuestionEvaluation.evaluation_id == curr_eval.id,
            QuestionEvaluation.question_number == question_number,
        )
    )
    if q_eval is None:
        raise HTTPException(status_code=404, detail=f"Question {question_number} not found in current evaluation.")

    # Preserve original_score if not already preserved
    if q_eval.original_score is None and q_eval.score is not None:
        q_eval.original_score = q_eval.score

    new_score = Decimal(str(round(body.override_score, 2)))
    q_eval.override_score = new_score
    q_eval.override_reason = body.override_reason.strip()
    q_eval.overridden_by = "staff"
    q_eval.overridden_at = func.now()

    # Recalculate evaluation overall score
    all_qs = list(
        session.scalars(
            select(QuestionEvaluation).where(
                QuestionEvaluation.evaluation_id == curr_eval.id,
            )
        ).all()
    )
    total = Decimal("0.00")
    max_scorable = Decimal("0.00")
    for q in all_qs:
        if q.override_score is not None:
            total += q.override_score
            max_scorable += q.max_score or Decimal("10.00")
        elif q.status in ("EVALUATED", "NO_ANSWER") and q.score is not None:
            total += q.score
            max_scorable += q.max_score or Decimal("10.00")

    curr_eval.total_score = total
    curr_eval.max_score = max_scorable
    if max_scorable > Decimal("0.00"):
        curr_eval.percentage = Decimal(str(round(float(total / max_scorable) * 100, 1)))

    session.commit()
    logger.info(
        "Overrode Q%d score for %s: %s -> %s (reason: %s)",
        question_number, interview_id, q_eval.original_score, new_score, q_eval.override_reason,
    )

    return {
        "success": True,
        "interview_id": interview_id,
        "question_number": question_number,
        "evaluation_id": curr_eval.id,
        "original_score": float(q_eval.original_score) if q_eval.original_score is not None else None,
        "override_score": float(q_eval.override_score),
        "override_reason": q_eval.override_reason,
        "total_score": float(curr_eval.total_score),
        "max_score": float(curr_eval.max_score),
        "percentage": float(curr_eval.percentage) if curr_eval.percentage is not None else None,
    }


@router.post("/generate", response_model=GenerateResponse)
async def generate(file: UploadFile = File(...)):
    """Synchronous resume-upload flow (original MVP endpoint).

    After a successful LLM response this endpoint also:
    - Creates a COMPLETED interview row in the DB (race-free INT-… ID)
    - Persists the resume as a RECORD file
    - Saves deterministic evaluation keys for each question
    - Generates and persists the Question Sheet and Answer Key documents

    This means every resume uploaded via the home page automatically appears
    in the Dashboard with its Interview ID and document download buttons.
    The JSON response (GenerateResponse) is unchanged so the result page
    continues working exactly as before.
    """
    start_time = time.time()
    temp_path = None

    try:
        ext = validate_file(file, settings.MAX_FILE_SIZE_MB)
        logger.info(f"Processing {ext} file ({file.content_type})")

        temp_path = get_upload_path(ext)
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        try:
            if ext == ".pdf":
                extracted_text = extract_pdf_text(temp_path)
            elif ext in (".jpg", ".jpeg", ".png"):
                extracted_text = ocr_image(content)
            else:
                raise HTTPException(status_code=400, detail="Unsupported file type.")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Text extraction failed for {ext}: {e}")
            raise HTTPException(
                status_code=422,
                detail="We could not read the uploaded file. Please upload a clear, text-based PDF or a clearer image.",
            )

        cleaned_text = clean_resume_text(extracted_text)
        logger.info(f"Extracted {len(cleaned_text)} characters")

        if not validate_resume_text(cleaned_text):
            raise HTTPException(
                status_code=422,
                detail="We could not extract enough readable text from this resume. Please upload a clearer image or a text-based PDF.",
            )

        cleaned_text = truncate_resume_text(cleaned_text)
        contact_email, contact_phone = extract_contact_info(cleaned_text)

        result = generate_interview_questions(cleaned_text)

        duration = time.time() - start_time
        logger.info(f"Completed in {duration:.1f}s")

        # ── Persist interview record so it appears in the Dashboard ──────
        # This runs after the LLM call, so a failure here does not prevent
        # the user from seeing their result — we log and continue.
        interview_id_str: str | None = None
        try:
            with SessionLocal() as db_session:
                interview = interview_service.create_interview(
                    db_session,
                    content=content,
                    ext=ext,
                    candidate_name=result.candidate_name,
                    original_filename=file.filename,
                )
                # Immediately mark COMPLETED (no async worker needed for
                # the sync flow — everything already ran above).
                interview.status = "COMPLETED"
                interview.processing_stage = None

                # Save evaluation keys and generate documents for the single round
                save_interview_evaluation_keys(
                    db_session,
                    interview_id=interview.id,
                    result=result,
                )
                generate_and_persist_documents(
                    db_session,
                    interview=interview,
                    result=result,
                )

                # Generate temporary PDFs for HR and Interviewer
                pdf_paths = generate_interview_pdfs(
                    db_session,
                    interview=interview,
                    result=result,
                )
                store_pdf_paths(db_session, interview.id, pdf_paths)

                db_session.commit()
                interview_id_str = interview.interview_id
                logger.info(
                    "Sync flow: persisted interview %s for %s (questions ready, PDFs generated)",
                    interview_id_str, result.candidate_name,
                )
        except Exception as persist_err:
            # Non-fatal: user still gets their Q&A result. Dashboard will
            # not have this entry but nothing is broken for the user.
            logger.error(
                "Sync flow: failed to persist interview record: %s", persist_err,
            )

        return GenerateResponse(
            success=True,
            result=result,
            interview_id=interview_id_str,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while processing the resume. Please try again.",
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@router.post("/download/docx")
async def download_docx(result: InterviewResult, role: str = "interviewer"):
    try:
        docx_bytes = generate_docx(result, role=role)

        role_filenames = {
            "interviewer": "Interviewer_Technical_Guide",
            "hr": "HR_Recruiter_Guide",
            "candidate": "Candidate_Assessment_Sheet",
        }
        prefix = role_filenames.get(role, "Interview_Prep")
        safe_name = "".join(c for c in result.candidate_name if c.isalnum() or c in (" ", "_", "-")).replace(" ", "_")
        filename = f"VlookUp_{prefix}_{safe_name}.docx"

        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )
    except Exception as e:
        logger.error(f"DOCX generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate document.",
        )


@router.post(
    "/interviews/{interview_id}/pdf/{role}",
)
async def download_interview_pdf(
    interview_id: str,
    role: str,
    session: Session = Depends(get_db),
):
    """Download a temporary PDF for the given role (interviewer or hr)."""
    if role not in ("interviewer", "hr"):
        raise HTTPException(status_code=400, detail="Invalid role. Use 'interviewer' or 'hr'.")

    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    from app.services.document_service import generate_role_pdf

    result = reconstruct_interview_result(
        session, interview_pk=interview.id,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No interview data available for PDF generation.",
        )

    filepath, filename = generate_role_pdf(
        session,
        interview_pk=interview.id,
        role=role,
    )
    if filepath is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate PDF.",
        )

    from fastapi.responses import FileResponse
    return FileResponse(
        filepath,
        media_type="application/pdf",
        filename=filename,
    )


@router.post(
    "/interviews/{interview_id}/mark-as-done",
    response_model=MarkAsDoneResponse,
)
async def mark_interview_done(
    interview_id: str,
    session: Session = Depends(get_db),
):
    """Mark an interview as done. Auto-deletes generated PDFs.
    Contact info (email, phone) remains visible in the dashboard."""
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    try:
        interview_service.mark_as_done(session, interview)
        return MarkAsDoneResponse(
            success=True,
            interview_id=interview_id,
            status="DONE",
            message="Interview marked as done. PDFs deleted. Contact info remains visible.",
        )
    except Exception as e:
        logger.error(f"Mark-as-done failed for {interview_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to mark interview as done.",
        )


# ---------------------------------------------------------------------------
# Task 13 — MCQ Question Bank Routes
# ---------------------------------------------------------------------------

@router.get("/mcq/days", response_model=MCQDaysResponse)
def get_mcq_days():
    """Get available days (1-10) for MCQ question papers."""
    days = get_available_days()
    return MCQDaysResponse(days=days)


@router.get("/mcq/day/{day}", response_model=MCQDayResponse)
def get_mcq_day(day: int):
    """Get the status and questions for a specific day."""
    if day < 1 or day > 10:
        raise HTTPException(status_code=400, detail="Day must be 1-10.")
    status = get_day_status(day)
    return MCQDayResponse(**status)


@router.get("/mcq/day/{day}/download")
def download_mcq_paper(day: int):
    """Download the MCQ question paper DOCX for a specific day."""
    if day < 1 or day > 10:
        raise HTTPException(status_code=400, detail="Day must be 1-10.")
    try:
        filepath = generate_question_paper(day)

        # Read the file content and return it as a downloadable DOCX
        with open(filepath, "rb") as f:
            content = f.read()

        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="VlookUp_MCQ_Paper_Day_{day}.docx"'
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="MCQ dataset not found.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/mcq/day/{day}/upload", response_model=MCQUploadResponse)
def upload_mcq_answers(day: int, files: list[UploadFile] = File(...)):
    """Upload completed MCQ answer sheets and get scores.

    Each file is parsed to extract candidate names and their answer
    sequences. Answers are compared against the correct answer key
    for the day and individual scores are returned.
    """
    if day < 1 or day > 10:
        raise HTTPException(status_code=400, detail="Day must be 1-10.")

    correct_answers = _get_day_correct_answers(day)
    all_candidate_answers: dict[str, list[str]] = {}

    for upload in files:
        content = upload.file.read().decode("utf-8", errors="ignore")
        parsed = parse_uploaded_answer_sheet(content)
        for name, answers in parsed["candidates"].items():
            all_candidate_answers[name] = answers

    if not all_candidate_answers:
        raise HTTPException(status_code=400, detail="No candidate answers found.")

    scores = score_answer_sheet(day, correct_answers, all_candidate_answers)

    return MCQUploadResponse(
        success=True,
        day=day,
        scores=scores["candidates"],
        message=f"Scored {len(all_candidate_answers)} candidate(s) for day {day}.",
    )


@router.get("/mcq/day/{day}/results")
def get_mcq_results(day: int):
    """Get the correct answer key for a specific day."""
    if day < 1 or day > 10:
        raise HTTPException(status_code=400, detail="Day must be 1-10.")
    questions = _get_day_questions(day)
    correct = _get_day_correct_answers(day)
    return {
        "day": day,
        "questions": [q["question"] for q in questions],
        "correct_answers": correct,
        "total_questions": len(correct),
    }


@router.get("/mcq/day/{day}/download-answer-key")
def download_mcq_answer_key(day: int):
    """Download the MCQ answer key DOCX for a specific day."""
    if day < 1 or day > 10:
        raise HTTPException(status_code=400, detail="Day must be 1-10.")
    try:
        filepath = generate_mcq_answer_key(day)

        # Read the file content and return it as a downloadable DOCX
        with open(filepath, "rb") as f:
            content = f.read()

        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="VlookUp_MCQ_Answer_Key_Day_{day}.docx"'
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="MCQ dataset not found.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))