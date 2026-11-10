import json
import re
import uuid
from typing import Any, Dict, List, Optional, Set

from app.audit.service import record_audit
# moved inside function
from app.core.config import settings
from app.core.errors import ContinuityException
from app.db.session import db, get_utc_now
from app.extraction.llm_provider import ExtractedClaimItem, ExtractionOutput, SourceChunk, get_llm_provider
from app.extraction.prompt import PROMPT_VERSION
from app.schemas.enums import (
    ErrorCode,
    ExtractionRunStatus,
    FactType,
    QuoteMatchStatus,
    ReviewStatus,
    Sensitivity,
    SupportStatus,
    VerificationStatus,
)
from app.verification.service import verify_claim_evidence

CREDENTIAL_PATTERN = re.compile(
    r"(password(?!\s+reset)|passwd|secret|api[_-]?key|token|BEGIN[A-Z\s_-]*PRIVATE\s+KEY|[a-zA-Z0-9_\-]{32,})",
    re.IGNORECASE,
)


def chunk_text(text: str, source_id: str, max_chunk_size: int = 12000, overlap: int = 500) -> List[SourceChunk]:
    if len(text) <= max_chunk_size:
        return [SourceChunk(source_id=source_id, text=text, char_offset=0)]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chunk_size, len(text))
        if end < len(text):
            # Try to break on paragraph boundary \n\n or newline
            split_at = text.rfind("\n\n", start, end)
            if split_at == -1 or split_at <= start + 1000:
                split_at = text.rfind("\n", start, end)
            if split_at != -1 and split_at > start + 1000:
                end = split_at

        chunk_str = text[start:end]
        chunks.append(SourceChunk(source_id=source_id, text=chunk_str, char_offset=start))
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)

    return chunks


def is_credential_text(text: str) -> bool:
    if not text:
        return False
    return bool(CREDENTIAL_PATTERN.search(text))


