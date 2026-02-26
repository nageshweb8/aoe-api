"""COI verification & AI extraction endpoints — thin HTTP layer.

Business logic lives in :mod:`app.services.coi_service`.  This router is
responsible only for HTTP concerns: request validation, file handling,
and mapping domain exceptions to HTTP status codes.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.core.config import settings
from app.core.exceptions import COIExtractionError
from app.schemas.coi_verification import (
    AIExtractionRequest,
    AIExtractionResponse,
    COIVerificationResponse,
)
from app.services import coi_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/coi", tags=["COI"])

_ALLOWED_CONTENT_TYPE = "application/pdf"
_ALLOWED_EXTENSION = ".pdf"


# ---------------------------------------------------------------------------
# Shared file validation (HTTP concern — stays in the router)
# ---------------------------------------------------------------------------

async def _validate_and_read_pdf(file: UploadFile) -> bytes:
    """Validate the uploaded file and return its bytes.

    Raises HTTPException on invalid input.
    """
    if file.content_type != _ALLOWED_CONTENT_TYPE:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Only PDF files are accepted.",
        )

    filename = file.filename or ""
    if not filename.lower().endswith(_ALLOWED_EXTENSION):
        raise HTTPException(
            status_code=400,
            detail="Invalid file extension. Only .pdf files are accepted.",
        )

    contents = await file.read()

    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(contents) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds the {settings.max_upload_size_mb}MB limit.",
        )

    return contents


# ---------------------------------------------------------------------------
# POST /api/coi/verify — PDF upload (optionally AI-enhanced)
# ---------------------------------------------------------------------------

@router.post("/verify", response_model=COIVerificationResponse)
async def verify_coi(
    file: UploadFile = File(...),
    use_ai: bool = Query(
        default=False,
        description=(
            "When true, always run AI enhancement after pdfplumber extraction. "
            "When false (default), AI is invoked only if the extraction is incomplete."
        ),
    ),
):
    """Upload an ACORD 25 PDF, extract structured data, optionally
    enhance with OpenAI, validate expiration dates, and return JSON."""
    contents = await _validate_and_read_pdf(file)
    return await coi_service.verify_coi(contents, use_ai=use_ai)


# ---------------------------------------------------------------------------
# POST /api/coi/ai/extract — standalone AI extraction (raw text, no PDF)
# ---------------------------------------------------------------------------

@router.post(
    "/ai/extract",
    response_model=AIExtractionResponse,
    summary="AI COI Extraction",
    description=(
        "Send raw COI text and receive AI-extracted structured data with "
        "per-field confidence scores. No PDF upload required."
    ),
)
async def ai_extract_coi(body: AIExtractionRequest):
    """Standalone AI extraction — accepts raw text, returns structured JSON."""
    if not settings.ai_enabled:
        raise HTTPException(
            status_code=503,
            detail="AI features are not available. Configure OPENAI_API_KEY to enable.",
        )
    try:
        return await coi_service.ai_extract_from_text(body.raw_text)
    except COIExtractionError as exc:
        raise HTTPException(status_code=502, detail=f"AI extraction failed: {exc}") from exc


# ---------------------------------------------------------------------------
# POST /api/coi/ai/enhance — AI enhancement of existing extraction
# ---------------------------------------------------------------------------

@router.post(
    "/ai/enhance",
    response_model=AIExtractionResponse,
    summary="AI COI Enhancement",
    description=(
        "Upload a PDF and force AI enhancement — always runs both pdfplumber "
        "and OpenAI, returning the merged result with confidence scores."
    ),
)
async def ai_enhance_coi(file: UploadFile = File(...)):
    """Upload a PDF and force AI enhancement with confidence scores."""
    if not settings.ai_enabled:
        raise HTTPException(
            status_code=503,
            detail="AI features are not available. Configure OPENAI_API_KEY to enable.",
        )
    contents = await _validate_and_read_pdf(file)
    try:
        return await coi_service.ai_enhance_from_pdf(contents)
    except COIExtractionError as exc:
        raise HTTPException(status_code=502, detail=f"AI extraction failed: {exc}") from exc
