"""Vendor service — REFERENCE pattern for all services.

How to add a new service:
  1. Create app/services/my_entity.py
  2. Inject AsyncSession via constructor
  3. Instantiate the repository
  4. Delegate all DB work to the repository
  5. Raise AppException subclasses for business rule violations

Rule: No SQLAlchemy / no FastAPI here. Pure Python business logic.
"""


from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginationParams
from app.domain.vendor import Vendor
from app.repositories.vendor import VendorRepository
from app.schemas.vendor import VendorCreate, VendorUpdate

class VendorService:
    def __init__(self, session: AsyncSession, client_id: str):
        self._repo = VendorRepository(session, client_id)

    async def list_vendors(self, pagination: PaginationParams, status: str | None = None):
        filters = {"status": status} if status else None
        items, total = await self._repo.list(
            offset=pagination.offset,
            limit=pagination.limit,
            order_by=pagination.sort,
            order=pagination.order,
            filters=filters,
        )
        return items, total

    async def get_vendor(self, vendor_id: str) -> Vendor:
        vendor = await self._repo.get_by_id(vendor_id)
        if not vendor:
            raise NotFoundError("Vendor", vendor_id)
        return vendor

    async def create_vendor(self, data: VendorCreate) -> Vendor:
        return await self._repo.create(**data.model_dump(exclude_none=True))

    async def update_vendor(self, vendor_id: str, data: VendorUpdate) -> Vendor:
        _ = await self.get_vendor(vendor_id)  # raises 404 if missing
        updated = await self._repo.update(
            vendor_id, **data.model_dump(exclude_none=True, exclude_unset=True)
        )
        return updated  # type: ignore[return-value]

    async def delete_vendor(self, vendor_id: str) -> None:
        deleted = await self._repo.soft_delete(vendor_id)
        if not deleted:
            raise NotFoundError("Vendor", vendor_id)
