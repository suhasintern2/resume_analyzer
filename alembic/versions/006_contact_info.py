"""add email and phone contact columns to interviews

Revision ID: 006_contact_info
Revises: 005_score_overrides
Create Date: 2026-09-15

Task 10 (continued):
- Add nullable email / phone TEXT columns so the dashboard can show the
  candidate's contact info that was extracted from the resume.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_contact_info"
down_revision: Union[str, None] = "005_score_overrides"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("interviews", sa.Column("email", sa.Text, nullable=True))
    op.add_column("interviews", sa.Column("phone", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("interviews", "phone")
    op.drop_column("interviews", "email")