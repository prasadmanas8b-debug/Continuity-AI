import uuid
from typing import Any, Dict, Optional

from app.audit.service import record_audit
from app.core.errors import ContinuityException
from app.db.session import db, get_utc_now
from app.schemas.enums import ErrorCode, ReviewDecision, ReviewStatus, VerificationStatus
from app.verification.service import verify_claim_evidence


def review_claim(
    claim_id: str,
    reviewer_id: str,
    decision: ReviewDecision,
    expected_version: int,
    reviewed_statement: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    decision_to_status = {
        ReviewDecision.ACCEPT: ReviewStatus.ACCEPTED.value,
        ReviewDecision.EDIT: ReviewStatus.EDITED.value,
        ReviewDecision.REJECT: ReviewStatus.REJECTED.value,
        ReviewDecision.UNRESOLVED: ReviewStatus.UNRESOLVED.value,
    }

    with db.transaction() as cur:
        # 1. Fetch claim with write lock
        claim = db.query_one("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
        if not claim:
            raise ContinuityException(ErrorCode.NOT_FOUND, "Claim not found", status_code=404)

        if claim["version"] != expected_version:
            raise ContinuityException(
                code=ErrorCode.STALE_VERSION,
                message="This claim changed. Reload the latest version.",
                details={"current_version": claim["version"]},
                status_code=409,
            )

        # 2. Validate by decision
        evidence_rows = db.query_all("SELECT * FROM evidence WHERE claim_id = ?", (claim_id,))

        if decision == ReviewDecision.ACCEPT:
            if not evidence_rows:
                raise ContinuityException(
                    code=ErrorCode.CLAIM_NOT_ACCEPTABLE,
                    message="Cannot accept a claim with no evidence",
                    status_code=422,
                )
            if claim["verification_status"] == VerificationStatus.REJECTED.value:
                raise ContinuityException(
                    code=ErrorCode.CLAIM_NOT_ACCEPTABLE,
                    message="Cannot accept a claim whose verification is rejected",
                    status_code=422,
                )
            if claim["verification_status"] == VerificationStatus.UNCERTAIN.value:
                if not reason or not reason.strip():
                    raise ContinuityException(
                        code=ErrorCode.CLAIM_NOT_ACCEPTABLE,
                        message="Accepting an uncertain claim requires a non-blank reason",
                        status_code=422,
                    )

        elif decision == ReviewDecision.EDIT:
            if not reviewed_statement or not reviewed_statement.strip():
                raise ContinuityException(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Reviewed statement cannot be blank",
                    status_code=422,
                )
            cleaned_stmt = reviewed_statement.strip()
            if len(cleaned_stmt) > 1000:
                raise ContinuityException(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Reviewed statement cannot exceed 1000 characters",
                    status_code=422,
                )
            if cleaned_stmt == claim["statement"]:
                raise ContinuityException(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Reviewed statement must differ from the current statement",
                    status_code=422,
                )
            if not reason or not reason.strip():
                raise ContinuityException(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Reason is required when editing a claim statement",
                    status_code=422,
                )

        elif decision == ReviewDecision.REJECT:
            if not reason or not reason.strip():
                raise ContinuityException(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Reason is required when rejecting a claim",
                    status_code=422,
                )

        # 3. Apply review update
        new_version = claim["version"] + 1
        new_statement = reviewed_statement.strip() if decision == ReviewDecision.EDIT else claim["statement"]
        target_review_status = decision_to_status[decision]

        now = get_utc_now()
        cur.execute(
            """
            UPDATE claims 
            SET statement = ?, review_status = ?, version = ?, updated_at = ?
            WHERE claim_id = ?
            """,
            (new_statement, target_review_status, new_version, now, claim_id),
        )

        review_id = str(uuid.uuid4())
        reviewer = db.query_one("SELECT display_name FROM users WHERE user_id = ?", (reviewer_id,))
        reviewer_name = reviewer["display_name"] if reviewer else "Manager"

        cur.execute(
            """
            INSERT INTO reviews (
                review_id, claim_id, reviewer_id, decision, original_statement,
                reviewed_statement, reason, claim_version_after, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                claim_id,
                reviewer_id,
                decision.value,
                claim["statement"],  # wording before this action
                reviewed_statement.strip() if decision == ReviewDecision.EDIT else None,
                reason.strip() if reason else None,
                new_version,
                now,
            ),
        )

        record_audit(
            cur,
            actor_id=reviewer_id,
            project_id=claim["project_id"],
            action="claim.reviewed",
            entity_type="claim",
            entity_id=claim_id,
            summary=f"Reviewed claim {claim_id} with decision {decision.value} to version {new_version}",
        )

    # 4. If edited: re-verify and re-detect conflicts
    if decision == ReviewDecision.EDIT:
        verify_claim_evidence(claim_id)
        from app.conflicts.service import detect_conflicts_for_project
        detect_conflicts_for_project(claim["project_id"])

    # Load fresh review record and claim
    review_record = {
        "review_id": review_id,
        "claim_id": claim_id,
        "reviewer_id": reviewer_id,
        "reviewer_name": reviewer_name,
        "decision": decision.value,
        "original_statement": claim["statement"],
        "reviewed_statement": reviewed_statement.strip() if decision == ReviewDecision.EDIT else None,
        "reason": reason.strip() if reason else None,
        "claim_version_after": new_version,
        "created_at": now,
    }

    updated_claim = db.query_one("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
    import json
    updated_claim["audience_roles"] = json.loads(updated_claim["audience_roles"])

    ev_rows = db.query_all("SELECT * FROM evidence WHERE claim_id = ?", (claim_id,))
    for ev in ev_rows:
        ev["locator"] = json.loads(ev["locator"])
        s = db.query_one("SELECT filename, document_date FROM sources WHERE source_id = ?", (ev["source_id"],))
        ev["source_label"] = s["filename"] if s else "Source"
        ev["source_date"] = s["document_date"] if s else None
    updated_claim["evidence"] = ev_rows

    conf_ids = [
        r["conflict_id"]
        for r in db.query_all("SELECT conflict_id FROM conflict_claims WHERE claim_id = ?", (claim_id,))
    ]
    updated_claim["conflict_ids"] = conf_ids

    return {
        "review": review_record,
        "claim": updated_claim,
    }
