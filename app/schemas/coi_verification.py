
from pydantic import BaseModel, Field

class COIProducer(BaseModel):
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    fax: str | None = None
    email: str | None = None

class COIInsured(BaseModel):
    name: str | None = None
    address: str | None = None

class COICertificateHolder(BaseModel):
    name: str | None = None
    address: str | None = None

class COIInsurer(BaseModel):
    letter: str | None = None
    name: str | None = None
    naic_number: str | None = Field(default=None, alias="naicNumber")

    model_config = {"populate_by_name": True}

class COIPolicy(BaseModel):
    type_of_insurance: str = Field(alias="typeOfInsurance")
    policy_number: str = Field(alias="policyNumber")
    policy_effective_date: str = Field(alias="policyEffectiveDate")
    policy_expiration_date: str = Field(alias="policyExpirationDate")
    limits: dict[str, str] | None = None
    insurer_letter: str | None = Field(default=None, alias="insurerLetter")

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
    certificate_number: str | None = Field(default=None, alias="certificateNumber")
    certificate_date: str | None = Field(default=None, alias="certificateDate")
    producer: COIProducer | None = None
    insured: COIInsured | None = None
    certificate_holder: COICertificateHolder | None = Field(
        default=None, alias="certificateHolder"
    )
    insurers: list[COIInsurer] | None = None
    policies: list[COIPolicy] = Field(default_factory=list)
    expiration_warnings: list[COIPolicyExpiration] | None = Field(
        default=None, alias="expirationWarnings"
    )
    status: str  # verified | expired | partial | invalid_document | error
    message: str | None = None
    source_type: str = Field(
        default="pdf", alias="sourceType",
        description="Origin of the extraction: pdf, image, or text.",
    )

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
    certificate_number: str | None = Field(default=None, alias="certificateNumber")
    certificate_date: str | None = Field(default=None, alias="certificateDate")
    producer: COIProducer | None = None
    insured: COIInsured | None = None
    certificate_holder: COICertificateHolder | None = Field(
        default=None, alias="certificateHolder"
    )
    insurers: list[COIInsurer] | None = None
    policies: list[COIPolicy] = Field(default_factory=list)
    expiration_warnings: list[COIPolicyExpiration] | None = Field(
        default=None, alias="expirationWarnings"
    )
    corrections: list[str] = Field(default_factory=list)
    requires_review: bool = Field(
        default=False, alias="requiresReview",
        description=(
            "True when overall confidence is below the review threshold "
            "or any individual field confidence is below the field threshold."
        ),
    )
    review_reasons: list[str] = Field(
        default_factory=list, alias="reviewReasons",
        description="Human-readable reasons why this extraction was flagged for review.",
    )
    status: str
    message: str | None = None
    source_type: str = Field(
        default="pdf", alias="sourceType",
        description="Origin of the extraction: pdf, image, or text.",
    )

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
