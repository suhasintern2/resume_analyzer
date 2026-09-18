import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_ENV: str = os.getenv("APP_ENV", "development")

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://resume:resume@localhost:5432/resume",
    )
    DB_ECHO: bool = os.getenv("DB_ECHO", "false").lower() == "true"
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-3.5-flash")
    LLM_FALLBACK_MODELS: list[str] = [
        m.strip()
        for m in os.getenv(
            "LLM_FALLBACK_MODELS",
            "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3.6-flash",
        ).split(",")
        if m.strip()
    ]

    # Persistent storage root for "record" files (§6 of the amendment) —
    # never auto-deleted by request-cleanup logic.
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")

    # Record-file retention window (amendment §6 / Task 6). The scheduled
    # retention job purges record files + their `files` rows only for
    # interviews whose evaluation completed longer ago than RETENTION_DAYS.
    RETENTION_DAYS: int = int(os.getenv("RETENTION_DAYS", "30"))

    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    MAX_RESUME_CHARACTERS: int = int(os.getenv("MAX_RESUME_CHARACTERS", "50000"))

    # Task 9 — handwritten answer scripts (scanned pages) may be larger than
    # a typed resume; validated separately from the resume upload.
    ANSWER_SCRIPT_MAX_FILE_SIZE_MB: int = int(
        os.getenv("ANSWER_SCRIPT_MAX_FILE_SIZE_MB", "10")
    )

    # Task 12 — fully AI-free answer-script pipeline (OMR + TrOCR).
    # TrOCR model for handwriting recognition (Microsoft, via Hugging Face transformers).
    # Model choices: "microsoft/trocr-base-handwritten" (faster) or
    #                "microsoft/trocr-large-handwritten" (higher accuracy, more VRAM).
    TROCR_MODEL: str = os.getenv("TROCR_MODEL", "microsoft/trocr-base-handwritten")
    # Device: "cpu" or "cuda" (if available).
    TROCR_DEVICE: str = os.getenv("TROCR_DEVICE", "cpu")
    # Working DPI scanned answer pages are rasterized to before OMR detection.
    OMR_DPI: int = int(os.getenv("OMR_DPI", "200"))
    # A checkbox interior is "marked" when its dark-pixel ratio >= threshold.
    OMR_INK_THRESHOLD: float = float(os.getenv("OMR_INK_THRESHOLD", "0.18"))

    # Task 13 — MCQ Question Bank.
    MCQ_STORAGE_DIR: str = os.getenv("MCQ_STORAGE_DIR", "generated/mcq_sheets")
    MCQ_DATASET_PATH: str = os.getenv("MCQ_DATASET_PATH", "generated/mcq_bank/mcq_dataset.json")
    MCQ_RESULTS_DIR: str = os.getenv("MCQ_RESULTS_DIR", "generated/mcq_results")

    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

    MIN_RESUME_TEXT_LENGTH: int = int(os.getenv("MIN_RESUME_TEXT_LENGTH", "200"))

    # Task 8 — background worker (polling loop, no external broker).
    WORKER_ENABLED: bool = os.getenv("WORKER_ENABLED", "true").lower() == "true"
    WORKER_POLL_INTERVAL_SECONDS: float = float(
        os.getenv("WORKER_POLL_INTERVAL_SECONDS", "2")
    )

    # Task 10 — Deterministic evaluator weights (must sum to 1.0)
    KEYWORD_WEIGHT: float = float(os.getenv("KEYWORD_WEIGHT", "0.25"))
    CONCEPT_WEIGHT: float = float(os.getenv("CONCEPT_WEIGHT", "0.40"))
    PHRASE_WEIGHT: float = float(os.getenv("PHRASE_WEIGHT", "0.15"))
    SIMILARITY_WEIGHT: float = float(os.getenv("SIMILARITY_WEIGHT", "0.10"))
    STRUCTURE_WEIGHT: float = float(os.getenv("STRUCTURE_WEIGHT", "0.10"))

    EVALUATOR_VERSION: str = os.getenv("EVALUATOR_VERSION", "v1.0.0-deterministic")
    JOB_POLL_INTERVAL_SECONDS: float = float(os.getenv("JOB_POLL_INTERVAL_SECONDS", "3.0"))

    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))


settings = Settings()
