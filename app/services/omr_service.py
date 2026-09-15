"""Deterministic OMR (optical mark recognition) for answer scripts (Task 12).

Active Task 12 requirement: the answer-script pipeline runs with **zero** LLM
calls.  MCQ answers are read with a pure image-processing OMR pass
(Pillow + numpy): each printed checkbox from the question sheet's
``layout_metadata`` is measured for interior ink density, and exactly one
marked option maps to that question's chosen letter.  Open-ended answers are
OCR'd locally with TrOCR (see ``ocr_service``).

No cv2 / OpenCV dependency — all image processing uses numpy and Pillow.

The whole module is deterministic: given the same page and the same
thresholds it always returns the same marks.  There is no guesswork — if a
mark cannot be attributed or too many are present, the caller stores
``AMBIGUOUS_MARK`` and the question is held out of scoring.
"""

import io
import logging
import numpy as np
import pymupdf as fitz
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _to_gray(image: Image.Image) -> np.ndarray:
    """PIL RGB → uint8 grayscale numpy array."""
    return np.array(image.convert("L"), dtype=np.uint8)


def _otsu_thresh(gray: np.ndarray) -> int:
    """Compute Otsu's binarisation threshold (pure numpy, no cv2)."""
    hist, _ = np.histogram(gray.flatten(), bins=256, range=(0, 256))
    total = gray.size
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


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Correct small page skew (<=15°) so checkbox coordinates stay aligned.

    Uses PCA on the dark-pixel coordinate cloud to estimate the skew angle,
    then corrects it with PIL rotation.  Fails safe: if there is too little
    ink or an extreme / tiny angle the page is returned unchanged.
    No cv2 required.
    """
    coords = np.column_stack(np.where(gray < 128))  # shape: (N, 2) — (row, col)
    if len(coords) < 200:
        return gray

    # PCA: the first principal component gives the dominant ink orientation.
    mean = coords.mean(axis=0)
    centered = (coords - mean).astype(np.float64)
    # Covariance of (row, col) cloud → eigenvector of largest eigenvalue = main axis.
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # Eigenvector corresponding to the largest eigenvalue.
    main_vec = eigenvectors[:, np.argmax(eigenvalues)]
    # Angle between the main axis and the horizontal (col axis).
    # coords are (row, col) so we swap to get (x=col, y=row).
    angle = float(np.degrees(np.arctan2(main_vec[0], main_vec[1])))

    # Normalise to (-90, 90] — the sign convention: positive = clockwise.
    if angle < -45:
        angle += 90
    elif angle > 45:
        angle -= 90

    if abs(angle) < 0.2 or abs(angle) > 15:
        return gray

    # PIL.Image.rotate rotates counter-clockwise, so negate for deskew.
    h, w = gray.shape
    pil_gray = Image.fromarray(gray, mode="L")
    rotated = pil_gray.rotate(
        -angle,
        resample=Image.BICUBIC,
        expand=False,
        fillcolor=255,
    )
    return np.array(rotated, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Page rasterisation
# ---------------------------------------------------------------------------

def rasterize_image_page(content: bytes, dpi: int | None = None) -> Image.Image:
    """Load a single-page image blob as an RGB PIL image."""
    dpi = dpi or settings.OMR_DPI  # noqa: F841 — kept for API symmetry
    return Image.open(io.BytesIO(content)).convert("RGB")


def rasterize_pdf_page(file_path: str, page_index: int, dpi: int | None = None) -> Image.Image:
    """Rasterize one PDF page to an RGB PIL image at the OMR working DPI."""
    dpi = dpi or settings.OMR_DPI
    doc = fitz.open(file_path)
    try:
        page = doc.load_page(page_index)
        pix = page.get_pixmap(dpi=dpi)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Checkbox localisation
# ---------------------------------------------------------------------------

def _find_rect_contour(patch: np.ndarray) -> tuple[int, int, int, int] | None:
    """Look for a near-square filled region within a patch (checkbox glyph).

    Pure numpy implementation — no cv2.  Binarises the patch with Otsu's
    method, labels connected components via a simple flood-fill approach, and
    returns the bounding box ``(top, left, height, width)`` of the best
    near-square component, or None if nothing plausible is found.
    """
    if patch.shape[0] < 6 or patch.shape[1] < 6:
        return None

    thresh = _otsu_thresh(patch)
    # Binary mask: True = dark (ink / border).
    binary = patch < thresh
    if not binary.any():
        return None

    # Simple connected-component labelling with scipy if available, otherwise
    # fall back to returning None (the caller uses the expected-box fallback).
    try:
        from scipy.ndimage import label as nd_label
        labeled, num_features = nd_label(binary)
    except ImportError:
        return None

    if num_features == 0:
        return None

    patch_area = float(patch.shape[0] * patch.shape[1])
    best: tuple[int, int, int, int] | None = None
    best_area = 0.0

    for comp_id in range(1, num_features + 1):
        rows, cols = np.where(labeled == comp_id)
        if rows.size == 0:
            continue
        top, bot = int(rows.min()), int(rows.max())
        left, right = int(cols.min()), int(cols.max())
        bh = bot - top + 1
        bw = right - left + 1
        area = float(bh * bw)
        if area < patch_area * 0.05 or area > patch_area * 0.9:
            continue
        if bw < 2 or bh < 2:
            continue
        aspect = bw / bh if bh >= bw else bh / bw
        if aspect < 0.5:
            continue
        if area > best_area:
            best_area = area
            best = (top, left, bh, bw)

    return best


def _locate_box(gray: np.ndarray, box: dict) -> tuple[int, int, int, int]:
    """Best-effort pixel rect ``(top, left, height, width)`` for a checkbox.

    Starts at the normalised box coordinates; tries to refine by finding a
    plausible near-square component in the surrounding patch (tolerates small
    printing shifts).  Falls back to the expected location when nothing better
    is found.
    """
    h, w = gray.shape
    cx = int(w * (box["x"] + box["w"] / 2))
    cy = int(h * (box["y"] + box["h"] / 2))
    half_w = max(int(w * box["w"]), 4)
    half_h = max(int(h * box["h"]), 4)

    x0, x1 = max(cx - half_w, 0), min(cx + half_w, w)
    y0, y1 = max(cy - half_h, 0), min(cy + half_h, h)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return (y0, x0, y1 - y0, x1 - x0)

    patch = gray[y0:y1, x0:x1]
    found = _find_rect_contour(patch)
    if found is not None:
        top, left, ph, pw = found
        return (y0 + top, x0 + left, ph, pw)

    # Fallback: use the expected box location directly.
    return (y0, x0, y1 - y0, x1 - x0)


# ---------------------------------------------------------------------------
# Ink density measurement
# ---------------------------------------------------------------------------

def measure_checkbox_ink(gray: np.ndarray, box: dict) -> float:
    """Dark-pixel ratio inside a normalised checkbox box.

    ``box`` uses normalised 0..1 page coords (``x, y, w, h``).  If a real
    rectangular checkbox component is found in the surrounding patch it is
    measured instead (tolerates small printing shifts); otherwise the
    expected box location is used.  The interior excludes the printed border
    (inset by ~12%) so an unfilled ``☐`` reads ~0 and a filled mark reads
    high.  Returns ink ratio in 0..1.
    """
    rect = _locate_box(gray, box)
    py, px, ph, pw = rect
    inset = max(int(min(pw, ph) * 0.12), 1)
    y0, y1 = py + inset, py + ph - inset
    x0, x1 = px + inset, px + pw - inset
    if y1 <= y0 or x1 <= x0:
        return 0.0
    roi = gray[y0:y1, x0:x1]
    if roi.size == 0:
        return 0.0
    return float(np.mean(roi < 128))


# ---------------------------------------------------------------------------
# Question-level detection
# ---------------------------------------------------------------------------

def detect_marked_options(
    gray: np.ndarray,
    layout_questions: list[dict],
    ink_threshold: float | None = None,
) -> dict[int, dict]:
    """Detect filled checkboxes for a page.

    ``layout_questions`` is the ``pages[].questions`` entry from the round's
    question-sheet ``layout_metadata``.  Each question yields:
    ``{"status": "MARKED"|"UNMARKED", "marks": [letter], "ink_ratios": {...}}``.

    A checkbox counts as marked when its interior ink ratio is >= the
    threshold.  The caller decides single vs ambiguous from ``marks``.
    """
    ink_threshold = ink_threshold if ink_threshold is not None else settings.OMR_INK_THRESHOLD
    results: dict[int, dict] = {}
    for qmeta in layout_questions:
        number = qmeta.get("number")
        marks: list[str] = []
        ratios: dict[str, float] = {}
        for opt in qmeta.get("options", []):
            box = opt.get("box") or {}
            label = opt.get("label", "?")
            ratio = measure_checkbox_ink(gray, box)
            ratios[label] = round(ratio, 4)
            if ratio >= ink_threshold:
                marks.append(label)
        results[number] = {
            "status": "MARKED" if marks else "UNMARKED",
            "marks": marks,
            "ink_ratios": ratios,
        }
    return results


def mark_status_for_question(omr_result: dict) -> tuple[str, str]:
    """Turn one question's OMR result into ``(status, content)``.

    - no marks  -> ("BLANK", "")
    - one mark  -> ("TRANSCRIBED", "OPTION_<letter>")
    - >1 marks  -> ("AMBIGUOUS_MARK", "MULTIPLE_<letters>")
    """
    marks = omr_result.get("marks") or []
    if not marks:
        return "BLANK", ""
    if len(marks) == 1:
        return "TRANSCRIBED", f"OPTION_{marks[0]}"
    joined = "_".join(sorted(marks))
    return "AMBIGUOUS_MARK", f"MULTIPLE_{joined}"