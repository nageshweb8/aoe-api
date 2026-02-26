"""COI verification service — orchestrates parsing, AI enhancement, and response building.

This module owns all COI-specific business logic.  Routers delegate to
functions here and never contain domain logic directly.

Responsibilities:
  - Document classification (is this an ACORD 25 COI?)
  - pdfplumber + AI orchestration and data merging
  - Policy expiration checking
  - Response-model construction with safe builders
"""


import logging
import uuid
from datetime import date
from typing import Any

from app.core.config import settings
from app.core.exceptions import COIExtractionError
from app.schemas.coi_verification import (
    AIExtractionResponse,
    COICertificateHolder,
    COIInsured,
    COIInsurer,
    COIPolicy,
    COIPolicyExpiration,
    COIProducer,
    COIVerificationResponse,
    FieldConfidence,
)
from app.services.parser import extract_raw_text, parse_acord25_pdf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COI_KEYWORDS: list[str] = [
    "CERTIFICATE OF LIABILITY INSURANCE",
    "CERTIFICATE OF INSURANCE",
    "ACORD 25",
    "ACORD",
    "PRODUCER",
    "INSURED",
    "INSURER",
    "POLICY NUMBER",
    "GENERAL LIABILITY",
    "AUTOMOBILE LIABILITY",
    "WORKERS COMPENSATION",
    "UMBRELLA",
    "CERTIFICATE HOLDER",
]

COI_KEYWORD_THRESHOLD: int = 3

# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def looks_like_coi(raw_text: str) -> bool:
    """Heuristic: does the raw text look like a COI / ACORD 25 document?"""
    if not raw_text or not raw_text.strip():
        return False
    upper = raw_text.upper()
    hits = sum(1 for kw in COI_KEYWORDS if kw in upper)
    return hits >= COI_KEYWORD_THRESHOLD

def extraction_is_incomplete(parsed: dict[str, Any]) -> bool:
    """Return True when the pdfplumber result is missing important fields."""
    if not parsed.get("policies"):
        return True
    insured_name = (parsed.get("insured") or {}).get("name", "")
    if not insured_name or insured_name == "Unknown":
        return True
    producer_name = (parsed.get("producer") or {}).get("name", "")
    if not producer_name:
        return True
    return False

# ---------------------------------------------------------------------------
# Expiration checking (A2 — moved from schemas/coi_verification.py)
# ---------------------------------------------------------------------------

def check_expired_policies(
    policies: list[COIPolicy],
    reference_date: date | None = None,
) -> list[COIPolicyExpiration]:
    """Return a list of expired policy details compared to *reference_date* (default: today)."""
    ref = reference_date or date.today()
    expired: list[COIPolicyExpiration] = []

    for policy in policies:
        try:
            exp_date = date.fromisoformat(policy.policy_expiration_date)
        except ValueError:
            continue

        if exp_date < ref:
            days = (ref - exp_date).days
            expired.append(
                COIPolicyExpiration(
                    type_of_insurance=policy.type_of_insurance,
                    policy_number=policy.policy_number,
                    policy_effective_date=policy.policy_effective_date,
                    policy_expiration_date=policy.policy_expiration_date,
                    days_expired=days,
                )
            )

    return expired

# ---------------------------------------------------------------------------
# Safe model builders (never raise — return fallback on bad data)
# ---------------------------------------------------------------------------

def _safe_producer(data: Any) -> COIProducer | None:
    if not data or not isinstance(data, dict):
        return None
    try:
        return COIProducer(**data)
    except Exception:
        return None

def _safe_insured(data: Any) -> COIInsured:
    if not data or not isinstance(data, dict):
        return COIInsured(name="Unknown")
    try:
        return COIInsured(**data)
    except Exception:
        return COIInsured(name="Unknown")

def _safe_certificate_holder(data: Any) -> COICertificateHolder | None:
    if not data or not isinstance(data, dict):
        return None
    try:
        return COICertificateHolder(**data)
    except Exception:
        return None

def _safe_insurers(data: Any) -> list[COIInsurer] | None:
    if not data or not isinstance(data, list):
        return None
    result: list[COIInsurer] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            result.append(COIInsurer(**item))
        except Exception:
            continue
    return result if result else None

