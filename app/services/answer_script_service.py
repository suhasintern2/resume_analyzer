"""Answer-script orchestration: upload persistence + AI-free processing.

Task 9 established the ANSWER_SCRIPT RECORD files and the OCR/segmentation
pipeline.  Task 12 revises it to be fully AI-free and round-scoped:

- Uploaded pages are RECORD files scoped to a round via ``round_id``.
- ``process_answer_script`` runs in the job worker.  It reads MCQ answers
  with a **pure OMR pass** (Pillow + OpenCV ink-density measurement against
  the printed question sheet's ``layout_metadata``) and open-ended answers
  with local **TrOCR** (``microsoft/trocr-base-handwritten`` via Hugging Face
  ``transformers``).  No LLM call is involved anywhere in this flow.
- The resulting ``answer_segments`` rows are round-scoped; the round's status
  (and the interview's, which mirrors the active round) becomes SEGMENTED /
  SEGMENTATION_UNCERTAIN — alignment is never guessed, and an MCQ with more
  than one marked checkbox is stored as ``AMBIGUOUS_MARK`` and held out of
  scoring.

``reassign_segment`` remains the human review/override path; after any manual
reassignment the round's segmentation status is recomputed.
"""

import logging
import os

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AnswerSegment,
    File,
    Interview,
    QuestionEvaluationKey,
)
from app.services.answer_segmentation import (
    SegmentRecord,
    matches_question_numbers,
    segment_ocr_text,
)
from app.services import interview_service
from app.services.ocr_service import (
    ocr_handwriting_image,
    ocr_handwriting_pdf,
)
from app.services.omr_service import (
    detect_marked_options,
    mark_status_for_question,
    rasterize_image_page,
    rasterize_pdf_page,
    _deskew,
    _to_gray,
)
from app.services.pipeline_service import PipelineError
from app.services.file_store import delete_stored_file, persist_record

logger = logging.getLogger(__name__)

_DB_ANSWER_SCRIPT = "ANSWER_SCRIPT"
_DB_QUESTION_SHEET = "QUESTION_SHEET"

# Statuses that indicate the interview is actively flowing through
# the answer-script/evaluation lifecycle.
_ACTIVE_INTERVIEW_STATUSES = {
    "ANSWER_UPLOADED", "SEGMENTED", "SEGMENTATION_UNCERTAIN", "EVALUATING",
}


def resolve_active_answer_round(
    session: Session,
    interview: Interview,
) -> None:
    """In a single round system, we don't have rounds, so we return None.

    The interview itself tracks the status through the answer-script pipeline.
    """
    return None


def persist_answer_scripts(
    session: Session,
    *,
    interview: Interview,
    scripts: list[tuple[bytes, str]],
) -> int:
    """Replace all ANSWER_SCRIPT record files for an interview.

    Idempotent re-upload: previous ANSWER_SCRIPT rows for the interview
    and their files are removed first.  Sets the interview to ANSWER_UPLOADED
    so the worker picks it up.  Returns how many pages were persisted.
    """
    existing = list_answer_script_files(
        session, interview_pk=interview.id,
    )
    for old in existing:
        delete_stored_file(old.file_path)
        session.delete(old)
    session.flush()

    count = 0
    for content, ext in scripts:
        path = persist_record(
            content,
            interview_id=interview.interview_id,
            file_type="ANSWER_SCRIPT",
            ext=ext,
        )
        session.add(
            File(
                interview_id=interview.id,
                file_type=_DB_ANSWER_SCRIPT,
                file_path=path,
            )
        )
        count += 1

    interview.status = "ANSWER_UPLOADED"
    interview.processing_stage = None
    session.commit()
    return count




def list_answer_script_files(
    session: Session,
    *,
    interview_pk: int,
) -> list[File]:
    return list(
        session.scalars(
            select(File).where(
                File.interview_id == interview_pk,
                File.file_type == _DB_ANSWER_SCRIPT,
            )
        ).all()
    )


def _question_sheet_layout(
    session: Session,
    *,
    interview_pk: int,
) -> dict | None:
    """layout_metadata of the question sheet (OMR reference)."""
    sheet = session.scalar(
        select(File).where(
            File.interview_id == interview_pk,
            File.file_type == _DB_QUESTION_SHEET,
        )
    )
    if sheet is None:
        return None
    metadata = sheet.layout_metadata
    if not isinstance(metadata, dict) or not metadata.get("pages"):
        return None
    return metadata


def count_question_keys(
    session: Session,
    *,
    interview_pk: int,
) -> int:
    return session.scalar(
        select(func.count()).select_from(QuestionEvaluationKey).where(
            QuestionEvaluationKey.interview_id == interview_pk,
        )
    ) or 0


