import logging
from app.services.llm_service import get_llm_provider
from app.models.schemas import InterviewResult

logger = logging.getLogger(__name__)


def generate_interview_questions(resume_text: str) -> InterviewResult:
    provider = get_llm_provider()

    logger.info("Sending resume to LLM...")

    result = provider.generate_with_retry(resume_text)

    logger.info(f"LLM returned {len(result.questions)} questions")

    return result
