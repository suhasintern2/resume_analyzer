"""Deterministic answer evaluator — pure scoring layers, zero LLM calls.

Task 10 (Part A):
Multi-layer deterministic evaluation engine:
  Layer 1: Text normalization & canonicalization
  Layer 2: Keyword matching
  Layer 3: Synonym / concept group expansion
  Layer 4: Phrase matching
  Layer 5: TF-IDF cosine similarity against shared reference corpus
  Layer 6: Required concept coverage
  Layer 7: Question-type rules & structure scoring
  Weighted final score (0–10)

Special states:
  BLANK / [BLANK]           -> status NO_ANSWER, score 0
  ILLEGIBLE / [ILLEGIBLE]   -> status OCR_FAILED, score None (N/A)
  SEGMENTATION_UNCERTAIN    -> status UNCERTAIN, score None (held out of totals)

Configurable weights via environment variables:
  KEYWORD_WEIGHT, CONCEPT_WEIGHT, PHRASE_WEIGHT, SIMILARITY_WEIGHT, STRUCTURE_WEIGHT
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    AnswerSegment,
    Evaluation,
    Interview,
    InterviewRound,
    QuestionConceptKey,
    QuestionEvaluation,
    QuestionEvaluationKey,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable weights (normalized to sum to 1.0)
# ---------------------------------------------------------------------------

def get_layer_weights() -> dict[str, float]:
    raw = {
        "keywords": float(getattr(settings, "KEYWORD_WEIGHT", 0.25)),
        "concepts": float(getattr(settings, "CONCEPT_WEIGHT", 0.40)),
        "phrases": float(getattr(settings, "PHRASE_WEIGHT", 0.15)),
        "similarity": float(getattr(settings, "SIMILARITY_WEIGHT", 0.10)),
        "structure": float(getattr(settings, "STRUCTURE_WEIGHT", 0.10)),
    }
    total = sum(raw.values())
    if total > 0:
        return {k: v / total for k, v in raw.items()}
    return {
        "keywords": 0.25,
        "concepts": 0.40,
        "phrases": 0.15,
        "similarity": 0.10,
        "structure": 0.10,
    }


# ---------------------------------------------------------------------------
# Technical synonyms & concept groups (Layer 3)
# ---------------------------------------------------------------------------

TECHNICAL_SYNONYMS: dict[str, list[str]] = {
    "postgres": ["postgresql", "postgres", "pg"],
    "postgresql": ["postgres", "postgresql", "pg"],
    "db": ["database", "datastore", "db"],
    "database": ["db", "database", "datastore"],
    "auth": ["authentication", "auth"],
    "authentication": ["auth", "authentication"],
    "api": ["endpoint", "api"],
    "endpoint": ["api", "endpoint"],
    "k8s": ["kubernetes", "k8s"],
    "kubernetes": ["k8s", "kubernetes"],
    "js": ["javascript", "js"],
    "javascript": ["js", "javascript"],
    "ts": ["typescript", "ts"],
    "typescript": ["ts", "typescript"],
    "py": ["python", "py"],
    "python": ["py", "python"],
    "async": ["asynchronous", "async"],
    "asynchronous": ["async", "asynchronous"],
    "sync": ["synchronous", "sync"],
    "synchronous": ["sync", "synchronous"],
    "param": ["parameter", "argument", "param"],
    "parameter": ["param", "argument", "parameter"],
    "arg": ["argument", "parameter", "arg"],
    "args": ["arguments", "parameters", "args"],
    "repo": ["repository", "repo"],
    "repository": ["repo", "repository"],
    "dir": ["directory", "folder", "dir"],
    "directory": ["dir", "folder", "directory"],
    "cfg": ["config", "configuration", "cfg"],
    "config": ["configuration", "cfg", "config"],
    "configuration": ["config", "cfg", "configuration"],
    "msg": ["message", "msg"],
    "message": ["msg", "message"],
    "func": ["function", "method", "func"],
    "function": ["func", "method", "function"],
    "sql": ["structured query language"],
}

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
    "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with",
    "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've",
    "your", "yours", "yourself", "yourselves",
}

_TOKEN_RE = re.compile(r"\b[a-z0-9_+#.-]{2,}\b")
_PUNCT_RE = re.compile(r"[^\w\s]")


def _normalize_text(text: str) -> str:
    """Normalize text: lowercase, strip extra whitespace, normalize hyphens."""
    if not text:
        return ""
    text = text.lower()
    text = text.replace("-", " ").replace("/", " ")
    text = _PUNCT_RE.sub(" ", text)
    return " ".join(text.split())


def _tokenize(text: str, filter_stopwords: bool = False) -> list[str]:
    """Tokenize normalized text into words."""
    norm = _normalize_text(text)
    tokens = _TOKEN_RE.findall(norm)
    if filter_stopwords:
        return [t for t in tokens if t not in STOPWORDS]
    return tokens


def _unique_tokens(text: str, filter_stopwords: bool = False) -> set[str]:
    return set(_tokenize(text, filter_stopwords=filter_stopwords))


def _stem(token: str) -> str:
    """Lightweight English suffix trimmer for plural/verb forms."""
    t = token.lower()
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    if t.endswith("es") and len(t) > 4:
        return t[:-2]
    if t.endswith("s") and not t.endswith("ss") and len(t) > 3:
        return t[:-1]
    if t.endswith("ing") and len(t) > 5:
        return t[:-3]
    if t.endswith("ed") and len(t) > 4:
        return t[:-2]
    return t


def _expand_tokens(tokens: set[str]) -> set[str]:
    """Expand token set with technical synonyms/abbreviations."""
    expanded = set(tokens)
    for tok in tokens:
        syns = TECHNICAL_SYNONYMS.get(tok)
        if syns:
            for s in syns:
                for sub in _tokenize(s):
                    expanded.add(sub)
    return expanded


# ---------------------------------------------------------------------------
# Layer Scorers
# ---------------------------------------------------------------------------

def score_keywords(answer_text: str, keywords: list[str]) -> float:
    """Layer 2: Keyword coverage. Returns 0.0 to 1.0."""
    if not keywords:
        return 1.0
    ans_tokens = _expand_tokens(_unique_tokens(answer_text))
    stemmed_ans_tokens = {_stem(t) for t in ans_tokens}
    ans_norm = _normalize_text(answer_text)

    matched = 0
    for kw in keywords:
        kw_norm = _normalize_text(kw)
        if not kw_norm:
            matched += 1
            continue
        # Direct phrase in answer
        if kw_norm in ans_norm:
            matched += 1
            continue
        # Check synonyms
        syns = TECHNICAL_SYNONYMS.get(kw.lower(), [])
        if any(_normalize_text(s) in ans_norm for s in syns):
            matched += 1
            continue
        # Check stemmed tokens
        kw_tokens = set(_tokenize(kw))
        stemmed_kw = {_stem(t) for t in kw_tokens}
        if stemmed_kw and stemmed_kw.issubset(stemmed_ans_tokens):
            matched += 1
            continue
        # Check if single token matches any stemmed answer token
        if len(kw_tokens) == 1 and _stem(list(kw_tokens)[0]) in stemmed_ans_tokens:
            matched += 1
            continue
    return matched / len(keywords)


def score_concepts(answer_text: str, concepts: list[tuple[str, float]]) -> float:
    """Layer 6 & Layer 3: Required concept coverage with synonym expansion.
    Returns 0.0 to 1.0."""
    if not concepts:
        return 1.0
    ans_tokens = _expand_tokens(_unique_tokens(answer_text))
    stemmed_ans_tokens = {_stem(t) for t in ans_tokens}
    ans_norm = _normalize_text(answer_text)

    total_weight = sum(w for _, w in concepts) or 1.0
    earned = 0.0

    for name, weight in concepts:
        norm_name = _normalize_text(name)
        if norm_name in ans_norm:
            earned += weight
            continue

        # Check concept synonyms
        syns = TECHNICAL_SYNONYMS.get(name.lower(), [])
        if any(_normalize_text(s) in ans_norm for s in syns):
            earned += weight
            continue

        c_tokens = set(_tokenize(name))
        if not c_tokens:
            earned += weight
            continue

        # Stemmed overlap
        stemmed_c = {_stem(t) for t in c_tokens}
        overlap = len(stemmed_c & stemmed_ans_tokens) / len(stemmed_c)
        if overlap >= 0.5:
            coverage = min(1.0, overlap / 0.6)
        elif overlap >= 0.3:
            coverage = overlap * 0.8
        else:
            coverage = 0.0
        earned += weight * coverage

    return min(1.0, earned / total_weight)


def score_phrases(answer_text: str, phrases: list[str]) -> float:
    """Layer 4: Important phrase matching. Returns 0.0 to 1.0."""
    if not phrases:
        return 1.0
    ans_norm = _normalize_text(answer_text)
    ans_tokens = _expand_tokens(_unique_tokens(answer_text))
    stemmed_ans_tokens = {_stem(t) for t in ans_tokens}

    matched = 0
    for phrase in phrases:
        p_norm = _normalize_text(phrase)
        if not p_norm:
            matched += 1
            continue
        if p_norm in ans_norm:
            matched += 1
            continue
        # Check synonyms (only multi-word equivalents, not single-token acronyms)
        syns = [s for s in TECHNICAL_SYNONYMS.get(phrase.lower(), []) if len(_tokenize(s)) >= 2]
        if any(_normalize_text(s) in ans_norm for s in syns):
            matched += 1
            continue
        # Allow partial token overlap for long phrases (>= 3 words)
        p_tokens = set(_tokenize(phrase))
        stemmed_p = {_stem(t) for t in p_tokens}
        if len(p_tokens) >= 2 and len(stemmed_p & stemmed_ans_tokens) / len(stemmed_p) >= 0.65:
            matched += 0.8
        elif stemmed_p and stemmed_p.issubset(stemmed_ans_tokens):
            matched += 1.0

    return min(1.0, matched / len(phrases))


# ---------------------------------------------------------------------------
# Layer 5: TF-IDF Cosine Similarity against shared reference corpus
# ---------------------------------------------------------------------------

def build_tfidf_corpus(documents: list[list[str]]) -> tuple[dict[str, int], dict[str, float]]:
    """Build shared vocabulary and inverse document frequency across corpus."""
    df: dict[str, int] = {}
    for doc in documents:
        # Filter stopwords
        filtered_doc = [t for t in doc if t.lower() not in STOPWORDS]
        for tok in set(filtered_doc):
            df[tok] = df.get(tok, 0) + 1
    n = max(len(documents), 1)
    vocab = {tok: idx for idx, tok in enumerate(sorted(df))}
    idf = {tok: math.log((n + 1) / (cnt + 1)) + 1.0 for tok, cnt in df.items()}
    return vocab, idf


def tfidf_vectorize(
    tokens: list[str], vocabulary: dict[str, int], idf: dict[str, float]
) -> dict[int, float]:
    """Compute TF-IDF sparse vector for a document."""
    if not tokens:
        return {}
    tf = Counter(tokens)
    vec: dict[int, float] = {}
    doc_len = len(tokens)
    for tok, count in tf.items():
        if tok in vocabulary:
            idx = vocabulary[tok]
            vec[idx] = (count / doc_len) * idf.get(tok, 1.0)
    return vec


def cosine_similarity(a: dict[int, float], b: dict[int, float]) -> float:
    """Compute cosine similarity between two sparse vectors."""
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[k] * b[k] for k in common)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return min(1.0, dot / (mag_a * mag_b))


def score_similarity(
    answer_text: str,
    sample_answer: str,
    vocab: dict[str, int],
    idf: dict[str, float],
) -> float:
    """Layer 5: Cosine similarity between candidate answer and sample answer."""
    ans_tokens = _tokenize(answer_text, filter_stopwords=True)
    sample_tokens = _tokenize(sample_answer, filter_stopwords=True)
    if not ans_tokens or not sample_tokens:
        return 0.0
    ans_vec = tfidf_vectorize(ans_tokens, vocab, idf)
    sample_vec = tfidf_vectorize(sample_tokens, vocab, idf)
    return cosine_similarity(ans_vec, sample_vec)


# ---------------------------------------------------------------------------
# Layer 7: Question-Type Rules & Structure Score
# ---------------------------------------------------------------------------

_BEHAVIORAL_MARKERS = {
    "situation", "task", "action", "result", "when", "team", "project",
    "challenge", "resolved", "improved", "implemented", "handled", "outcome",
}


def score_structure(
    answer_text: str,
    category: str,
    relevance_score: float,
) -> float:
    """Evaluate structural adequacy for the question type.

    CRITICAL per Spec 2 & Task 10:
    Do NOT let long irrelevant answers score higher purely on length.
    If the answer has near-zero relevance (keywords/concepts/similarity = 0),
    structure score is zero.
    """
    if relevance_score <= 0.05:
        return 0.0

    tokens = _tokenize(answer_text)
    token_count = len(tokens)
    if token_count < 5:
        base = token_count / 10.0
    elif token_count < 20:
        base = 0.5 + (token_count - 5) / 30.0
    else:
        base = 1.0

    cat_lower = (category or "").lower()
    if "behavioral" in cat_lower or "hr" in cat_lower:
        # Check for STAR or situational markers
        ans_tokens_set = set(tokens)
        star_matches = len(ans_tokens_set & _BEHAVIORAL_MARKERS)
        bonus = min(0.3, star_matches * 0.1)
        base = min(1.0, base + bonus)

    # Scale structure score by candidate relevance so length cannot fake substance
    relevance_multiplier = min(1.0, relevance_score * 2.0)
    return min(1.0, base * relevance_multiplier)


# ---------------------------------------------------------------------------
# MCQ Matching Helper
# ---------------------------------------------------------------------------

def _is_mcq(category: str, options: list[str] | None, correct_option: str | None) -> bool:
    if correct_option:
        return True
    cat = (category or "").lower()
    return "mcq" in cat or (bool(options) and len(options) >= 2)


def _check_mcq_answer(answer_text: str, correct_option: str | None, options: list[str] | None) -> bool:
    if not correct_option:
        return False
    ans_clean = answer_text.strip().upper()
    corr_clean = correct_option.strip().upper()

    # Exact match: "A", "B", "C", etc.
    if ans_clean == corr_clean:
        return True

    # Starts with letter: e.g. "B) ...", "B.", "OPTION B"
    if ans_clean.startswith(corr_clean) and len(ans_clean) <= 4:
        return True
    if f"OPTION {corr_clean}" in ans_clean or f"({corr_clean})" in ans_clean:
        return True

    # Matching option text if option text exists
    if options:
        for opt in options:
            if opt.strip().upper().startswith(corr_clean):
                opt_body = opt.split(")", 1)[-1].strip() if ")" in opt else opt
                if opt_body and _normalize_text(opt_body) in _normalize_text(answer_text):
                    return True
    return False


# ---------------------------------------------------------------------------
# Deterministic Feedback Generation (evidence thresholds, no LLM)
# ---------------------------------------------------------------------------

def generate_deterministic_feedback(
    status: str,
    score: Decimal | None,
    max_score: Decimal,
    category: str,
    is_mcq_question: bool = False,
    correct_option: str | None = None,
    is_correct: bool = False,
    keyword_score: float = 0.0,
    concept_score: float = 0.0,
) -> str:
    """Generate simple, deterministic feedback based purely on evidence thresholds.
    Zero LLM involvement."""
    if status == "NO_ANSWER":
        return "No answer was provided."
    if status == "OCR_FAILED":
        return "Unable to evaluate because the answer could not be read reliably."
    if status == "UNCERTAIN":
        return "Unable to evaluate because question alignment is uncertain."

    if is_mcq_question:
        if is_correct:
            return f"Correct — selected expected option {correct_option}."
        return f"Incorrect — expected option {correct_option}."

    if score is None:
        return "Unable to evaluate this answer."

    pct = float((score / max_score) * 100) if max_score > 0 else 0.0

    if pct >= 80:
        return "Excellent coverage of the expected concepts."
    if pct >= 60:
        return "Good answer with most key concepts covered."
    if pct >= 40:
        return "Partial coverage. Some important concepts are missing."
    if pct >= 20:
        return "Limited answer. Several expected concepts were not detected."
    return "Answer does not address the required concepts."


# ---------------------------------------------------------------------------
# Question Evaluator
# ---------------------------------------------------------------------------

def evaluate_single_question(
    *,
    question_number: int,
    question_text: str,
    category: str,
    options: list[str] | None,
    correct_option: str | None,
    sample_answer: str,
    answer_text: str,
    answer_status: str,
    keywords: list[str],
    concepts: list[tuple[str, float]],
    phrases: list[str],
    vocab: dict[str, int],
    idf: dict[str, float],
    weights: dict[str, float],
    max_score: int = 10,
) -> dict[str, Any]:
    """Evaluate one candidate question answer deterministically."""

    def _dec(val: float | None) -> Decimal | None:
        if val is None:
            return None
        return Decimal(str(round(val, 2)))

    # Handle special states from Task 9 explicitly
    clean_text = (answer_text or "").strip()
    status_upper = (answer_status or "").upper()

    if status_upper == "BLANK" or clean_text == "[BLANK]" or not clean_text:
        return {
            "question_number": question_number,
            "score": Decimal("0.00"),
            "max_score": Decimal(str(max_score)),
            "keyword_score": Decimal("0.00"),
            "concept_score": Decimal("0.00"),
            "phrase_score": Decimal("0.00"),
            "similarity_score": Decimal("0.00"),
            "structure_score": Decimal("0.00"),
            "status": "NO_ANSWER",
            "feedback": generate_deterministic_feedback("NO_ANSWER", Decimal("0"), Decimal(str(max_score)), category),
        }

    if status_upper == "ILLEGIBLE" or clean_text == "[ILLEGIBLE]":
        return {
            "question_number": question_number,
            "score": None,
            "max_score": Decimal(str(max_score)),
            "keyword_score": None,
            "concept_score": None,
            "phrase_score": None,
            "similarity_score": None,
            "structure_score": None,
            "status": "OCR_FAILED",
            "feedback": generate_deterministic_feedback("OCR_FAILED", None, Decimal(str(max_score)), category),
        }

    if status_upper in ("UNCERTAIN", "SEGMENTATION_UNCERTAIN"):
        return {
            "question_number": question_number,
            "score": None,
            "max_score": Decimal(str(max_score)),
            "keyword_score": None,
            "concept_score": None,
            "phrase_score": None,
            "similarity_score": None,
            "structure_score": None,
            "status": "UNCERTAIN",
            "feedback": generate_deterministic_feedback("UNCERTAIN", None, Decimal(str(max_score)), category),
        }

    # Task 12 — OMR detected more than one marked checkbox for this MCQ. The
    # content is "MULTIPLE_A_C". Held out of scoring (like OCR_FAILED): never
    # silently picked.
    if status_upper == "AMBIGUOUS_MARK":
        return {
            "question_number": question_number,
            "score": None,
            "max_score": Decimal(str(max_score)),
            "keyword_score": None,
            "concept_score": None,
            "phrase_score": None,
            "similarity_score": None,
            "structure_score": None,
            "status": "UNCERTAIN",
            "feedback": "Multiple options were marked for this question — held out for review.",
        }

    # Check if MCQ question
    is_mcq = _is_mcq(category, options, correct_option)
    if is_mcq and correct_option:
        is_corr = _check_mcq_answer(clean_text, correct_option, options)
        score_val = Decimal(str(max_score)) if is_corr else Decimal("0.00")
        layer_val = Decimal("1.00") if is_corr else Decimal("0.00")
        return {
            "question_number": question_number,
            "score": score_val,
            "max_score": Decimal(str(max_score)),
            "keyword_score": layer_val,
            "concept_score": layer_val,
            "phrase_score": layer_val,
            "similarity_score": layer_val,
            "structure_score": layer_val,
            "status": "EVALUATED",
            "feedback": generate_deterministic_feedback(
                "EVALUATED",
                score_val,
                Decimal(str(max_score)),
                category,
                is_mcq_question=True,
                correct_option=correct_option,
                is_correct=is_corr,
            ),
        }

    # Open-ended question scoring
    kw_score = score_keywords(clean_text, keywords)
    conc_score = score_concepts(clean_text, concepts)
    phrase_score = score_phrases(clean_text, phrases)
    sim_score = score_similarity(clean_text, sample_answer, vocab, idf)

    # Core relevance before structure.
    # If no keywords AND no concepts matched, the answer is irrelevant to the question topic.
    if kw_score <= 0.0 and conc_score <= 0.0:
        relevance = 0.0
    else:
        relevance = max(kw_score, conc_score, sim_score)
    struct_score = score_structure(clean_text, category, relevance)

    weighted = (
        weights["keywords"] * kw_score
        + weights["concepts"] * conc_score
        + weights["phrases"] * phrase_score
        + weights["similarity"] * sim_score
        + weights["structure"] * struct_score
    )

    final_score = round(weighted * max_score, 2)
    score_dec = Decimal(str(final_score))
    max_dec = Decimal(str(max_score))

    feedback = generate_deterministic_feedback(
        "EVALUATED",
        score_dec,
        max_dec,
        category,
        keyword_score=kw_score,
        concept_score=conc_score,
    )

    return {
        "question_number": question_number,
        "score": score_dec,
        "max_score": max_dec,
        "keyword_score": _dec(kw_score),
        "concept_score": _dec(conc_score),
        "phrase_score": _dec(phrase_score),
        "similarity_score": _dec(sim_score),
        "structure_score": _dec(struct_score),
        "status": "EVALUATED",
        "feedback": feedback,
    }


# ---------------------------------------------------------------------------
# AnswerEvaluationService
# ---------------------------------------------------------------------------

@dataclass
class QuestionKeyData:
    question_number: int
    question_text: str = ""
    sample_answer: str = ""
    category: str = "Technical"
    correct_option: str | None = None
    options: list[str] | None = None
    keywords: list[str] = field(default_factory=list)
    concepts: list[tuple[str, float]] = field(default_factory=list)
    phrases: list[str] = field(default_factory=list)


class AnswerEvaluationService:
    """Service orchestrating deterministic evaluation of interviews."""

    @classmethod
    def load_evaluation_keys(
        cls,
        session: Session,
        interview_pk: int,
        round_id: int | None = None,
    ) -> dict[int, QuestionKeyData]:
        """Load evaluation keys and concepts for an interview round.

        ``round_id=None`` matches legacy pre-round keys (round_id NULL).
        """
        query = select(QuestionEvaluationKey).where(
            QuestionEvaluationKey.interview_id == interview_pk,
        )
        if round_id is not None:
            query = query.where(QuestionEvaluationKey.round_id == round_id)
        else:
            query = query.where(QuestionEvaluationKey.round_id.is_(None))
        rows = list(
            session.scalars(query.order_by(QuestionEvaluationKey.question_number)).all()
        )
        keys: dict[int, QuestionKeyData] = {}
        for row in rows:
            concepts = list(
                session.scalars(
                    select(QuestionConceptKey)
                    .where(QuestionConceptKey.question_key_id == row.id)
                ).all()
            )
            keys[row.question_number] = QuestionKeyData(
                question_number=row.question_number,
                question_text=row.question_text or "",
                sample_answer=row.sample_answer or "",
                category=row.category or "Technical",
                correct_option=row.correct_option,
                options=list(row.options) if row.options else None,
                keywords=list(row.keywords or []),
                concepts=[(c.name, float(c.weight)) for c in concepts],
                phrases=list(row.important_phrases or []),
            )
        return keys

    @classmethod
    def evaluate_interview(
        cls,
        session: Session,
        interview: Interview,
        segments: list[AnswerSegment] | None = None,
        override_keys: dict[int, QuestionKeyData] | None = None,
        round_id: int | None = None,
    ) -> dict[str, Any]:
        """Evaluate an interview round deterministically across all questions."""
        if segments is None:
            query = select(AnswerSegment).where(
                AnswerSegment.interview_id == interview.id,
            )
            if round_id is not None:
                query = query.where(AnswerSegment.round_id == round_id)
            else:
                query = query.where(AnswerSegment.round_id.is_(None))
            segments = list(
                session.scalars(
                    query.order_by(
                        AnswerSegment.question_number.nulls_last(), AnswerSegment.id,
                    )
                ).all()
            )

        eval_keys = override_keys or cls.load_evaluation_keys(
            session, interview.id, round_id=round_id,
        )
        weights = get_layer_weights()

        # Build reference corpus from all sample answers + concept/phrase text
        corpus_docs: list[list[str]] = []
        for key in eval_keys.values():
            if key.sample_answer:
                corpus_docs.append(_tokenize(key.sample_answer))
            for cname, _ in key.concepts:
                corpus_docs.append(_tokenize(cname))
            for p in key.phrases:
                corpus_docs.append(_tokenize(p))

        if not corpus_docs:
            corpus_docs = [["empty", "corpus"]]

        vocab, idf = build_tfidf_corpus(corpus_docs)

        # Map segments by question_number
        seg_map: dict[int, AnswerSegment] = {}
        for seg in segments:
            if seg.question_number is not None and seg.question_number not in seg_map:
                seg_map[seg.question_number] = seg

        is_interview_uncertain = interview.status == "SEGMENTATION_UNCERTAIN"

        question_results: list[dict[str, Any]] = []
        total_scorable = Decimal("0.00")
        max_scorable = Decimal("0.00")

        # Evaluate every question in the evaluation keys (sorted by question_number)
        q_numbers = sorted(eval_keys.keys()) if eval_keys else []
        if not q_numbers and segments:
            # Fallback if keys are not stored by number
            q_numbers = sorted({s.question_number for s in segments if s.question_number})

        for q_num in q_numbers:
            key = eval_keys.get(q_num, QuestionKeyData(question_number=q_num))
            seg = seg_map.get(q_num)

            if is_interview_uncertain:
                # Held out until manually resolved
                res = {
                    "question_number": q_num,
                    "score": None,
                    "max_score": Decimal("10.00"),
                    "keyword_score": None,
                    "concept_score": None,
                    "phrase_score": None,
                    "similarity_score": None,
                    "structure_score": None,
                    "status": "UNCERTAIN",
                    "feedback": "Answer alignment uncertain — pending manual review.",
                }
            elif seg is None:
                res = {
                    "question_number": q_num,
                    "score": Decimal("0.00"),
                    "max_score": Decimal("10.00"),
                    "keyword_score": Decimal("0.00"),
                    "concept_score": Decimal("0.00"),
                    "phrase_score": Decimal("0.00"),
                    "similarity_score": Decimal("0.00"),
                    "structure_score": Decimal("0.00"),
                    "status": "NO_ANSWER",
                    "feedback": "No answer was provided.",
                }
            else:
                res = evaluate_single_question(
                    question_number=q_num,
                    question_text=key.question_text,
                    category=key.category,
                    options=key.options,
                    correct_option=key.correct_option,
                    sample_answer=key.sample_answer,
                    answer_text=seg.content or "",
                    answer_status=str(seg.status),
                    keywords=key.keywords,
                    concepts=key.concepts,
                    phrases=key.phrases,
                    vocab=vocab,
                    idf=idf,
                    weights=weights,
                    max_score=10,
                )

            question_results.append(res)

            # Accumulate scores for evaluated/no-answer questions only
            if res["status"] in ("EVALUATED", "NO_ANSWER") and res["score"] is not None:
                total_scorable += res["score"]
                max_scorable += res["max_score"]

        percentage: Decimal | None = None
        if max_scorable > Decimal("0.00"):
            percentage = Decimal(str(round(float(total_scorable / max_scorable) * 100, 1)))

        return {
            "interview_id": interview.interview_id,
            "total_score": total_scorable,
            "max_score": max_scorable,
            "percentage": percentage,
            "evaluator_version": getattr(settings, "EVALUATOR_VERSION", "v1.0.0-deterministic"),
            "question_results": question_results,
        }

    @classmethod
    def persist_evaluation(
        cls,
        session: Session,
        interview: Interview,
        eval_data: dict[str, Any],
        round_id: int | None = None,
    ) -> Evaluation:
        """Persist evaluation results into the database in a single transaction.

        Round-scoped (Task 12): the evaluation is pinned per
        (interview, round), so round-1 and round-2 results coexist.  Legacy
        rows use ``round_id=None``.

        Guarantees:
        - Exactly one evaluation has is_current = true per interview round
        - Previous evaluations are set is_current = false, preserving history
        - Original deterministic scores are recorded on question_evaluations
        - Updates interview.status to EVALUATED
        """
        # 1. Flip previous evaluations for this (interview, round) to false.
        query = select(Evaluation).where(
            Evaluation.interview_id == interview.id,
            Evaluation.is_current.is_(True),
        )
        if round_id is not None:
            query = query.where(Evaluation.round_id == round_id)
        else:
            query = query.where(Evaluation.round_id.is_(None))
        prev_evals = list(session.scalars(query).all())
        for prev in prev_evals:
            prev.is_current = False
        session.flush()

        # 2. Insert new current Evaluation row (round-scoped).
        new_eval = Evaluation(
            interview_id=interview.id,
            round_id=round_id,
            evaluator_version=eval_data.get("evaluator_version", "v1.0.0-deterministic"),
            total_score=eval_data.get("total_score"),
            max_score=eval_data.get("max_score"),
            percentage=eval_data.get("percentage"),
            status="EVALUATED",
            is_current=True,
        )
        session.add(new_eval)
        session.flush()

        # 3. Insert QuestionEvaluation rows
        for q_res in eval_data.get("question_results", []):
            q_eval = QuestionEvaluation(
                evaluation_id=new_eval.id,
                question_number=q_res["question_number"],
                score=q_res["score"],
                original_score=q_res["score"],
                max_score=q_res["max_score"],
                keyword_score=q_res["keyword_score"],
                concept_score=q_res["concept_score"],
                phrase_score=q_res["phrase_score"],
                similarity_score=q_res["similarity_score"],
                structure_score=q_res["structure_score"],
                status=q_res["status"],
                feedback=q_res["feedback"],
            )
            session.add(q_eval)

        # 4. Update interview + round state
        interview.status = "EVALUATED"
        interview.processing_stage = None
        interview.error_reason = None
        if round_id is not None:
            round_obj = session.get(InterviewRound, round_id)
            if round_obj is not None:
                round_obj.status = "EVALUATED"
        session.commit()

        logger.info(
            "Evaluation completed for interview %s round=%s (score=%s/%s)",
            interview.interview_id, round_id,
            new_eval.total_score,
            new_eval.max_score,
        )
        return new_eval
