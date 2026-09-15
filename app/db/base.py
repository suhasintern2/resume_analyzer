"""Declarative base for SQLAlchemy ORM models.

No models are defined yet (Task 1 is infra-only). Task 2 will add the
interviews / files / evaluations / question_evaluations tables as ORM
classes that inherit from this ``Base``.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass