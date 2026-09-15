"""ORM models for the Resume Analyzer data model.

These classes define the schema for Task 2's Alembic migration. They carry
no query logic — only column/type/index definitions. Business logic (Task 3+)
will live in service layers, not here.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db.base import Base

# ---------------------------------------------------------------------------
# Enum definitions — kept in sync with the Alembic migration that creates
# the Postgres ENUM types.  create_type=False / create_constraint=False so
# Alembic owns type lifecycle, not create_all / Model.metadata.create_engine.
# ---------------------------------------------------------------------------

_interview_status = (
    "QUEUED",
    "PROCESSING",
    "COMPLETED",
    "FAILED",
    "ANSWER_UPLOADED",
    "SEGMENTED",
    "SEGMENTATION_UNCERTAIN",
    "EVALUATING",
    "EVALUATED",
    "EVALUATION_FAILED",
)

_processing_stage = (
    "EXTRACTING", "GENERATING", "FORMATTING", "EXTRACTING_ANSWERS",
    "EVALUATING_ANSWERS",
)

_answer_segment_status = ("TRANSCRIBED", "BLANK", "ILLEGIBLE", "AMBIGUOUS_MARK")

_evaluation_status = ("PENDING", "EVALUATED", "EVALUATION_FAILED")

_question_eval_status = (
    "EVALUATED",
    "NO_ANSWER",
    "OCR_FAILED",
    "UNCERTAIN",
    "SEGMENTATION_UNCERTAIN",
)

_file_type = ("RESUME", "QUESTION_SHEET", "ANSWER_KEY", "ANSWER_SCRIPT")

# Task 11 — per-round lifecycle vocabulary (TEXT column, not a PG enum).
_round_status = (
    "NOT_STARTED",
    "QUESTIONS_GENERATING",
    "QUESTIONS_READY",
    "ANSWER_UPLOADED",
    "SEGMENTED",
    "SEGMENTATION_UNCERTAIN",
    "EVALUATING",
    "EVALUATED",
    "EVALUATION_FAILED",
    "FAILED",
)

ROUND_1 = 1
ROUND_2 = 2
ROUND_NUMBERS = (ROUND_1, ROUND_2)

InterviewStatusType = sa.Enum(
    *_interview_status, name="interview_status",
    create_constraint=False, create_type=False,
)
ProcessingStageType = sa.Enum(
    *_processing_stage, name="processing_stage",
    create_constraint=False, create_type=False,
)
AnswerSegmentStatusType = sa.Enum(
    *_answer_segment_status, name="answer_segment_status",
    create_constraint=False, create_type=False,
)
EvaluationStatusType = sa.Enum(
    *_evaluation_status, name="evaluation_status",
    create_constraint=False, create_type=False,
)
QuestionEvalStatusType = sa.Enum(
    *_question_eval_status, name="question_eval_status",
    create_constraint=False, create_type=False,
)
FileTypeType = sa.Enum(
    *_file_type, name="file_type",
    create_constraint=False, create_type=False,
)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

class Interview(Base):
    __tablename__ = "interviews"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    interview_id = sa.Column(sa.Text, unique=True, nullable=False)
    candidate_name = sa.Column(sa.Text)
    email = sa.Column(sa.Text)
    phone = sa.Column(sa.Text)
    original_filename = sa.Column(sa.Text)
    display_name = sa.Column(sa.Text)
    status = sa.Column(InterviewStatusType, nullable=False)
    processing_stage = sa.Column(ProcessingStageType)
    error_reason = sa.Column(sa.Text)
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at = sa.Column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        onupdate=sa.func.now(),
    )


class File(Base):
    __tablename__ = "files"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    interview_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("interview_rounds.id", ondelete="CASCADE"),
    )
    file_type = sa.Column(FileTypeType, nullable=False)
    file_path = sa.Column(sa.Text, nullable=False)
    # Task 12 — OMR layout metadata for the printed question sheet (checkbox
    # bounding boxes in normalized page coordinates). NULL for everything
    # that is not an OMR-scannable question sheet.
    layout_metadata = sa.Column(postgresql.JSONB)
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    interview_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("interview_rounds.id", ondelete="CASCADE"),
    )
    evaluator_version = sa.Column(sa.Text, nullable=False)
    total_score = sa.Column(sa.Numeric)
    max_score = sa.Column(sa.Numeric)
    percentage = sa.Column(sa.Numeric)
    status = sa.Column(EvaluationStatusType, nullable=False)
    is_current = sa.Column(
        sa.Boolean, nullable=False, server_default=sa.text("true"),
    )
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at = sa.Column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        onupdate=sa.func.now(),
    )


class QuestionEvaluation(Base):
    __tablename__ = "question_evaluations"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    evaluation_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_number = sa.Column(sa.Integer, nullable=False)
    score = sa.Column(sa.Numeric)
    max_score = sa.Column(sa.Numeric)
    keyword_score = sa.Column(sa.Numeric)
    concept_score = sa.Column(sa.Numeric)
    phrase_score = sa.Column(sa.Numeric)
    similarity_score = sa.Column(sa.Numeric)
    structure_score = sa.Column(sa.Numeric)
    status = sa.Column(QuestionEvalStatusType, nullable=False)
    feedback = sa.Column(sa.Text)
    original_score = sa.Column(sa.Numeric)
    override_score = sa.Column(sa.Numeric)
    override_reason = sa.Column(sa.Text)
    overridden_by = sa.Column(sa.Text)
    overridden_at = sa.Column(sa.TIMESTAMP(timezone=True))


class QuestionEvaluationKey(Base):
    """Task 5 — one row per question's deterministic evaluation key.

    Stores the LLM-generated keywords and important_phrases as queryable
    Postgres TEXT[] arrays, and the weighted concepts via the
    QuestionConceptKey child table (never a mixed-purpose JSON blob).
    Weights stored here are the server-side normalized values.
    """

    __tablename__ = "question_evaluation_keys"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    interview_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("interview_rounds.id", ondelete="CASCADE"),
    )
    question_number = sa.Column(sa.Integer, nullable=False)
    keywords = sa.Column(postgresql.ARRAY(sa.Text), nullable=False)
    important_phrases = sa.Column(postgresql.ARRAY(sa.Text), nullable=False)
    question_text = sa.Column(sa.Text)
    sample_answer = sa.Column(sa.Text)
    category = sa.Column(sa.Text)
    correct_option = sa.Column(sa.Text)
    options = sa.Column(postgresql.ARRAY(sa.Text))
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        sa.UniqueConstraint("interview_id", "round_id", "question_number"),
    )


class QuestionConceptKey(Base):
    """One row per weighted concept for a question's evaluation key."""

    __tablename__ = "question_concept_keys"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    question_key_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("question_evaluation_keys.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = sa.Column(sa.Text, nullable=False)
    weight = sa.Column(sa.Numeric, nullable=False)
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


class AnswerSegment(Base):
    """Task 9 — one OCR'd block of the candidate's handwritten answer sheet.

    ``question_number`` is NULL only while the automatic matcher could not
    align a block to a question (SEGMENTATION_UNCERTAIN) — such blocks are
    review/override targets, never silently guessed. A human reassignment
    sets ``is_manual_override`` and preserves the originally-detected number
    in ``original_question_number``.
    """

    __tablename__ = "answer_segments"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    interview_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("interview_rounds.id", ondelete="CASCADE"),
    )
    question_number = sa.Column(sa.Integer, nullable=True)
    content = sa.Column(sa.Text, nullable=False)
    status = sa.Column(AnswerSegmentStatusType, nullable=False)
    is_manual_override = sa.Column(
        sa.Boolean, nullable=False, server_default=sa.text("false"),
    )
    original_question_number = sa.Column(sa.Integer, nullable=True)
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at = sa.Column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        onupdate=sa.func.now(),
    )


class InterviewRound(Base):
    """One row per interview round (Task 11).

    ``status`` is a TEXT vocabulary (see ``_round_status``) owned by the
    round-scoped services/worker — deliberately not a PG enum so the
    vocabulary can grow (it does: SEGMENTED / SEGMENTATION_UNCERTAIN were
    added to the spec list so the round flow mirrors the answer-script
    lifecycle). ``selected_for_next_round`` is only meaningful on round 1:
    NULL until a staff decision, then True (advance) or False (reject).
    """

    __tablename__ = "interview_rounds"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    interview_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_number = sa.Column(sa.Integer, nullable=False)
    status = sa.Column(sa.Text, nullable=False)
    selected_for_next_round = sa.Column(sa.Boolean)
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at = sa.Column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.UniqueConstraint("interview_id", "round_number"),
    )
