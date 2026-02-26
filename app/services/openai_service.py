"""COI AI extraction service — OpenAI-powered validation and enhancement layer.

Provides two capabilities:
1. **Document validation** — Detects whether text is from a valid ACORD 25 / COI
   document and rejects non-insurance documents with a clear reason.
2. **Structured extraction** — Extracts/enhances COI data with per-field
   confidence scores.

Can be used as a standalone extractor (raw text in → structured JSON out) or
as a validation+correction layer on top of pdfplumber.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from openai import AsyncOpenAI, OpenAIError

from app.core.config import settings
from app.core.exceptions import COIExtractionError

logger = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────

COI_EXTRACTION_PROMPT = """You are an expert insurance document analyst specialising in ACORD 25 Certificates of Liability Insurance.

## STEP 1 — Document Validation
First, determine whether the provided text is from an insurance Certificate of Liability (COI / ACORD 25) document.

Signs of a valid COI:
- Contains "Certificate of Liability Insurance", "ACORD 25", or similar header
- Has a PRODUCER section (insurance agency)
- Has an INSURED section
- Lists insurance POLICIES with policy numbers, dates, and coverage limits
- Has INSURER companies (A–F)
- Has a CERTIFICATE HOLDER section

If the text is NOT from a COI / insurance certificate, you MUST return:
{
  "is_coi": false,
  "rejection_reason": "<clear, user-friendly explanation of why this is not a COI, e.g. 'This appears to be a [document type]. Please upload a valid ACORD 25 Certificate of Insurance.'>",
  "confidence": 0.0,
  "field_confidence": {
    "producer": 0.0, "insured": 0.0, "certificate_holder": 0.0,
    "insurers": 0.0, "policies": 0.0, "certificate_date": 0.0
  },
  "data": {},
  "corrections": []
}

## STEP 2 — Data Extraction (only if the document IS a valid COI)
Extract structured certificate data from the raw text.

If a prior machine extraction is provided under "Machine Extraction", use it as a baseline — correct errors, fill missing fields, and normalise formatting. If no machine extraction is provided, extract all fields directly from the raw text.

Field definitions:
- producer: Insurance agency that issued the certificate (name, address, phone, fax, email).
- insured: The entity covered by the insurance (name, address).
- certificate_holder: The party requesting the certificate (name, address).
- insurers: List of insurance companies (letter A-F, company name, NAIC number).
- policies: Each policy with type of insurance, policy number, effective date (YYYY-MM-DD), expiration date (YYYY-MM-DD), insurer letter, and limits (name→value map).
- certificate_date: Date the certificate was issued (YYYY-MM-DD).

Output ONLY valid JSON matching this schema:

{
  "is_coi": true,
  "confidence": <float 0.0-1.0 overall extraction confidence>,
  "field_confidence": {
    "producer": <float>,
    "insured": <float>,
    "certificate_holder": <float>,
    "insurers": <float>,
    "policies": <float>,
    "certificate_date": <float>
  },
  "data": {
    "certificateDate": "<YYYY-MM-DD or null>",
    "producer": {
      "name": "<string>",
      "address": "<string or null>",
      "phone": "<string or null>",
      "fax": "<string or null>",
      "email": "<string or null>"
    },
    "insured": {
      "name": "<string>",
      "address": "<string or null>"
    },
    "certificateHolder": {
      "name": "<string>",
      "address": "<string or null>"
    } or null,
    "insurers": [
      {
        "letter": "<A-F>",
        "name": "<string>",
        "naicNumber": "<string or null>"
      }
    ],
    "policies": [
      {
        "typeOfInsurance": "<string>",
        "policyNumber": "<string>",
        "policyEffectiveDate": "<YYYY-MM-DD>",
        "policyExpirationDate": "<YYYY-MM-DD>",
        "insurerLetter": "<A-F or null>",
        "limits": {"<limit name>": "<dollar value>"} or null
      }
    ]
  },
  "corrections": [
    "<human-readable description of each correction or enhancement made>"
  ]
}

## Confidence Scoring Rules
- 1.0 = field clearly present and unambiguous
- 0.8-0.9 = field present but minor formatting issues corrected
- 0.5-0.7 = field partially present, some inference required
- 0.1-0.4 = field mostly inferred from context, low certainty
- 0.0 = field not found at all

## Rules
1. Output ONLY valid JSON — no markdown, no commentary.
2. Normalise all dates to YYYY-MM-DD.
3. Normalise dollar amounts to "$X,XXX" format.
4. If a field cannot be determined, set it to null and lower that field's confidence.
5. The "corrections" array must list every change made vs the machine extraction (empty array if none).
6. The "is_coi" field MUST always be present."""


class COIAIService:
    """Thin async wrapper around OpenAI for COI document validation and data extraction."""

    def __init__(self) -> None:
        if not settings.ai_enabled:
            raise COIExtractionError(
                "OpenAI API key is not configured. Set OPENAI_API_KEY in your .env file."
            )
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout,
        )
        self.model = settings.openai_model
        self.max_tokens = settings.openai_max_tokens

    # ── Core OpenAI call ──────────────────────────────────────────────────

    async def _call_openai(
        self, system_prompt: str, user_message: str
    ) -> Dict[str, Any]:
        """Send an async request to OpenAI and return parsed JSON."""
        try:
            logger.info(
                "Calling OpenAI model=%s, input_length=%d",
                self.model,
                len(user_message),
            )
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_completion_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise COIExtractionError("Empty response from OpenAI")

            logger.info("OpenAI call successful")
            return json.loads(content)

        except OpenAIError as exc:
            logger.error("OpenAI API error: %s", exc)
            raise COIExtractionError(f"OpenAI service error: {exc}") from exc
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON from OpenAI: %s", exc)
            raise COIExtractionError(f"Invalid JSON response: {exc}") from exc

    # ── Public methods ────────────────────────────────────────────────────

    async def validate_and_extract(
        self,
        raw_text: str,
        machine_extraction: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Validate the document and extract COI data in a single call.

        The AI first checks if the text is from a COI document. If not, it
        returns ``is_coi=False`` with a rejection reason. If yes, it extracts
        structured data with confidence scores.

        Args:
            raw_text: The raw text content from the PDF.
            machine_extraction: Optional prior pdfplumber extraction result.

        Returns:
            Dict with ``is_coi``, ``confidence``, ``field_confidence``,
            ``data``, and ``corrections`` keys.
        """
        parts = [f"Raw Certificate Text:\n{raw_text}"]
        if machine_extraction:
            parts.append(
                f"\nMachine Extraction (baseline):\n{json.dumps(machine_extraction, indent=2, default=str)}"
            )
        user_message = "\n".join(parts)
        return await self._call_openai(COI_EXTRACTION_PROMPT, user_message)


def get_ai_service() -> COIAIService:
    """Factory that creates a COIAIService instance.

    Raises ``COIExtractionError`` when the OpenAI key is not configured.
    """
    return COIAIService()
