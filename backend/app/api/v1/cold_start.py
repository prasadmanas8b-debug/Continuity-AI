from typing import List, Optional
from fastapi import APIRouter, Depends, Header

from app.api.v1.deps import (
    check_idempotency,
    get_current_user_id,
    require_project_membership,
    require_project_role,
    save_idempotency,
)
from app.cold_start.service import get_cold_start_summary, submit_cold_start_result
from app.core.errors import ContinuityException
from app.db.session import db
from app.schemas.enums import ColdStartOutcome, ErrorCode, UserRole
from app.schemas.models import (
    ColdStartResult,
    ColdStartResultRequest,
    ColdStartSummary,
    ColdStartTask,
)

router = APIRouter(tags=["ColdStart"])


@router.get("/handovers/{handover_id}/cold-start/tasks", response_model=List[ColdStartTask])
def get_cold_start_tasks(
    handover_id: str,
    user_id: str = Depends(get_current_user_id),
):
    h = db.query_one("SELECT * FROM handovers WHERE handover_id = ?", (handover_id,))
    if not h:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)

    mem = require_project_membership(h["project_id"], user_id)
    role = mem["role"]

    # Incoming member matching recipient role or manager preview
    if role == UserRole.INCOMING_MEMBER.value:
        if mem.get("recipient_role") != h["recipient_role"]:
            raise ContinuityException(ErrorCode.NOT_FOUND, "Tasks not found for your role", status_code=404)
        if h["status"] != "approved":
            raise ContinuityException(ErrorCode.HANDOVER_NOT_APPROVED, "Handover not approved", status_code=409)
    elif role != UserRole.MANAGER.value:
        raise ContinuityException(ErrorCode.FORBIDDEN, "Not authorized to access cold start tasks", status_code=403)

    task_rows = db.query_all(
        """
        SELECT task_id, handover_id, ordinal, task_prompt 
        FROM cold_start_tasks 
        WHERE handover_id = ? 
        ORDER BY ordinal ASC
        """,
        (handover_id,),
    )
    # Never return expected_reference to client!
    return [
        ColdStartTask(
            task_id=t["task_id"],
            handover_id=t["handover_id"],
            ordinal=t["ordinal"],
            task_prompt=t["task_prompt"],
        )
        for t in task_rows
    ]


@router.post("/cold-start/tasks/{task_id}/results", response_model=ColdStartResult, status_code=201)
def record_cold_start_result(
    task_id: str,
    req: ColdStartResultRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user_id: str = Depends(get_current_user_id),
):
    cached = check_idempotency(idempotency_key, user_id, f"cold_start:{task_id}", req.dict())
    if cached:
        return cached

    result = submit_cold_start_result(
        task_id=task_id,
        tester_id=user_id,
        outcome=req.outcome,
        time_seconds=req.time_seconds,
        hints_used=req.hints_used,
        missing_information=req.missing_information,
    )

    formatted = ColdStartResult(
        result_id=result["result_id"],
        task_id=result["task_id"],
        tester_id=result["tester_id"],
        outcome=ColdStartOutcome(result["outcome"]),
        time_seconds=result["time_seconds"],
        hints_used=result["hints_used"],
        missing_information=result.get("missing_information"),
        created_at=result["created_at"],
    )
    save_idempotency(idempotency_key, user_id, f"cold_start:{task_id}", req.dict(), 201, formatted.dict())
    return formatted


@router.get("/handovers/{handover_id}/cold-start/summary", response_model=ColdStartSummary)
def get_summary(
    handover_id: str,
    user_id: str = Depends(get_current_user_id),
):
    h = db.query_one("SELECT * FROM handovers WHERE handover_id = ?", (handover_id,))
    if not h:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)

    require_project_role(h["project_id"], user_id, [UserRole.MANAGER])
    summary_data = get_cold_start_summary(handover_id)
    return ColdStartSummary(**summary_data)
