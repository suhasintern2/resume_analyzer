"""score overrides, evaluation key metadata, evaluating stage

Revision ID: 005_score_overrides
Revises: 004_answer_scripts
Create Date: 2026-09-14

Task 10:
- Add score override columns to question_evaluations:
  original_score, override_score, override_reason, overridden_by, overridden_at
- Add question and sample_answer metadata columns to question_evaluation_keys
  for deterministic evaluation: question_text, sample_answer, category, correct_option, options
- Extend processing_stage ENUM with EVALUATING_ANSWERS
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_score_overrides"
down_revision: Union[str, None] = "004_answer_scripts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROCESSING_STAGE = (
    "EXTRACTING",
    "GENERATING",
    "FORMATTING",
    "EXTRACTING_ANSWERS",
    "EVALUATING_ANSWERS",
)

_PREV_PROCESSING_STAGE = (
    "EXTRACTING",
    "GENERATING",
    "FORMATTING",
    "EXTRACTING_ANSWERS",
)


def _replace_enum(
    enum_name: str,
    values: tuple[str, ...],
    columns: list[tuple[str, str]],
) -> None:
    legacy = f"{enum_name}z_legacy"
    rendered_values = ", ".join(f"'{v}'" for v in values)
    op.execute(sa.text(f"ALTER TYPE {enum_name} RENAME TO {legacy};"))
    op.execute(sa.text(f"CREATE TYPE {enum_name} AS ENUM ({rendered_values});"))
    for table, column in columns:
        op.execute(
            sa.text(
                f"ALTER TABLE {table} ALTER COLUMN {column} "
                f"TYPE {enum_name} USING {column}::text::{enum_name};"
            )
        )
    op.execute(sa.text(f"DROP TYPE IF EXISTS {legacy} CASCADE;"))


def upgrade() -> None:
    _replace_enum(
        "processing_stage",
        _PROCESSING_STAGE,
        [("interviews", "processing_stage")],
    )

    # question_evaluations overrides
    op.add_column("question_evaluations", sa.Column("original_score", sa.Numeric, nullable=True))
    op.add_column("question_evaluations", sa.Column("override_score", sa.Numeric, nullable=True))
    op.add_column("question_evaluations", sa.Column("override_reason", sa.Text, nullable=True))
    op.add_column("question_evaluations", sa.Column("overridden_by", sa.Text, nullable=True))
    op.add_column("question_evaluations", sa.Column("overridden_at", sa.TIMESTAMP(timezone=True), nullable=True))

    # question_evaluation_keys metadata
    op.add_column("question_evaluation_keys", sa.Column("question_text", sa.Text, nullable=True))
    op.add_column("question_evaluation_keys", sa.Column("sample_answer", sa.Text, nullable=True))
    op.add_column("question_evaluation_keys", sa.Column("category", sa.Text, nullable=True))
    op.add_column("question_evaluation_keys", sa.Column("correct_option", sa.Text, nullable=True))
    op.add_column("question_evaluation_keys", sa.Column("options", postgresql.ARRAY(sa.Text), nullable=True))


def downgrade() -> None:
    op.drop_column("question_evaluation_keys", "options")
    op.drop_column("question_evaluation_keys", "correct_option")
    op.drop_column("question_evaluation_keys", "category")
    op.drop_column("question_evaluation_keys", "sample_answer")
    op.drop_column("question_evaluation_keys", "question_text")

    op.drop_column("question_evaluations", "overridden_at")
    op.drop_column("question_evaluations", "overridden_by")
    op.drop_column("question_evaluations", "override_reason")
    op.drop_column("question_evaluations", "override_score")
    op.drop_column("question_evaluations", "original_score")

    _replace_enum(
        "processing_stage",
        _PREV_PROCESSING_STAGE,
        [("interviews", "processing_stage")],
    )
