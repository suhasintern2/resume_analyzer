"""Record-file persistence (amendment §6 — Scratch vs Record).

"Record" files (resume, question sheet, answer key, answer script,
generated evaluation report) must persist on disk with their path stored
in the ``files`` table — never deleted by request-cleanup logic. Deletion
is only ever an explicit, deliberate operation: the scheduled retention
job, or a rollback of a failed creation.

Storage convention (Task 6): RECORD files live under a per-interview
directory, ``<UPLOAD_DIR>/<interview_id>/``, using safe server-generated
uuid4-based filenames — never the client's original filename. The path
stored in ``files.file_path`` is the relative path:

    <UPLOAD_DIR>/INT-20260914-261/RESUME_<uuid4>.pdf

The ``files`` row is the source of truth for what exists and where; the
retention job operates off those rows, not directory scanning.
"""

import logging
import os
import uuid

from app.config import settings

logger = logging.getLogger(__name__)


def _upload_root() -> str:
    root = settings.UPLOAD_DIR
    os.makedirs(root, exist_ok=True)
    return root


def _record_dir(interview_id: str) -> str:
    """Absolute path of the per-interview record directory."""
    directory = os.path.join(_upload_root(), interview_id)
    os.makedirs(directory, exist_ok=True)
    return directory


def persist_record(
    content: bytes,
    *,
    interview_id: str,
    file_type: str,
    ext: str,
) -> str:
    """Write a RECORD file for an interview.

    Returns the relative path (e.g.
    ``uploads/INT-20260914-261/RESUME_<uuid4>.pdf``) to store in the
    ``files`` table. ``ext`` should already start with a dot (".pdf").
    """
    safe_type = "".join(c for c in file_type.upper() if c.isalnum() or c == "_")
    filename = f"{safe_type}_{uuid.uuid4().hex}{ext}"
    absolute = os.path.join(_record_dir(interview_id), filename)
    with open(absolute, "wb") as f:
        f.write(content)
    logger.info(
        "Stored record file %s (%d bytes)", os.path.basename(absolute), len(content)
    )
    return os.path.join(
        settings.UPLOAD_DIR, interview_id, filename
    ).replace(os.sep, "/")


def delete_stored_file(relative_path: str | None) -> None:
    """Explicitly delete a stored record file. Deliberate operation only.

    Only deletes the exact path recorded in ``files.file_path``; never
    scans or cleans a directory. Non-existent files are a no-op.
    """
    if not relative_path:
        return
    try:
        os.remove(relative_path)
        logger.info("Deleted record file %s", relative_path)
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.warning("Could not delete stored file %s: %s", relative_path, e)