from pydantic import BaseModel


class QuestionAnswer(BaseModel):
    number: int
    category: str
    question: str
    answer: str


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
