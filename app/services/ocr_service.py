import base64
import io
import logging
import httpx
import torch
from PIL import Image
import pymupdf as fitz
from app.config import settings
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

logger = logging.getLogger(__name__)

MAX_IMAGE_DIMENSION = 1600

# Markers kept for the segmentation module's classification rules.
BLANK_MARKER = "[BLANK]"
ILLEGIBLE_MARKER = "[ILLEGIBLE]"

_RESUME_OCR_PROMPT = (
    "You are an OCR assistant. Extract ALL the text from the resume image(s) "
    "accurately, preserving the original structure, section headings, bullet points, "
    "skills, dates, company names, project names and technologies. "
    "Return ONLY the extracted plain text with no commentary."
)

_HANDWRITING_OCR_PROMPT = (
    "You are an OCR assistant specialized in reading handwritten text. "
    "Extract ALL handwritten text from this image accurately. "
    "If the image contains numbered questions and answers, preserve the numbering "
    "(e.g. '1.', '2.', 'Q1', 'Q2'). "
    "For each answer, transcribe the handwritten text exactly as written. "
    "If a question has no answer written, output nothing for that question. "
    "If text is illegible, write [ILLEGIBLE] on that line. "
    "Return ONLY the extracted plain text with no commentary."
)


# Initialize TrOCR model and processor lazily to avoid startup overhead
_trocr_processor = None
_trocr_model = None


def _get_trocr_model():
    """Lazy load TrOCR model and processor."""
    global _trocr_processor, _trocr_model
    if _trocr_processor is None or _trocr_model is None:
        try:
            logger.info("Loading TrOCR model: %s", settings.TROCR_MODEL)
            _trocr_processor = TrOCRProcessor.from_pretrained(settings.TROCR_MODEL)
            _trocr_model = VisionEncoderDecoderModel.from_pretrained(settings.TROCR_MODEL)
            _trocr_model.to(settings.TROCR_DEVICE)
            _trocr_model.eval()
            logger.info("TrOCR model loaded successfully on %s", settings.TROCR_DEVICE)
        except Exception as e:
            logger.error("Failed to load TrOCR model: %s", e)
            raise
    return _trocr_processor, _trocr_model


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def _preprocess_image(image: Image.Image) -> Image.Image:
    """Resize an image so its largest dimension <= MAX_IMAGE_DIMENSION."""
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


# ---------------------------------------------------------------------------
# Gemini Vision API call (shared by resume OCR)
# ---------------------------------------------------------------------------


def _extract_with_llm(
    images: list[dict],
    prompt: str,
    temperature: float = 0.1,
) -> str:
    if not images:
        return ""

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.LLM_MODEL}:generateContent?key={settings.LLM_API_KEY}"
    )

    parts = [{"text": prompt}]
    parts.extend({"inline_data": img} for img in images)

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": temperature},
    }

    with httpx.Client(timeout=settings.LLM_TIMEOUT) as client:
        import time as _time
        for _retry in range(3):
            response = client.post(url, json=payload)
            if response.status_code != 429:
                break
            wait = 20 * (_retry + 1)
            logger.warning("LLM 429 rate-limit; retry %d/3 after %ds", _retry + 1, wait)
            _time.sleep(wait)
        response.raise_for_status()
        data = response.json()
        content_parts = data["candidates"][0]["content"]["parts"]
        return "\n".join(p["text"] for p in content_parts if "text" in p).strip()


# ---------------------------------------------------------------------------
# Resume OCR (unchanged - still uses Gemini Vision for resumes)
# ---------------------------------------------------------------------------


def ocr_image(image_bytes: bytes) -> str:
    """Resume OCR via Gemini Vision."""
    try:
        mime, b64 = _image_to_base64(image_bytes)
        return _extract_with_llm(
            [{"mime_type": mime, "data": b64}],
            _RESUME_OCR_PROMPT,
        )
    except Exception as e:
        logger.error("Image OCR failed: %s", e)
        raise


def ocr_pdf(file_path: str) -> str:
    """Resume PDF OCR via Gemini Vision — page-by-page."""
    try:
        doc = fitz.open(file_path)
        page_texts = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            png_bytes = pix.tobytes("png")
            mime, b64 = _image_to_base64(png_bytes, mime_type="image/png")
            text = _extract_with_llm(
                [{"mime_type": mime, "data": b64}], _RESUME_OCR_PROMPT
            )
            if text.strip():
                page_texts.append(text.strip())
        doc.close()
        return "\n\n".join(page_texts)
    except Exception as e:
        logger.error("PDF OCR failed: %s", e)
        raise


# ---------------------------------------------------------------------------
# Handwriting OCR (TrOCR - AI-free, local implementation)
# ---------------------------------------------------------------------------


def ocr_handwriting_image(image_bytes: bytes) -> str:
    """Transcribe one scanned handwriting image via local TrOCR (AI-free)."""
    try:
        # Load and preprocess image
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != "RGB":
            image = image.convert("RGB")
        image = _preprocess_image(image)

        # Get TrOCR model and processor
        processor, model = _get_trocr_model()

        # Process image with TrOCR
        pixel_values = processor(image, return_tensors="pt").pixel_values.to(settings.TROCR_DEVICE)

        # Generate text
        with torch.no_grad():
            generated_ids = model.generate(pixel_values, max_length=512)
            generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

        # Clean up the text - TrOCR sometimes adds extra spaces or newlines
        generated_text = generated_text.strip()

        logger.info("TrOCR OCR'd handwriting image (%d chars)", len(generated_text))
        return generated_text

    except Exception as e:
        logger.error("Handwriting image OCR failed: %s", e)
        raise


def ocr_handwriting_pdf(file_path: str) -> str:
    """Transcribe a scanned PDF of a handwritten answer sheet via local TrOCR (AI-free).

    Each page is processed locally with TrOCR for best accuracy.
    """
    try:
        doc = fitz.open(file_path)
        page_texts: list[str] = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            png_bytes = pix.tobytes("png")

            # Process with TrOCR
            image = Image.open(io.BytesIO(png_bytes))
            if image.mode != "RGB":
                image = image.convert("RGB")
            image = _preprocess_image(image)

            processor, model = _get_trocr_model()
            pixel_values = processor(image, return_tensors="pt").pixel_values.to(settings.TROCR_DEVICE)

            with torch.no_grad():
                generated_ids = model.generate(pixel_values, max_length=512)
                generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

            text = generated_text.strip()
            if text.strip():
                page_texts.append(text.strip())

            logger.info(
                "TrOCR OCR'd handwriting page %d/%d for %s (%d chars)",
                page_num + 1, len(doc), file_path, len(text.strip()),
            )

        doc.close()
        return "\n\n".join(page_texts)
    except Exception as e:
        logger.error("Handwriting PDF OCR failed: %s", e)
        raise