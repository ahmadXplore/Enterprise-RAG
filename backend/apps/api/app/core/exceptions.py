"""Custom application exceptions and safe error handlers."""
from typing import Any

from apps.api.app.core.logging import logger
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    """Base exception for application errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Any = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(code="NOT_FOUND", message=message, status_code=status.HTTP_404_NOT_FOUND)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenException(AppException):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(code="FORBIDDEN", message=message, status_code=status.HTTP_403_FORBIDDEN)


class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(code="CONFLICT", message=message, status_code=status.HTTP_409_CONFLICT)


def get_request_id(request: Request) -> str:
    """Retrieve request ID from state or header."""
    return getattr(request.state, "request_id", request.headers.get("X-Request-ID", "unknown"))


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = get_request_id(request)
    logger.warning(
        f"Handled application exception: [{exc.code}] {exc.message}",
        extra={"extra": {"request_id": request_id, "code": exc.code}},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
            }
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = get_request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "request_id": request_id,
            }
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = get_request_id(request)
    # Sanitize validation errors to avoid leaking internal models
    clean_errors = []
    for err in exc.errors():
        clean_errors.append({
            "field": " -> ".join(str(loc) for loc in err.get("loc", [])),
            "issue": err.get("msg", "Invalid value"),
        })

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request payload validation failed.",
                "request_id": request_id,
                "details": clean_errors,
            }
        },
    )


async def database_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Safely catch database errors without leaking connection details (Rule 4, 10, 14)."""
    request_id = get_request_id(request)
    logger.error(
        f"Database operation error: {type(exc).__name__}",
        exc_info=exc,
        extra={"extra": {"request_id": request_id}},
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": {
                "code": "DATABASE_UNAVAILABLE",
                "message": "Database service is temporarily unavailable. Please try again later.",
                "request_id": request_id,
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled exceptions and log server-side without exposing trace to client."""
    request_id = get_request_id(request)
    logger.error(
        f"Unhandled server error: {str(exc)}",
        exc_info=exc,
        extra={"extra": {"request_id": request_id}},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": (
                    "An unexpected error occurred. Please contact support with the request ID."
                ),
                "request_id": request_id,
            }
        },
    )
