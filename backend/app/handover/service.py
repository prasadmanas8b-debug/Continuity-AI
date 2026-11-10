import json
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from app.audit.service import record_audit
from app.cold_start.service import generate_cold_start_tasks_for_handover
from app.core.errors import ContinuityException
from app.db.session import db, get_utc_now
from app.permissions.policy import eligible_for_handover, filter_valid_handover_evidence
from app.schemas.enums import (
    ErrorCode,
    FactType,
    HandoverStatus,
    QuoteMatchStatus,
    RecipientRole,
    ReviewStatus,
    SectionKey,
    Sensitivity,
    UncertaintyLabel,
    UserRole,
    VerificationStatus,
)

SECTION_MAPPING = {
    FactType.STATUS.value: SectionKey.CURRENT_STATUS.value,
    FactType.DECISION.value: SectionKey.DECISIONS.value,
    FactType.OWNER.value: SectionKey.RESPONSIBILITIES.value,
    FactType.BLOCKER.value: SectionKey.BLOCKERS_DEPENDENCIES.value,
    FactType.DEPENDENCY.value: SectionKey.BLOCKERS_DEPENDENCIES.value,
    FactType.RISK.value: SectionKey.RISKS.value,
    FactType.NEXT_ACTION.value: SectionKey.NEXT_ACTIONS.value,
    FactType.QUESTION.value: SectionKey.UNRESOLVED_QUESTIONS.value,
}

SECTION_ORDER = [
    SectionKey.CURRENT_STATUS.value,
    SectionKey.DECISIONS.value,
    SectionKey.RESPONSIBILITIES.value,
    SectionKey.BLOCKERS_DEPENDENCIES.value,
    SectionKey.RISKS.value,
    SectionKey.NEXT_ACTIONS.value,
    SectionKey.UNRESOLVED_QUESTIONS.value,
]

SECTION_TITLES = {
    SectionKey.CURRENT_STATUS.value: "Current Status",
    SectionKey.DECISIONS.value: "Decisions and Rationale",
    SectionKey.RESPONSIBILITIES.value: "Responsibilities",
    SectionKey.BLOCKERS_DEPENDENCIES.value: "Blockers and Dependencies",
    SectionKey.RISKS.value: "Risks",
    SectionKey.NEXT_ACTIONS.value: "Next Actions",
    SectionKey.UNRESOLVED_QUESTIONS.value: "Unresolved Questions",
}


def _determine_uncertainty_label(
    claim: Dict[str, Any],
    claim_open_conflict: bool,
) -> UncertaintyLabel:
    # Priority: conflicted > unresolved > uncertain > none
    if claim_open_conflict:
        return UncertaintyLabel.CONFLICTED
    if claim["review_status"] == ReviewStatus.UNRESOLVED.value:
        return UncertaintyLabel.UNRESOLVED
    if claim["verification_status"] == VerificationStatus.UNCERTAIN.value:
        return UncertaintyLabel.UNCERTAIN
    return UncertaintyLabel.NONE


