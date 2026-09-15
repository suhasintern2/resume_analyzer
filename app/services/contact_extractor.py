"""Best-effort email/phone extraction from cleaned resume text.

Kept deliberately simple and conservative: returns the first plausible match
and never raises. This is display-only convenience data for the dashboard,
so false negatives are preferred over false positives (e.g. we reject
all-same-digit runs that look like phone numbers but usually are not).
"""

import re

_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
)

_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[ .\-]?)?"
    r"(?:\(\d{2,5}\)[ .\-]?)?"
    r"\d{2,4}[ .\-]?\d{3,4}[ .\-]?\d{3,4}"
)


def extract_email(text: str | None) -> str | None:
    """Return the first email-looking string, lowercased, or ``None``."""
    if not text:
        return None
    match = _EMAIL_RE.search(text)
    return match.group(0).strip(".").lower() if match else None


def extract_phone(text: str | None) -> str | None:
    """Return the first plausible phone number, or ``None``.

    A candidate must normalize to 7–15 digits; year-like or all-same-digit
    runs (GPA, IDs, dates) are filtered out.
    """
    if not text:
        return None
    for match in _PHONE_RE.finditer(text):
        candidate = match.group(0).strip()
        digits = re.sub(r"\D", "", candidate)
        if not (7 <= len(digits) <= 15):
            continue
        if len(set(digits)) == 1:
            continue
        return candidate
    return None


def extract_contact_info(text: str | None) -> tuple[str | None, str | None]:
    """Return ``(email, phone)`` extracted from the given text."""
    return extract_email(text), extract_phone(text)