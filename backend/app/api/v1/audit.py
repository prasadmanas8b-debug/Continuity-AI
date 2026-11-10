from typing import List
from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import get_current_user_id, require_project_role
from app.db.session import db
from app.schemas.enums import UserRole
from app.schemas.models import AuditEntry, AuditListResponse

router = APIRouter(tags=["Audit"])


@router.get("/projects/{project_id}/audit", response_model=AuditListResponse)
def list_audit_log(
    project_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
):
    require_project_role(project_id, user_id, [UserRole.MANAGER])

    total = db.query_one(
        "SELECT COUNT(*) as t FROM audit_log WHERE project_id = ?",
        (project_id,),
    )["t"]

    rows = db.query_all(
        """
        SELECT * FROM audit_log 
        WHERE project_id = ? 
        ORDER BY created_at DESC 
        LIMIT ? OFFSET ?
        """,
        (project_id, limit, offset),
    )

    items = [
        AuditEntry(
            audit_id=r["audit_id"],
            project_id=r["project_id"],
            actor_id=r["actor_id"],
            action=r["action"],
            entity_type=r["entity_type"],
            entity_id=r["entity_id"],
            summary=r["summary"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
    return AuditListResponse(items=items, total=total)
