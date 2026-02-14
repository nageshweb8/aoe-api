from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class COIProducer(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None


class COIInsured(BaseModel):
    name: str
    address: Optional[str] = None


class COICertificateHolder(BaseModel):
    name: str
    address: Optional[str] = None


class COIInsurer(BaseModel):
    letter: str
    name: str
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
    certificate_number: Optional[str] = Field(default=None, alias="certificateNumber")
    certificate_date: Optional[str] = Field(default=None, alias="certificateDate")
    producer: Optional[COIProducer] = None
    insured: COIInsured
    certificate_holder: Optional[COICertificateHolder] = Field(
        default=None, alias="certificateHolder"
    )
    insurers: Optional[list[COIInsurer]] = None
    policies: list[COIPolicy]
    expiration_warnings: Optional[list[COIPolicyExpiration]] = Field(
        default=None, alias="expirationWarnings"
    )
    status: str  # verified | expired | partial | error
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    env: str


def check_expired_policies(
    policies: list[COIPolicy],
    reference_date: Optional[date] = None,
) -> list[COIPolicyExpiration]:
    """Return a list of expired policy details compared to the reference date (default: today)."""
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
