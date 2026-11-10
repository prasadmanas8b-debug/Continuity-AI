import json
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile

from app.api.v1.deps import (
    check_idempotency,
    get_current_user_id,
    require_project_membership,
    require_project_role,
    save_idempotency,
)
from app.audit.service import record_audit
from app.core.errors import ContinuityException
from app.db.session import db
from app.ingestion.service import ingest_github_repository, ingest_uploaded_file
from app.schemas.enums import ErrorCode, IngestionStatus, Sensitivity, SourceType, UserRole
from app.schemas.models import (
    GitHubImportRequest,
    GitHubImportResponse,
    Source,
    SourceExcerptResponse,
    SourceListResponse,
)

router = APIRouter(tags=["Sources"])


def _format_source_row(r: dict) -> Source:
    roles = json.loads(r["audience_roles"]) if isinstance(r.get("audience_roles"), str) else (r.get("audience_roles") or [])
    return Source(
        source_id=r["source_id"],
        project_id=r["project_id"],
        source_type=SourceType(r["source_type"]),
        filename=r["filename"],
        source_reference=r["source_reference"],
        content_hash=r["content_hash"],
        sensitivity=Sensitivity(r["sensitivity"]),
        audience_roles=roles,
        ingestion_status=IngestionStatus(r["ingestion_status"]),
        error_message=r.get("error_message"),
        document_date=r.get("document_date"),
        size_bytes=r["size_bytes"],
        created_at=r["created_at"],
    )


@router.get("/projects/{project_id}/sources", response_model=SourceListResponse)
def list_sources(
    project_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
):
    mem = require_project_role(project_id, user_id, [UserRole.MANAGER, UserRole.CONTRIBUTOR])
    role = mem["role"]

    if role == UserRole.MANAGER.value:
        rows = db.query_all(
            """
            SELECT * FROM sources 
            WHERE project_id = ? AND ingestion_status <> 'archived'
            ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
            (project_id, limit, offset),
        )
        total = db.query_one(
            "SELECT COUNT(*) as t FROM sources WHERE project_id = ? AND ingestion_status <> 'archived'",
            (project_id,),
        )["t"]
    else:
        # Contributor sees normal sensitivity only
        rows = db.query_all(
            """
            SELECT * FROM sources 
            WHERE project_id = ? AND sensitivity = 'normal' AND ingestion_status <> 'archived'
            ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
            (project_id, limit, offset),
        )
        total = db.query_one(
            "SELECT COUNT(*) as t FROM sources WHERE project_id = ? AND sensitivity = 'normal' AND ingestion_status <> 'archived'",
            (project_id,),
        )["t"]

    items = [_format_source_row(r) for r in rows]
    return SourceListResponse(items=items, total=total)


@router.post("/projects/{project_id}/sources/upload", response_model=Source, status_code=201)
async def upload_source(
    project_id: str,
    file: UploadFile = File(...),
    document_date: Optional[str] = Form(None),
    sensitivity: Optional[str] = Form("normal"),
    audience_roles: Optional[str] = Form(None),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user_id: str = Depends(get_current_user_id),
):
    require_project_role(project_id, user_id, [UserRole.MANAGER, UserRole.CONTRIBUTOR])

    content = await file.read()
    raw_hash = f"{file.filename}:{len(content)}"
    cached = check_idempotency(idempotency_key, user_id, f"upload:{project_id}", raw_hash)
    if cached:
        return cached

    sens_enum = Sensitivity(sensitivity) if sensitivity in (s.value for s in Sensitivity) else Sensitivity.NORMAL
    roles_list = [r.strip() for r in audience_roles.split(",") if r.strip()] if audience_roles else []

    row = ingest_uploaded_file(
        project_id=project_id,
        actor_id=user_id,
        raw_bytes=content,
        original_filename=file.filename or "uploaded_file",
        document_date=document_date,
        sensitivity=sens_enum,
        audience_roles=roles_list,
    )
    formatted = _format_source_row(row)
    save_idempotency(idempotency_key, user_id, f"upload:{project_id}", raw_hash, 201, formatted.dict())
    return formatted


