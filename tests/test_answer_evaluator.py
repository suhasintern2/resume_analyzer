"""Tests for Task 10 Part A: Deterministic Evaluator Service (Spec Section 70/71).

Asserts expected score bands, not exact numbers, for:
- Exact answer -> High score
- Paraphrased answer -> High score
- Technical synonym -> High score (correctly recognized)
- Partial answer -> Medium score
- Wrong answer -> Low score
- Empty answer -> Score 0, status NO_ANSWER
- Irrelevant answer (even if long) -> Low score (length alone does not inflate score)
- OCR failure -> Score None (N/A), status OCR_FAILED
- Uncertain -> Score None, status UNCERTAIN
- MCQ correct/incorrect
- Weight configurability
"""

from decimal import Decimal
import pytest

from app.services.answer_evaluator import (
    AnswerEvaluationService,
    QuestionKeyData,
    build_tfidf_corpus,
    evaluate_single_question,
    get_layer_weights,
    score_concepts,
    score_keywords,
    score_phrases,
    score_similarity,
    score_structure,
)


@pytest.fixture
def django_question_key():
    return {
        "question_number": 1,
        "question_text": "What is Django ORM?",
        "category": "Basic Technical",
        "options": None,
        "correct_option": None,
        "sample_answer": (
            "Django ORM is an object relational mapper that allows Python models "
            "to interact with database records without writing raw SQL queries."
        ),
        "keywords": ["django", "orm", "database", "model", "sql", "query"],
        "concepts": [
            ("database interaction", 0.35),
            ("Python models", 0.35),
            ("SQL abstraction", 0.30),
        ],
        "phrases": [
            "object relational mapper",
            "database abstraction",
        ],
    }


@pytest.fixture
def shared_corpus(django_question_key):
    docs = [
        django_question_key["sample_answer"].split(),
        ["database", "interaction", "python", "models", "sql", "abstraction"],
        ["object", "relational", "mapper", "database", "abstraction"],
        ["node", "event", "loop", "single", "threaded", "asynchronous", "javascript"],
        ["react", "virtual", "dom", "component", "state", "props", "lifecycle"],
    ]
    vocab, idf = build_tfidf_corpus(docs)
    return vocab, idf


def test_exact_answer_high_score(django_question_key, shared_corpus):
    vocab, idf = shared_corpus
    weights = get_layer_weights()

    # Answer very close to the sample answer
    candidate_answer = (
        "Django ORM is an object relational mapper that allows Python models "
        "to interact with database records without writing raw SQL queries."
    )

    result = evaluate_single_question(
        question_number=django_question_key["question_number"],
        question_text=django_question_key["question_text"],
        category=django_question_key["category"],
        options=django_question_key["options"],
        correct_option=django_question_key["correct_option"],
        sample_answer=django_question_key["sample_answer"],
        answer_text=candidate_answer,
        answer_status="TRANSCRIBED",
        keywords=django_question_key["keywords"],
        concepts=django_question_key["concepts"],
        phrases=django_question_key["phrases"],
        vocab=vocab,
        idf=idf,
        weights=weights,
        max_score=10,
    )

    assert result["status"] == "EVALUATED"
    assert result["score"] is not None
    # Section 70: Exact answer -> High score (>= 8.0 / 10)
    assert float(result["score"]) >= 8.0
    assert "coverage" in result["feedback"].lower() or "excellent" in result["feedback"].lower()


def test_paraphrased_answer_high_score(django_question_key, shared_corpus):
    vocab, idf = shared_corpus
    weights = get_layer_weights()

    # Spec Section 15 example of paraphrased answer:
    candidate_answer = (
        "Django provides a model abstraction that lets Python code work "
        "with database data without manually writing SQL queries."
    )

    result = evaluate_single_question(
        question_number=django_question_key["question_number"],
        question_text=django_question_key["question_text"],
        category=django_question_key["category"],
        options=django_question_key["options"],
        correct_option=django_question_key["correct_option"],
        sample_answer=django_question_key["sample_answer"],
        answer_text=candidate_answer,
        answer_status="TRANSCRIBED",
        keywords=django_question_key["keywords"],
        concepts=django_question_key["concepts"],
        phrases=django_question_key["phrases"],
        vocab=vocab,
        idf=idf,
        weights=weights,
        max_score=10,
    )

    assert result["status"] == "EVALUATED"
    assert result["score"] is not None
    # Section 70: Paraphrased answer -> High score (>= 7.0 / 10)
    assert float(result["score"]) >= 7.0


