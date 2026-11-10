import hashlib
import json
from typing import Any, Callable, Dict, List, Optional
from fastapi import Header, Request, Response
from fastapi.responses import JSONResponse

from app.core.auth import get_current_user_id
from app.core.errors import ContinuityException
from app.db.session import db, get_utc_now
from app.schemas.enums import ErrorCode, UserRole


def check_idempotency(
    key: Optional[str],
    actor_id: str,
    route: str,
    request_body: Any,
) -> Optional[JSONResponse]:
    if not key:
        return None

    body_bytes = json.dumps(request_body, sort_keys=True).encode("utf-8") if request_body is not None else b""
    body_hash = hashlib.sha256(body_bytes).hexdigest()

    existing = db.query_one(
        "SELECT * FROM idempotency_keys WHERE key = ? AND actor_id = ? AND route = ?",
        (key, actor_id, route),
    )
    if existing:
        if existing["request_hash"] != body_hash:
            raise ContinuityException(
                code=ErrorCode.IDEMPOTENCY_CONFLICT,
                message="Same Idempotency-Key reused with a different request payload",
                status_code=409,
            )
        # Return stored response
        content = json.loads(existing["response_body"])
        return JSONResponse(status_code=existing["response_status"], content=content)
    return None


def save_idempotency(
    key: Optional[str],
    actor_id: str,
    route: str,
    request_body: Any,
    response_status: int,
    response_content: Any,
):
    if not key:
        return
    body_bytes = json.dumps(request_body, sort_keys=True).encode("utf-8") if request_body is not None else b""
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    now = get_utc_now()
    with db.transaction() as cur:
        cur.execute(
            """
            INSERT OR REPLACE INTO idempotency_keys (
                key, actor_id, route, request_hash, response_status, response_body, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (key, actor_id, route, body_hash, response_status, json.dumps(response_content), now),
        )


def require_project_membership(project_id: str, user_id: str) -> Dict[str, Any]:
    membership = db.query_one(
        """
        SELECT * FROM project_memberships 
        WHERE project_id = ? AND user_id = ? AND membership_status = 'active'
        """,
        (project_id, user_id),
    )
    if not membership:
        # Check if project even exists or membership is revoked
        # Section 7.6 / 9.2: "A user whose membership is revoked gets 404 on everything in that project."
        raise ContinuityException(
            code=ErrorCode.NOT_FOUND,
            message="Project not found or membership revoked",
            status_code=404,
        )
    return membership


def require_project_role(project_id: str, user_id: str, allowed_roles: List[UserRole]) -> Dict[str, Any]:
    membership = require_project_membership(project_id, user_id)
    user_role = membership["role"]
    allowed_values = [r.value for r in allowed_roles]
    if user_role not in allowed_values:
        raise ContinuityException(
            code=ErrorCode.FORBIDDEN,
            message=f"Action not permitted for role {user_role}",
            status_code=403,
        )
    return membership
