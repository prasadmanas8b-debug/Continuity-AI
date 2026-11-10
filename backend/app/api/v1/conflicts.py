from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import (
    get_current_user_id,
    require_project_membership,
    require_project_role,
)
from app.audit.service import record_audit
from app.core.errors import ContinuityException
from app.db.session import db, get_utc_now
from app.schemas.enums import (
    ConflictRecordStatus,
    ConflictStatus,
    ConflictType,
    ErrorCode,
    FactType,
    UserRole,
)
from app.schemas.models import (
    Conflict,
    ConflictListResponse,
    ConflictResolutionRequest,
)
from app.api.v1.claims import _hydrate_claim

router = APIRouter(tags=["Conflicts"])


def _hydrate_conflict(c: dict) -> Conflict:
    cid = c["conflict_id"]
    claim_rows = db.query_all(
        """
        SELECT c.* 
        FROM claims c
        JOIN conflict_claims cc ON c.claim_id = cc.claim_id
        WHERE cc.conflict_id = ? AND c.archived = 0
        ORDER BY c.created_at ASC
        """,
        (cid,),
    )
    claims = [_hydrate_claim(r) for r in claim_rows]

    return Conflict(
        conflict_id=c["conflict_id"],
        project_id=c["project_id"],
        item_id=c["item_id"],
        fact_type=FactType(c["fact_type"]),
        conflict_type=ConflictType(c["conflict_type"]),
        status=ConflictRecordStatus(c["status"]),
        is_critical=bool(c["is_critical"]),
        summary=c["summary"],
        resolution_note=c.get("resolution_note"),
        claims=claims,
        created_at=c["created_at"],
        resolved_at=c.get("resolved_at"),
    )


@router.get("/projects/{project_id}/conflicts", response_model=ConflictListResponse)
def list_conflicts(
    project_id: str,
    status: Optional[ConflictRecordStatus] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
):
    require_project_role(project_id, user_id, [UserRole.MANAGER, UserRole.CONTRIBUTOR])

    conditions = ["project_id = ?"]
    params: List[object] = [project_id]

    if status:
        conditions.append("status = ?")
        params.append(status.value)

    where_clause = " AND ".join(conditions)
    total = db.query_one(f"SELECT COUNT(*) as t FROM conflicts WHERE {where_clause}", tuple(params))["t"]

    query = f"""
    SELECT * FROM conflicts 
    WHERE {where_clause}
    ORDER BY is_critical DESC, created_at DESC
    LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    rows = db.query_all(query, tuple(params))

    items = [_hydrate_conflict(r) for r in rows]
    return ConflictListResponse(items=items, total=total)


@router.get("/conflicts/{conflict_id}", response_model=Conflict)
def get_conflict_detail(
    conflict_id: str,
    user_id: str = Depends(get_current_user_id),
):
    conf = db.query_one("SELECT * FROM conflicts WHERE conflict_id = ?", (conflict_id,))
    if not conf:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Conflict not found", status_code=404)

    require_project_role(conf["project_id"], user_id, [UserRole.MANAGER, UserRole.CONTRIBUTOR])
    return _hydrate_conflict(conf)


@router.post("/conflicts/{conflict_id}/resolution", response_model=Conflict)
def resolve_conflict(
    conflict_id: str,
    req: ConflictResolutionRequest,
    user_id: str = Depends(get_current_user_id),
):
    conf = db.query_one("SELECT * FROM conflicts WHERE conflict_id = ?", (conflict_id,))
    if not conf:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Conflict not found", status_code=404)

    require_project_role(conf["project_id"], user_id, [UserRole.MANAGER])

    # Validation
    if req.status == ConflictRecordStatus.RESOLVED and (not req.resolution_note or not req.resolution_note.strip()):
        raise ContinuityException(
            code=ErrorCode.VALIDATION_ERROR,
            message="Resolution note is required when status is resolved",
            status_code=422,
        )

    now = get_utc_now()
    with db.transaction() as cur:
        cur.execute(
            """
            UPDATE conflicts 
            SET status = ?, resolution_note = ?, resolved_by = ?, resolved_at = ?
            WHERE conflict_id = ?
            """,
            (
                req.status.value,
                req.resolution_note.strip() if req.resolution_note else None,
                user_id if req.status == ConflictRecordStatus.RESOLVED else None,
                now if req.status == ConflictRecordStatus.RESOLVED else None,
                conflict_id,
            ),
        )

        # Handle superseded claim if provided
        if req.superseded_claim_id:
            # Check claim belongs to conflict
            in_conf = db.query_one(
                "SELECT * FROM conflict_claims WHERE conflict_id = ? AND claim_id = ?",
                (conflict_id, req.superseded_claim_id),
            )
            if in_conf:
                cur.execute(
                    """
                    UPDATE claims 
                    SET conflict_status = 'superseded', version = version + 1, updated_at = ?
                    WHERE claim_id = ?
                    """,
                    (now, req.superseded_claim_id),
                )

        record_audit(
            cur,
            actor_id=user_id,
            project_id=conf["project_id"],
            action="conflict.resolved",
            entity_type="conflict",
            entity_id=conflict_id,
            summary=f"Conflict {conflict_id} updated to status {req.status.value}",
        )

    updated = db.query_one("SELECT * FROM conflicts WHERE conflict_id = ?", (conflict_id,))
    return _hydrate_conflict(updated)
