import os
import tempfile
import pytest
from app.services.pdf_extractor import extract_pdf_text


def test_extract_text_from_pdf():
    import fitz

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "John Doe\nSoftware Engineer\nPython, Django, React\nExperience at Tech Corp")
        doc.save(tmp_path)
        doc.close()

        text = extract_pdf_text(tmp_path)
        assert len(text) > 0
        assert "John Doe" in text
        assert "Python" in text
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
