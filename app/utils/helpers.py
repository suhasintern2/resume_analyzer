import os
import uuid
from app.config import settings


def generate_safe_filename(extension: str) -> str:
    return f"{uuid.uuid4().hex}{extension}"


def get_upload_path(extension: str) -> str:
    os.makedirs("uploads", exist_ok=True)
    filename = generate_safe_filename(extension)
    return os.path.join("uploads", filename)


def validate_resume_text(text: str) -> bool:
    return len(text.strip()) >= settings.MIN_RESUME_TEXT_LENGTH


def truncate_resume_text(text: str) -> str:
    max_chars = settings.MAX_RESUME_CHARACTERS
    if len(text) <= max_chars:
        return text

    return text[:max_chars]
