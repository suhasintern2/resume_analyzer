from app.services.text_cleaner import clean_resume_text


def test_clean_basic_text():
    raw = "John   Doe\n\n\n\nPython   Developer"
    cleaned = clean_resume_text(raw)
    assert "John Doe" in cleaned
    assert "Python Developer" in cleaned
    assert "\n\n\n" not in cleaned


def test_clean_empty_text():
    assert clean_resume_text("") == ""
    assert clean_resume_text(None) == ""


def test_clean_removes_page_numbers():
    raw = "John Doe\n42\nPython Developer"
    cleaned = clean_resume_text(raw)
    assert "42" not in cleaned.split("\n")
