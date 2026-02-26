"""Shared Pydantic schema base with camelCase aliases."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """All API schemas inherit from this to auto-generate camelCase aliases."""

    model_config = {
        "populate_by_name": True,
        "alias_generator": to_camel,
        "from_attributes": True,
    }


class HealthResponse(BaseModel):
    """Health-check response returned by /health."""
    status: str = "ok"
    app: str
    env: str
