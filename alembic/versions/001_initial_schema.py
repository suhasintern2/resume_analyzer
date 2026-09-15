"""initial schema

Revision ID: 001_initial
Revises: None
Create Date: 2026-09-14

Creates the four core tables (interviews, files, evaluations,
question_evaluations) with Postgres ENUM types, cascading FKs, a
partial unique index on evaluations.is_current, and an updated_at
trigger for interviews + evaluations.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── Enum value tuples ───────────────────────────────────────────────────

_INTERVIEW_STATUS = (
    "QUEUED", "PROCESSING", "COMPLETED", "FAILED",
    "ANSWER_UPLOADED", "EVALUATING", "EVALUATED", "EVALUATION_FAILED",
)
_PROCESSING_STAGE = ("EXTRACTING", "GENERATING", "FORMATTING")
_EVALUATION_STATUS = ("PENDING", "EVALUATED", "EVALUATION_FAILED")
_QUESTION_EVAL_STATUS = (
    "EVALUATED", "NO_ANSWER", "OCR_FAILED", "UNCERTAIN", "SEGMENTATION_UNCERTAIN",
)
_FILE_TYPE = ("RESUME", "QUESTION_SHEET", "ANSWER_KEY", "ANSWER_SCRIPT")

_ENUM_NAMES = [
    "interview_status",
    "processing_stage",
    "evaluation_status",
    "question_eval_status",
    "file_type",
]


def upgrade() -> None:
    # ── interviews ──────────────────────────────────────────────────────
    # Enum types are created automatically by create_table when the
    # sa.Enum column is defined inline.  Because this is a fresh DB,
    # there are no pre-existing types to conflict with.
    op.create_table(
        "interviews",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("interview_id", sa.Text, unique=True, nullable=False),
        sa.Column("candidate_name", sa.Text),
        sa.Column(
            "status",
            sa.Enum(*_INTERVIEW_STATUS, name="interview_status"),
            nullable=False,
        ),
        sa.Column(
            "processing_stage",
            sa.Enum(*_PROCESSING_STAGE, name="processing_stage"),
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )

    # ── files ───────────────────────────────────────────────────────────
    op.create_table(
        "files",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "interview_id", sa.Integer,
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "file_type",
            sa.Enum(*_FILE_TYPE, name="file_type"),
            nullable=False,
        ),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )

    # ── evaluations ─────────────────────────────────────────────────────
    op.create_table(
        "evaluations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "interview_id", sa.Integer,
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evaluator_version", sa.Text, nullable=False),
        sa.Column("total_score", sa.Numeric),
        sa.Column("max_score", sa.Numeric),
        sa.Column("percentage", sa.Numeric),
        sa.Column(
            "status",
            sa.Enum(*_EVALUATION_STATUS, name="evaluation_status"),
            nullable=False,
        ),
        sa.Column(
            "is_current", sa.Boolean, nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )

    # At most one is_current=true per interview
    op.create_index(
        "uq_evaluations_current",
        "evaluations",
        ["interview_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    # ── question_evaluations ────────────────────────────────────────────
    op.create_table(
        "question_evaluations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "evaluation_id", sa.Integer,
            sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_number", sa.Integer, nullable=False),
        sa.Column("score", sa.Numeric),
        sa.Column("max_score", sa.Numeric),
        sa.Column("keyword_score", sa.Numeric),
        sa.Column("concept_score", sa.Numeric),
        sa.Column("phrase_score", sa.Numeric),
        sa.Column("similarity_score", sa.Numeric),
        sa.Column("structure_score", sa.Numeric),
        sa.Column(
            "status",
            sa.Enum(*_QUESTION_EVAL_STATUS, name="question_eval_status"),
            nullable=False,
        ),
        sa.Column("feedback", sa.Text),
    )

    # One row per question number per evaluation run
    op.create_index(
        "uq_question_eval_per_question",
        "question_evaluations",
        ["evaluation_id", "question_number"],
        unique=True,
    )

    # ── updated_at trigger (shared function for interviews + evaluations)
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))
    op.execute(sa.text(
        "CREATE TRIGGER trg_interviews_updated_at "
        "BEFORE UPDATE ON interviews "
        "FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();"
    ))
    op.execute(sa.text(
        "CREATE TRIGGER trg_evaluations_updated_at "
        "BEFORE UPDATE ON evaluations "
        "FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();"
    ))


def downgrade() -> None:
    # Triggers and function
    op.execute(sa.text(
        "DROP TRIGGER IF EXISTS trg_evaluations_updated_at ON evaluations;"
    ))
    op.execute(sa.text(
        "DROP TRIGGER IF EXISTS trg_interviews_updated_at ON interviews;"
    ))
    op.execute(sa.text(
        "DROP FUNCTION IF EXISTS update_updated_at_column;"
    ))

    # Indexes before tables
    op.drop_index(
        "uq_question_eval_per_question", table_name="question_evaluations",
    )
    op.drop_table("question_evaluations")
    op.drop_index("uq_evaluations_current", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_table("files")
    op.drop_table("interviews")

    # Drop ENUM types (CASCADE needed in case of leftover usage)
    for name in _ENUM_NAMES:
        op.execute(sa.text(
            f"DROP TYPE IF EXISTS {name} CASCADE;"
        ))