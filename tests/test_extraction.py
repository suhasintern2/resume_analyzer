import os
import tempfile
import pytest
from app.services.pdf_extractor import extract_pdf_text


def test_extract_text_from_pdf():
    import fitz

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "John Doe\nSoftware Engineer\nPython, Django, React\nExperience at Tech Corp")
        doc.save(tmp.name)
        doc.close()

        try:
            text = extract_pdf_text(tmp.name)
            assert len(text) > 0
            assert "John Doe" in text
            assert "Python" in text
        finally:
            os.remove(tmp.name)
