import re


def clean_resume_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r'[^\S\n]+', ' ', text)

    text = re.sub(r'\n{3,}', '\n\n', text)

    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if re.match(r'^\d+\s*$', stripped):
            continue
        cleaned_lines.append(stripped)

    text = '\n'.join(cleaned_lines)

    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
