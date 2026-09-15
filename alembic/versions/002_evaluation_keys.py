"""evaluation keys per question

Revision ID: 002_evaluation_keys
Revises: 001_initial
Create Date: 2026-09-14

Task 5: persist the deterministic LLM-generated evaluation key (keywords,
weighted concepts, important phrases) per question for an interview. Two
new tables:

* question_evaluation_keys  — one row per question for an interview, with
  TEXT[] arrays for keywords and important_phrases.
* question_concept_keys     — one row per weighted concept, child of
  question_evaluation_keys, holding name + normalized weight.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_evaluation_keys"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "question_evaluation_keys",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "interview_id", sa.Integer,
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_number", sa.Integer, nullable=False),
        sa.Column("keywords", postgresql.ARRAY(sa.Text), nullable=False),
        sa.Column("important_phrases", postgresql.ARRAY(sa.Text), nullable=False),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )

    op.create_index(
        "uq_eval_key_per_question",
        "question_evaluation_keys",
        ["interview_id", "question_number"],
        unique=True,
    )

    op.create_table(
        "question_concept_keys",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "question_key_id", sa.Integer,
            sa.ForeignKey("question_evaluation_keys.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("weight", sa.Numeric, nullable=False),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )

    op.create_index(
        "ix_concept_key_question",
        "question_concept_keys",
        ["question_key_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_concept_key_question", table_name="question_concept_keys")
    op.drop_table("question_concept_keys")
    op.drop_index("uq_eval_key_per_question", table_name="question_evaluation_keys")
    op.drop_table("question_evaluation_keys")