"""SQLAlchemy ORM model for Vendors.

This is the REFERENCE module showing the pattern for all domain models:
  - Inherit Base, TenantMixin, TimestampMixin
  - UUID primary key
  - client_id for multi-tenancy (from TenantMixin)
  - created_at / updated_at / deleted_at (from TimestampMixin)
Copy this pattern when adding new domain models (e.g. Building, Agent, etc.).
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.mixins import TenantMixin, TimestampMixin


class Vendor(Base, TenantMixin, TimestampMixin):
    __tablename__ = "vendors"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    address_street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address_zip: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    agent_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    agent_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    agent_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    agent_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # "active" | "inactive" | "suspended"
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships (add more as new domain models are created)
    coi_records: Mapped[List["COIRecord"]] = relationship(
        back_populates="vendor", lazy="noload"
    )
