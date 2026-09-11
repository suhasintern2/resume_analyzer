import json
import logging
import httpx
from app.prompts.interview_prompt import SYSTEM_PROMPT, build_user_prompt, RETRY_PROMPT_SUFFIX
from app.models.schemas import InterviewResult
from app.config import settings

logger = logging.getLogger(__name__)


class LLMProvider:
    def generate_interview_qa(self, resume_text: str) -> InterviewResult:
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.base_url = "https://api.openai.com/v1"

    def _call_api(self, messages: list[dict], timeout: float = 60.0) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
        }

        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def generate_interview_qa(self, resume_text: str) -> InterviewResult:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(resume_text)},
        ]

        response_text = self._call_api(messages, timeout=settings.LLM_TIMEOUT)

        return self._parse_response(response_text)

    def _parse_response(self, response_text: str) -> InterviewResult:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        data = json.loads(cleaned)
        return InterviewResult(**data)

    def generate_with_retry(self, resume_text: str) -> InterviewResult:
        try:
            return self.generate_interview_qa(resume_text)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"First LLM attempt failed: {e}, retrying...")

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT + RETRY_PROMPT_SUFFIX},
                {"role": "user", "content": build_user_prompt(resume_text)},
            ]

            response_text = self._call_api(messages, timeout=settings.LLM_TIMEOUT)
            return self._parse_response(response_text)


class GeminiProvider(LLMProvider):
    def __init__(self):
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.fallback_models = settings.LLM_FALLBACK_MODELS
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _build_payload(self, user_content: str, system_instruction: str = None) -> dict:
        payload = {
            "contents": [{"parts": [{"text": user_content}]}],
            "generationConfig": {
                "temperature": 0.7,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        return payload

    def _call_api(self, payload: dict, model: str) -> str:
        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
        with httpx.Client(timeout=settings.LLM_TIMEOUT) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            parts = data["candidates"][0]["content"]["parts"]
            return next(p["text"] for p in parts if "text" in p)

    def _parse_response(self, response_text: str) -> InterviewResult:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        data = json.loads(cleaned)
        return InterviewResult(**data)

    def generate_interview_qa(self, resume_text: str) -> InterviewResult:
        return self._try_models(resume_text)

    def _try_models(self, resume_text: str) -> InterviewResult:
        models = [self.model] + [m for m in self.fallback_models if m != self.model]
        errors = []

        for model in models:
            try:
                payload = self._build_payload(
                    user_content=build_user_prompt(resume_text),
                    system_instruction=SYSTEM_PROMPT,
                )
                response_text = self._call_api(payload, model)
                return self._parse_response(response_text)
            except (json.JSONDecodeError, httpx.HTTPError, KeyError, ValueError) as e:
                errors.append(f"{model}: {e}")
                logger.warning(f"Model {model} failed: {e}, trying next model...")

                if model != models[-1]:
                    try:
                        payload = self._build_payload(
                            user_content=build_user_prompt(resume_text),
                            system_instruction=SYSTEM_PROMPT + RETRY_PROMPT_SUFFIX,
                        )
                        response_text = self._call_api(payload, model)
                        return self._parse_response(response_text)
                    except Exception as retry_e:
                        errors.append(f"{model} (retry): {retry_e}")
                        logger.warning(f"Retry on {model} failed: {retry_e}")

        raise RuntimeError(f"All LLM models failed: {'; '.join(errors)}")

    def generate_with_retry(self, resume_text: str) -> InterviewResult:
        return self._try_models(resume_text)


def get_llm_provider() -> LLMProvider:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "openai":
        return OpenAIProvider()
    elif provider == "gemini":
        return GeminiProvider()
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
