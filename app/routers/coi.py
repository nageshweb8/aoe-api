"""COI verification & AI extraction endpoints — thin HTTP layer.

Business logic lives in :mod:`app.services.coi_service`.  This router is
responsible only for HTTP concerns: request validation, file handling,
and mapping domain exceptions to HTTP status codes.
"""


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

_ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/png": "image",
}
_ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "pdf",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
}


# ---------------------------------------------------------------------------
# Shared file validation (HTTP concern — stays in the router)
# ---------------------------------------------------------------------------

def _detect_file_kind(file: UploadFile) -> str:
    """Return ``'pdf'`` or ``'image'`` based on content type and extension.

    Raises :class:`HTTPException` when the file type is not supported.
    """
    kind_by_ct = _ALLOWED_CONTENT_TYPES.get(file.content_type or "")

    filename = (file.filename or "").lower()
    ext = ""
    for e in _ALLOWED_EXTENSIONS:
        if filename.endswith(e):
            ext = e
            break
    kind_by_ext = _ALLOWED_EXTENSIONS.get(ext)

    # Accept if either content-type or extension matches
    kind = kind_by_ct or kind_by_ext
    if not kind:
        accepted = ", ".join(sorted({*_ALLOWED_EXTENSIONS}))
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type '{file.content_type}'. "
                f"Accepted formats: {accepted}"
            ),
        )
    return kind


async def _validate_and_read_file(file: UploadFile) -> tuple[bytes, str]:
    """Validate the uploaded file and return ``(contents, kind)``.

    *kind* is ``'pdf'`` or ``'image'``.
    Raises HTTPException on invalid input.
    """
    kind = _detect_file_kind(file)

    contents = await file.read()

    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(contents) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds the {settings.max_upload_size_mb}MB limit.",
        )

    return contents, kind


# ---------------------------------------------------------------------------
# POST /api/coi/verify — PDF or image upload (optionally AI-enhanced)
# ---------------------------------------------------------------------------

@router.post("/verify", response_model=COIVerificationResponse)
async def verify_coi(
    file: UploadFile = File(...),
    use_ai: bool = Query(
        default=False,
        description=(
            "When true, always run AI enhancement after extraction. "
            "When false (default), AI is invoked only if the extraction is incomplete. "
            "Image uploads (JPEG/PNG) always use AI regardless of this flag."
        ),
    ),
):
    """Upload an ACORD 25 document (PDF, JPEG, or PNG), extract structured
    data, optionally enhance with OpenAI, validate expiration dates, and
    return JSON."""
    contents, kind = await _validate_and_read_file(file)

    if kind == "image":
        # Images always go through Vision AI
        if not settings.ai_enabled:
            raise HTTPException(
                status_code=503,
                detail="AI features are not available. Configure OPENAI_API_KEY to enable image processing.",
            )
        mime = file.content_type or "image/png"
        try:
            return await coi_service.ai_extract_from_image(contents, mime_type=mime)
        except COIExtractionError as exc:
            raise HTTPException(status_code=502, detail=f"AI extraction failed: {exc}") from exc

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
        "Upload a PDF or image and force AI enhancement — always runs AI, "
        "returning the result with confidence scores. For PDFs, pdfplumber "
        "extraction is used as a baseline before AI. For images, Vision API "
        "extracts directly."
    ),
)
async def ai_enhance_coi(file: UploadFile = File(...)):
    """Upload a document and force AI enhancement with confidence scores."""
    if not settings.ai_enabled:
        raise HTTPException(
            status_code=503,
            detail="AI features are not available. Configure OPENAI_API_KEY to enable.",
        )
    contents, kind = await _validate_and_read_file(file)
    try:
        if kind == "image":
            mime = file.content_type or "image/png"
            return await coi_service.ai_extract_from_image(contents, mime_type=mime)
        return await coi_service.ai_enhance_from_pdf(contents)
    except COIExtractionError as exc:
        raise HTTPException(status_code=502, detail=f"AI extraction failed: {exc}") from exc
