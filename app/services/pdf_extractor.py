import fitz
from app.services.ocr_service import ocr_pdf


MIN_EXTRACTED_TEXT_LENGTH = 200


def extract_pdf_text(file_path: str) -> str:
    doc = fitz.open(file_path)
    text_parts = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page_text = page.get_text("text")
        if page_text.strip():
            text_parts.append(page_text.strip())

    doc.close()

    full_text = "\n\n".join(text_parts)

    if len(full_text.strip()) < MIN_EXTRACTED_TEXT_LENGTH:
        ocr_text = ocr_pdf(file_path)
        if len(ocr_text.strip()) > len(full_text.strip()):
            return ocr_text

    return full_text
