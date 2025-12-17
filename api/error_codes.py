"""Error codes and HTTP status mappings for standardized error handling."""

from enum import Enum
from typing import Dict


class ErrorCode(str, Enum):
    """Standard error codes for the application."""

    # Client errors (4xx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    VENDOR_NOT_FOUND = "VENDOR_NOT_FOUND"
    COMMITMENT_NOT_FOUND = "COMMITMENT_NOT_FOUND"
    INTERACTION_NOT_FOUND = "INTERACTION_NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server errors (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    TIMEOUT = "TIMEOUT"

    # Provider-specific errors
    ANTHROPIC_ERROR = "ANTHROPIC_ERROR"
    OPENAI_ERROR = "OPENAI_ERROR"
    GOOGLE_ERROR = "GOOGLE_ERROR"


ERROR_STATUS_MAP: Dict[ErrorCode, int] = {
    # Client errors
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.DOCUMENT_NOT_FOUND: 404,
    ErrorCode.VENDOR_NOT_FOUND: 404,
    ErrorCode.COMMITMENT_NOT_FOUND: 404,
    ErrorCode.INTERACTION_NOT_FOUND: 404,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.CONFLICT: 409,
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,

    # Server errors
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    ErrorCode.CIRCUIT_BREAKER_OPEN: 503,
    ErrorCode.PROVIDER_ERROR: 502,
    ErrorCode.DATABASE_ERROR: 500,
    ErrorCode.TIMEOUT: 504,
    ErrorCode.ANTHROPIC_ERROR: 502,
    ErrorCode.OPENAI_ERROR: 502,
    ErrorCode.GOOGLE_ERROR: 502,
}


def get_status_code(error_code: ErrorCode) -> int:
    """Get HTTP status code for an error code."""
    return ERROR_STATUS_MAP.get(error_code, 500)
