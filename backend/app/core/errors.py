import uuid
from typing import Any, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.enums import ErrorCode

ERROR_STATUS_MAP = {
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.HANDOVER_REVOKED: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.STALE_VERSION: 409,
    ErrorCode.DUPLICATE_SOURCE: 409,
    ErrorCode.IDEMPOTENCY_CONFLICT: 409,
    ErrorCode.EXTRACTION_IN_PROGRESS: 409,
    ErrorCode.APPROVAL_BLOCKED_CONFLICT: 409,
    ErrorCode.HANDOVER_IMMUTABLE: 409,
    ErrorCode.HANDOVER_NOT_APPROVED: 409,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.UNSUPPORTED_FILE_TYPE: 415,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.EMPTY_FILE: 422,
    ErrorCode.CORRUPT_FILE: 422,
    ErrorCode.NO_EXTRACTABLE_TEXT: 422,
    ErrorCode.CLAIM_NOT_ACCEPTABLE: 422,
    ErrorCode.GITHUB_URL_INVALID: 422,
    ErrorCode.GITHUB_RATE_LIMITED: 429,
    ErrorCode.GITHUB_UNAVAILABLE: 502,
    ErrorCode.AI_BAD_OUTPUT: 502,
    ErrorCode.AI_UNAVAILABLE: 503,
    ErrorCode.STORAGE_UNAVAILABLE: 503,
    ErrorCode.DATABASE_UNAVAILABLE: 503,
    ErrorCode.INTERNAL_ERROR: 500,
}


class ContinuityException(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Any] = None,
        status_code: Optional[int] = None,
    ):
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code or ERROR_STATUS_MAP.get(code, 400)
        super().__init__(message)


def build_error_response(
    code: str,
    message: str,
    details: Optional[Any] = None,
    status_code: int = 400,
    request_id: Optional[str] = None,
) -> JSONResponse:
    req_id = request_id or str(uuid.uuid4())
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": req_id,
        }
    }
    return JSONResponse(status_code=status_code, content=payload)


async def continuity_exception_handler(request: Request, exc: ContinuityException):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return build_error_response(
        code=exc.code.value if hasattr(exc.code, "value") else str(exc.code),
        message=exc.message,
        details=exc.details,
        status_code=exc.status_code,
        request_id=req_id,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return build_error_response(
        code=ErrorCode.VALIDATION_ERROR.value,
        message="Request validation error",
        details={"errors": exc.errors()},
        status_code=422,
        request_id=req_id,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    code_map = {
        401: ErrorCode.UNAUTHENTICATED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        413: ErrorCode.FILE_TOO_LARGE,
        415: ErrorCode.UNSUPPORTED_FILE_TYPE,
        422: ErrorCode.VALIDATION_ERROR,
        500: ErrorCode.INTERNAL_ERROR,
    }
    err_code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    msg = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    return build_error_response(
        code=err_code.value,
        message=msg,
        details=None,
        status_code=exc.status_code,
        request_id=req_id,
    )


async def generic_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    # Do not leak stack traces or internal secrets
    return build_error_response(
        code=ErrorCode.INTERNAL_ERROR.value,
        message="An unexpected error occurred. Please try again.",
        details=None,
        status_code=500,
        request_id=req_id,
    )
