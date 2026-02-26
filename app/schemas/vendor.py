"""Vendor Pydantic schemas (request DTOs and response models)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.schemas.common import CamelModel


class VendorCreate(CamelModel):
    company_name: str
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    agent_name: Optional[str] = None
    agent_company: Optional[str] = None
    agent_email: Optional[str] = None
    agent_phone: Optional[str] = None
    notes: Optional[str] = None


class VendorUpdate(CamelModel):
    company_name: Optional[str] = None
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    agent_name: Optional[str] = None
    agent_company: Optional[str] = None
    agent_email: Optional[str] = None
    agent_phone: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class VendorOut(CamelModel):
    id: str
    client_id: str
    company_name: str
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    agent_name: Optional[str] = None
    agent_company: Optional[str] = None
    agent_email: Optional[str] = None
    agent_phone: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime



