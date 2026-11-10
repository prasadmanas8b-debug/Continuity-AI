import json
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, Query

from app.api.v1.deps import (
    check_idempotency,
    get_current_user_id,
    require_project_membership,
    require_project_role,
    save_idempotency,
)
from app.core.errors import ContinuityException
from app.db.session import db
from app.handover.service import (
    approve_handover,
    create_handover_draft,
    get_handover_detail,
    get_handover_eligibility,
    get_handover_summary,
    refresh_handover_draft,
    revoke_handover,
)
from app.schemas.enums import (
    ErrorCode,
    HandoverStatus,
    RecipientRole,
    UserRole,
)
from app.schemas.models import (
    Eligibility,
    Handover,
    HandoverApproveRequest,
    HandoverCreateRequest,
    HandoverDetail,
    HandoverListResponse,
)

router = APIRouter(tags=["Handovers"])


def _format_handover_summary(h: dict) -> Handover:
    return Handover(
        handover_id=h["handover_id"],
        project_id=h["project_id"],
        version=h["version"],
        status=HandoverStatus(h["status"]),
        recipient_role=RecipientRole(h["recipient_role"]),
        included_claim_count=h["included_claim_count"],
        excluded_claim_count=h["excluded_claim_count"],
        approved_by=h.get("approved_by"),
        approved_at=h.get("approved_at"),
        approval_override=h.get("approval_override"),
        created_at=h["created_at"],
    )


@router.get("/projects/{project_id}/handovers", response_model=HandoverListResponse)
def list_handovers(
    project_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
):
    mem = require_project_membership(project_id, user_id)
    role = mem["role"]

    if role == UserRole.MANAGER.value:
        rows = db.query_all(
            """
            SELECT * FROM handovers 
            WHERE project_id = ? 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
            """,
            (project_id, limit, offset),
        )
        total = db.query_one(
            "SELECT COUNT(*) as t FROM handovers WHERE project_id = ?",
            (project_id,),
        )["t"]
    elif role == UserRole.INCOMING_MEMBER.value:
        # Addendum A8: approved (and revoked, flagged) handovers for their own recipient role only
        rec_role = mem.get("recipient_role")
        rows = db.query_all(
            """
            SELECT * FROM handovers 
            WHERE project_id = ? AND recipient_role = ? AND status IN ('approved', 'revoked')
            ORDER BY version DESC 
            LIMIT ? OFFSET ?
            """,
            (project_id, rec_role, limit, offset),
        )
        total = db.query_one(
            """
            SELECT COUNT(*) as t FROM handovers 
            WHERE project_id = ? AND recipient_role = ? AND status IN ('approved', 'revoked')
            """,
            (project_id, rec_role),
        )["t"]
    else:
        # Contributors do not see handovers
        return HandoverListResponse(items=[], total=0)

    items = [_format_handover_summary(get_handover_summary(r["handover_id"])) for r in rows]
    return HandoverListResponse(items=items, total=total)


@router.post("/projects/{project_id}/handovers", response_model=Handover, status_code=201)
def create_handover(
    project_id: str,
    req: HandoverCreateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user_id: str = Depends(get_current_user_id),
):
    require_project_role(project_id, user_id, [UserRole.MANAGER])

    cached = check_idempotency(idempotency_key, user_id, f"handover_create:{project_id}", req.dict())
    if cached:
        return cached

    summary = create_handover_draft(
        project_id=project_id,
        actor_id=user_id,
        recipient_role=req.recipient_role,
    )
    formatted = _format_handover_summary(summary)
    save_idempotency(idempotency_key, user_id, f"handover_create:{project_id}", req.dict(), 201, formatted.dict())
    return formatted


@router.post("/handovers/{handover_id}/refresh", response_model=Handover)
def refresh_handover(
    handover_id: str,
    user_id: str = Depends(get_current_user_id),
):
    h = db.query_one("SELECT project_id FROM handovers WHERE handover_id = ?", (handover_id,))
    if not h:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)
    require_project_role(h["project_id"], user_id, [UserRole.MANAGER])

    summary = refresh_handover_draft(handover_id, user_id)
    return _format_handover_summary(summary)


@router.get("/handovers/{handover_id}/eligibility", response_model=Eligibility)
def preview_eligibility(
    handover_id: str,
    user_id: str = Depends(get_current_user_id),
):
    h = db.query_one("SELECT project_id FROM handovers WHERE handover_id = ?", (handover_id,))
    if not h:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)
    require_project_role(h["project_id"], user_id, [UserRole.MANAGER])

    elig_data = get_handover_eligibility(handover_id)
    return Eligibility(**elig_data)


@router.post("/handovers/{handover_id}/approve", response_model=Handover)
def approve_handover_endpoint(
    handover_id: str,
    req: HandoverApproveRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user_id: str = Depends(get_current_user_id),
):
    h = db.query_one("SELECT project_id FROM handovers WHERE handover_id = ?", (handover_id,))
    if not h:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)
    require_project_role(h["project_id"], user_id, [UserRole.MANAGER])

    cached = check_idempotency(idempotency_key, user_id, f"handover_approve:{handover_id}", req.dict())
    if cached:
        return cached

    summary = approve_handover(
        handover_id=handover_id,
        actor_id=user_id,
        override_reason=req.override_reason,
    )
    formatted = _format_handover_summary(summary)
    save_idempotency(idempotency_key, user_id, f"handover_approve:{handover_id}", req.dict(), 200, formatted.dict())
    return formatted


@router.post("/handovers/{handover_id}/revoke", response_model=Handover)
def revoke_handover_endpoint(
    handover_id: str,
    user_id: str = Depends(get_current_user_id),
):
    h = db.query_one("SELECT project_id FROM handovers WHERE handover_id = ?", (handover_id,))
    if not h:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)
    require_project_role(h["project_id"], user_id, [UserRole.MANAGER])

    summary = revoke_handover(handover_id, user_id)
    return _format_handover_summary(summary)


@router.get("/handovers/{handover_id}", response_model=HandoverDetail)
def get_handover_view(
    handover_id: str,
    user_id: str = Depends(get_current_user_id),
):
    detail = get_handover_detail(handover_id, user_id)
    return HandoverDetail(**detail)
