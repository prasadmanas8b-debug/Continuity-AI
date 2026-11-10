import hashlib
import json
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.audit.service import record_audit
from app.core.config import settings
from app.core.errors import ContinuityException
from app.db.session import db, get_utc_now
from app.ingestion.github import GitHubClient
from app.ingestion.pdf import extract_pdf_text_and_offsets, extract_text_file_and_offsets
from app.schemas.enums import ErrorCode, IngestionStatus, Sensitivity, SourceType
from app.storage.local import storage_service


def sanitize_filename(filename: str) -> str:
    base = os.path.basename(filename)
    clean = "".join(ch for ch in base if ch.isprintable() and ch not in "/\\")
    return clean[:255] or "document"


def get_source_type_from_filename(filename: str) -> SourceType:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return SourceType.PDF
    elif lower.endswith(".txt"):
        return SourceType.TXT
    elif lower.endswith(".md"):
        return SourceType.MD
    elif lower.endswith(".docx"):
        raise ContinuityException(
            code=ErrorCode.UNSUPPORTED_FILE_TYPE,
            message="DOCX format is reserved for Round 3 and not supported in Round 2.",
            status_code=415,
        )
    else:
        raise ContinuityException(
            code=ErrorCode.UNSUPPORTED_FILE_TYPE,
            message="Only PDF, TXT and MD files are supported.",
            status_code=415,
        )


