"""SQLAlchemy ORM models for COI Records and Validation Results."""


import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.mixins import TenantMixin, TimestampMixin

class COIRecord(Base, TenantMixin, TimestampMixin):
    """One uploaded COI document (all versions share a lineage_id)."""

    __tablename__ = "coi_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    lineage_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # building_id stored as plain reference (add FK when Building domain model is created)
    building_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    uploaded_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    uploaded_by_token_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Blob storage reference
    blob_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Extracted data (JSON dump from parser)
    extraction_data: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    # Parsed key fields (denormalized for query performance)
    insured_name: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    earliest_expiry: Mapped[date | None] = mapped_column(Date, index=True, nullable=True)

    # Workflow status: pending | valid | expired | rejected | approved | invalid_document
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    vendor: Mapped["Vendor"] = relationship(back_populates="coi_records", lazy="noload")
    validations: Mapped[list["COIValidation"]] = relationship(
        back_populates="coi_record", lazy="selectin", cascade="all, delete-orphan"
    )

class COIValidation(Base, TenantMixin, TimestampMixin):
    """One row per requirement check performed against a COI record."""

    __tablename__ = "coi_validations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    coi_record_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coi_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    check_name: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    required_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actual_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # "pass" | "fail" | "warning" | "n/a"
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    coi_record: Mapped["COIRecord"] = relationship(back_populates="validations")

