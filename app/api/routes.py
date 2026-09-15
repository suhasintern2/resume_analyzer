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
    InterviewRound,
    QuestionEvaluation,
    ROUND_1,
    ROUND_2,
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
    get_document_file,
    list_documents,
)
from app.services.evaluation_key_service import save_interview_evaluation_keys
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
)
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _round_or_404(
    interview: Interview,
    round_number: int,
    session: Session,
) -> InterviewRound:
    """Load a round row for an interview, or 404 if it does not exist."""
    round_obj = interview_service.get_round(
        session, interview_pk=interview.id, round_number=round_number,
    )
    if round_obj is None:
        raise HTTPException(
            status_code=404,
            detail=f"Round {round_number} does not exist for this interview.",
        )
    return round_obj


def _assert_round2_unlocked(
    interview: Interview,
    session: Session,
) -> InterviewRound:
    """Enforce the Task 12 round-2 access gate.

    Round 2 questions exist upfront; downloads/uploads/evaluation for round 2
    are only allowed once round 1 is EVALUATED and the staff member selected
    the candidate for the next round.
    """
    r1 = _round_or_404(interview, ROUND_1, session)
    r2 = _round_or_404(interview, ROUND_2, session)
    if r1.status != "EVALUATED":
        raise HTTPException(
            status_code=409,
            detail="Round 2 is locked until Round 1 has been fully evaluated.",
        )
    if not r1.selected_for_next_round:
        raise HTTPException(
            status_code=409,
            detail="Round 2 is locked until this candidate is selected for Round 2.",
        )
    return r2


def _latest_round_eval(
    session: Session,
    interview: Interview,
    round_number: int,
) -> Evaluation | None:
    """Current-pinned evaluation for one specific round of an interview."""
    return session.scalar(
        select(Evaluation)
        .join(InterviewRound, Evaluation.round_id == InterviewRound.id)
        .where(
            Evaluation.interview_id == interview.id,
            InterviewRound.round_number == round_number,
            Evaluation.is_current.is_(True),
        )
    )


def _build_round_summaries(
    session: Session,
    interview: Interview,
) -> list[dict]:
    """Round-1/Round-2 status plus per-round evaluation scores."""
    rounds = interview_service.list_rounds(
        session, interview_pk=interview.id,
    )
    summaries: list[dict] = []
    for r in rounds:
        eval_row = _latest_round_eval(session, interview, r.round_number)
        summaries.append({
            "round_number": r.round_number,
            "status": r.status,
            "selected_for_next_round": r.selected_for_next_round,
            "score": float(eval_row.total_score) if eval_row and eval_row.total_score is not None else None,
            "max_score": float(eval_row.max_score) if eval_row and eval_row.max_score is not None else None,
            "percentage": float(eval_row.percentage) if eval_row and eval_row.percentage is not None else None,
        })
    return summaries


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
        # Top-level score surface = Round 1 when a round-1 row exists
        # (dashboard sorts by Round-1 score); legacy pre-round rows fall back
        # to the unscoped current evaluation.
        r1 = interview_service.get_round(
            session, interview_pk=iv.id, round_number=ROUND_1,
        )
        if r1 is not None:
            curr_eval = _latest_round_eval(session, iv, ROUND_1)
        else:
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
                rounds=_build_round_summaries(session, iv),
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
        rounds=_build_round_summaries(session, interview),
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


