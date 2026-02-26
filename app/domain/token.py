"""SQLAlchemy ORM model for tokenized vendor upload links."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.mixins import TenantMixin, TimestampMixin


class UploadToken(Base, TenantMixin, TimestampMixin):
    __tablename__ = "upload_tokens"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)

    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    building_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    template_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Expiry and usage
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    use_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # -1 = unlimited
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
