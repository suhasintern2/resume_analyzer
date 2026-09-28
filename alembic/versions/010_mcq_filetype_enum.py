"""Add MCQ_ANSWER_SHEET to FileType enum

Revision ID: 010_mcq_filetype_enum
Revises: 009_mcq_tables
Create Date: 2026-09-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010_mcq_filetype_enum"
down_revision: Union[str, None] = "009_mcq_tables"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def _replace_enum(
    enum_name: str,
    values: tuple[str, ...],
    columns: list[tuple[str, str]],
) -> None:
    """Rename -> recreate -> cast -> drop recovery-safe ENUM extension."""
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
    # Update FileType enum in files table
    _FILE_TYPE = ("RESUME", "QUESTION_SHEET", "ANSWER_KEY", "ANSWER_SCRIPT", "MCQ_SHEET", "MCQ_ANSWER_SHEET")

    _replace_enum(
        "file_type",
        _FILE_TYPE,
        [("files", "file_type")]
    )


def downgrade() -> None:
    # Revert FileType enum in files table (remove MCQ_ANSWER_SHEET)
    _FILE_TYPE = ("RESUME", "QUESTION_SHEET", "ANSWER_KEY", "ANSWER_SCRIPT", "MCQ_SHEET")

    _replace_enum(
        "file_type",
        _FILE_TYPE,
        [("files", "file_type")]
    )