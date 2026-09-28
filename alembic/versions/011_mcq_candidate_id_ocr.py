"""Part D correction — candidate_id rename, OCR detail columns, nullable score

Revises daily_mcq_results for the handwritten sequence-OCR pipeline:
- candidate_name -> candidate_id (consistently across results view)
- adds row_status / raw_ocr_text / answer_detail
- score becomes nullable (ILLEGIBLE rows store NULL, never 0)

Guards make this safe whether or not 009 was applied with the old or new
column set (009 itself has been updated for fresh databases).

Revision ID: 011_mcq_candidate_id_ocr
Revises: 010_mcq_filetype_enum
Create Date: 2026-09-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "011_mcq_candidate_id_ocr"
down_revision: Union[str, None] = "010_mcq_filetype_enum"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :table AND column_name = :column"
    ), {"table": table, "column": column})
    return result.first() is not None


def upgrade() -> None:
    if _column_exists("daily_mcq_results", "candidate_name") and not _column_exists(
        "daily_mcq_results", "candidate_id"
    ):
        op.alter_column(
            "daily_mcq_results", "candidate_name",
            new_column_name="candidate_id",
            existing_type=sa.Text(),
            existing_nullable=False,
        )

    if not _column_exists("daily_mcq_results", "candidate_id"):
        op.add_column(
            "daily_mcq_results",
            sa.Column("candidate_id", sa.Text(), nullable=False, server_default=""),
        )

    if not _column_exists("daily_mcq_results", "row_status"):
        op.add_column(
            "daily_mcq_results",
            sa.Column("row_status", sa.Text(), nullable=False, server_default="OK"),
        )

    if not _column_exists("daily_mcq_results", "raw_ocr_text"):
        op.add_column(
            "daily_mcq_results",
            sa.Column("raw_ocr_text", sa.Text(), nullable=True),
        )

    if not _column_exists("daily_mcq_results", "answer_detail"):
        op.add_column(
            "daily_mcq_results",
            sa.Column("answer_detail", postgresql.JSONB(), nullable=True),
        )

    # score must accept NULL for ILLEGIBLE rows
    op.alter_column(
        "daily_mcq_results", "score",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "daily_mcq_results", "score",
        existing_type=sa.Integer(),
        nullable=False,
    )
    if _column_exists("daily_mcq_results", "answer_detail"):
        op.drop_column("daily_mcq_results", "answer_detail")
    if _column_exists("daily_mcq_results", "raw_ocr_text"):
        op.drop_column("daily_mcq_results", "raw_ocr_text")
    if _column_exists("daily_mcq_results", "row_status"):
        op.drop_column("daily_mcq_results", "row_status")
    if _column_exists("daily_mcq_results", "candidate_id"):
        op.alter_column(
            "daily_mcq_results", "candidate_id",
            new_column_name="candidate_name",
            existing_type=sa.Text(),
            existing_nullable=False,
        )
