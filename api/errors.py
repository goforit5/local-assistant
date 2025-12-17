"""Standardized error handling for FastAPI following RFC 7807 Problem Details."""

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.error_codes import ErrorCode, get_status_code

logger = logging.getLogger(__name__)


class ProblemDetails(BaseModel):
    """
    RFC 7807 Problem Details for HTTP APIs.

    See: https://tools.ietf.org/html/rfc7807
    """
    type: str = Field(
        ...,
        description="URI reference that identifies the problem type"
    )
    title: str = Field(
        ...,
        description="Short, human-readable summary of the problem"
    )
    status: int = Field(
        ...,
        description="HTTP status code"
    )
    detail: str = Field(
        ...,
        description="Human-readable explanation specific to this occurrence"
    )
    instance: str = Field(
        ...,
        description="URI reference identifying the specific occurrence"
    )
    error_code: str = Field(
        ...,
        description="Application-specific error code for client handling"
    )
    request_id: str = Field(
        ...,
        description="Unique request identifier for tracing"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "https://api.local-assistant.dev/errors/document-not-found",
                "title": "Document Not Found",
                "status": 404,
                "detail": "Document with ID 'doc-123' does not exist",
                "instance": "/api/v1/documents/doc-123",
                "error_code": "DOCUMENT_NOT_FOUND",
                "request_id": "req-abc123def456"
            }
        }


