import json
from fastapi import APIRouter, Depends, Response

from app.api.v1.deps import get_current_user_id, require_project_role
from app.core.errors import ContinuityException
from app.db.session import db
from app.extraction.service import start_extraction_run
from app.schemas.enums import ErrorCode, ExtractionRunStatus, UserRole
from app.schemas.models import ExtractionRun, ExtractionRunCreateRequest

router = APIRouter(tags=["Extractions"])


def _format_run_row(r: dict) -> ExtractionRun:
    source_ids = json.loads(r["source_ids"]) if isinstance(r.get("source_ids"), str) else (r.get("source_ids") or [])
    return ExtractionRun(
        run_id=r["run_id"],
        project_id=r["project_id"],
        status=ExtractionRunStatus(r["status"]),
        source_ids=source_ids,
        claims_created=r["claims_created"],
        claims_rejected_by_validation=r["claims_rejected_by_validation"],
        error_code=r.get("error_code"),
        error_message=r.get("error_message"),
        started_at=r["started_at"],
        finished_at=r.get("finished_at"),
    )


@router.post("/projects/{project_id}/extractions", response_model=ExtractionRun, status_code=202)
def create_extraction_run(
    project_id: str,
    req: ExtractionRunCreateRequest,
    user_id: str = Depends(get_current_user_id),
):
    require_project_role(project_id, user_id, [UserRole.MANAGER, UserRole.CONTRIBUTOR])
    run_dict = start_extraction_run(
        project_id=project_id,
        actor_id=user_id,
        source_ids=req.source_ids,
    )
    return _format_run_row(run_dict)


@router.get("/extractions/{run_id}", response_model=ExtractionRun)
def get_extraction_run(
    run_id: str,
    user_id: str = Depends(get_current_user_id),
):
    run = db.query_one("SELECT * FROM extraction_runs WHERE run_id = ?", (run_id,))
    if not run:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Extraction run not found", status_code=404)

    require_project_role(run["project_id"], user_id, [UserRole.MANAGER, UserRole.CONTRIBUTOR])
    return _format_run_row(run)
