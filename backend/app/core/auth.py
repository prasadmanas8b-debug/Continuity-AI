import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional
from fastapi import Depends, Header, HTTPException, Request

from app.core.config import settings
from app.core.errors import ContinuityException
from app.schemas.enums import ErrorCode, UserRole


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(user_id: str, expires_hours: Optional[int] = None) -> tuple[str, str]:
    hrs = expires_hours or settings.JWT_EXPIRES_HOURS
    now = int(time.time())
    exp = now + hrs * 3600
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user_id, "iat": now, "exp": exp}

    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    unsigned_token = f"{_b64_encode(header_bytes)}.{_b64_encode(payload_bytes)}"
    sig = hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        unsigned_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    token = f"{unsigned_token}.{_b64_encode(sig)}"

    # ISO-8601 UTC string for expires_at
    from datetime import datetime, timezone
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    return token, expires_at


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            raise ValueError("Malformed token")
        unsigned_token = f"{parts[0]}.{parts[1]}"
        expected_sig = hmac.new(
            settings.JWT_SECRET.encode("utf-8"),
            unsigned_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        actual_sig = _b64_decode(parts[2])
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("Invalid signature")

        payload_bytes = _b64_decode(parts[1])
        payload = json.loads(payload_bytes.decode("utf-8"))
        if "exp" in payload and payload["exp"] < int(time.time()):
            raise ValueError("Token expired")
        return payload
    except Exception as e:
        raise ContinuityException(
            code=ErrorCode.UNAUTHENTICATED,
            message="Missing, invalid or expired token",
            status_code=401,
        )


def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise ContinuityException(
            code=ErrorCode.UNAUTHENTICATED,
            message="Missing Authorization header",
            status_code=401,
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise ContinuityException(
            code=ErrorCode.UNAUTHENTICATED,
            message="Invalid Authorization header format. Expected Bearer <token>",
            status_code=401,
        )
    payload = decode_access_token(parts[1])
    user_id = payload.get("sub")
    if not user_id:
        raise ContinuityException(
            code=ErrorCode.UNAUTHENTICATED,
            message="Token subject missing",
            status_code=401,
        )
    return user_id
