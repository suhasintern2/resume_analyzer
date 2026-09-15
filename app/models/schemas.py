from datetime import datetime

from pydantic import BaseModel, field_validator


class Concept(BaseModel):
    """A concept that a strong answer must cover, with relative weight."""

    name: str
    weight: float


class QuestionAnswer(BaseModel):
    number: int
    category: str
    question: str
    options: list[str] | None = None
    correct_option: str | None = None
    answer: str
    hr_answer: str | None = None

    # Task 5 — deterministic evaluation key (per amendment §9)
    keywords: list[str]
    required_concepts: list[Concept]
    important_phrases: list[str]

    @field_validator("required_concepts")
    @classmethod
    def normalize_concept_weights(cls, concepts: list[Concept]) -> list[Concept]:
        """Normalize weights server-side (amendment §9).

        LLMs are unreliable at exact arithmetic, so a non-1.0 sum is NOT a
        validation error. Each weight is divided by the total. We only raise
        (triggering the provider's retry-once path) when weights are missing,
        non-numeric, or the concepts list is empty — i.e. when normalization
        itself cannot work.
        """
        if not concepts:
            raise ValueError("required_concepts must contain at least one concept")
        total = sum(c.weight for c in concepts)
        if total <= 0:
            raise ValueError(
                "concept weights must be positive numbers summing to more than zero"
            )
        return [
            c.model_copy(update={"weight": c.weight / total}) for c in concepts
        ]


class InterviewResult(BaseModel):
    candidate_name: str
    summary: str
    questions: list[QuestionAnswer]


class GenerateResponse(BaseModel):
    success: bool
    result: InterviewResult | None = None
    error: str | None = None
    interview_id: str | None = None  # set when the interview was persisted to DB


class ErrorResponse(BaseModel):
    success: bool = False
    error: str


class InterviewCreateResponse(BaseModel):
    success: bool
    interview_id: str
    status: str


class InterviewRenameRequest(BaseModel):
    """Update the dashboard label for an interview (display-only)."""

    display_name: str | None = None


class InterviewDetail(BaseModel):
    id: int
    interview_id: str
    candidate_name: str | None = None
    email: str | None = None
    phone: str | None = None
    original_filename: str | None = None
    display_name: str | None = None
    status: str
    processing_stage: str | None = None
    error_reason: str | None = None
    created_at: datetime
    rounds: list[InterviewRoundSummary] = []


class AnswerScriptUploadResponse(BaseModel):
    success: bool
    interview_id: str
    status: str
    files_uploaded: int


class SegmentReassignRequest(BaseModel):
    question_number: int


class AnswerSegmentOut(BaseModel):
    id: int
    question_number: int | None = None
    original_question_number: int | None = None
    content: str
    status: str
    is_manual_override: bool
    created_at: datetime
    updated_at: datetime


class ScoreOverrideRequest(BaseModel):
    override_score: float
    override_reason: str


class QuestionEvaluationOut(BaseModel):
    id: int
    question_number: int
    score: float | None = None
    original_score: float | None = None
    override_score: float | None = None
    override_reason: str | None = None
    overridden_by: str | None = None
    overridden_at: datetime | None = None
    is_overridden: bool = False
    max_score: float | None = None
    keyword_score: float | None = None
    concept_score: float | None = None
    phrase_score: float | None = None
    similarity_score: float | None = None
    structure_score: float | None = None
    status: str
    feedback: str | None = None


class EvaluationDetailOut(BaseModel):
    interview_id: str
    evaluation_id: int
    evaluator_version: str
    total_score: float | None = None
    max_score: float | None = None
    percentage: float | None = None
    status: str
    is_current: bool = True
    created_at: datetime
    questions: list[QuestionEvaluationOut]


class InterviewRoundSummary(BaseModel):
    round_number: int
    status: str
    selected_for_next_round: bool | None = None
    # Task 12 — per-round score surfaced so the dashboard can sort/list by
    # Round 1 score independently of round 2.
    score: float | None = None
    max_score: float | None = None
    percentage: float | None = None


class InterviewListItem(BaseModel):
    id: int
    interview_id: str
    candidate_name: str | None = None
    email: str | None = None
    phone: str | None = None
    original_filename: str | None = None
    display_name: str | None = None
    status: str
    processing_stage: str | None = None
    error_reason: str | None = None
    score: float | None = None
    max_score: float | None = None
    percentage: float | None = None
    created_at: datetime
    updated_at: datetime
    rounds: list[InterviewRoundSummary] = []


class InterviewListResponse(BaseModel):
    interviews: list[InterviewListItem]


class EvaluationStartResponse(BaseModel):
    success: bool
    interview_id: str
    status: str

