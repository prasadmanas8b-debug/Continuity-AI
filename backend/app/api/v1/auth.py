from typing import List
from fastapi import APIRouter, Depends

from app.api.v1.deps import get_current_user_id
from app.core.auth import create_access_token
from app.core.errors import ContinuityException
from app.db.session import db
from app.schemas.enums import ErrorCode, RecipientRole, UserRole
from app.schemas.models import (
    CurrentUserResponse,
    DemoLoginRequest,
    DemoLoginResponse,
    ProjectMembershipSummary,
    User,
)

router = APIRouter(tags=["Auth"])


@router.get("/auth/demo-users", response_model=List[User])
def list_demo_users():
    rows = db.query_all("SELECT user_id, display_name, email FROM users ORDER BY created_at ASC")
    return [User(**r) for r in rows]


@router.post("/auth/demo-login", response_model=DemoLoginResponse)
def demo_login(req: DemoLoginRequest):
    user = db.query_one("SELECT * FROM users WHERE user_id = ?", (req.user_id,))
    if not user:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Demo user not found", status_code=404)

    token, expires_at = create_access_token(req.user_id)
    membership_rows = db.query_all(
        """
        SELECT project_id, role, recipient_role 
        FROM project_memberships 
        WHERE user_id = ? AND membership_status = 'active'
        """,
        (req.user_id,),
    )
    memberships = [
        ProjectMembershipSummary(
            project_id=m["project_id"],
            role=UserRole(m["role"]),
            recipient_role=RecipientRole(m["recipient_role"]) if m.get("recipient_role") else None,
        )
        for m in membership_rows
    ]

    return DemoLoginResponse(
        access_token=token,
        token_type="bearer",
        expires_at=expires_at,
        user=User(user_id=user["user_id"], display_name=user["display_name"], email=user["email"]),
        memberships=memberships,
    )


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user_profile(user_id: str = Depends(get_current_user_id)):
    user = db.query_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if not user:
        raise ContinuityException(ErrorCode.NOT_FOUND, "User not found", status_code=404)

    membership_rows = db.query_all(
        """
        SELECT project_id, role, recipient_role 
        FROM project_memberships 
        WHERE user_id = ? AND membership_status = 'active'
        """,
        (user_id,),
    )
    memberships = [
        ProjectMembershipSummary(
            project_id=m["project_id"],
            role=UserRole(m["role"]),
            recipient_role=RecipientRole(m["recipient_role"]) if m.get("recipient_role") else None,
        )
        for m in membership_rows
    ]
    return CurrentUserResponse(
        user=User(user_id=user["user_id"], display_name=user["display_name"], email=user["email"]),
        memberships=memberships,
    )
