from pydantic import BaseModel


class QuestionAnswer(BaseModel):
    number: int
    category: str
    question: str
    options: list[str] | None = None
    correct_option: str | None = None
    answer: str
    hr_answer: str | None = None


class InterviewResult(BaseModel):
    candidate_name: str
    summary: str
    questions: list[QuestionAnswer]


class GenerateResponse(BaseModel):
    success: bool
    result: InterviewResult | None = None
    error: str | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
