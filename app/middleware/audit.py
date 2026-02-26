"""Audit logging middleware — records every state-changing request to audit_trail."""


import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Methods that mutate state
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

class AuditMiddleware(BaseHTTPMiddleware):
    """Logs all write operations.

    Each audit row is written asynchronously AFTER the response is sent so it
    never adds latency to the request. Failures in audit logging are caught and
    logged to stderr — they never raise to the caller.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000)

        if request.method in _WRITE_METHODS:
            # Fire-and-forget: don't await here so the response is not delayed
            import asyncio

            asyncio.create_task(
                self._record(request, response.status_code, duration_ms)
            )

        return response

    async def _record(
        self, request: Request, status_code: int, duration_ms: int
    ) -> None:
        """Persist an audit row. Swallows all errors to avoid cascading failures."""
        try:
            from app.core.config import settings

            user_id = None
            client_id = settings.default_client_id

            # Infer entity from path  e.g. /api/v1/vendors/123 → ("vendor", "123")
            parts = [p for p in request.url.path.strip("/").split("/") if p]
            entity_type = parts[-2] if len(parts) >= 2 else parts[-1] if parts else "unknown"
            entity_id = parts[-1] if len(parts) >= 2 else None

            from app.db.base import async_session_factory
            from app.domain.audit import AuditTrail

            async with async_session_factory() as session:
                session.add(
                    AuditTrail(
                        client_id=client_id or "unknown",
                        user_id=user_id,
                        ip_address=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                        action=f"{request.method}:{status_code}",
                        entity_type=entity_type.rstrip("s"),  # simple singularize
                        entity_id=entity_id if entity_id and len(entity_id) == 36 else None,
                        description=f"{request.method} {request.url.path} → {status_code} ({duration_ms}ms)",
                    )
                )
                await session.commit()
        except Exception as exc:  # pragma: no cover
            import sys

            print(f"[AuditMiddleware] error: {exc}", file=sys.stderr)
