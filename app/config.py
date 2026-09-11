import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_ENV: str = os.getenv("APP_ENV", "development")

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-3.5-flash")
    LLM_FALLBACK_MODELS: list[str] = [
        m.strip()
        for m in os.getenv(
            "LLM_FALLBACK_MODELS",
            "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3.6-flash",
        ).split(",")
        if m.strip()
    ]

    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    MAX_RESUME_CHARACTERS: int = int(os.getenv("MAX_RESUME_CHARACTERS", "50000"))

    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

    MIN_RESUME_TEXT_LENGTH: int = int(os.getenv("MIN_RESUME_TEXT_LENGTH", "200"))


settings = Settings()