@router.post("/projects/{project_id}/sources/github", response_model=GitHubImportResponse, status_code=201)
def import_github(
    project_id: str,
    req: GitHubImportRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user_id: str = Depends(get_current_user_id),
):
    require_project_role(project_id, user_id, [UserRole.MANAGER, UserRole.CONTRIBUTOR])

    cached = check_idempotency(idempotency_key, user_id, f"github:{project_id}", req.dict())
    if cached:
        return cached

    sources, skipped = ingest_github_repository(
        project_id=project_id,
        actor_id=user_id,
        repo_url=req.repo_url,
        sensitivity=req.sensitivity or Sensitivity.NORMAL,
        audience_roles=req.audience_roles or [],
    )

    formatted_sources = [_format_source_row(s) for s in sources]
    resp = GitHubImportResponse(sources=formatted_sources, skipped=skipped)
    save_idempotency(idempotency_key, user_id, f"github:{project_id}", req.dict(), 201, resp.dict())
    return resp


@router.get("/sources/{source_id}", response_model=Source)
def get_source_detail(
    source_id: str,
    user_id: str = Depends(get_current_user_id),
):
    source = db.query_one("SELECT * FROM sources WHERE source_id = ?", (source_id,))
    if not source:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Source not found", status_code=404)

    mem = require_project_membership(source["project_id"], user_id)
    if mem["role"] == UserRole.INCOMING_MEMBER.value:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Source not found", status_code=404)
    if mem["role"] == UserRole.CONTRIBUTOR.value and source["sensitivity"] == Sensitivity.RESTRICTED.value:
        # Restricted records not revealed to contributors (return 404, not 403)
        raise ContinuityException(ErrorCode.NOT_FOUND, "Source not found", status_code=404)

    return _format_source_row(source)


@router.get("/sources/{source_id}/excerpt", response_model=SourceExcerptResponse)
def get_source_excerpt(
    source_id: str,
    char_start: int = Query(..., ge=0),
    char_end: int = Query(..., ge=0),
    user_id: str = Depends(get_current_user_id),
):
    source = db.query_one("SELECT * FROM sources WHERE source_id = ?", (source_id,))
    if not source:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Source not found", status_code=404)

    mem = require_project_membership(source["project_id"], user_id)
    if mem["role"] == UserRole.INCOMING_MEMBER.value:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Source not found", status_code=404)
    if mem["role"] == UserRole.CONTRIBUTOR.value and source["sensitivity"] == Sensitivity.RESTRICTED.value:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Source not found", status_code=404)

    if char_end < char_start:
        raise ContinuityException(ErrorCode.VALIDATION_ERROR, "char_end must be >= char_start", status_code=422)

    # Max window 2000 chars per 7.5
    if char_end - char_start > 2000:
        char_end = char_start + 2000

    text_row = db.query_one("SELECT text FROM source_texts WHERE source_id = ?", (source_id,))
    full_text = text_row["text"] if text_row else ""
    excerpt_text = full_text[char_start:char_end]

    return SourceExcerptResponse(
        text=excerpt_text,
        char_start=char_start,
        char_end=char_start + len(excerpt_text),
    )


@router.post("/sources/{source_id}/archive", response_model=Source)
def archive_source(
    source_id: str,
    user_id: str = Depends(get_current_user_id),
):
    source = db.query_one("SELECT * FROM sources WHERE source_id = ?", (source_id,))
    if not source:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Source not found", status_code=404)

    require_project_role(source["project_id"], user_id, [UserRole.MANAGER])

    with db.transaction() as cur:
        cur.execute(
            "UPDATE sources SET ingestion_status = 'archived' WHERE source_id = ?",
            (source_id,),
        )
        record_audit(
            cur,
            actor_id=user_id,
            project_id=source["project_id"],
            action="source.archived",
            entity_type="source",
            entity_id=source_id,
            summary=f"Archived source {source_id}",
        )

    updated = db.query_one("SELECT * FROM sources WHERE source_id = ?", (source_id,))
    return _format_source_row(updated)
