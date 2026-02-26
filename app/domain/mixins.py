"""Reusable SQLAlchemy column mixins and Base."""

from __future__ import annotations

from datetime import datetime, timezone

from typing import Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    """Adds created_at, updated_at, deleted_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now,
        onupdate=_now,
        server_default=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class TenantMixin:
    """Adds client_id column for multi-tenancy."""

    client_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