def _compute_snapshots_for_role(
    project_id: str,
    recipient_role: RecipientRole,
) -> Tuple[List[Dict[str, Any]], int, List[Dict[str, Any]]]:
    """Returns (included_snapshots, excluded_count, open_critical_conflicts)"""
    all_claims = db.query_all(
        "SELECT * FROM claims WHERE project_id = ? AND archived = 0 ORDER BY created_at ASC",
        (project_id,),
    )
    all_evidence = db.query_all(
        """
        SELECT e.*, s.filename, s.document_date, s.sensitivity AS source_sensitivity
        FROM evidence e
        JOIN sources s ON e.source_id = s.source_id
        WHERE s.project_id = ?
        """,
        (project_id,),
    )
    evidence_by_claim: Dict[str, List[Dict[str, Any]]] = {}
    source_sens_map = {}
    for ev in all_evidence:
        evidence_by_claim.setdefault(ev["claim_id"], []).append(ev)
        source_sens_map[ev["source_id"]] = ev["source_sensitivity"]

    # Open conflicts in project
    open_conflicts = db.query_all(
        """
        SELECT c.*, cc.claim_id 
        FROM conflicts c
        JOIN conflict_claims cc ON c.conflict_id = cc.conflict_id
        WHERE c.project_id = ? AND c.status IN ('open', 'unresolved')
        """,
        (project_id,),
    )
    conflict_claims_map: Dict[str, List[Dict[str, Any]]] = {}
    for c in open_conflicts:
        conflict_claims_map.setdefault(c["claim_id"], []).append(c)

    included_snapshots = []
    included_claim_ids = set()

    for claim in all_claims:
        cid = claim["claim_id"]
        ev_list = evidence_by_claim.get(cid, [])
        valid_ev = filter_valid_handover_evidence(ev_list, source_sens_map)

        claim_aud = json.loads(claim["audience_roles"]) if claim.get("audience_roles") else []
        claim_dict = dict(claim)
        claim_dict["audience_roles"] = claim_aud

        if not eligible_for_handover(claim_dict, valid_ev, recipient_role):
            continue

        included_claim_ids.add(cid)
        sec_key = SECTION_MAPPING.get(claim["fact_type"], SectionKey.CURRENT_STATUS.value)
        has_open_conf = cid in conflict_claims_map
        unc_label = _determine_uncertainty_label(claim, has_open_conf)

        ev_snapshots = [
            {
                "evidence_id": e["evidence_id"],
                "source_label": e["filename"],
                "source_date": e["document_date"],
                "exact_quote": e["exact_quote"],
                "locator": json.loads(e["locator"]),
                "support_status": e["support_status"],
            }
            for e in valid_ev
        ]

        snapshot = {
            "claim_id": cid,
            "section_key": sec_key,
            "item_id": claim["item_id"],
            "fact_type": claim["fact_type"],
            "statement_snapshot": claim["statement"],
            "owner_snapshot": claim["owner"],
            "verification_status_snapshot": claim["verification_status"],
            "review_status_snapshot": claim["review_status"],
            "uncertainty_label": unc_label.value,
            "evidence_snapshot": json.dumps(ev_snapshots),
        }
        included_snapshots.append(snapshot)

    # Sort snapshots by section order then item_id
    sec_rank = {sec: idx for idx, sec in enumerate(SECTION_ORDER)}
    included_snapshots.sort(key=lambda s: (sec_rank.get(s["section_key"], 99), s["item_id"]))
    for idx, s in enumerate(included_snapshots):
        s["sort_order"] = idx

    excluded_count = len(all_claims) - len(included_snapshots)

    # Find open critical conflicts involving included claims
    open_critical_conflicts = []
    seen_conf_ids = set()
    for conf in open_conflicts:
        if conf["is_critical"] and conf["claim_id"] in included_claim_ids:
            if conf["conflict_id"] not in seen_conf_ids:
                seen_conf_ids.add(conf["conflict_id"])
                open_critical_conflicts.append({
                    "conflict_id": conf["conflict_id"],
                    "summary": conf["summary"],
                })

    return included_snapshots, excluded_count, open_critical_conflicts


def create_handover_draft(project_id: str, actor_id: str, recipient_role: RecipientRole) -> Dict[str, Any]:
    # Version = max(version for this project and recipient_role) + 1
    max_ver_row = db.query_one(
        "SELECT MAX(version) AS max_v FROM handovers WHERE project_id = ? AND recipient_role = ?",
        (project_id, recipient_role.value),
    )
    next_ver = (max_ver_row["max_v"] or 0) + 1

    snapshots, excluded_count, _ = _compute_snapshots_for_role(project_id, recipient_role)
    handover_id = str(uuid.uuid4())
    now = get_utc_now()

    with db.transaction() as cur:
        cur.execute(
            """
            INSERT INTO handovers (
                handover_id, project_id, version, status, recipient_role,
                approved_by, approved_at, approval_override,
                excluded_claim_count, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                handover_id,
                project_id,
                next_ver,
                HandoverStatus.DRAFT.value,
                recipient_role.value,
                None,
                None,
                None,
                excluded_count,
                actor_id,
                now,
            ),
        )

        for s in snapshots:
            cur.execute(
                """
                INSERT INTO handover_claims (
                    handover_id, claim_id, section_key, item_id, fact_type,
                    statement_snapshot, owner_snapshot, verification_status_snapshot,
                    review_status_snapshot, uncertainty_label, evidence_snapshot, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    handover_id,
                    s["claim_id"],
                    s["section_key"],
                    s["item_id"],
                    s["fact_type"],
                    s["statement_snapshot"],
                    s["owner_snapshot"],
                    s["verification_status_snapshot"],
                    s["review_status_snapshot"],
                    s["uncertainty_label"],
                    s["evidence_snapshot"],
                    s["sort_order"],
                ),
            )

        record_audit(
            cur,
            actor_id=actor_id,
            project_id=project_id,
            action="handover.created",
            entity_type="handover",
            entity_id=handover_id,
            summary=f"Created handover draft v{next_ver} for {recipient_role.value} with {len(snapshots)} claims",
        )

    return get_handover_summary(handover_id)


