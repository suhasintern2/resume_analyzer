import logging
from app.services.llm_service import get_llm_provider
from app.models.schemas import InterviewResult

logger = logging.getLogger(__name__)


def generate_interview_questions(resume_text: str, round_number: int = 1) -> InterviewResult:
    provider = get_llm_provider()

    logger.info("Sending resume to LLM (round %d)...", round_number)

    result = provider.generate_with_retry(resume_text, round_number=round_number)

    logger.info(f"LLM returned {len(result.questions)} questions for round {round_number}")

    return result
