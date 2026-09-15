"""Tests for Task 5 — LLM evaluation-key generation and persistence.

Requires Postgres from docker-compose; rows/files created here are cleaned up.
"""

import io

import fitz
import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.db.models import Interview, QuestionConceptKey, QuestionEvaluationKey
from app.models.schemas import InterviewResult, QuestionAnswer
from app.services import interview_service
from app.services.evaluation_key_service import save_interview_evaluation_keys

SAMPLE = {
    "candidate_name": "Jane Smith",
    "summary": "Full-stack engineer familiar with the MERN stack.",
    "questions": [
        {
            "number": 1,
            "category": "MCQ",
            "question": "Which one best describes a covering index?",
            "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
            "correct_option": "B",
            "answer": "A covering index is one that includes all columns needed",
            "hr_answer": "It means the database never needs to look up the actual row.",
            "keywords": ["covering index", "B-tree", "include columns"],
            "required_concepts": [
                {"name": "indexing", "weight": 0.6},
                {"name": "query planning", "weight": 0.4},
            ],
            "important_phrases": ["no additional lookup", "leaf pages"],
        },
        {
            "number": 6,
            "category": "Basic Technical",
            "question": "Explain the event loop in Node.js.",
            "options": None,
            "correct_option": None,
            "answer": "The event loop processes the queue...",
            "hr_answer": "Node handles many tasks at once using a single main thread.",
            "keywords": ["event loop", "microtask", "macrotask"],
            "required_concepts": [
                {"name": "event loop", "weight": 1.0},
            ],
            "important_phrases": ["single-threaded", "queue"],
        },
    ],
}


def _pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Jane Smith\nSoftware Engineer\nSkills: Python, Django, React",
    )
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _parse(data: dict) -> InterviewResult:
    """Run data through the same validation path the LLM providers use."""
    return InterviewResult(**data)


def test_normal_weights_around_one_parse_and_are_accepted():
    result = _parse(SAMPLE)
    assert len(result.questions) == 2
    q1 = result.questions[0]
    assert q1.keywords == ["covering index", "B-tree", "include columns"]
    assert q1.important_phrases == ["no additional lookup", "leaf pages"]
    assert len(q1.required_concepts) == 2
    # Weights sum to exactly 1.0 -> unchanged by normalization
    assert q1.required_concepts[0].weight == pytest.approx(0.6)
    assert q1.required_concepts[1].weight == pytest.approx(0.4)
    # Single 1.0 concept also preserved
    assert result.questions[1].required_concepts[0].weight == pytest.approx(1.0)


def test_weights_not_summing_to_one_are_normalized_not_rejected():
    data = {
        "candidate_name": "Jane",
        "summary": "s",
        "questions": [
            {
                "number": 1,
                "category": "MCQ",
                "question": "q",
                "options": None,
                "correct_option": None,
                "answer": "a",
                "hr_answer": "h",
                "keywords": ["k1", "k2"],
                "required_concepts": [
                    {"name": "concept A", "weight": 0.7},
                    {"name": "concept B", "weight": 0.7},
                ],
                "important_phrases": ["p1"],
            }
        ],
    }
    result = _parse(data)
    q = result.questions[0]
    total = sum(c.weight for c in q.required_concepts)
    assert total == pytest.approx(1.0, abs=1e-6)
    weights = [c.weight for c in q.required_concepts]
    assert weights[0] == pytest.approx(0.5, abs=1e-6)
    assert weights[1] == pytest.approx(0.5, abs=1e-6)


def test_weights_summing_to_more_than_one_normalized():
    data = {
        "candidate_name": "Jane",
        "summary": "s",
        "questions": [
            {
                "number": 2,
                "category": "Basic Technical",
                "question": "q",
                "options": None,
                "correct_option": None,
                "answer": "a",
                "hr_answer": "h",
                "keywords": ["k"],
                "required_concepts": [
                    {"name": "a", "weight": 1.0},
                    {"name": "b", "weight": 1.5},
                    {"name": "c", "weight": 2.5},
                ],
                "important_phrases": ["p"],
            }
        ],
    }
    result = _parse(data)
    weights = [c.weight for c in result.questions[0].required_concepts]
    assert sum(weights) == pytest.approx(1.0)
    # relative proportions preserved: 1.0:1.5:2.5 -> 0.2:0.3:0.5
    assert weights == pytest.approx([0.2, 0.3, 0.5])


