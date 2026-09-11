import os
import time
import logging
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.utils.file_validation import validate_file
from app.utils.helpers import get_upload_path, validate_resume_text, truncate_resume_text
from app.services.pdf_extractor import extract_pdf_text
from app.services.ocr_service import ocr_image
from app.services.text_cleaner import clean_resume_text
from app.services.question_generator import generate_interview_questions
from app.services.document_generator import generate_docx
from app.models.schemas import GenerateResponse, InterviewResult
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/generate", response_model=GenerateResponse)
async def generate(file: UploadFile = File(...)):
    start_time = time.time()
    temp_path = None

    try:
        ext = validate_file(file, settings.MAX_FILE_SIZE_MB)
        logger.info(f"Processing {ext} file ({file.content_type})")

        temp_path = get_upload_path(ext)
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        if ext == ".pdf":
            extracted_text = extract_pdf_text(temp_path)
        elif ext in (".jpg", ".jpeg", ".png"):
            extracted_text = ocr_image(content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type.")

        cleaned_text = clean_resume_text(extracted_text)
        logger.info(f"Extracted {len(cleaned_text)} characters")

        if not validate_resume_text(cleaned_text):
            raise HTTPException(
                status_code=422,
                detail="We could not extract enough readable text from this resume. Please upload a clearer image or a text-based PDF.",
            )

        cleaned_text = truncate_resume_text(cleaned_text)

        result = generate_interview_questions(cleaned_text)

        duration = time.time() - start_time
        logger.info(f"Completed in {duration:.1f}s")

        return GenerateResponse(success=True, result=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while processing the resume. Please try again.",
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@router.post("/download/docx")
async def download_docx(result: InterviewResult):
    try:
        docx_bytes = generate_docx(result)

        from fastapi.responses import Response
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="interview_prep_{result.candidate_name.replace(" ", "_")}.docx"'
            },
        )
    except Exception as e:
        logger.error(f"DOCX generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate document.",
        )
