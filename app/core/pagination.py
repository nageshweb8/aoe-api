"""Pagination helpers for list endpoints."""


from fastapi import Query
from pydantic import BaseModel


class PaginationParams:
    """FastAPI dependency for `?page=1&limit=20&sort=created_at&order=desc`."""

    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="Page number (1-based)"),
        limit: int = Query(default=20, ge=1, le=200, description="Items per page"),
        sort: str = Query(default="created_at", description="Sort field"),
        order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort order"),
    ):
        self.page = page
        self.limit = limit
        self.sort = sort
        self.order = order

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


class PageMeta(BaseModel):
    total: int
    page: int
    limit: int
    pages: int

    model_config = {"populate_by_name": True}