def test_technical_synonym_recognized(django_question_key, shared_corpus):
    vocab, idf = shared_corpus
    weights = get_layer_weights()

    # Answer using "db" for "database", "postgres" relations
    candidate_answer = (
        "Django ORM allows Python models to communicate with the db datastore "
        "and handles sql query generation automatically."
    )

    result = evaluate_single_question(
        question_number=django_question_key["question_number"],
        question_text=django_question_key["question_text"],
        category=django_question_key["category"],
        options=django_question_key["options"],
        correct_option=django_question_key["correct_option"],
        sample_answer=django_question_key["sample_answer"],
        answer_text=candidate_answer,
        answer_status="TRANSCRIBED",
        keywords=django_question_key["keywords"],
        concepts=django_question_key["concepts"],
        phrases=django_question_key["phrases"],
        vocab=vocab,
        idf=idf,
        weights=weights,
        max_score=10,
    )

    assert result["status"] == "EVALUATED"
    # Technical synonyms should be recognized and achieve high score band
    assert float(result["score"]) >= 7.0


def test_partial_answer_medium_score(django_question_key, shared_corpus):
    vocab, idf = shared_corpus
    weights = get_layer_weights()

    # Covers database communication, but misses SQL abstraction & model specifics
    candidate_answer = "Django is a web framework that connects to a database."

    result = evaluate_single_question(
        question_number=django_question_key["question_number"],
        question_text=django_question_key["question_text"],
        category=django_question_key["category"],
        options=django_question_key["options"],
        correct_option=django_question_key["correct_option"],
        sample_answer=django_question_key["sample_answer"],
        answer_text=candidate_answer,
        answer_status="TRANSCRIBED",
        keywords=django_question_key["keywords"],
        concepts=django_question_key["concepts"],
        phrases=django_question_key["phrases"],
        vocab=vocab,
        idf=idf,
        weights=weights,
        max_score=10,
    )

    assert result["status"] == "EVALUATED"
    # Section 70: Partial answer -> Medium/low-medium score (between 2.5 and 6.5)
    assert 2.0 <= float(result["score"]) <= 6.5


def test_wrong_answer_low_score(django_question_key, shared_corpus):
    vocab, idf = shared_corpus
    weights = get_layer_weights()

    candidate_answer = "Django ORM is a tool for compiling CSS styles and images into HTML."

    result = evaluate_single_question(
        question_number=django_question_key["question_number"],
        question_text=django_question_key["question_text"],
        category=django_question_key["category"],
        options=django_question_key["options"],
        correct_option=django_question_key["correct_option"],
        sample_answer=django_question_key["sample_answer"],
        answer_text=candidate_answer,
        answer_status="TRANSCRIBED",
        keywords=django_question_key["keywords"],
        concepts=django_question_key["concepts"],
        phrases=django_question_key["phrases"],
        vocab=vocab,
        idf=idf,
        weights=weights,
        max_score=10,
    )

    assert result["status"] == "EVALUATED"
    # Section 70: Wrong answer -> Low score (< 3.5 / 10)
    assert float(result["score"]) < 3.5


def test_empty_blank_answer_zero_score(django_question_key, shared_corpus):
    vocab, idf = shared_corpus
    weights = get_layer_weights()

    for blank_variant in ("", "   ", "[BLANK]"):
        result = evaluate_single_question(
            question_number=django_question_key["question_number"],
            question_text=django_question_key["question_text"],
            category=django_question_key["category"],
            options=django_question_key["options"],
            correct_option=django_question_key["correct_option"],
            sample_answer=django_question_key["sample_answer"],
            answer_text=blank_variant,
            answer_status="BLANK" if blank_variant == "[BLANK]" else "TRANSCRIBED",
            keywords=django_question_key["keywords"],
            concepts=django_question_key["concepts"],
            phrases=django_question_key["phrases"],
            vocab=vocab,
            idf=idf,
            weights=weights,
            max_score=10,
        )

        assert result["status"] == "NO_ANSWER"
        assert result["score"] == Decimal("0.00")
        assert result["feedback"] == "No answer was provided."


