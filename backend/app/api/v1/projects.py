import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import (
    get_current_user_id,
    require_project_membership,
    require_project_role,
)
from app.audit.service import record_audit
from app.core.errors import ContinuityException
from app.db.session import db, get_utc_now
from app.schemas.enums import ErrorCode, RecipientRole, UserRole
from app.schemas.models import (
    MemberItem,
    MemberRevokeResponse,
    Project,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectMembersResponse,
    ProjectSummary,
)

router = APIRouter(tags=["Projects"])


def _build_project_summary(proj: dict, user_id: str) -> ProjectSummary:
    pid = proj["project_id"]
    membership = db.query_one(
        "SELECT role FROM project_memberships WHERE project_id = ? AND user_id = ? AND membership_status = 'active'",
        (pid, user_id),
    )
    my_role = UserRole(membership["role"]) if membership else UserRole.CONTRIBUTOR

    src_count = db.query_one(
        "SELECT COUNT(*) as c FROM sources WHERE project_id = ? AND ingestion_status <> 'archived'",
        (pid,),
    )["c"]
    claim_count = db.query_one(
        "SELECT COUNT(*) as c FROM claims WHERE project_id = ? AND archived = 0",
        (pid,),
    )["c"]
    open_conf_count = db.query_one(
        "SELECT COUNT(*) as c FROM conflicts WHERE project_id = ? AND status IN ('open', 'unresolved')",
        (pid,),
    )["c"]
    pending_rev_count = db.query_one(
        "SELECT COUNT(*) as c FROM claims WHERE project_id = ? AND archived = 0 AND review_status = 'pending'",
        (pid,),
    )["c"]
    latest_handover = db.query_one(
        "SELECT MAX(version) as mv FROM handovers WHERE project_id = ? AND status = 'approved'",
        (pid,),
    )["mv"]

    return ProjectSummary(
        project_id=proj["project_id"],
        name=proj["name"],
        description=proj["description"],
        created_at=proj["created_at"],
        updated_at=proj["updated_at"],
        source_count=src_count,
        claim_count=claim_count,
        open_conflict_count=open_conf_count,
        pending_review_count=pending_rev_count,
        latest_handover_version=latest_handover,
        my_role=my_role,
    )


@router.get("/projects", response_model=ProjectListResponse)
def list_projects(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
):
    rows = db.query_all(
        """
        SELECT p.* 
        FROM projects p
        JOIN project_memberships pm ON p.project_id = pm.project_id
        WHERE pm.user_id = ? AND pm.membership_status = 'active'
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, limit, offset),
    )
    total = db.query_one(
        """
        SELECT COUNT(*) as t 
        FROM projects p
        JOIN project_memberships pm ON p.project_id = pm.project_id
        WHERE pm.user_id = ? AND pm.membership_status = 'active'
        """,
        (user_id,),
    )["t"]

    items = [_build_project_summary(r, user_id) for r in rows]
    return ProjectListResponse(items=items, total=total)


@router.post("/projects", response_model=Project, status_code=201)
def create_project(
    req: ProjectCreateRequest,
    user_id: str = Depends(get_current_user_id),
):
    # Addendum A9: allowed for any authenticated user who is not exclusively an incoming member
    memberships = db.query_all(
        "SELECT role FROM project_memberships WHERE user_id = ? AND membership_status = 'active'",
        (user_id,),
    )
    if memberships and all(m["role"] == UserRole.INCOMING_MEMBER.value for m in memberships):
        raise ContinuityException(
            code=ErrorCode.FORBIDDEN,
            message="Incoming members cannot create projects",
            status_code=403,
        )

    project_id = str(uuid.uuid4())
    now = get_utc_now()
    with db.transaction() as cur:
        cur.execute(
            """
            INSERT INTO projects (project_id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, req.name, req.description, now, now),
        )
        cur.execute(
            """
            INSERT INTO project_memberships (project_id, user_id, role, recipient_role, membership_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, user_id, UserRole.MANAGER.value, None, "active", now),
        )
        record_audit(
            cur,
            actor_id=user_id,
            project_id=project_id,
            action="project.created",
            entity_type="project",
            entity_id=project_id,
            summary=f"Created project {req.name}",
        )

    proj = db.query_one("SELECT * FROM projects WHERE project_id = ?", (project_id,))
    return Project(**proj)


@router.get("/projects/{project_id}", response_model=ProjectSummary)
def get_project_summary(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
):
    membership = require_project_membership(project_id, user_id)
    if membership["role"] == UserRole.INCOMING_MEMBER.value:
        raise ContinuityException(ErrorCode.FORBIDDEN, "Incoming members cannot view project summary", status_code=403)

    proj = db.query_one("SELECT * FROM projects WHERE project_id = ?", (project_id,))
    return _build_project_summary(proj, user_id)


@router.get("/projects/{project_id}/members", response_model=ProjectMembersResponse)
def get_project_members(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
):
    require_project_role(project_id, user_id, [UserRole.MANAGER])
    rows = db.query_all(
        """
        SELECT u.user_id, u.display_name, u.email, pm.role, pm.recipient_role,
               pm.membership_status, pm.created_at, pm.revoked_at
        FROM project_memberships pm
        JOIN users u ON pm.user_id = u.user_id
        WHERE pm.project_id = ?
        ORDER BY pm.created_at ASC
        """,
        (project_id,),
    )
    items = [
        MemberItem(
            user_id=r["user_id"],
            display_name=r["display_name"],
            email=r["email"],
            role=UserRole(r["role"]),
            recipient_role=RecipientRole(r["recipient_role"]) if r.get("recipient_role") else None,
            membership_status=r["membership_status"],
            created_at=r["created_at"],
            revoked_at=r["revoked_at"],
        )
        for r in rows
    ]
    return ProjectMembersResponse(items=items, total=len(items))


@router.post("/projects/{project_id}/members/{target_user_id}/revoke", response_model=MemberRevokeResponse)
def revoke_member(
    project_id: str,
    target_user_id: str,
    user_id: str = Depends(get_current_user_id),
):
    require_project_role(project_id, user_id, [UserRole.MANAGER])
    target_mem = db.query_one(
        "SELECT * FROM project_memberships WHERE project_id = ? AND user_id = ?",
        (project_id, target_user_id),
    )
    if not target_mem:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Member not found in project", status_code=404)

    now = get_utc_now()
    with db.transaction() as cur:
        cur.execute(
            """
            UPDATE project_memberships 
            SET membership_status = 'revoked', revoked_at = ?
            WHERE project_id = ? AND user_id = ?
            """,
            (now, project_id, target_user_id),
        )
        # Revoke handovers created by or intended for this member if incoming
        cur.execute(
            """
            UPDATE handovers 
            SET status = 'revoked'
            WHERE project_id = ? AND created_by = ?
            """,
            (project_id, target_user_id),
        )
        record_audit(
            cur,
            actor_id=user_id,
            project_id=project_id,
            action="member.revoked",
            entity_type="membership",
            entity_id=target_user_id,
            summary=f"Revoked membership for user {target_user_id}",
        )

    return MemberRevokeResponse(status="revoked")