@router.post("/interviews/{interview_id}/select-next-round")
def select_interview_next_round(
    interview_id: str,
    session: Session = Depends(get_db),
):
    """Select the candidate for Round 2 — the access-gate action (Task 12).

    Both rounds' questions are generated upfront at upload time now; this
    endpoint only flips the round-1 ``selected_for_next_round`` flag, which
    unlocks round-2 downloads/uploads/evaluation that were previously gated on
    generation. Requires round 1 to be fully EVALUATED. Idempotent — calling
    it twice returns the round-2 row without error.
    """
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    r2 = _assert_round2_unlocked(interview, session)
    try:
        round2 = interview_service.round2_unlock_access(
            session, interview,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {
        "success": True,
        "interview_id": interview_id,
        "round_number": ROUND_2,
        "round_id": round2.id,
        "status": round2.status,
        "message": (
            "Round 2 access unlocked — round-2 downloads and answer uploads "
            "are now available on the Dashboard."
        ),
    }


def _resolve_round_id(
    interview: Interview,
    session: Session,
    round_number: int | None,
    *,
    unlock_required: bool,
) -> int:
    """Resolve a round number to a round PK, enforcing the Task 12 gate.

    ``round_number=None`` means Round 1 (legacy calls).  When the caller
    touches round-2 content and ``unlock_required`` is set, the access gate
    (round 1 EVALUATED + selected_for_next_round) is enforced.
    """
    if round_number is None:
        round_number = ROUND_1
    if round_number == ROUND_2:
        round_obj = _assert_round2_unlocked(interview, session) if unlock_required else _round_or_404(
            interview, ROUND_2, session,
        )
    else:
        round_obj = _round_or_404(interview, ROUND_1, session)
    return round_obj.id


@router.get("/interviews/{interview_id}/documents")
def list_interview_documents(interview_id: str, session: Session = Depends(get_db)):
    """List available generated documents for an interview.

    Only returns documents that have been generated (question_sheet,
    answer_key) — does not include the RESUME upload.  Each entry carries its
    ``round_number`` so the Dashboard can group per round (Task 12).
    """
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    files = list_documents(session, interview_pk=interview.id)
    rounds_by_id = {
        r.id: r.round_number
        for r in interview_service.list_rounds(session, interview_pk=interview.id)
    }
    return {
        "interview_id": interview_id,
        "documents": [
            {
                "file_type": db_to_file_type(f.file_type),
                "file_path": f.file_path,
                "round_number": rounds_by_id.get(f.round_id, None),
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in files
        ],
    }


@router.get("/interviews/{interview_id}/documents/{file_type}")
def download_interview_document(
    interview_id: str,
    file_type: str,
    round_number: int | None = None,
    session: Session = Depends(get_db),
):
    """Download a generated document by file_type (round-scoped, Task 12).

    Validates that file_type is one of the allowed values and belongs to
    the specified interview_id before serving. Never accepts raw paths.
    ``round_number`` selects the round; defaults to Round 1. Round-2
    downloads require the round-2 access gate to be met.
    """
    if file_type not in DOCUMENT_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file_type}'. "
            f"Allowed: {', '.join(sorted(DOCUMENT_FILE_TYPES))}",
        )

    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    round_id = _resolve_round_id(
        interview, session, round_number, unlock_required=True,
    )
    file_row = get_document_file(
        session, interview_pk=interview.id, file_type=file_type, round_id=round_id,
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
    round_number: int | None = Form(default=None),
    session: Session = Depends(get_db),
):
    """Upload scanned handwritten answer-script pages for an interview.

    Round-scoped (Task 12): ``round_number`` defaults to Round 1. Round-2
    uploads require the access gate (round 1 EVALUATED + selected for round
    2).  Only valid once the interview has finished question generation
    (COMPLETED) or is already in the answer-script flow.  Re-uploading
    replaces the previous pages.  Persisted as RECORD ANSWER_SCRIPT files;
    OMR/OCR/segmentation is the job worker's job (status -> ANSWER_UPLOADED).
    """
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    round_id = _resolve_round_id(
        interview, session, round_number, unlock_required=True,
    )
    resolved_round = int(round_number or ROUND_1)

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
        round_id=round_id,
    )
    logger.info(
        "Uploaded %d answer script page(s) for %s round %d (status=%s)",
        count, interview.interview_id, resolved_round, interview.status,
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
    round_number: int | None = None,
    session: Session = Depends(get_db),
):
    """List the segmented answer blocks for an interview round, for review.

    ``round_number`` defaults to Round 1. Round 2 requires the access gate.
    """
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    round_id = _resolve_round_id(
        interview, session, round_number, unlock_required=True,
    )
    resolved_round = int(round_number or ROUND_1)

    round_obj = interview_service.get_round(session, interview_pk=interview.id, round_number=resolved_round)
    if round_obj.status not in {"SEGMENTED", "SEGMENTATION_UNCERTAIN"}:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No segments yet for round {resolved_round} (status: {round_obj.status}). "
                "Upload and process an answer script first."
            ),
        )
    segments = answer_script_service.get_segments(
        session, interview_pk=interview.id, round_id=round_id,
    )
    return {
        "interview_id": interview_id,
        "round_number": resolved_round,
        "status": round_obj.status,
        "processing_stage": interview.processing_stage,
        "matched": round_obj.status == "SEGMENTED",
        "segments": [_segment_json(s) for s in segments],
    }


@router.post("/interviews/{interview_id}/segments/{segment_id}/reassign")
def reassign_segment(
    interview_id: str,
    segment_id: int,
    body: SegmentReassignRequest,
    round_number: int | None = None,
    session: Session = Depends(get_db),
):
    """Manually correct a segment's question alignment.

    Records the originally-detected number and the manual override, then
    re-derives the round's segmentation status from the corrected set.
    """
    if body.question_number < 1:
        raise HTTPException(
            status_code=400, detail="question_number must be a positive integer.",
        )

    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    round_id = _resolve_round_id(
        interview, session, round_number, unlock_required=True,
    )

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
    resolved_round = int(round_number or ROUND_1)
    aligned = answer_script_service.recompute_segmentation_status(
        session, interview=interview, round_number=resolved_round,
    )
    return {
        "interview_id": interview_id,
        "round_number": resolved_round,
        "status": interview.status,
        "matched": aligned,
        "segment": _segment_json(segment),
    }


