"""Persist LLM-generated deterministic evaluation keys (Task 5).

After ``generate_interview_questions`` returns an ``InterviewResult`` whose
questions carry ``keywords``, ``required_concepts`` (weights already
normalized server-side by the Pydantic validator) and ``important_phrases``,
this module stores that key per question for an interview so the
deterministic evaluator (Task 10) can query it — structured tables, not a
mixed-purpose JSON blob.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import QuestionConceptKey, QuestionEvaluationKey
from app.models.schemas import InterviewResult

logger = logging.getLogger(__name__)


def save_interview_evaluation_keys(
    session: Session,
    *,
    interview_id: int,
    result: InterviewResult,
    round_id: int | None = None,
) -> int:
    """Persist one evaluation key row per question, replacing any existing
    keys for the same interview + round.  ``round_id`` is None for legacy
    (pre-Task-11) single-round records. Returns the number of rows saved."""
    if round_id is None:
        existing = list(
            session.scalars(
                select(QuestionEvaluationKey).where(
                    QuestionEvaluationKey.interview_id == interview_id,
                    QuestionEvaluationKey.round_id.is_(None),
                )
            ).all()
        )
    else:
        existing = list(
            session.scalars(
                select(QuestionEvaluationKey).where(
                    QuestionEvaluationKey.interview_id == interview_id,
                    QuestionEvaluationKey.round_id == round_id,
                )
            ).all()
        )
    for key in existing:
        session.delete(key)
    session.flush()

    saved = 0
    for question in result.questions:
        key = QuestionEvaluationKey(
            interview_id=interview_id,
            round_id=round_id,
            question_number=question.number,
            keywords=list(question.keywords),
            important_phrases=list(question.important_phrases),
            question_text=question.question,
            sample_answer=question.answer,
            category=question.category,
            correct_option=question.correct_option,
            options=list(question.options) if question.options else None,
        )
        session.add(key)
        session.flush()  # obtain key.id for the concept children

        for concept in question.required_concepts:
            session.add(
                QuestionConceptKey(
                    question_key_id=key.id,
                    name=concept.name,
                    weight=concept.weight,
                )
            )
        saved += 1

    session.flush()
    logger.info(
        "Saved %d question evaluation keys for interview id=%s", saved, interview_id
    )
    return saved