def ingest_uploaded_file(
    project_id: str,
    actor_id: str,
    raw_bytes: bytes,
    original_filename: str,
    document_date: Optional[str] = None,
    sensitivity: Sensitivity = Sensitivity.NORMAL,
    audience_roles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if len(raw_bytes) > settings.MAX_UPLOAD_BYTES:
        raise ContinuityException(
            code=ErrorCode.FILE_TOO_LARGE,
            message=f"This file is over 10 MB. Split it or upload a smaller file.",
            status_code=413,
        )

    if len(raw_bytes) == 0:
        raise ContinuityException(
            code=ErrorCode.EMPTY_FILE,
            message="The file is empty. Choose a file that contains text.",
            status_code=422,
        )

    clean_filename = sanitize_filename(original_filename)
    source_type = get_source_type_from_filename(clean_filename)

    if source_type == SourceType.PDF:
        text, page_offsets = extract_pdf_text_and_offsets(raw_bytes)
    else:
        text, page_offsets = extract_text_file_and_offsets(raw_bytes, clean_filename)

    content_hash = hashlib.sha256(raw_bytes).hexdigest()

    existing = db.query_one(
        """
        SELECT source_id FROM sources 
        WHERE project_id = ? AND content_hash = ? AND ingestion_status <> 'archived'
        """,
        (project_id, content_hash),
    )
    if existing:
        raise ContinuityException(
            code=ErrorCode.DUPLICATE_SOURCE,
            message="This content was already imported.",
            details={"existing_source_id": existing["source_id"]},
            status_code=409,
        )

    source_id = str(uuid.uuid4())
    storage_key = storage_service.save_file(raw_bytes)
    now = get_utc_now()
    roles = audience_roles if audience_roles is not None else []
    roles_json = json.dumps(roles)
    page_offsets_json = json.dumps(page_offsets)
    source_reference = clean_filename

    try:
        with db.transaction() as cur:
            cur.execute(
                """
                INSERT INTO sources (
                    source_id, project_id, source_type, filename, source_reference,
                    storage_key, content_hash, size_bytes, sensitivity, audience_roles,
                    ingestion_status, error_message, document_date, source_metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    project_id,
                    source_type.value,
                    clean_filename,
                    source_reference,
                    storage_key,
                    content_hash,
                    len(raw_bytes),
                    sensitivity.value,
                    roles_json,
                    IngestionStatus.PROCESSED.value,
                    None,
                    document_date,
                    "{}",
                    now,
                ),
            )
            cur.execute(
                """
                INSERT INTO source_texts (source_id, text, page_offsets)
                VALUES (?, ?, ?)
                """,
                (source_id, text, page_offsets_json),
            )
            record_audit(
                cur,
                actor_id=actor_id,
                project_id=project_id,
                action="source.imported",
                entity_type="source",
                entity_id=source_id,
                summary=f"Imported source {source_id} type {source_type.value}",
            )
    except Exception as e:
        storage_service.delete_file(storage_key)
        raise ContinuityException(
            code=ErrorCode.STORAGE_UNAVAILABLE,
            message="Failed to persist source record in database",
            status_code=503,
        )

    row = db.query_one("SELECT * FROM sources WHERE source_id = ?", (source_id,))
    row["audience_roles"] = json.loads(row["audience_roles"])
    row.pop("storage_key", None)
    row.pop("source_metadata", None)
    return row


def ingest_github_repository(
    project_id: str,
    actor_id: str,
    repo_url: str,
    sensitivity: Sensitivity = Sensitivity.NORMAL,
    audience_roles: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    client = GitHubClient()
    commit_sha, files = client.fetch_repo_files(repo_url)

    imported_sources = []
    skipped_files = []
    roles = audience_roles if audience_roles is not None else []
    roles_json = json.dumps(roles)

    for file_info in files:
        path = file_info["path"]
        raw_bytes = file_info["content"]

        if len(raw_bytes) == 0:
            skipped_files.append({"path": path, "reason": "File is empty"})
            continue

        try:
            text, page_offsets = extract_text_file_and_offsets(raw_bytes, path)
        except Exception as e:
            skipped_files.append({"path": path, "reason": str(e)})
            continue

        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        existing = db.query_one(
            """
            SELECT source_id FROM sources 
            WHERE project_id = ? AND content_hash = ? AND ingestion_status <> 'archived'
            """,
            (project_id, content_hash),
        )
        if existing:
            skipped_files.append({"path": path, "reason": "Duplicate content already imported"})
            continue

        source_id = str(uuid.uuid4())
        storage_key = storage_service.save_file(raw_bytes)
        now = get_utc_now()
        source_reference = f"{repo_url}@{commit_sha}:{path}"
        meta = json.dumps({"repo_url": repo_url, "path": path, "commit_sha": commit_sha})

        try:
            with db.transaction() as cur:
                cur.execute(
                    """
                    INSERT INTO sources (
                        source_id, project_id, source_type, filename, source_reference,
                        storage_key, content_hash, size_bytes, sensitivity, audience_roles,
                        ingestion_status, error_message, document_date, source_metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        project_id,
                        SourceType.GITHUB.value,
                        path,
                        source_reference,
                        storage_key,
                        content_hash,
                        len(raw_bytes),
                        sensitivity.value,
                        roles_json,
                        IngestionStatus.PROCESSED.value,
                        None,
                        None,
                        meta,
                        now,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO source_texts (source_id, text, page_offsets)
                    VALUES (?, ?, ?)
                    """,
                    (source_id, text, json.dumps(page_offsets)),
                )
                record_audit(
                    cur,
                    actor_id=actor_id,
                    project_id=project_id,
                    action="source.imported",
                    entity_type="source",
                    entity_id=source_id,
                    summary=f"Imported GitHub source {source_id} {path}",
                )

            row = db.query_one("SELECT * FROM sources WHERE source_id = ?", (source_id,))
            row["audience_roles"] = json.loads(row["audience_roles"])
            row.pop("storage_key", None)
            row.pop("source_metadata", None)
            imported_sources.append(row)
        except Exception:
            storage_service.delete_file(storage_key)

    if not imported_sources and not skipped_files:
        raise ContinuityException(
            code=ErrorCode.GITHUB_URL_INVALID,
            message="No suitable markdown or text files found in repository",
            status_code=422,
        )

    return imported_sources, skipped_files
