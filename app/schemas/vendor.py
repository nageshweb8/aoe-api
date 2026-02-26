"""Vendor Pydantic schemas (request DTOs and response models)."""


from datetime import datetime

from app.schemas.common import CamelModel

class VendorCreate(CamelModel):
    company_name: str
    address_street: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    contact_name: str | None = None
    contact_title: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    agent_name: str | None = None
    agent_company: str | None = None
    agent_email: str | None = None
    agent_phone: str | None = None
    notes: str | None = None

class VendorUpdate(CamelModel):
    company_name: str | None = None
    address_street: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    contact_name: str | None = None
    contact_title: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    agent_name: str | None = None
    agent_company: str | None = None
    agent_email: str | None = None
    agent_phone: str | None = None
    status: str | None = None
    notes: str | None = None

class VendorOut(CamelModel):
    id: str
    client_id: str
    company_name: str
    address_street: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    contact_name: str | None = None
    contact_title: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    agent_name: str | None = None
    agent_company: str | None = None
    agent_email: str | None = None
    agent_phone: str | None = None
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

