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
from app.review.service import review_claim
from app.schemas.enums import (
    ConflictStatus,
    ErrorCode,
    FactType,
    QuoteMatchStatus,
    ReviewDecision,
    ReviewStatus,
    Sensitivity,
    SupportStatus,
    UserRole,
    VerificationStatus,
)
from app.schemas.models import (
    Claim,
    ClaimDetail,
    ClaimListResponse,
    Evidence,
    EvidenceLocator,
    ReviewRecord,
    ReviewRequest,
    ReviewResponse,
)

router = APIRouter(tags=["Claims"])


def _hydrate_claim(r: dict) -> Claim:
    cid = r["claim_id"]
    audience = json.loads(r["audience_roles"]) if isinstance(r.get("audience_roles"), str) else (r.get("audience_roles") or [])

    ev_rows = db.query_all(
        """
        SELECT e.*, s.filename, s.document_date 
        FROM evidence e
        LEFT JOIN sources s ON e.source_id = s.source_id
        WHERE e.claim_id = ?
        """,
        (cid,),
    )
    evidence_list = []
    for ev in ev_rows:
        loc = json.loads(ev["locator"]) if isinstance(ev.get("locator"), str) else (ev.get("locator") or {})
        evidence_list.append(
            Evidence(
                evidence_id=ev["evidence_id"],
                source_id=ev["source_id"],
                source_label=ev.get("filename") or "Source",
                source_date=ev.get("document_date"),
                exact_quote=ev["exact_quote"],
                locator=EvidenceLocator(**loc),
                quote_match_status=QuoteMatchStatus(ev["quote_match_status"]),
                support_status=SupportStatus(ev["support_status"]),
                support_note=ev.get("support_note"),
            )
        )

    conf_ids = [
        cc["conflict_id"]
        for cc in db.query_all("SELECT conflict_id FROM conflict_claims WHERE claim_id = ?", (cid,))
    ]

    return Claim(
        claim_id=r["claim_id"],
        project_id=r["project_id"],
        item_id=r["item_id"],
        fact_type=FactType(r["fact_type"]),
        statement=r["statement"],
        original_statement=r["original_statement"],
        owner=r.get("owner"),
        verification_status=VerificationStatus(r["verification_status"]),
        conflict_status=ConflictStatus(r["conflict_status"]),
        review_status=ReviewStatus(r["review_status"]),
        sensitivity=Sensitivity(r["sensitivity"]),
        audience_roles=audience,
        version=r["version"],
        evidence=evidence_list,
        conflict_ids=conf_ids,
        extraction_run_id=r["extraction_run_id"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


@router.get("/projects/{project_id}/claims", response_model=ClaimListResponse)
def list_claims(
    project_id: str,
    verification_status: Optional[VerificationStatus] = Query(None),
    conflict_status: Optional[ConflictStatus] = Query(None),
    review_status: Optional[ReviewStatus] = Query(None),
    fact_type: Optional[FactType] = Query(None),
    item_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
):
    mem = require_project_role(project_id, user_id, [UserRole.MANAGER, UserRole.CONTRIBUTOR])
    role = mem["role"]

    conditions = ["project_id = ?", "archived = 0"]
    params: List[Any] = [project_id]

    if role == UserRole.CONTRIBUTOR.value:
        conditions.append("sensitivity = 'normal'")

    if verification_status:
        conditions.append("verification_status = ?")
        params.append(verification_status.value)
    if conflict_status:
        conditions.append("conflict_status = ?")
        params.append(conflict_status.value)
    if review_status:
        conditions.append("review_status = ?")
        params.append(review_status.value)
    if fact_type:
        conditions.append("fact_type = ?")
        params.append(fact_type.value)
    if item_id:
        conditions.append("item_id = ?")
        params.append(item_id)

    where_clause = " AND ".join(conditions)
    total = db.query_one(f"SELECT COUNT(*) as t FROM claims WHERE {where_clause}", tuple(params))["t"]

    query = f"""
    SELECT * FROM claims 
    WHERE {where_clause}
    ORDER BY created_at ASC
    LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    rows = db.query_all(query, tuple(params))

    items = [_hydrate_claim(r) for r in rows]
    return ClaimListResponse(items=items, total=total)


@router.get("/claims/{claim_id}", response_model=ClaimDetail)
def get_claim_detail(
    claim_id: str,
    user_id: str = Depends(get_current_user_id),
):
    claim_row = db.query_one("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
    if not claim_row:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Claim not found", status_code=404)

    mem = require_project_membership(claim_row["project_id"], user_id)
    if mem["role"] == UserRole.INCOMING_MEMBER.value:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Claim not found", status_code=404)
    if mem["role"] == UserRole.CONTRIBUTOR.value and claim_row["sensitivity"] == Sensitivity.RESTRICTED.value:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Claim not found", status_code=404)

    base_claim = _hydrate_claim(claim_row)

    review_rows = db.query_all(
        """
        SELECT r.*, u.display_name AS reviewer_name
        FROM reviews r
        JOIN users u ON r.reviewer_id = u.user_id
        WHERE r.claim_id = ?
        ORDER BY r.created_at ASC
        """,
        (claim_id,),
    )
    history = [
        ReviewRecord(
            review_id=r["review_id"],
            claim_id=r["claim_id"],
            reviewer_id=r["reviewer_id"],
            reviewer_name=r["reviewer_name"],
            decision=ReviewDecision(r["decision"]),
            original_statement=r["original_statement"],
            reviewed_statement=r.get("reviewed_statement"),
            reason=r.get("reason"),
            claim_version_after=r["claim_version_after"],
            created_at=r["created_at"],
        )
        for r in review_rows
    ]

    claim_dict = base_claim.dict()
    claim_dict["review_history"] = history
    return ClaimDetail(**claim_dict)


@router.post("/claims/{claim_id}/reviews", response_model=ReviewResponse, status_code=201)
def submit_review(
    claim_id: str,
    req: ReviewRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user_id: str = Depends(get_current_user_id),
):
    claim_row = db.query_one("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
    if not claim_row:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Claim not found", status_code=404)

    require_project_role(claim_row["project_id"], user_id, [UserRole.MANAGER])

    cached = check_idempotency(idempotency_key, user_id, f"review:{claim_id}", req.dict())
    if cached:
        return cached

    result = review_claim(
        claim_id=claim_id,
        reviewer_id=user_id,
        decision=req.decision,
        expected_version=req.expected_version,
        reviewed_statement=req.reviewed_statement,
        reason=req.reason,
    )

    # Format into ReviewResponse
    review_rec = ReviewRecord(**result["review"])
    claim_obj = _hydrate_claim(result["claim"])
    resp = ReviewResponse(review=review_rec, claim=claim_obj)

    save_idempotency(idempotency_key, user_id, f"review:{claim_id}", req.dict(), 201, resp.dict())
    return resp
