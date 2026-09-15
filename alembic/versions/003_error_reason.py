"""add error_reason to interviews

Revision ID: 003_error_reason
Revises: 002_evaluation_keys
Create Date: 2026-09-14

Task 8: the worker persists a stored, safe error reason on the interview
when the pipeline fails (never stack traces — those are logged server-side
only). Adds ``interviews.error_reason``.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_error_reason"
down_revision: Union[str, None] = "002_evaluation_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "interviews",
        sa.Column("error_reason", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interviews", "error_reason")