def start_extraction_run(
    project_id: str,
    actor_id: str,
    source_ids: Optional[List[str]] = None,
    provider=None,
) -> Dict[str, Any]:
    # Check if a run is already running for the project
    active = db.query_one(
        "SELECT * FROM extraction_runs WHERE project_id = ? AND status = 'running'",
        (project_id,),
    )
    if active:
        raise ContinuityException(
            code=ErrorCode.EXTRACTION_IN_PROGRESS,
            message="An extraction run is already in progress for this project",
            status_code=409,
        )

    # Select sources
    if source_ids:
        placeholders = ",".join(["?"] * len(source_ids))
        sources = db.query_all(
            f"""
            SELECT s.*, st.text 
            FROM sources s
            JOIN source_texts st ON s.source_id = st.source_id
            WHERE s.project_id = ? AND s.source_id IN ({placeholders}) AND s.ingestion_status <> 'archived'
            """,
            (project_id, *source_ids),
        )
    else:
        # All processed, non-archived sources with no claims yet
        sources = db.query_all(
            """
            SELECT s.*, st.text 
            FROM sources s
            JOIN source_texts st ON s.source_id = st.source_id
            WHERE s.project_id = ? AND s.ingestion_status = 'processed'
              AND s.source_id NOT IN (SELECT DISTINCT source_id FROM evidence WHERE source_id IS NOT NULL)
            """,
            (project_id,),
        )

    run_id = str(uuid.uuid4())
    now = get_utc_now()
    llm = provider or get_llm_provider()
    selected_source_ids = [s["source_id"] for s in sources]

    # Create extraction_runs record
    with db.transaction() as cur:
        cur.execute(
            """
            INSERT INTO extraction_runs (
                run_id, project_id, status, source_ids, claims_created,
                claims_rejected_by_validation, llm_provider, llm_model,
                prompt_version, error_code, error_message, started_at, finished_at, started_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                project_id,
                ExtractionRunStatus.RUNNING.value,
                json.dumps(selected_source_ids),
                0,
                0,
                settings.LLM_PROVIDER,
                settings.LLM_MODEL,
                PROMPT_VERSION,
                None,
                None,
                now,
                None,
                actor_id,
            ),
        )
        record_audit(
            cur,
            actor_id=actor_id,
            project_id=project_id,
            action="extraction.started",
            entity_type="extraction_run",
            entity_id=run_id,
            summary=f"Started extraction run {run_id} over {len(selected_source_ids)} sources",
        )

    # Execute extraction
    execute_extraction_pipeline(run_id, project_id, actor_id, sources, llm)

    row = db.query_one("SELECT * FROM extraction_runs WHERE run_id = ?", (run_id,))
    row["source_ids"] = json.loads(row["source_ids"])
    return row


def execute_extraction_pipeline(
    run_id: str,
    project_id: str,
    actor_id: str,
    sources: List[Dict[str, Any]],
    llm,
):
    total_created = 0
    total_rejected = 0
    successful_chunks = 0
    failed_chunks = 0
    error_code = None
    error_message = None

    # Load existing known item_ids
    existing_items = db.query_all(
        "SELECT DISTINCT item_id FROM claims WHERE project_id = ? AND archived = 0",
        (project_id,),
    )
    known_item_ids = [r["item_id"] for r in existing_items]

    # Project source IDs set to discard hallucinated source references
    valid_proj_source_ids = {
        s["source_id"] for s in db.query_all("SELECT source_id FROM sources WHERE project_id = ?", (project_id,))
    }

    # Map source_id to audience_roles and sensitivity
    source_props = {}
    for s in db.query_all("SELECT source_id, sensitivity, audience_roles FROM sources WHERE project_id = ?", (project_id,)):
        source_props[s["source_id"]] = {
            "sensitivity": s["sensitivity"],
            "audience_roles": json.loads(s["audience_roles"]) if s.get("audience_roles") else [],
        }

    extracted_claims_accumulator: List[Dict[str, Any]] = []

    for src in sources:
        # Check restricted source exclusion rule
        if src["sensitivity"] == "restricted" and not settings.EXTRACT_RESTRICTED:
            continue

        chunks = chunk_text(src["text"], src["source_id"])
        for chunk in chunks:
            try:
                output: ExtractionOutput = llm.extract_claims(chunk, known_item_ids)
                successful_chunks += 1
                for item in output.claims[:30]:
                    extracted_claims_accumulator.append({
                        "item": item,
                        "source_id": src["source_id"],
                    })
            except ContinuityException as ce:
                failed_chunks += 1
                error_code = ce.code.value
                error_message = ce.message
            except Exception as e:
                failed_chunks += 1
                error_code = ErrorCode.AI_BAD_OUTPUT.value
                error_message = "Model output failed validation after retries"

    # Merge duplicates inside the run: same item_id, fact_type and normalised statement
    merged_map: Dict[tuple, Dict[str, Any]] = {}
    for entry in extracted_claims_accumulator:
        item: ExtractedClaimItem = entry["item"]
        norm_stmt = " ".join(item.statement.strip().lower().split())
        key = (item.item_id, item.fact_type.value, norm_stmt)

        if key not in merged_map:
            merged_map[key] = {
                "item_id": item.item_id,
                "fact_type": item.fact_type.value,
                "statement": item.statement.strip(),
                "owner": item.owner,
                "quotes": list(item.quotes),
                "audience_roles": set(item.audience_roles),
            }
        else:
            merged_map[key]["quotes"].extend(item.quotes)
            merged_map[key]["audience_roles"].update(item.audience_roles)
            if not merged_map[key]["owner"] and item.owner:
                merged_map[key]["owner"] = item.owner

    created_claim_ids = []
    now = get_utc_now()

    with db.transaction() as cur:
        for key, claim_data in merged_map.items():
            claim_id = str(uuid.uuid4())
            item_id = claim_data["item_id"]
            fact_type = claim_data["fact_type"]
            statement = claim_data["statement"]
            owner = claim_data["owner"]

            # Filter valid evidence quotes from this project (discard hallucinated sources)
            valid_quotes = [q for q in claim_data["quotes"] if q.source_id in valid_proj_source_ids]

            # Secret flagging (independent backend rule)
            is_secret = is_credential_text(statement) or any(is_credential_text(q.exact_quote) for q in valid_quotes)
            claim_sensitivity = Sensitivity.RESTRICTED.value if is_secret else Sensitivity.NORMAL.value

            # If any evidence source has sensitivity = restricted, inherit restricted
            for q in valid_quotes:
                if source_props.get(q.source_id, {}).get("sensitivity") == "restricted":
                    claim_sensitivity = Sensitivity.RESTRICTED.value

            # Addendum A1: claim.audience_roles is union of evidence sources' audiences,
            # but empty (all roles) if any evidence source is empty.
            if not valid_quotes:
                claim_audience = []
            else:
                has_empty_source_audience = False
                source_audiences_union = set()
                for q in valid_quotes:
                    src_aud = source_props.get(q.source_id, {}).get("audience_roles", [])
                    if not src_aud:
                        has_empty_source_audience = True
                    else:
                        source_audiences_union.update(src_aud)

                if has_empty_source_audience:
                    claim_audience = []
                else:
                    claim_audience = sorted(list(source_audiences_union))

            # Initial status
            verif_status = VerificationStatus.UNCERTAIN.value if valid_quotes else VerificationStatus.REJECTED.value

            cur.execute(
                """
                INSERT INTO claims (
                    claim_id, project_id, extraction_run_id, item_id, fact_type,
                    original_statement, statement, owner, verification_status,
                    conflict_status, review_status, sensitivity, audience_roles,
                    version, archived, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?)
                """,
                (
                    claim_id,
                    project_id,
                    run_id,
                    item_id,
                    fact_type,
                    statement,
                    statement,
                    owner,
                    verif_status,
                    "none",
                    ReviewStatus.PENDING.value,
                    claim_sensitivity,
                    json.dumps(claim_audience),
                    now,
                    now,
                ),
            )

            # Insert evidence rows
            for q in valid_quotes:
                ev_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO evidence (
                        evidence_id, claim_id, source_id, exact_quote, locator,
                        quote_match_status, support_status, support_note, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ev_id,
                        claim_id,
                        q.source_id,
                        q.exact_quote,
                        json.dumps({"page": 1}),
                        QuoteMatchStatus.UNCHECKED.value,
                        SupportStatus.UNCHECKED.value,
                        None,
                        now,
                    ),
                )

            created_claim_ids.append(claim_id)
            total_created += 1

    # Run M3 verification for every new claim
    for cid in created_claim_ids:
        verify_claim_evidence(cid, provider=llm)

    # Run M4 conflict detection for the project
    from app.conflicts.service import detect_conflicts_for_project; detect_conflicts_for_project(project_id, provider=llm)

    final_status = (
        ExtractionRunStatus.SUCCEEDED.value
        if (successful_chunks > 0 or len(sources) == 0)
        else ExtractionRunStatus.FAILED.value
    )

    with db.transaction() as cur:
        cur.execute(
            """
            UPDATE extraction_runs 
            SET status = ?, claims_created = ?, claims_rejected_by_validation = ?,
                error_code = ?, error_message = ?, finished_at = ?
            WHERE run_id = ?
            """,
            (
                final_status,
                total_created,
                total_rejected,
                error_code if final_status == ExtractionRunStatus.FAILED.value else None,
                error_message if final_status == ExtractionRunStatus.FAILED.value else None,
                get_utc_now(),
                run_id,
            ),
        )
        record_audit(
            cur,
            actor_id=actor_id,
            project_id=project_id,
            action="extraction.finished",
            entity_type="extraction_run",
            entity_id=run_id,
            summary=f"Finished extraction run {run_id} status {final_status} with {total_created} claims",
        )
