"""Vendor CRUD router — REFERENCE pattern for all v1 routers.

Pattern:
  1. Declare a router with prefix and tags
  2. Inject DB session + current user via Depends
  3. Instantiate the service with (session, user.client_id)
  4. Call service methods and wrap result in response envelope

Copy this file when building Building, Agent, etc. routers.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.pagination import PaginationParams
from app.core.response import DataResponse, ListResponse, paginated
from app.db.base import get_db
from app.schemas.vendor import VendorCreate, VendorOut, VendorUpdate
from app.services.vendor import VendorService

router = APIRouter(prefix="/vendors", tags=["Vendors"])


# ------------------------------------------------------------------
# Helper — instantiate service with session + default client
# ------------------------------------------------------------------

def _svc(session: AsyncSession) -> VendorService:
    return VendorService(session, settings.default_client_id)


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.get("", response_model=ListResponse[VendorOut])
async def list_vendors(
    filter_status: Optional[str] = Query(default=None, alias="status", description="Filter by status"),
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_db),
):
    """List all vendors (paginated). Filter by ?status=active|inactive|suspended."""
    items, total = await _svc(session).list_vendors(pagination, status=filter_status)
    return paginated(
        [VendorOut.model_validate(v) for v in items],
        total, pagination.page, pagination.limit,
    )


@router.post("", response_model=DataResponse[VendorOut], status_code=status.HTTP_201_CREATED)
async def create_vendor(
    body: VendorCreate,
    session: AsyncSession = Depends(get_db),
):
    """Create a new vendor."""
    vendor = await _svc(session).create_vendor(body)
    return {"data": VendorOut.model_validate(vendor)}


@router.get("/{vendor_id}", response_model=DataResponse[VendorOut])
async def get_vendor(
    vendor_id: str,
    session: AsyncSession = Depends(get_db),
):
    vendor = await _svc(session).get_vendor(vendor_id)
    return {"data": VendorOut.model_validate(vendor)}


@router.put("/{vendor_id}", response_model=DataResponse[VendorOut])
async def update_vendor(
    vendor_id: str,
    body: VendorUpdate,
    session: AsyncSession = Depends(get_db),
):
    vendor = await _svc(session).update_vendor(vendor_id, body)
    return {"data": VendorOut.model_validate(vendor)}


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor(
    vendor_id: str,
    session: AsyncSession = Depends(get_db),
):
    await _svc(session).delete_vendor(vendor_id)

