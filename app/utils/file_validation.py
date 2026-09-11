import os
from fastapi import UploadFile, HTTPException

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}


def validate_file(file: UploadFile, max_size_mb: int = 10) -> str:
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF, JPG, JPEG, or PNG file.",
        )

    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Please upload a PDF, JPG, JPEG, or PNG file.",
            )

    max_bytes = max_size_mb * 1024 * 1024

    content = file.file.read()
    file_size = len(content)
    file.file.seek(0)

    if file_size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"The file is too large. Maximum allowed size is {max_size_mb} MB.",
        )

    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    return ext
