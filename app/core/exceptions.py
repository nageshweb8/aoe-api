"""Application-level exceptions and FastAPI exception handlers."""


from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, status_code: int = 500, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)

class NotFoundError(AppException):
    def __init__(self, entity: str, entity_id: str | None = None):
        msg = f"{entity} not found" if not entity_id else f"{entity} '{entity_id}' not found"
        super().__init__(msg, status_code=404, code="NOT_FOUND")

class ForbiddenError(AppException):
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, status_code=403, code="FORBIDDEN")

class UnauthorizedError(AppException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401, code="UNAUTHORIZED")

class ConflictError(AppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=409, code="CONFLICT")

class ValidationError(AppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=422, code="VALIDATION_ERROR")

class COIExtractionError(AppException):
    """Raised when the AI extraction call fails (upstream service error)."""

    def __init__(self, message: str):
        super().__init__(message, status_code=502, code="AI_EXTRACTION_ERROR")

# ---------------------------------------------------------------------------
# FastAPI exception handlers
# ---------------------------------------------------------------------------

def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}

def register_exception_handlers(app: FastAPI) -> None:
    """Attach all custom exception handlers to the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message),
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=_error_body("NOT_FOUND", "Resource not found"),
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_error_body("INTERNAL_ERROR", "An unexpected error occurred"),
        )
