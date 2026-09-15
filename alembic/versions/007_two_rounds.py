"""two-round delivery, short IDs, filename/display labels

Revision ID: 007_two_rounds
Revises: 006_contact_info
Create Date: 2026-09-15

Task 11 (Revised):
- interviews: add original_filename + display_name (display/labeling only;
  the generated storage filename stays uuid4-based and separate).
- New interview_rounds table (round_number 1|2, per-round status via a
  TEXT vocabulary, selected_for_next_round flag on round 1).
- files / evaluations / question_evaluation_keys / answer_segments get a
  nullable round_id (NULL = legacy pre-round rows / resume record file).
- evaluations.is_current now applies per (interview_id, round_id): the old
  partial unique index on (interview_id) is replaced with
  (interview_id, COALESCE(round_id, -1)) WHERE is_current=true.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_two_rounds"
down_revision: Union[str, None] = "006_contact_info"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── interviews: display labels (never the storage filename) ─────────
    op.add_column("interviews", sa.Column("original_filename", sa.Text, nullable=True))
    op.add_column("interviews", sa.Column("display_name", sa.Text, nullable=True))

    # ── interview_rounds ─────────────────────────────────────────────────
    op.create_table(
        "interview_rounds",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "interview_id", sa.Integer,
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("selected_for_next_round", sa.Boolean, nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("interview_id", "round_number", name="uq_round_per_interview"),
        sa.CheckConstraint(
            "round_number IN (1, 2)", name="ck_round_number_1_or_2",
        ),
    )
    op.create_index(
        "ix_interview_rounds_status", "interview_rounds", ["status"],
    )

    # ── round_id on round-scoped child tables ────────────────────────────
    op.add_column(
        "files", sa.Column(
            "round_id", sa.Integer,
            sa.ForeignKey("interview_rounds.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "evaluations", sa.Column(
            "round_id", sa.Integer,
            sa.ForeignKey("interview_rounds.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "question_evaluation_keys", sa.Column(
            "round_id", sa.Integer,
            sa.ForeignKey("interview_rounds.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "answer_segments", sa.Column(
            "round_id", sa.Integer,
            sa.ForeignKey("interview_rounds.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # Helpers for round-scoped lookups
    op.create_index(
        "ix_files_round_id", "files", ["round_id"],
    )
    op.create_index(
        "ix_evaluations_round_id", "evaluations", ["round_id"],
    )
    op.create_index(
        "ix_question_evaluation_keys_round_id",
        "question_evaluation_keys", ["round_id"],
    )
    op.create_index(
        "ix_answer_segments_round_id", "answer_segments", ["round_id"],
    )

    # ── is_current now per (interview_id, round_id) ──────────────────────
    op.drop_index("uq_evaluations_current", table_name="evaluations")
    op.create_index(
        "uq_evaluations_current_per_round",
        "evaluations",
        [sa.text("interview_id"), sa.text("COALESCE(round_id, -1)")],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    # updated_at trigger for interview_rounds
    op.execute(sa.text(
        "CREATE TRIGGER trg_interview_rounds_updated_at "
        "BEFORE UPDATE ON interview_rounds "
        "FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "DROP TRIGGER IF EXISTS trg_interview_rounds_updated_at ON interview_rounds;"
    ))

    op.drop_index("uq_evaluations_current_per_round", table_name="evaluations")
    op.create_index(
        "uq_evaluations_current",
        "evaluations",
        ["interview_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    op.drop_index("ix_answer_segments_round_id", table_name="answer_segments")
    op.drop_index("ix_question_evaluation_keys_round_id", table_name="question_evaluation_keys")
    op.drop_index("ix_evaluations_round_id", table_name="evaluations")
    op.drop_index("ix_files_round_id", table_name="files")

    op.drop_column("answer_segments", "round_id")
    op.drop_column("question_evaluation_keys", "round_id")
    op.drop_column("evaluations", "round_id")
    op.drop_column("files", "round_id")

    op.drop_index("ix_interview_rounds_status", table_name="interview_rounds")
    op.drop_table("interview_rounds")

    op.drop_column("interviews", "display_name")
    op.drop_column("interviews", "original_filename")