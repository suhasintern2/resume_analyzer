"""Deterministic OCR-text segmentation of handwritten answer sheets (Task 9).

The OCR prompt (ocr_service) is told to reproduce question markers as
they appear (``Question 1``, ``Q2``, ...) and to emit the literal
``[BLANK]`` / ``[ILLEGIBLE]`` markers for empty/unreadable regions.

This module splits that plain text into per-block segments and classifies
each block.  Crucially, alignment is NEVER guessed:

- If the detected question numbers are exactly ``1..N`` each once, the
  interview is SEGMENTED.
- Otherwise (missing, duplicate, out-of-range or scrambled markers) the
  interview is SEGMENTATION_UNCERTAIN and the blocks are kept in document
  order for human review/override — a missing marker is never silently
  filled in.

A block is ``BLANK`` only when its entire content is empty or is made up
solely of ``[BLANK]`` markers; ``ILLEGIBLE`` only when its entire content
is solely ``[ILLEGIBLE]`` markers.  Text that merely contains a marker
inline is still TRANSCRIBED (the marker stays in the transcription so the
human reviewer can see the ambiguity).
"""

import re

from dataclasses import dataclass

from app.services.ocr_service import BLANK_MARKER, ILLEGIBLE_MARKER

# Matches a printed question marker at the start of a line:
#   "Question 1", "Question no. 2", "Q3", "Answer 4", "ANSWER 5", ...
# The trailing ``[#.:\-)]?\s*`` consumes a following colon/dot/bracket + any
# whitespace so the segment content is the answer text, not ": answer".
_MARKER_RE = re.compile(
    r"(?im)^\s*(?:question\s*|answer\s*|q\s*)[#.:\-]?\s*(?:no\.?|number)?\s*(\d{1,3})\b[#.:\-)]?\s*",
)

# A block whose whole content is just one or more of the same marker.
_MARKER_ONLY_RE = re.compile(
    rf"^\s*(?:\[\s*(?:blank|illegible)\s*\]\s*){{1,3}}$",
    re.IGNORECASE,
)


@dataclass
class SegmentRecord:
    """One segmented block: the question it was aligned to (None when it
    could not be aligned) plus its transcribed content and classification."""

    question_number: int | None
    content: str
    status: str  # "TRANSCRIBED" | "BLANK" | "ILLEGIBLE"


@dataclass
class _Block:
    question_number: int | None
    content: str


def _split_blocks(ocr_text: str) -> list[_Block]:
    matches = list(_MARKER_RE.finditer(ocr_text))
    if not matches:
        return [_Block(None, ocr_text)]

    blocks: list[_Block] = []

    preamble = ocr_text[: matches[0].start()].strip()
    if preamble:
        blocks.append(_Block(None, preamble))

    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(ocr_text)
        content = ocr_text[start:end].strip()
        blocks.append(_Block(int(match.group(1)), content))

    return blocks


def _classify(content: str) -> tuple[str, str]:
    """Return ``(status, stored_content)`` for one block's raw text."""
    stripped = content.strip()
    if not stripped:
        return "BLANK", ""

    marker_only = _MARKER_ONLY_RE.match(stripped)
    if marker_only:
        marker = stripped.upper()
        if ILLEGIBLE_MARKER in marker:
            return "ILLEGIBLE", ""
        return "BLANK", ""

    # Marker plus surrounding text is still real content: TRANSCRIBED with
    # the literal marker preserved for the human reviewer.
    return "TRANSCRIBED", stripped


def segment_ocr_text(
    ocr_text: str,
    question_count: int,
) -> tuple[list[SegmentRecord], bool]:
    """Split OCR'd answer-sheet text into segments.

    Returns ``(segments, matched)`` where ``matched`` is True only when the
    detected question numbers are exactly ``1..question_count``, each
    exactly once.  On a match the segments are returned in document order
    (any unnumbered preamble first, then the aligned questions in order);
    otherwise in document order.
    """
    blocks = _split_blocks(ocr_text or "")

    numbered = [b.question_number for b in blocks if b.question_number is not None]
    expected = list(range(1, question_count + 1))
    matched = sorted(numbered) == expected

    if matched:
        by_number = {
            b.question_number: b for b in blocks if b.question_number is not None
        }
        ordered = [by_number[n] for n in expected]
        extras = [b for b in blocks if b.question_number is None]
        blocks = extras + ordered

    segments = []
    for b in blocks:
        status, content = _classify(b.content)
        segments.append(SegmentRecord(
            question_number=b.question_number,
            content=content,
            status=status,
        ))
    return segments, matched


def matches_question_numbers(
    segments: list[SegmentRecord],
    question_count: int,
) -> bool:
    """Re-check whether the current segments align cleanly to 1..N.

    Used after a manual reassignment: distinct 1..N numbers, each exactly
    once.  Still no guessing — this is exact set equality.
    """
    numbered = [s.question_number for s in segments if s.question_number is not None]
    return sorted(numbered) == list(range(1, question_count + 1))