def test_empty_required_concepts_fails_validation():
    data = {
        "candidate_name": "Jane",
        "summary": "s",
        "questions": [
            {
                "number": 1,
                "category": "MCQ",
                "question": "q",
                "options": None,
                "correct_option": None,
                "answer": "a",
                "hr_answer": "h",
                "keywords": ["k"],
                "required_concepts": [],
                "important_phrases": ["p"],
            }
        ],
    }
    with pytest.raises(Exception):
        _parse(data)


def test_missing_non_numeric_weights_fail_validation():
    # missing weight
    data = SAMPLE.copy()
    q = dict(SAMPLE["questions"][0])
    q["required_concepts"] = [{"name": "x"}, {"name": "y", "weight": 0.4}]
    data["questions"] = [q]
    with pytest.raises(Exception):
        _parse(data)

    # non-numeric weight
    data = SAMPLE.copy()
    q = dict(SAMPLE["questions"][0])
    q["required_concepts"] = [
        {"name": "x", "weight": "high"},
        {"name": "y", "weight": 0.4},
    ]
    data["questions"] = [q]
    with pytest.raises(Exception):
        _parse(data)


def test_gemini_parse_response_handles_markdown_and_normalizes():
    from app.services.llm_service import GeminiProvider

    payload = "```json\n" + __import__("json").dumps(SAMPLE) + "\n```"
    provider = GeminiProvider()
    result = provider._parse_response(payload)
    assert result.candidate_name == "Jane Smith"
    assert result.questions[0].required_concepts[0].weight == pytest.approx(0.6)


@pytest.fixture
def interview_ids():
    ids: list[str] = []
    yield ids
    if not ids:
        return
    with SessionLocal() as session:
        for iv_id in ids:
            iv = interview_service.get_interview(session, iv_id)
            if iv:
                session.delete(iv)
        session.commit()


def test_persist_evaluation_keys_roundtrip(interview_ids):
    pdf = _pdf_bytes()
    with SessionLocal() as session:
        iv = interview_service.create_interview(
            session, content=pdf, ext="pdf", candidate_name="Jane Smith"
        )
        session.commit()
        iv_id = iv.interview_id
        interview_ids.append(iv_id)

        result = _parse(SAMPLE)
        saved = save_interview_evaluation_keys(
            session, interview_id=iv.id, result=result
        )
        session.commit()

        assert saved == 2

        keys = list(
            session.scalars(
                select(QuestionEvaluationKey).where(
                    QuestionEvaluationKey.interview_id == iv.id
                )
            )
        )
        assert len(keys) == 2
        by_number = {k.question_number: k for k in keys}
        assert sorted(by_number) == [1, 6]

        concepts = list(
            session.scalars(
                select(QuestionConceptKey).where(
                    QuestionConceptKey.question_key_id.in_(
                        [k.id for k in keys]
                    )
                )
            )
        )
        assert len(concepts) == 3

        # weights persisted are the normalized ones
        q1 = by_number[1]
        q1_concepts = [
            c for c in concepts if c.question_key_id == q1.id
        ]
        assert {c.name: float(c.weight) for c in q1_concepts} == {
            "indexing": pytest.approx(0.6),
            "query planning": pytest.approx(0.4),
        }


def test_persist_evaluation_keys_replaces_existing(interview_ids):
    pdf = _pdf_bytes()
    with SessionLocal() as session:
        iv = interview_service.create_interview(
            session, content=pdf, ext="pdf"
        )
        session.commit()
        iv_id = iv.interview_id
        interview_ids.append(iv_id)

        save_interview_evaluation_keys(session, interview_id=iv.id, result=_parse(SAMPLE))
        session.commit()

        # Re-save same result -> replaces, no leftovers
        save_interview_evaluation_keys(session, interview_id=iv.id, result=_parse(SAMPLE))
        session.commit()

        keys = list(
            session.scalars(
                select(QuestionEvaluationKey).where(
                    QuestionEvaluationKey.interview_id == iv.id
                )
            )
        )
        assert len(keys) == 2

        concepts = list(
            session.scalars(
                select(QuestionConceptKey).where(
                    QuestionConceptKey.question_key_id.in_([k.id for k in keys])
                )
            )
        )
        assert len(concepts) == 3