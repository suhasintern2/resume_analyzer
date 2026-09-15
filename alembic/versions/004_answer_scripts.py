"""answer scripts: enums + answer_segments table

Revision ID: 004_answer_scripts
Revises: 003_error_reason
Create Date: 2026-09-14

Task 9: the answer-script OCR/sub-segmentation pipeline stage
(``EXTRACTING_ANSWERS``), the post-segmentation states (``SEGMENTED`` /
``SEGMENTATION_UNCERTAIN``), and the ``answer_segments`` table that holds
the OCR-transcribed per-question candidate answers for review and manual
correction before evaluation (Task 10).

Postgres ENUM values are extended in place via the rename -> recreate ->
cast -> drop recipe so the revision stays reversible against any earlier
schema.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_answer_scripts"
down_revision: Union[str, None] = "003_error_reason"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Full value sets after this migration.
_INTERVIEW_STATUS = (
    "QUEUED", "PROCESSING", "COMPLETED", "FAILED", "ANSWER_UPLOADED",
    "SEGMENTED", "SEGMENTATION_UNCERTAIN", "EVALUATING",
    "EVALUATED", "EVALUATION_FAILED",
)
_PROCESSING_STAGE = ("EXTRACTING", "GENERATING", "FORMATTING", "EXTRACTING_ANSWERS")
_ANSWER_SEGMENT_STATUS = ("TRANSCRIBED", "BLANK", "ILLEGIBLE")


def _replace_enum(
    enum_name: str,
    values: tuple[str, ...],
    columns: list[tuple[str, str]],
) -> None:
    """Recreate an ENUM type with a new value set.

    Postgres has no ALTER TYPE ... ADD VALUE ... before v10 was fine but
    cannot run inside a transaction block (which Alembic runs in), so the
    portable recipe is: rename the old type, create the new one, cast every
    referencing column ``old::text::new``, then drop the old type.
    """
    legacy = f"{enum_name}z_legacy"
    rendered_values = ", ".join(f"'{v}'" for v in values)
    op.execute(sa.text(f"ALTER TYPE {enum_name} RENAME TO {legacy};"))
    op.execute(sa.text(f"CREATE TYPE {enum_name} AS ENUM ({rendered_values});"))
    for table, column in columns:
        op.execute(sa.text(
            f"ALTER TABLE {table} ALTER COLUMN {column} "
            f"TYPE {enum_name} USING {column}::text::{enum_name};"
        ))
    op.execute(sa.text(f"DROP TYPE IF EXISTS {legacy} CASCADE;"))


def upgrade() -> None:
    # ── Extend the two enums the answer-script flow uses ────────────────
    _replace_enum(
        "processing_stage",
        _PROCESSING_STAGE,
        [("interviews", "processing_stage")],
    )
    _replace_enum(
        "interview_status",
        _INTERVIEW_STATUS,
        [("interviews", "status")],
    )

    # ── answer_segments ─────────────────────────────────────────────────
    # One row per segmented block of OCR'd handwriting. question_number is
    # NULL when the OCR could not be aligned to a question (review/override
    # target); is_manual_override + original_question_number record any
    # human reassignment that happened outside the automatic matcher.
    op.create_table(
        "answer_segments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "interview_id", sa.Integer,
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_number", sa.Integer, nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Enum(*_ANSWER_SEGMENT_STATUS, name="answer_segment_status"),
            nullable=False,
        ),
        sa.Column(
            "is_manual_override", sa.Boolean,
            nullable=False, server_default=sa.text("false"),
        ),
        sa.Column("original_question_number", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index(
        "ix_answer_segments_interview_id",
        "answer_segments",
        ["interview_id"],
    )

    op.execute(sa.text(
        "CREATE TRIGGER trg_answer_segments_updated_at "
        "BEFORE UPDATE ON answer_segments "
        "FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "DROP TRIGGER IF EXISTS trg_answer_segments_updated_at ON answer_segments;"
    ))
    op.drop_index("ix_answer_segments_interview_id", table_name="answer_segments")
    op.drop_table("answer_segments")
    op.execute(sa.text("DROP TYPE IF EXISTS answer_segment_status CASCADE;"))

    _replace_enum(
        "interview_status",
        (
            "QUEUED", "PROCESSING", "COMPLETED", "FAILED", "ANSWER_UPLOADED",
            "EVALUATING", "EVALUATED", "EVALUATION_FAILED",
        ),
        [("interviews", "status")],
    )
    _replace_enum(
        "processing_stage",
        ("EXTRACTING", "GENERATING", "FORMATTING"),
        [("interviews", "processing_stage")],
    )