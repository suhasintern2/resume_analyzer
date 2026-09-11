import io
import logging
import pymupdf as fitz
from PIL import Image

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    pytesseract = None
    TESSERACT_AVAILABLE = False

logger = logging.getLogger(__name__)


def _get_tesseract():
    if not TESSERACT_AVAILABLE:
        raise RuntimeError("OCR is not available: pytesseract is not installed.")
    try:
        import shutil
        if shutil.which("tesseract") is None:
            raise RuntimeError("OCR is not available: tesseract binary not found.")
    except Exception as e:
        raise RuntimeError(f"OCR is not available: {e}")
    return pytesseract


def preprocess_image(image: Image.Image) -> Image.Image:
    img = image.convert("L")
    width, height = img.size
    if width < 1000:
        ratio = 1000 / width
        img = img.resize((int(width * ratio), int(height * ratio)), Image.LANCZOS)
    return img


def ocr_image(image_bytes: bytes) -> str:
    try:
        tesseract = _get_tesseract()
        image = Image.open(io.BytesIO(image_bytes))
        processed = preprocess_image(image)
        text = tesseract.image_to_string(processed)
        return text
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        raise


def ocr_pdf(file_path: str) -> str:
    try:
        tesseract = _get_tesseract()
        doc = fitz.open(file_path)
        all_text = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            processed = preprocess_image(img)
            text = tesseract.image_to_string(processed)
            if text.strip():
                all_text.append(text.strip())

        doc.close()
        return "\n\n".join(all_text)
    except Exception as e:
        logger.error(f"PDF OCR failed: {e}")
        raise