@router.post("/interviews/{interview_id}/evaluate", response_model=EvaluationStartResponse)
def evaluate_interview_endpoint(
    interview_id: str,
    round_number: int | None = None,
    session: Session = Depends(get_db),
):
    """Trigger deterministic answer evaluation for an interview round via background worker.

    ``round_number`` defaults to Round 1. Round-2 evaluation requires the
    access gate to be met.
    """
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    resolved_round = int(round_number or ROUND_1)
    round_id = _resolve_round_id(
        interview, session, resolved_round, unlock_required=True,
    )
    round_obj = interview_service.get_round(session, interview_pk=interview.id, round_number=resolved_round)

    _ALLOWED_EVALUATE_STATUSES = {
        "SEGMENTED", "SEGMENTATION_UNCERTAIN", "EVALUATED", "EVALUATION_FAILED",
    }
    if round_obj.status not in _ALLOWED_EVALUATE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Round {resolved_round} is not in a ready state for evaluation (status: {round_obj.status}). "
                "Answers must be uploaded and segmented first."
            ),
        )

    round_obj.status = "EVALUATING"
    interview.status = "EVALUATING"
    interview.processing_stage = None
    interview.error_reason = None
    session.commit()

    logger.info(
        "Enqueued interview %s round %d for evaluation",
        interview.interview_id, resolved_round,
    )
    return EvaluationStartResponse(
        success=True,
        interview_id=interview.interview_id,
        status=interview.status,
    )


@router.get("/interviews/{interview_id}/evaluation", response_model=EvaluationDetailOut)
def get_interview_evaluation(
    interview_id: str,
    round_number: int | None = None,
    session: Session = Depends(get_db),
):
    """Retrieve the current evaluation result for an interview round.

    ``round_number`` defaults to Round 1. Round-2 evaluation requires the
    access gate.
    """
    interview = interview_service.get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")

    resolved_round = int(round_number or ROUND_1)
    _resolve_round_id(interview, session, resolved_round, unlock_required=True)

    round_obj = interview_service.get_round(session, interview_pk=interview.id, round_number=resolved_round)
    if round_obj is None:
        raise HTTPException(
            status_code=404,
            detail=f"Round {resolved_round} does not exist for this interview.",
        )

    curr_eval = session.scalar(
        select(Evaluation).where(
            Evaluation.interview_id == interview.id,
            Evaluation.round_id == round_obj.id,
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
    round_number: int | None = None,
    session: Session = Depends(get_db),
):
    """Override a question score with an auditable reason (round-scoped).
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

    resolved_round = int(round_number or ROUND_1)
    _resolve_round_id(interview, session, resolved_round, unlock_required=True)
    round_obj = interview_service.get_round(session, interview_pk=interview.id, round_number=resolved_round)
    if round_obj is None:
        raise HTTPException(
            status_code=404,
            detail=f"Round {resolved_round} does not exist for this interview.",
        )

    curr_eval = session.scalar(
        select(Evaluation).where(
            Evaluation.interview_id == interview.id,
            Evaluation.round_id == round_obj.id,
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

                # Task 12 — both rounds are active from creation.
                round1 = interview_service.get_round(
                    db_session, interview_pk=interview.id, round_number=ROUND_1,
                )
                round2 = interview_service.get_round(
                    db_session, interview_pk=interview.id, round_number=ROUND_2,
                )
                if round1 is None or round2 is None:
                    raise ValueError("round rows missing for sync-flow interview")

                # Round 1: keys + documents (result already generated above)
                save_interview_evaluation_keys(
                    db_session,
                    interview_id=interview.id,
                    result=result,
                    round_id=round1.id,
                )
                generate_and_persist_documents(
                    db_session,
                    interview=interview,
                    result=result,
                    round_id=round1.id,
                )
                round1.status = "QUESTIONS_READY"
                round1.selected_for_next_round = None

                # Round 2: generate questions upfront too (unlock is an
                # access gate later, never a generation trigger).
                result2 = generate_interview_questions(
                    cleaned_text, round_number=ROUND_2,
                )
                save_interview_evaluation_keys(
                    db_session,
                    interview_id=interview.id,
                    result=result2,
                    round_id=round2.id,
                )
                generate_and_persist_documents(
                    db_session,
                    interview=interview,
                    result=result2,
                    round_id=round2.id,
                )
                round2.status = "QUESTIONS_READY"
                round2.selected_for_next_round = None

                db_session.commit()
                interview_id_str = interview.interview_id
                logger.info(
                    "Sync flow: persisted interview %s for %s (both rounds ready)",
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
