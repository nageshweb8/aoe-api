"""COI verification endpoint — POST /api/coi/verify."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.models import (
    COICertificateHolder,
    COIInsured,
    COIInsurer,
    COIPolicy,
    COIProducer,
    COIVerificationResponse,
    check_expired_policies,
)
from app.parser import parse_acord25_pdf

router = APIRouter(prefix="/api/coi", tags=["COI"])

ALLOWED_CONTENT_TYPE = "application/pdf"
ALLOWED_EXTENSION = ".pdf"


@router.post("/verify", response_model=COIVerificationResponse)
async def verify_coi(file: UploadFile = File(...)):
    """
    Accept an ACORD 25 Certificate of Insurance PDF, extract structured data,
    validate policy expiration dates, and return a JSON response.
    """
    # --- Security: validate file type ---
    if file.content_type != ALLOWED_CONTENT_TYPE:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Only PDF files are accepted.",
        )

    filename = file.filename or ""
    if not filename.lower().endswith(ALLOWED_EXTENSION):
        raise HTTPException(
            status_code=400,
            detail="Invalid file extension. Only .pdf files are accepted.",
        )

    # --- Security: validate file size ---
    contents = await file.read()
    if len(contents) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds the {settings.max_upload_size_mb}MB limit.",
        )

    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # --- Parse PDF ---
    try:
        parsed = parse_acord25_pdf(contents)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse the PDF document: {exc}",
        ) from exc

    # --- Build response models ---
    producer = (
        COIProducer(**parsed["producer"]) if parsed.get("producer") else None
    )
    insured_data = parsed.get("insured", {})
    insured = COIInsured(name=insured_data.get("name", "Unknown"), address=insured_data.get("address"))

    certificate_holder = (
        COICertificateHolder(**parsed["certificateHolder"])
        if parsed.get("certificateHolder")
        else None
    )
    insurers = (
        [COIInsurer(**i) for i in parsed["insurers"]] if parsed.get("insurers") else None
    )
    policies = [COIPolicy(**p) for p in parsed.get("policies", [])]

    # --- Expiration check ---
    expiration_warnings = check_expired_policies(policies)

    # --- Determine overall status ---
    if not policies:
        status = "partial"
        message = "No policies could be extracted from this certificate."
    elif expiration_warnings:
        status = "expired"
        count = len(expiration_warnings)
        message = f"{count} {'policy has' if count == 1 else 'policies have'} expired."
    else:
        status = "verified"
        message = "All policies are active and verified."

    return COIVerificationResponse(
        id=str(uuid.uuid4()),
        certificate_number=None,
        certificate_date=parsed.get("certificateDate"),
        producer=producer,
        insured=insured,
        certificate_holder=certificate_holder,
        insurers=insurers,
        policies=policies,
        expiration_warnings=expiration_warnings if expiration_warnings else None,
        status=status,
        message=message,
    )
