"""Generic async repository with soft-delete, pagination, and tenant isolation."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic CRUD repository. All queries are filtered by client_id.

    Soft-deletes: rows with `deleted_at IS NOT NULL` are excluded from all
    standard reads. Hard-delete is intentionally never exposed.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession, client_id: str):
        self._session = session
        self._client_id = client_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _base_query(self):
        """Return a SELECT filtered by client_id and excluding soft-deleted rows."""
        q = select(self.model).where(self.model.client_id == self._client_id)
        if hasattr(self.model, "deleted_at"):
            q = q.where(self.model.deleted_at.is_(None))
        return q

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, entity_id: str) -> ModelT | None:
        result = await self._session.execute(
            self._base_query().where(self.model.id == entity_id)
        )
        return result.scalars().first()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        order_by: str = "created_at",
        order: str = "desc",
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[ModelT], int]:
        """Return (items, total_count) with pagination and optional column filters."""
        q = self._base_query()

        # Apply simple equality filters
        if filters:
            for col_name, value in filters.items():
                if value is not None and hasattr(self.model, col_name):
                    q = q.where(getattr(self.model, col_name) == value)

        # Count
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self._session.execute(count_q)).scalar_one()

        # Order + paginate
        col = getattr(self.model, order_by, None)
        if col is not None:
            q = q.order_by(col.desc() if order == "desc" else col.asc())
        q = q.offset(offset).limit(limit)

        items = (await self._session.execute(q)).scalars().all()
        return list(items), total

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(self, **kwargs: Any) -> ModelT:
        instance = self.model(client_id=self._client_id, **kwargs)
        self._session.add(instance)
        await self._session.flush()  # populate id
        await self._session.refresh(instance)
        return instance

    async def update(self, entity_id: str, **kwargs: Any) -> ModelT | None:
        from datetime import datetime, timezone

        kwargs.pop("id", None)
        kwargs.pop("client_id", None)
        if "updated_at" not in kwargs and hasattr(self.model, "updated_at"):
            kwargs["updated_at"] = datetime.now(timezone.utc)

        await self._session.execute(
            update(self.model)
            .where(self.model.id == entity_id)
            .where(self.model.client_id == self._client_id)
            .values(**kwargs)
        )
        await self._session.flush()
        return await self.get_by_id(entity_id)

    async def soft_delete(self, entity_id: str) -> bool:
        from datetime import datetime, timezone

        result = await self._session.execute(
            update(self.model)
            .where(self.model.id == entity_id)
            .where(self.model.client_id == self._client_id)
            .values(deleted_at=datetime.now(timezone.utc))
        )
        await self._session.flush()
        return result.rowcount > 0
