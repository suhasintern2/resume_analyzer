import base64
import io
import logging
import httpx
from PIL import Image
import pymupdf as fitz
from app.config import settings

logger = logging.getLogger(__name__)

MAX_IMAGE_DIMENSION = 1600


def _preprocess_image(image: Image.Image) -> Image.Image:
    if image.mode != "RGB":
        image = image.convert("RGB")
    width, height = image.size
    max_dim = max(width, height)
    if max_dim > MAX_IMAGE_DIMENSION:
        ratio = MAX_IMAGE_DIMENSION / max_dim
        image = image.resize((int(width * ratio), int(height * ratio)), Image.LANCZOS)
    return image


def _image_to_base64(image_bytes: bytes, mime_type: str = None) -> tuple[str, str]:
    image = Image.open(io.BytesIO(image_bytes))
    image = _preprocess_image(image)
    buffer = io.BytesIO()
    if mime_type == "image/png":
        image.save(buffer, format="PNG")
        mime = "image/png"
    else:
        image.save(buffer, format="JPEG", quality=90)
        mime = "image/jpeg"
    return mime, base64.b64encode(buffer.getvalue()).decode()


def _extract_with_llm(images: list[dict]) -> str:
    if not images:
        return ""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.LLM_MODEL}:generateContent?key={settings.LLM_API_KEY}"

    parts = [
        {
            "text": (
                "You are an OCR assistant. Extract ALL the text from the resume image(s) "
                "accurately, preserving the original structure, section headings, bullet points, "
                "skills, dates, company names, project names and technologies. "
                "Return ONLY the extracted plain text with no commentary."
            )
        }
    ]
    parts.extend({"inline_data": img} for img in images)

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.1},
    }

    with httpx.Client(timeout=settings.LLM_TIMEOUT) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        content_parts = data["candidates"][0]["content"]["parts"]
        return "\n".join(p["text"] for p in content_parts if "text" in p).strip()


def ocr_image(image_bytes: bytes) -> str:
    try:
        mime, b64 = _image_to_base64(image_bytes)
        text = _extract_with_llm([{"mime_type": mime, "data": b64}])
        return text
    except Exception as e:
        logger.error(f"Image OCR failed: {e}")
        raise


def ocr_pdf(file_path: str) -> str:
    try:
        doc = fitz.open(file_path)
        page_texts = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            png_bytes = pix.tobytes("png")
            mime, b64 = _image_to_base64(png_bytes, mime_type="image/png")
            text = _extract_with_llm([{"mime_type": mime, "data": b64}])
            if text.strip():
                page_texts.append(text.strip())

        doc.close()
        return "\n\n".join(page_texts)
    except Exception as e:
        logger.error(f"PDF OCR failed: {e}")
        raise