class AppException(Exception):
    """Base exception class for application errors."""

    def __init__(
        self,
        detail: str,
        error_code: ErrorCode,
        title: Optional[str] = None,
        status_code: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize application exception.

        Args:
            detail: Human-readable error description
            error_code: Application error code
            title: Short error title (defaults to error_code)
            status_code: HTTP status code (defaults based on error_code)
            extra: Additional context data
        """
        self.detail = detail
        self.error_code = error_code
        self.title = title or error_code.value.replace("_", " ").title()
        self.status_code = status_code or get_status_code(error_code)
        self.extra = extra or {}
        super().__init__(detail)


class DocumentNotFoundError(AppException):
    """Document not found exception."""

    def __init__(self, document_id: str, detail: Optional[str] = None):
        super().__init__(
            detail=detail or f"Document with ID '{document_id}' does not exist",
            error_code=ErrorCode.DOCUMENT_NOT_FOUND,
            title="Document Not Found",
            extra={"document_id": document_id}
        )


class VendorNotFoundError(AppException):
    """Vendor not found exception."""

    def __init__(self, vendor_id: str, detail: Optional[str] = None):
        super().__init__(
            detail=detail or f"Vendor with ID '{vendor_id}' does not exist",
            error_code=ErrorCode.VENDOR_NOT_FOUND,
            title="Vendor Not Found",
            extra={"vendor_id": vendor_id}
        )


class CommitmentNotFoundError(AppException):
    """Commitment not found exception."""

    def __init__(self, commitment_id: str, detail: Optional[str] = None):
        super().__init__(
            detail=detail or f"Commitment with ID '{commitment_id}' does not exist",
            error_code=ErrorCode.COMMITMENT_NOT_FOUND,
            title="Commitment Not Found",
            extra={"commitment_id": commitment_id}
        )


class InteractionNotFoundError(AppException):
    """Interaction not found exception."""

    def __init__(self, interaction_id: str, detail: Optional[str] = None):
        super().__init__(
            detail=detail or f"Interaction with ID '{interaction_id}' does not exist",
            error_code=ErrorCode.INTERACTION_NOT_FOUND,
            title="Interaction Not Found",
            extra={"interaction_id": interaction_id}
        )


class ValidationError(AppException):
    """Validation error exception."""

    def __init__(self, detail: str, field: Optional[str] = None):
        extra = {"field": field} if field else {}
        super().__init__(
            detail=detail,
            error_code=ErrorCode.VALIDATION_ERROR,
            title="Validation Error",
            extra=extra
        )


class RateLimitExceededError(AppException):
    """Rate limit exceeded exception."""

    def __init__(
        self,
        detail: Optional[str] = None,
        retry_after: Optional[int] = None
    ):
        extra = {"retry_after": retry_after} if retry_after else {}
        super().__init__(
            detail=detail or "Rate limit exceeded. Please retry after some time.",
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            title="Rate Limit Exceeded",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            extra=extra
        )


class CircuitBreakerOpenError(AppException):
    """Circuit breaker open exception."""

    def __init__(self, service: str, detail: Optional[str] = None):
        super().__init__(
            detail=detail or f"Service '{service}' is temporarily unavailable due to repeated failures",
            error_code=ErrorCode.CIRCUIT_BREAKER_OPEN,
            title="Service Temporarily Unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            extra={"service": service}
        )


class ProviderError(AppException):
    """Provider (AI service) error exception."""

    def __init__(self, provider: str, detail: str, original_error: Optional[str] = None):
        error_code_map = {
            "anthropic": ErrorCode.ANTHROPIC_ERROR,
            "openai": ErrorCode.OPENAI_ERROR,
            "google": ErrorCode.GOOGLE_ERROR,
        }
        extra = {"provider": provider}
        if original_error:
            extra["original_error"] = original_error

        super().__init__(
            detail=detail,
            error_code=error_code_map.get(provider.lower(), ErrorCode.PROVIDER_ERROR),
            title=f"{provider.title()} Provider Error",
            status_code=status.HTTP_502_BAD_GATEWAY,
            extra=extra
        )


def create_problem_details(
    request: Request,
    error_code: ErrorCode,
    title: str,
    detail: str,
    status_code: int,
    request_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
) -> ProblemDetails:
    """
    Create RFC 7807 Problem Details response.

    Args:
        request: FastAPI request object
        error_code: Application error code
        title: Short error title
        detail: Detailed error description
        status_code: HTTP status code
        request_id: Request ID for tracing
        extra: Additional context data

    Returns:
        ProblemDetails object
    """
    req_id = request_id or str(uuid.uuid4())

    # Log error with structured logging
    logger.error(
        "API error occurred",
        extra={
            "request_id": req_id,
            "error_code": error_code.value,
            "status_code": status_code,
            "path": str(request.url.path),
            "method": request.method,
            "detail": detail,
            **(extra or {})
        }
    )

    problem = ProblemDetails(
        type=f"https://api.local-assistant.dev/errors/{error_code.value.lower().replace('_', '-')}",
        title=title,
        status=status_code,
        detail=detail,
        instance=str(request.url.path),
        error_code=error_code.value,
        request_id=req_id
    )

    # Add extra fields if provided
    if extra:
        for key, value in extra.items():
            setattr(problem, key, value)

    return problem


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Global exception handler for AppException and its subclasses.

    Args:
        request: FastAPI request object
        exc: Application exception

    Returns:
        JSONResponse with RFC 7807 Problem Details
    """
    request_id = getattr(request.state, "request_id", None)

    problem = create_problem_details(
        request=request,
        error_code=exc.error_code,
        title=exc.title,
        detail=exc.detail,
        status_code=exc.status_code,
        request_id=request_id,
        extra=exc.extra
    )

    headers = {}
    if exc.error_code == ErrorCode.RATE_LIMIT_EXCEEDED and "retry_after" in exc.extra:
        headers["Retry-After"] = str(exc.extra["retry_after"])

    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(exclude_none=True),
        headers=headers
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Generic exception handler for unhandled exceptions.

    Args:
        request: FastAPI request object
        exc: Unhandled exception

    Returns:
        JSONResponse with RFC 7807 Problem Details
    """
    request_id = getattr(request.state, "request_id", None)

    # Log full exception for debugging
    logger.exception(
        "Unhandled exception occurred",
        extra={
            "request_id": request_id,
            "path": str(request.url.path),
            "method": request.method,
            "exception_type": type(exc).__name__
        }
    )

    problem = create_problem_details(
        request=request,
        error_code=ErrorCode.INTERNAL_ERROR,
        title="Internal Server Error",
        detail="An unexpected error occurred. Please try again later.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        request_id=request_id,
        extra={"exception_type": type(exc).__name__}
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=problem.model_dump(exclude_none=True)
    )