def refresh_handover_draft(handover_id: str, actor_id: str) -> Dict[str, Any]:
    handover = db.query_one("SELECT * FROM handovers WHERE handover_id = ?", (handover_id,))
    if not handover:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)
    if handover["status"] != HandoverStatus.DRAFT.value:
        raise ContinuityException(ErrorCode.HANDOVER_IMMUTABLE, "Only draft handovers can be refreshed", status_code=409)

    snapshots, excluded_count, _ = _compute_snapshots_for_role(
        handover["project_id"], RecipientRole(handover["recipient_role"])
    )

    with db.transaction() as cur:
        cur.execute("DELETE FROM handover_claims WHERE handover_id = ?", (handover_id,))
        cur.execute(
            "UPDATE handovers SET excluded_claim_count = ? WHERE handover_id = ?",
            (excluded_count, handover_id),
        )
        for s in snapshots:
            cur.execute(
                """
                INSERT INTO handover_claims (
                    handover_id, claim_id, section_key, item_id, fact_type,
                    statement_snapshot, owner_snapshot, verification_status_snapshot,
                    review_status_snapshot, uncertainty_label, evidence_snapshot, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    handover_id,
                    s["claim_id"],
                    s["section_key"],
                    s["item_id"],
                    s["fact_type"],
                    s["statement_snapshot"],
                    s["owner_snapshot"],
                    s["verification_status_snapshot"],
                    s["review_status_snapshot"],
                    s["uncertainty_label"],
                    s["evidence_snapshot"],
                    s["sort_order"],
                ),
            )
        record_audit(
            cur,
            actor_id=actor_id,
            project_id=handover["project_id"],
            action="handover.refreshed",
            entity_type="handover",
            entity_id=handover_id,
            summary=f"Refreshed handover draft {handover_id}",
        )

    return get_handover_summary(handover_id)


def get_handover_eligibility(handover_id: str) -> Dict[str, Any]:
    handover = db.query_one("SELECT * FROM handovers WHERE handover_id = ?", (handover_id,))
    if not handover:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)

    snapshots, excluded_count, open_critical_conflicts = _compute_snapshots_for_role(
        handover["project_id"], RecipientRole(handover["recipient_role"])
    )
    can_approve = len(open_critical_conflicts) == 0

    return {
        "eligible_claim_count": len(snapshots),
        "excluded_claim_count": excluded_count,
        "open_critical_conflicts": open_critical_conflicts,
        "can_approve_without_override": can_approve,
    }


def approve_handover(
    handover_id: str,
    actor_id: str,
    override_reason: Optional[str] = None,
) -> Dict[str, Any]:
    handover = db.query_one("SELECT * FROM handovers WHERE handover_id = ?", (handover_id,))
    if not handover:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)
    if handover["status"] != HandoverStatus.DRAFT.value:
        raise ContinuityException(ErrorCode.HANDOVER_IMMUTABLE, "Attempt to change an approved handover", status_code=409)

    # 1. Recompute snapshot
    refresh_handover_draft(handover_id, actor_id)
    eligibility = get_handover_eligibility(handover_id)

    # 2. Check if zero claims are eligible
    if eligibility["eligible_claim_count"] == 0:
        raise ContinuityException(
            code=ErrorCode.VALIDATION_ERROR,
            message="Cannot approve handover with zero eligible claims",
            details={"reason": "NO_ELIGIBLE_CLAIMS"},
            status_code=422,
        )

    # 3. Apply D-07: open critical conflicts check
    open_critical = eligibility["open_critical_conflicts"]
    override_payload = None

    if open_critical:
        if not override_reason or len(override_reason.strip()) < 10:
            raise ContinuityException(
                code=ErrorCode.APPROVAL_BLOCKED_CONFLICT,
                message="Approval blocked by open critical conflict. An override reason of at least 10 characters is required.",
                details={"conflicts": open_critical},
                status_code=409,
            )
        override_payload = {
            "reason": override_reason.strip(),
            "conflict_ids": [c["conflict_id"] for c in open_critical],
        }

    now = get_utc_now()
    with db.transaction() as cur:
        cur.execute(
            """
            UPDATE handovers 
            SET status = 'approved', approved_by = ?, approved_at = ?, approval_override = ?
            WHERE handover_id = ?
            """,
            (actor_id, now, json.dumps(override_payload) if override_payload else None, handover_id),
        )
        # Generate cold-start tasks
        generate_cold_start_tasks_for_handover(handover_id)
        record_audit(
            cur,
            actor_id=actor_id,
            project_id=handover["project_id"],
            action="handover.approved",
            entity_type="handover",
            entity_id=handover_id,
            summary=f"Approved handover {handover_id} v{handover['version']}",
        )

    return get_handover_summary(handover_id)


def revoke_handover(handover_id: str, actor_id: str) -> Dict[str, Any]:
    handover = db.query_one("SELECT * FROM handovers WHERE handover_id = ?", (handover_id,))
    if not handover:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)

    with db.transaction() as cur:
        cur.execute("UPDATE handovers SET status = 'revoked' WHERE handover_id = ?", (handover_id,))
        record_audit(
            cur,
            actor_id=actor_id,
            project_id=handover["project_id"],
            action="handover.revoked",
            entity_type="handover",
            entity_id=handover_id,
            summary=f"Revoked handover {handover_id}",
        )
    return get_handover_summary(handover_id)


def get_handover_summary(handover_id: str) -> Dict[str, Any]:
    h = db.query_one("SELECT * FROM handovers WHERE handover_id = ?", (handover_id,))
    if not h:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)

    count_row = db.query_one(
        "SELECT COUNT(*) as inc_count FROM handover_claims WHERE handover_id = ?",
        (handover_id,),
    )
    inc_count = count_row["inc_count"] if count_row else 0

    override = json.loads(h["approval_override"]) if h.get("approval_override") else None
    return {
        "handover_id": h["handover_id"],
        "project_id": h["project_id"],
        "version": h["version"],
        "status": h["status"],
        "recipient_role": h["recipient_role"],
        "included_claim_count": inc_count,
        "excluded_claim_count": h["excluded_claim_count"],
        "approved_by": h["approved_by"],
        "approved_at": h["approved_at"],
        "approval_override": override,
        "created_at": h["created_at"],
    }


def get_handover_detail(handover_id: str, current_user_id: str) -> Dict[str, Any]:
    h = db.query_one("SELECT * FROM handovers WHERE handover_id = ?", (handover_id,))
    if not h:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)

    if h["status"] == "revoked":
        raise ContinuityException(
            code=ErrorCode.HANDOVER_REVOKED,
            message="This handover has been withdrawn by the project manager.",
            status_code=403,
        )

    # Check caller permissions
    membership = db.query_one(
        """
        SELECT * FROM project_memberships 
        WHERE project_id = ? AND user_id = ? AND membership_status = 'active'
        """,
        (h["project_id"], current_user_id),
    )
    if not membership:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Project not found or membership revoked", status_code=404)

    role = membership["role"]
    if h["status"] == "draft" and role != UserRole.MANAGER.value:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Draft handovers are only accessible to managers", status_code=404)

    if role == UserRole.INCOMING_MEMBER.value:
        if membership.get("recipient_role") != h["recipient_role"]:
            raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found for your role", status_code=404)
        if h["status"] != HandoverStatus.APPROVED.value:
            raise ContinuityException(ErrorCode.HANDOVER_NOT_APPROVED, "Handover is not yet approved", status_code=409)

    project = db.query_one("SELECT name, description FROM projects WHERE project_id = ?", (h["project_id"],))

    # Read snapshots
    claims_snapshots = db.query_all(
        "SELECT * FROM handover_claims WHERE handover_id = ? ORDER BY sort_order ASC",
        (handover_id,),
    )

    # Build sections
    sections_map = {sec: [] for sec in SECTION_ORDER}
    included_claim_ids = set()

    for cs in claims_snapshots:
        cid = cs["claim_id"]
        included_claim_ids.add(cid)
        claim_obj = {
            "claim_id": cid,
            "item_id": cs["item_id"],
            "fact_type": cs["fact_type"],
            "statement": cs["statement_snapshot"],
            "owner": cs["owner_snapshot"],
            "verification_status": cs["verification_status_snapshot"],
            "review_status": cs["review_status_snapshot"],
            "uncertainty_label": cs["uncertainty_label"],
            "evidence": json.loads(cs["evidence_snapshot"]),
        }
        sec_k = cs["section_key"]
        if sec_k in sections_map:
            sections_map[sec_k].append(claim_obj)

    sections = [
        {
            "section_key": sec_k,
            "title": SECTION_TITLES[sec_k],
            "claims": sections_map[sec_k],
        }
        for sec_k in SECTION_ORDER
    ]

    # Open conflicts: included claims only, safe summary
    open_confs = db.query_all(
        """
        SELECT c.conflict_id, c.summary, cc.claim_id 
        FROM conflicts c
        JOIN conflict_claims cc ON c.conflict_id = cc.conflict_id
        WHERE c.project_id = ? AND c.status IN ('open', 'unresolved')
        """,
        (h["project_id"],),
    )
    conf_grouped: Dict[str, Dict[str, Any]] = {}
    for r in open_confs:
        conf_id = r["conflict_id"]
        cid = r["claim_id"]
        if cid in included_claim_ids:
            if conf_id not in conf_grouped:
                conf_grouped[conf_id] = {
                    "conflict_id": conf_id,
                    "summary": r["summary"],
                    "claim_ids": [],
                }
            conf_grouped[conf_id]["claim_ids"].append(cid)

    summary_info = get_handover_summary(handover_id)
    summary_info["project_name"] = project["name"] if project else "Project"
    summary_info["project_overview"] = project["description"] if project else None
    summary_info["sections"] = sections
    summary_info["open_conflicts"] = list(conf_grouped.values())
    return summary_info