def _safe_policies(data: Any) -> list[COIPolicy]:
    if not data or not isinstance(data, list):
        return []
    result: list[COIPolicy] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            result.append(COIPolicy(**item))
        except Exception:
            continue
    return result

# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------

def invalid_document_response(
    message: str = (
        "The uploaded document does not appear to be a valid ACORD 25 "
        "Certificate of Insurance. Please upload a valid COI document."
    ),
) -> COIVerificationResponse:
    """Return a clear invalid-document response instead of a 500 error."""
    return COIVerificationResponse(
        id=str(uuid.uuid4()),
        is_valid_coi=False,
        status="invalid_document",
        message=message,
        policies=[],
    )

def invalid_document_ai_response(
    message: str = (
        "The uploaded document does not appear to be a valid ACORD 25 "
        "Certificate of Insurance. Please upload a valid COI document."
    ),
) -> AIExtractionResponse:
    """Return a clear invalid-document AI response."""
    return AIExtractionResponse(
        id=str(uuid.uuid4()),
        is_valid_coi=False,
        confidence=0.0,
        field_confidence=FieldConfidence(),
        status="invalid_document",
        message=message,
        policies=[],
    )

def build_verification_response(
    parsed: dict[str, Any],
    *,
    confidence: float | None = None,
    field_confidence: dict[str, Any] | None = None,
    corrections: list[str] | None = None,
) -> COIVerificationResponse | AIExtractionResponse:
    """Build the appropriate response model from a parsed dict.

    When *confidence* is supplied an ``AIExtractionResponse`` is returned;
    otherwise a plain ``COIVerificationResponse``.
    """
    producer = _safe_producer(parsed.get("producer"))
    insured = _safe_insured(parsed.get("insured"))
    certificate_holder = _safe_certificate_holder(parsed.get("certificateHolder"))
    insurers = _safe_insurers(parsed.get("insurers"))
    policies = _safe_policies(parsed.get("policies"))

    expiration_warnings = check_expired_policies(policies)

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

    common: dict[str, Any] = dict(
        id=str(uuid.uuid4()),
        is_valid_coi=True,
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

    if confidence is not None:
        return AIExtractionResponse(
            **common,
            confidence=confidence,
            field_confidence=FieldConfidence(**(field_confidence or {})),
            corrections=corrections or [],
        )
    return COIVerificationResponse(**common)

# ---------------------------------------------------------------------------
# Internal: pdfplumber extraction with fallback
# ---------------------------------------------------------------------------

def _empty_parsed() -> dict[str, Any]:
    """Return a fresh empty-parsed dict (safe to mutate)."""
    return {
        "producer": None,
        "insured": {"name": "Unknown", "address": None},
        "certificateHolder": None,
        "insurers": None,
        "certificateDate": None,
        "policies": [],
    }

def _extract_text(contents: bytes) -> str:
    """Extract raw text from PDF bytes, returning empty string on failure."""
    try:
        return extract_raw_text(contents)
    except Exception:
        return ""

def _parse_pdf(contents: bytes) -> dict[str, Any]:
    """Run pdfplumber and return parsed dict, with safe fallback."""
    try:
        return parse_acord25_pdf(contents)
    except Exception as exc:
        logger.warning("pdfplumber parse failed: %s", exc)
        return _empty_parsed()

# ---------------------------------------------------------------------------
# Core orchestration — public API
# ---------------------------------------------------------------------------

_DEFAULT_NOT_COI_MSG = (
    "The uploaded document does not appear to be a valid ACORD 25 "
    "Certificate of Insurance. Please upload a valid COI document."
)

async def verify_coi(
    contents: bytes, *, use_ai: bool = False,
) -> COIVerificationResponse:
    """Parse an ACORD 25 PDF, optionally enhance with AI, and return verification.

    Non-COI documents receive a clear *invalid_document* response (never a 500).
    AI failures are non-fatal — they are logged and skipped.
    """
    raw_text = _extract_text(contents)
    parsed = _parse_pdf(contents)

    # --- Document classification ---
    has_coi_structure = bool(parsed.get("policies")) or bool(
        (parsed.get("producer") or {}).get("name")
    )
    text_looks_like_coi = looks_like_coi(raw_text)

    if not has_coi_structure and not text_looks_like_coi:
        # Definitely not a COI; if AI is enabled, give it one shot to confirm
        if settings.ai_enabled:
            try:
                from app.services.openai_service import get_ai_service

                ai_service = get_ai_service()
                ai_result = await ai_service.validate_and_extract(raw_text)

                if not ai_result.get("is_coi", False):
                    return invalid_document_response(
                        ai_result.get("rejection_reason", _DEFAULT_NOT_COI_MSG)
                    )

                # AI says it IS a COI — use AI data
                return build_verification_response(ai_result.get("data", {}))

            except Exception as exc:
                logger.warning("AI validation failed: %s", exc)

        return invalid_document_response()

    # --- AI enhancement layer (non-fatal) ---
    should_use_ai = use_ai or extraction_is_incomplete(parsed)

    if should_use_ai and settings.ai_enabled and raw_text.strip():
        try:
            from app.services.openai_service import get_ai_service

            ai_service = get_ai_service()
            ai_result = await ai_service.validate_and_extract(
                raw_text, machine_extraction=parsed,
            )

            # If AI says this isn't a COI, return invalid document
            if not ai_result.get("is_coi", True):
                return invalid_document_response(
                    ai_result.get("rejection_reason", _DEFAULT_NOT_COI_MSG)
                )

            ai_data = ai_result.get("data", {})

            # Merge: prefer AI data for missing/empty pdfplumber fields
            for key in ("producer", "insured", "certificateHolder", "insurers", "certificateDate"):
                if not parsed.get(key) and ai_data.get(key):
                    parsed[key] = ai_data[key]

            # If pdfplumber found no policies, use AI policies
            if not parsed.get("policies") and ai_data.get("policies"):
                parsed["policies"] = ai_data["policies"]

            logger.info(
                "AI enhancement applied — confidence=%.2f, corrections=%d",
                ai_result.get("confidence", 0),
                len(ai_result.get("corrections", [])),
            )
        except Exception as exc:
            logger.warning("AI enhancement failed (non-fatal): %s", exc)

    return build_verification_response(parsed)

async def ai_extract_from_text(raw_text: str) -> AIExtractionResponse:
    """AI-only extraction from raw COI text.

    Raises :class:`COIExtractionError` if the AI call fails.
    """
    from app.services.openai_service import get_ai_service

    ai_service = get_ai_service()
    ai_result = await ai_service.validate_and_extract(raw_text)

    if not ai_result.get("is_coi", False):
        return invalid_document_ai_response(
            ai_result.get(
                "rejection_reason",
                "The provided text does not appear to be from a Certificate of Insurance document.",
            )
        )

    ai_data = ai_result.get("data", {})
    return build_verification_response(
        ai_data,
        confidence=ai_result.get("confidence", 0.0),
        field_confidence=ai_result.get("field_confidence", {}),
        corrections=ai_result.get("corrections", []),
    )

async def ai_enhance_from_pdf(contents: bytes) -> AIExtractionResponse:
    """Parse PDF with pdfplumber, then always run AI enhancement.

    Raises :class:`COIExtractionError` if the AI call fails.
    """
    raw_text = _extract_text(contents)
    parsed = _parse_pdf(contents)

    from app.services.openai_service import get_ai_service

    ai_service = get_ai_service()

    # When raw_text is empty (scanned/image PDF), tell the AI the context
    if not raw_text.strip():
        ai_text = (
            "(No extractable text — this appears to be a scanned/image-based PDF. "
            "The pdfplumber extraction below is all that could be recovered.)"
        )
    else:
        ai_text = raw_text

    ai_result = await ai_service.validate_and_extract(
        ai_text, machine_extraction=parsed,
    )

    # Not a COI document
    if not ai_result.get("is_coi", False):
        return invalid_document_ai_response(
            ai_result.get("rejection_reason", _DEFAULT_NOT_COI_MSG)
        )

    ai_data = ai_result.get("data", {})

    # Merge: prefer AI corrections over pdfplumber
    for key in ("producer", "insured", "certificateHolder", "insurers", "certificateDate"):
        if ai_data.get(key):
            parsed[key] = ai_data[key]
    if ai_data.get("policies"):
        parsed["policies"] = ai_data["policies"]

    return build_verification_response(
        parsed,
        confidence=ai_result.get("confidence", 0.0),
        field_confidence=ai_result.get("field_confidence", {}),
        corrections=ai_result.get("corrections", []),
    )
