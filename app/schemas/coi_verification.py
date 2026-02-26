from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class COIProducer(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None


class COIInsured(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None


class COICertificateHolder(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None


class COIInsurer(BaseModel):
    letter: Optional[str] = None
    name: Optional[str] = None
    naic_number: Optional[str] = Field(default=None, alias="naicNumber")

    model_config = {"populate_by_name": True}


class COIPolicy(BaseModel):
    type_of_insurance: str = Field(alias="typeOfInsurance")
    policy_number: str = Field(alias="policyNumber")
    policy_effective_date: str = Field(alias="policyEffectiveDate")
    policy_expiration_date: str = Field(alias="policyExpirationDate")
    limits: Optional[dict[str, str]] = None
    insurer_letter: Optional[str] = Field(default=None, alias="insurerLetter")

    model_config = {"populate_by_name": True}


class COIPolicyExpiration(BaseModel):
    type_of_insurance: str = Field(alias="typeOfInsurance")
    policy_number: str = Field(alias="policyNumber")
    policy_effective_date: str = Field(alias="policyEffectiveDate")
    policy_expiration_date: str = Field(alias="policyExpirationDate")
    days_expired: int = Field(alias="daysExpired")

    model_config = {"populate_by_name": True}


class COIVerificationResponse(BaseModel):
    id: str
    is_valid_coi: bool = Field(default=True, alias="isValidCoi")
    certificate_number: Optional[str] = Field(default=None, alias="certificateNumber")
    certificate_date: Optional[str] = Field(default=None, alias="certificateDate")
    producer: Optional[COIProducer] = None
    insured: Optional[COIInsured] = None
    certificate_holder: Optional[COICertificateHolder] = Field(
        default=None, alias="certificateHolder"
    )
    insurers: Optional[list[COIInsurer]] = None
    policies: list[COIPolicy] = Field(default_factory=list)
    expiration_warnings: Optional[list[COIPolicyExpiration]] = Field(
        default=None, alias="expirationWarnings"
    )
    status: str  # verified | expired | partial | invalid_document | error
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# AI-enhanced response models
# ---------------------------------------------------------------------------


class FieldConfidence(BaseModel):
    """Per-field confidence scores returned by the AI extraction layer."""

    producer: float = Field(default=0.0, ge=0.0, le=1.0)
    insured: float = Field(default=0.0, ge=0.0, le=1.0)
    certificate_holder: float = Field(default=0.0, ge=0.0, le=1.0, alias="certificateHolder")
    insurers: float = Field(default=0.0, ge=0.0, le=1.0)
    policies: float = Field(default=0.0, ge=0.0, le=1.0)
    certificate_date: float = Field(default=0.0, ge=0.0, le=1.0, alias="certificateDate")

    model_config = {"populate_by_name": True}


class AIExtractionResponse(BaseModel):
    """Response from the standalone AI extraction endpoint."""

    id: str
    is_valid_coi: bool = Field(default=True, alias="isValidCoi")
    confidence: float = Field(ge=0.0, le=1.0)
    field_confidence: FieldConfidence = Field(alias="fieldConfidence")
    certificate_number: Optional[str] = Field(default=None, alias="certificateNumber")
    certificate_date: Optional[str] = Field(default=None, alias="certificateDate")
    producer: Optional[COIProducer] = None
    insured: Optional[COIInsured] = None
    certificate_holder: Optional[COICertificateHolder] = Field(
        default=None, alias="certificateHolder"
    )
    insurers: Optional[list[COIInsurer]] = None
    policies: list[COIPolicy] = Field(default_factory=list)
    expiration_warnings: Optional[list[COIPolicyExpiration]] = Field(
        default=None, alias="expirationWarnings"
    )
    corrections: list[str] = Field(default_factory=list)
    status: str
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class AIExtractionRequest(BaseModel):
    """Request body for the standalone AI text extraction endpoint."""

    raw_text: str = Field(
        ...,
        alias="rawText",
        min_length=1,
        description="Raw text content from a COI document.",
    )

    model_config = {"populate_by_name": True}