def save_segments(
    session: Session,
    *,
    interview_pk: int,
    segments: list[SegmentRecord],
) -> int:
    """Replace all segments for an interview (idempotent re-run).

    A manual override must survive re-segmentation, so overridden rows are
    carried over (by detected original number) instead of being dropped.
    """
    query = select(AnswerSegment).where(AnswerSegment.interview_id == interview_pk)
    existing = list(session.scalars(query).all())
    overridden = {
        s.original_question_number or s.question_number: s
        for s in existing
        if s.is_manual_override
    }

    for old in existing:
        session.delete(old)
    session.flush()

    count = 0
    for record in segments:
        original = record.question_number
        prior = overridden.get(original)
        if prior is not None:
            # Keep the human's correction out of an automatic re-run.
            session.add(AnswerSegment(
                interview_id=interview_pk,
                question_number=prior.question_number,
                content=record.content,
                status=record.status,
                is_manual_override=True,
                original_question_number=prior.original_question_number
                or original,
            ))
        else:
            session.add(AnswerSegment(
                interview_id=interview_pk,
                question_number=record.question_number,
                content=record.content,
                status=record.status,
                is_manual_override=False,
                original_question_number=None,
            ))
        count += 1
    return count


def _rasterize_script_pages(
    file_row: File,
) -> list[object]:
    """Rasterize one uploaded script into deskewed grayscale pages (list of
    ``np.ndarray``)."""
    ext = os.path.splitext(file_row.file_path or "")[1].lower()
    pages: list[object] = []
    if ext == ".pdf":
        import pymupdf as fitz
        doc = fitz.open(file_row.file_path)
        try:
            for idx in range(len(doc)):
                pages.append(_deskew(_to_gray(rasterize_pdf_page(file_row.file_path, idx))))
        finally:
            doc.close()
    elif ext in (".jpg", ".jpeg", ".png"):
        with open(file_row.file_path, "rb") as fh:
            pages.append(_deskew(_to_gray(rasterize_image_page(fh.read()))))
    else:
        logger.warning(
            "Skipping answer script with unsupported ext %s: %s", ext, file_row.file_path,
        )
    return pages


def _omr_segments(
    pages: list[object],
    layout_metadata: dict,
) -> dict[int, SegmentRecord]:
    """OMR pass over every page against its question-sheet layout."""
    results: dict[int, SegmentRecord] = {}
    layout_pages = {p["index"]: p["questions"] for p in layout_metadata.get("pages", [])}

    for page_index, gray in enumerate(pages):
        questions = layout_pages.get(page_index)
        if not questions:
            logger.warning("No OMR layout for script page index %d", page_index)
            continue
        detections = detect_marked_options(gray, questions)
        for number, detection in detections.items():
            status, content = mark_status_for_question(detection)
            results[number] = SegmentRecord(
                question_number=number, content=content, status=status,
            )
            logger.info(
                "OMR Q%d -> status=%s marks=%s ratios=%s",
                number, status, detection.get("marks"),
                detection.get("ink_ratios"),
            )
    return results


