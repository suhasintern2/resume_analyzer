import base64
import io
import logging
import httpx
from PIL import Image
import pymupdf as fitz
from app.config import settings

logger = logging.getLogger(__name__)

MAX_IMAGE_DIMENSION = 1600

# Task 9 — deterministic markers the handwriting pipeline used to emit
# verbatim.  Task 12 replaces the handwriting LLM with local TrOCR, so
# markers are no longer emitted; the constants are kept for the segmentation
# module's classification rules (empty content -> BLANK, explicit marker ->
# ILLEGIBLE/blank).
BLANK_MARKER = "[BLANK]"
ILLEGIBLE_MARKER = "[ILLEGIBLE]"

_RESUME_OCR_PROMPT = (
    "You are an OCR assistant. Extract ALL the text from the resume image(s) "
    "accurately, preserving the original structure, section headings, bullet points, "
    "skills, dates, company names, project names and technologies. "
    "Return ONLY the extracted plain text with no commentary."
)

_HANDWRITING_OCR_PROMPT = None  # Task 12: handwriting OCR is TrOCR-based


# ---------------------------------------------------------------------------
# Lazy-loaded TrOCR model and processor
# ---------------------------------------------------------------------------

_trocr_processor = None
_trocr_model = None
_trocr_device = None


def _load_trocr() -> tuple:
    """Load TrOCR processor and model lazily (first call only)."""
    global _trocr_processor, _trocr_model, _trocr_device
    if _trocr_processor is None or _trocr_model is None:
        try:
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel
            import torch

            _trocr_device = settings.TROCR_DEVICE
            if _trocr_device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA requested but not available; falling back to CPU")
                _trocr_device = "cpu"

            logger.info(
                "Loading TrOCR model %s on %s ...", settings.TROCR_MODEL, _trocr_device
            )
            _trocr_processor = TrOCRProcessor.from_pretrained(settings.TROCR_MODEL)
            _trocr_model = VisionEncoderDecoderModel.from_pretrained(settings.TROCR_MODEL)
            _trocr_model.to(_trocr_device)
            _trocr_model.eval()
            logger.info("TrOCR model loaded successfully")
        except Exception as e:
            logger.error("Failed to load TrOCR model: %s", e)
            raise
    return _trocr_processor, _trocr_model, _trocr_device


# ---------------------------------------------------------------------------
# Resume OCR helpers — Gemini Vision (unchanged)
# ---------------------------------------------------------------------------

def _preprocess_image(image: Image.Image) -> Image.Image:
    """Resize a resume image so its largest dimension ≤ MAX_IMAGE_DIMENSION."""
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


def ocr_image(image_bytes: bytes) -> str:
    """Resume OCR via Gemini Vision (unchanged from Task 9)."""
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
    """Resume PDF OCR via Gemini Vision — page-by-page (unchanged from Task 9)."""
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
# TrOCR handwriting pipeline — line-aware page slicing
# ---------------------------------------------------------------------------
# TrOCR (microsoft/trocr-base-handwritten) is a **line-level** model: it was
# fine-tuned on cropped single-line text images (IAM handwriting dataset).
# Feeding it a full scanned page produces near-random output because the
# patch-based encoder was never trained on document-scale spatial layouts.
#
# Correct approach:
#   1. Binarise the page with a numpy-only Otsu threshold (no cv2 needed here;
#      the OMR module owns that import).
#   2. Build a horizontal projection histogram (dark-pixel count per row).
#   3. Merge adjacent "dark" rows — with a small gap-tolerance — into text-line
#      bounding intervals.
#   4. Crop each interval from the original RGB image, add a small vertical
#      pad, enforce TrOCR's minimum strip height, and run the model.
#   5. Join all decoded line strings with newlines into a single page text.
# ---------------------------------------------------------------------------

_MIN_LINE_HEIGHT_PX: int = 20   # strips shorter than this are skipped (noise)
_LINE_GAP_TOLERANCE: int = 6    # merge strips separated by ≤ this many blank rows
_MIN_DARK_PIXELS: int = 3       # a row needs ≥ this many dark pixels to count
_STRIP_PADDING_PX: int = 4      # vertical pad above/below each detected strip
_TROCR_MIN_HEIGHT: int = 32     # TrOCR patch encoder needs at least this height


def _otsu_threshold(gray_array) -> int:
    """Compute Otsu's binarisation threshold with pure numpy (no cv2)."""
    import numpy as np
    hist, _ = np.histogram(gray_array.flatten(), bins=256, range=(0, 256))
    total = gray_array.size
    sum_total = float(np.dot(np.arange(256, dtype=np.float64), hist))
    sum_bg = 0.0
    weight_bg = 0.0
    max_var = 0.0
    thresh = 127
    for t in range(256):
        weight_bg += hist[t]
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break
        sum_bg += t * float(hist[t])
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_total - sum_bg) / weight_fg
        var = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if var > max_var:
            max_var = var
            thresh = t
    return thresh


