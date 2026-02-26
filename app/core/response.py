"""Standardized JSON response envelope helpers."""


import math
from typing import Generic, TypeVar

from pydantic import BaseModel
from pydantic.alias_generators import to_camel

from app.core.pagination import PageMeta

T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):
    """Single-item response envelope: `{ data: {...} }`"""

    data: T

    model_config = {
        "populate_by_name": True,
        "alias_generator": to_camel,
    }


class ListResponse(BaseModel, Generic[T]):
    """Paginated list response envelope: `{ data: [...], meta: {...} }`"""

    data: list[T]
    meta: PageMeta

    model_config = {
        "populate_by_name": True,
        "alias_generator": to_camel,
    }


def paginated(items: list, total: int, page: int, limit: int) -> dict:
    """Build a paginated response dict for use with ListResponse."""
    return {
        "data": items,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": math.ceil(total / limit) if limit else 1,
        },
    }