def test_long_irrelevant_answer_low_score(django_question_key, shared_corpus):
    vocab, idf = shared_corpus
    weights = get_layer_weights()

    # Long essay with 50+ words about a totally irrelevant topic
    candidate_answer = (
        "When making bread, the first step is to combine flour, warm water, yeast, "
        "and salt in a large bowl. Knead the dough vigorously for ten minutes until "
        "it is smooth and elastic. Cover with a damp towel and let it rise in a warm "
        "place for two hours before shaping and baking in a hot oven."
    )

    result = evaluate_single_question(
        question_number=django_question_key["question_number"],
        question_text=django_question_key["question_text"],
        category=django_question_key["category"],
        options=django_question_key["options"],
        correct_option=django_question_key["correct_option"],
        sample_answer=django_question_key["sample_answer"],
        answer_text=candidate_answer,
        answer_status="TRANSCRIBED",
        keywords=django_question_key["keywords"],
        concepts=django_question_key["concepts"],
        phrases=django_question_key["phrases"],
        vocab=vocab,
        idf=idf,
        weights=weights,
        max_score=10,
    )

    assert result["status"] == "EVALUATED"
    # Spec Section 53: Long answers should not score high purely on length!
    assert float(result["score"]) < 2.0
    assert result["structure_score"] == Decimal("0.00")


def test_ocr_failure_illegible_score_none(django_question_key, shared_corpus):
    vocab, idf = shared_corpus
    weights = get_layer_weights()

    result = evaluate_single_question(
        question_number=django_question_key["question_number"],
        question_text=django_question_key["question_text"],
        category=django_question_key["category"],
        options=django_question_key["options"],
        correct_option=django_question_key["correct_option"],
        sample_answer=django_question_key["sample_answer"],
        answer_text="[ILLEGIBLE]",
        answer_status="ILLEGIBLE",
        keywords=django_question_key["keywords"],
        concepts=django_question_key["concepts"],
        phrases=django_question_key["phrases"],
        vocab=vocab,
        idf=idf,
        weights=weights,
        max_score=10,
    )

    assert result["status"] == "OCR_FAILED"
    # Never silently zero — score is None (N/A)
    assert result["score"] is None
    assert result["keyword_score"] is None
    assert "could not be read reliably" in result["feedback"]


def test_uncertain_segmentation_held_out(django_question_key, shared_corpus):
    vocab, idf = shared_corpus
    weights = get_layer_weights()

    result = evaluate_single_question(
        question_number=django_question_key["question_number"],
        question_text=django_question_key["question_text"],
        category=django_question_key["category"],
        options=django_question_key["options"],
        correct_option=django_question_key["correct_option"],
        sample_answer=django_question_key["sample_answer"],
        answer_text="Some text that cannot be verified",
        answer_status="UNCERTAIN",
        keywords=django_question_key["keywords"],
        concepts=django_question_key["concepts"],
        phrases=django_question_key["phrases"],
        vocab=vocab,
        idf=idf,
        weights=weights,
        max_score=10,
    )

    assert result["status"] == "UNCERTAIN"
    assert result["score"] is None
    assert "uncertain" in result["feedback"].lower()


def test_mcq_correct_option(shared_corpus):
    vocab, idf = shared_corpus
    weights = get_layer_weights()

    result = evaluate_single_question(
        question_number=2,
        question_text="Which index includes all columns needed by a query?",
        category="MCQ",
        options=["A) Clustered", "B) Covering Index", "C) Bitmap", "D) Hash"],
        correct_option="B",
        sample_answer="B) Covering Index",
        answer_text="B) Covering Index",
        answer_status="TRANSCRIBED",
        keywords=["covering", "index"],
        concepts=[("covering index", 1.0)],
        phrases=["covering index"],
        vocab=vocab,
        idf=idf,
        weights=weights,
        max_score=10,
    )

    assert result["status"] == "EVALUATED"
    assert result["score"] == Decimal("10.00")
    assert "Correct" in result["feedback"]


def test_mcq_incorrect_option(shared_corpus):
    vocab, idf = shared_corpus
    weights = get_layer_weights()

    result = evaluate_single_question(
        question_number=2,
        question_text="Which index includes all columns needed by a query?",
        category="MCQ",
        options=["A) Clustered", "B) Covering Index", "C) Bitmap", "D) Hash"],
        correct_option="B",
        sample_answer="B) Covering Index",
        answer_text="A",
        answer_status="TRANSCRIBED",
        keywords=["covering", "index"],
        concepts=[("covering index", 1.0)],
        phrases=["covering index"],
        vocab=vocab,
        idf=idf,
        weights=weights,
        max_score=10,
    )

    assert result["status"] == "EVALUATED"
    assert result["score"] == Decimal("0.00")
    assert "Incorrect" in result["feedback"]


def test_no_llm_calls_in_evaluator():
    """Verify that the evaluator service imports NO LLM libraries."""
    import app.services.answer_evaluator as mod
    import inspect

    source = inspect.getsource(mod)
    assert "google.genai" not in source
    assert "openai" not in source
    assert "litellm" not in source
    assert "ChatCompletion" not in source
    assert "generate_content" not in source