def _slice_page_into_lines(pil_image: Image.Image) -> list[Image.Image]:
    """Detect handwritten text lines in a full-page image.

    Returns a list of RGB PIL image crops, one per detected text-line strip,
    in top-to-bottom order.  Falls back to a single-element list containing
    the full page when no line structure can be found (blank sheet, very
    short page, etc.).
    """
    import numpy as np

    rgb = pil_image.convert("RGB")
    gray = np.array(rgb.convert("L"), dtype=np.uint8)

    thresh = _otsu_threshold(gray)
    dark = gray < thresh  # bool mask: True = ink pixel

    # Horizontal projection: dark-pixel count per row.
    row_sums = dark.sum(axis=1)  # shape: (page_height,)

    # Walk rows to collect (top, bottom) intervals of text lines.
    in_line = False
    line_start = 0
    gap_count = 0
    segments: list[tuple[int, int]] = []

    for row_idx, count in enumerate(row_sums):
        if count >= _MIN_DARK_PIXELS:
            if not in_line:
                line_start = row_idx
                in_line = True
            gap_count = 0
        else:
            if in_line:
                gap_count += 1
                if gap_count > _LINE_GAP_TOLERANCE:
                    segments.append((line_start, row_idx - gap_count))
                    in_line = False
                    gap_count = 0

    if in_line:
        segments.append((line_start, len(row_sums) - 1))

    # Discard tiny noise segments.
    segments = [
        (top, bot) for top, bot in segments if (bot - top + 1) >= _MIN_LINE_HEIGHT_PX
    ]

    if not segments:
        logger.debug(
            "_slice_page_into_lines: no text lines detected; returning full page"
        )
        return [rgb]

    logger.debug(
        "_slice_page_into_lines: %d text-line strips detected", len(segments)
    )

    width = rgb.width
    strips: list[Image.Image] = []
    for top, bot in segments:
        pad_top = max(0, top - _STRIP_PADDING_PX)
        pad_bot = min(rgb.height, bot + _STRIP_PADDING_PX + 1)
        strip = rgb.crop((0, pad_top, width, pad_bot))

        # Enforce TrOCR's minimum strip height (patch-encoder requirement).
        if strip.height < _TROCR_MIN_HEIGHT:
            canvas = Image.new("RGB", (strip.width, _TROCR_MIN_HEIGHT), (255, 255, 255))
            canvas.paste(strip, (0, 0))
            strip = canvas

        strips.append(strip)

    return strips


def _trocr_recognize(image: Image.Image) -> str:
    """Transcribe handwritten text from a full-page PIL image using TrOCR.

    The page is first sliced into individual text-line strips because TrOCR
    (microsoft/trocr-base-handwritten) is a line-level model — feeding it an
    entire page produces near-random output.  Each strip is inferred
    independently and the decoded strings are joined with newlines.
    """
    try:
        processor, model, device = _load_trocr()
        import torch

        strips = _slice_page_into_lines(image)
        decoded_lines: list[str] = []

        for strip in strips:
            if strip.mode != "RGB":
                strip = strip.convert("RGB")

            pixel_values = processor(
                images=strip, return_tensors="pt"
            ).pixel_values.to(device)

            with torch.no_grad():
                generated_ids = model.generate(pixel_values)

            line_text = processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0].strip()

            if line_text:
                decoded_lines.append(line_text)

        return "\n".join(decoded_lines)

    except Exception as e:
        logger.error("TrOCR recognition failed: %s", e)
        raise


def ocr_handwriting_image(image_bytes: bytes) -> str:
    """Transcribe one scanned handwriting image with local TrOCR.

    Task 12: fully AI-free (replaced Gemini Vision handwriting prompt).
    The page is sliced into text-line strips before inference — TrOCR is a
    line-level model and produces garbage when given a full page directly.
    Resume OCR (``ocr_image``) still uses Gemini and is untouched.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return _trocr_recognize(image)
    except Exception as e:
        logger.error("Handwriting image OCR failed: %s", e)
        raise


def ocr_handwriting_pdf(file_path: str) -> str:
    """Transcribe a scanned PDF of a handwritten answer sheet with TrOCR.

    Each page is rasterised at OMR_DPI (default 200 DPI for adequate
    resolution), then sliced into text-line strips before being passed to the
    TrOCR line model.
    """
    try:
        doc = fitz.open(file_path)
        page_texts: list[str] = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=settings.OMR_DPI)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            text = _trocr_recognize(image)
            if text.strip():
                page_texts.append(text.strip())

        doc.close()
        return "\n\n".join(page_texts)
    except Exception as e:
        logger.error("Handwriting PDF OCR failed: %s", e)
        raise