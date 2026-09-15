"""task12: AMBIGUOUS_MARK segment status + OMR layout_metadata

Revision ID: 008_task12_omr_ai_free
Revises: 007_two_rounds
Create Date: 2026-09-15

Task 12 (Part B — fully AI-free answer-script pipeline):
- Extend ``answer_segment_status`` with ``AMBIGUOUS_MARK``: an OMR-detected
  MCQ where more than one checkbox is marked above the ink threshold. Such a
  segment is held out of scoring (like OCR_FAILED), never silently scored.
- Add ``files.layout_metadata`` JSONB: the deterministic OMR checkbox
  bounding-box coordinate set for a printed question sheet. NULL for every
  file type that is not an OMR-scannable question sheet.

Postgres ENUM extension uses the rename -> recreate -> cast -> drop recipe
(identical to 004_answer_scripts).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_task12_omr_ai_free"
down_revision: Union[str, None] = "007_two_rounds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FULL_ANSWER_SEGMENT_STATUS = ("TRANSCRIBED", "BLANK", "ILLEGIBLE", "AMBIGUOUS_MARK")
_LEGACY_ANSWER_SEGMENT_STATUS = ("TRANSCRIBED", "BLANK", "ILLEGIBLE")


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
    _replace_enum(
        "answer_segment_status",
        _FULL_ANSWER_SEGMENT_STATUS,
        [("answer_segments", "status")],
    )

    op.add_column(
        "files",
        sa.Column("layout_metadata", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("files", "layout_metadata")

    _replace_enum(
        "answer_segment_status",
        _LEGACY_ANSWER_SEGMENT_STATUS,
        [("answer_segments", "status")],
    )