def process_answer_script(
    session: Session,
    interview: Interview,
) -> dict:
    """AI-free OMR+Tesseract processing of the interview's scripts.

    Called by the worker on a claimed ANSWER_UPLOADED interview.  Commits on
    success; raises on failure (the worker rolls back and marks FAILED).
    """
    question_count = count_question_keys(
        session, interview_pk=interview.id,
    )
    if question_count <= 0:
        raise PipelineError(
            f"No evaluation keys for {interview.interview_id} "
            "— cannot segment an answer sheet without questions."
        )

    files = list_answer_script_files(
        session, interview_pk=interview.id,
    )
    if not files:
        raise PipelineError(
            f"No answer script files for {interview.interview_id}."
        )

    layout_metadata = _question_sheet_layout(
        session, interview_pk=interview.id,
    )

    pages: list[object] = []
    for f in files:
        pages.extend(_rasterize_script_pages(f))

    omr_segments: dict[int, SegmentRecord] = {}

    if layout_metadata is not None and pages:
        try:
            omr_segments = _omr_segments(pages, layout_metadata)
            print(f"\nOMR DETECTED {len(omr_segments)} marked answers:")
            for qnum, seg in sorted(omr_segments.items()):
                print(f"  Q{qnum}: [{seg.status}] {seg.content}")
            print()
        except Exception as exc:  # noqa: BLE001
            logger.exception("OMR pass failed for %s; falling back to OCR only", interview.interview_id)
            omr_segments = {}

    ocr_text_parts: list[str] = []
    for f in files:
        ext = os.path.splitext(f.file_path or "")[1].lower()
        try:
            if ext == ".pdf":
                text = ocr_handwriting_pdf(f.file_path)
            elif ext in (".jpg", ".jpeg", ".png"):
                with open(f.file_path, "rb") as fh:
                    text = ocr_handwriting_image(fh.read())
            else:
                continue
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "OCR failed for answer script %s: %s", f.file_path, exc,
            )
            continue
        if text and text.strip():
            ocr_text_parts.append(text.strip())
        logger.info(
            "Local OCR'd answer script %s for %s (%d chars)",
            os.path.basename(f.file_path), interview.interview_id,
            len(text.strip()) if text else 0,
        )

    if not ocr_text_parts:
        logger.warning(
            "No OCR text extracted for %s — "
            "all questions will be BLANK/UNCERTAIN",
            interview.interview_id,
        )

    # OCR text -> aligned segments (open-ended answers, when printable
    # markers are present).  Kept per-question-number as a fallback source;
    # unnumbered blocks stay in for human review.
    ocr_segments_all: list[SegmentRecord] = []
    ocr_by_number: dict[int, SegmentRecord] = {}
    if ocr_text_parts:
        combined = "\n\n".join(ocr_text_parts)
        print(f"\n{'='*60}")
        print(f"RAW OCR TEXT ({len(combined)} chars):")
        print(f"{'='*60}")
        print(combined)
        print(f"{'='*60}\n")

        ocr_segments_all, _ocr_matched = segment_ocr_text(combined, question_count)
        for seg in ocr_segments_all:
            if seg.question_number is not None and seg.question_number not in ocr_by_number:
                ocr_by_number[seg.question_number] = seg

        print(f"SEGMENTED INTO {len(ocr_segments_all)} blocks (matched={_ocr_matched}):")
        for seg in ocr_segments_all:
            print(f"  Q{seg.question_number}: [{seg.status}] {seg.content[:80]}")
        print()

    # Merge: OMR wins for MCQ numbers, OCR fills the rest. Absent numbers are
    # left out (never guessed) so the interview is held out as UNCERTAIN.
    merged: list[SegmentRecord] = []
    for number in range(1, question_count + 1):
        if number in omr_segments:
            merged.append(omr_segments[number])
        elif number in ocr_by_number:
            merged.append(ocr_by_number[number])

    print(f"FINAL MERGED SEGMENTS ({len(merged)}/{question_count} questions):")
    for seg in merged:
        print(f"  Q{seg.question_number}: [{seg.status}] {seg.content[:100]}")
    missing = [n for n in range(1, question_count + 1) if n not in {s.question_number for s in merged}]
    if missing:
        print(f"  MISSING questions: {missing}")
    print()

    unnumbered = [s for s in ocr_segments_all if s.question_number is None]
    save_segments(
        session,
        interview_pk=interview.id,
        segments=unnumbered + merged,
    )

    aligned = len(merged) == question_count
    status = "SEGMENTED" if aligned else "SEGMENTATION_UNCERTAIN"
    interview.status = status
    interview.processing_stage = None
    session.commit()

    logger.info(
        "Interview %s -> %s (%d omr + %d ocr segments, %s)",
        interview.interview_id, status,
        len(omr_segments), len(ocr_by_number),
        "OMR+OCR" if layout_metadata else "OCR-only",
    )
    return {"matched": aligned, "segment_count": len(merged)}


def _segments_ordinal(
    session: Session,
    *,
    interview_pk: int,
) -> list[AnswerSegment]:
    """Return segments ordered for review: aligned first, then unnumbered."""
    return list(
        session.scalars(
            select(AnswerSegment).where(
                AnswerSegment.interview_id == interview_pk,
            ).order_by(
                AnswerSegment.question_number.nulls_last(),
                AnswerSegment.id,
            )
        ).all()
    )


def get_segments(
    session: Session,
    *,
    interview_pk: int,
) -> list[AnswerSegment]:
    return _segments_ordinal(session, interview_pk=interview_pk)


def reassign_segment(
    session: Session,
    segment: AnswerSegment,
    *,
    new_question_number: int,
) -> AnswerSegment:
    """Human override of a segment's question alignment.

    The originally-detected number is preserved on first override so the
    human's correction is auditable and re-segmentation can keep it.
    """
    original = segment.question_number
    if segment.is_manual_override:
        if segment.original_question_number is None:
            segment.original_question_number = original
    else:
        segment.original_question_number = original
        segment.is_manual_override = True

    segment.question_number = new_question_number
    session.commit()
    logger.info(
        "Segment %d reassigned Q%s -> Q%s (was manually overridden)",
        segment.id, segment.original_question_number, new_question_number,
    )
    return segment


def recompute_segmentation_status(
    session: Session,
    *,
    interview: Interview,
) -> bool:
    """After a manual correction, re-derive the interview's status.

    Exact set equality only: SEGMENTED when the stored question numbers are
    precisely ``1..N`` each once, otherwise SEGMENTATION_UNCERTAIN.
    """
    segments = _segments_ordinal(session, interview_pk=interview.id)
    question_count = count_question_keys(
        session, interview_pk=interview.id,
    )
    aligned = matches_question_numbers(
        [SegmentRecord(
            question_number=s.question_number,
            content=s.content,
            status=str(s.status),
        ) for s in segments],
        question_count,
    )
    status = "SEGMENTED" if aligned else "SEGMENTATION_UNCERTAIN"
    interview.status = status
    session.commit()
    return aligned