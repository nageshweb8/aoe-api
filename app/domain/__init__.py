"""Domain package — all ORM models are imported here so Alembic autogenerate detects them.

Folder intent:
  vendor.py  — REFERENCE pattern (copy when adding Building, Agent, etc.)
  coi.py     — COI records and per-check validation rows
  token.py   — Tokenized vendor upload links
  audit.py   — Immutable audit trail (never updated or deleted)
  mixins.py  — Shared TimestampMixin, TenantMixin
"""

from app.domain.audit import AuditTrail
from app.domain.coi import COIRecord, COIValidation
from app.domain.token import UploadToken
from app.domain.vendor import Vendor

__all__ = [
    "AuditTrail",
    "COIRecord",
    "COIValidation",
    "UploadToken",
    "Vendor",
]
