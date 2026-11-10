import json
import uuid
from typing import Any, Dict, List, Optional

from app.audit.service import record_audit
from app.core.errors import ContinuityException
from app.db.session import db, get_utc_now
from app.schemas.enums import ColdStartOutcome, ErrorCode, FactType


def generate_cold_start_tasks_for_handover(handover_id: str):
    # Deterministic generation from handover_claims snapshots
    claims = db.query_all(
        """
        SELECT * FROM handover_claims 
        WHERE handover_id = ? 
        ORDER BY sort_order ASC
        """,
        (handover_id,),
    )

    tasks_to_create = []

    # Task 1: A status claim -> "Find the current status of <item> and open its supporting source."
    status_claim = next((c for c in claims if c["fact_type"] == FactType.STATUS.value), None)
    if status_claim:
        item_name = status_claim["item_id"].replace("_", " ")
        prompt = f"Find the current status of {item_name} and open its supporting source."
        ev_list = json.loads(status_claim["evidence_snapshot"])
        expected_ref = {
            "claim_id": status_claim["claim_id"],
            "expected_status": status_claim["statement_snapshot"],
            "expected_evidence_ids": [e["evidence_id"] for e in ev_list],
        }
        tasks_to_create.append((1, prompt, expected_ref))

    # Task 2: A next_action claim, plus a dependency claim of same item_id if present
    next_action_claim = next((c for c in claims if c["fact_type"] == FactType.NEXT_ACTION.value), None)
    if next_action_claim:
        item_id = next_action_claim["item_id"]
        item_name = item_id.replace("_", " ")
        dep_claim = next((c for c in claims if c["fact_type"] == FactType.DEPENDENCY.value and c["item_id"] == item_id), None)
        if dep_claim:
            prompt = f"Identify the next action for {item_name} and its dependency."
            expected_ref = {
                "claim_ids": [next_action_claim["claim_id"], dep_claim["claim_id"]],
                "next_action": next_action_claim["statement_snapshot"],
                "dependency": dep_claim["statement_snapshot"],
            }
        else:
            prompt = f"Identify the next action for {item_name}."
            expected_ref = {
                "claim_ids": [next_action_claim["claim_id"]],
                "next_action": next_action_claim["statement_snapshot"],
            }
        tasks_to_create.append((2, prompt, expected_ref))

    # Task 3: An owner claim, or a next_action claim with an owner
    owner_claim = next((c for c in claims if c["fact_type"] == FactType.OWNER.value and c.get("owner_snapshot")), None)
    if not owner_claim:
        owner_claim = next((c for c in claims if c["fact_type"] == FactType.NEXT_ACTION.value and c.get("owner_snapshot")), None)

    if owner_claim:
        activity = owner_claim["item_id"].replace("_", " ")
        prompt = f"Find who owns {activity} and locate the relevant instructions."
        expected_ref = {
            "claim_id": owner_claim["claim_id"],
            "expected_owner": owner_claim["owner_snapshot"],
            "expected_statement": owner_claim["statement_snapshot"],
        }
        tasks_to_create.append((3, prompt, expected_ref))

    now = get_utc_now()
    with db.transaction() as cur:
        for ordinal, prompt, exp_ref in tasks_to_create:
            task_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO cold_start_tasks (task_id, handover_id, ordinal, task_prompt, expected_reference, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, handover_id, ordinal, prompt, json.dumps(exp_ref), now),
            )


def submit_cold_start_result(
    task_id: str,
    tester_id: str,
    outcome: ColdStartOutcome,
    time_seconds: int,
    hints_used: int,
    missing_information: Optional[str] = None,
) -> Dict[str, Any]:
    task = db.query_one("SELECT * FROM cold_start_tasks WHERE task_id = ?", (task_id,))
    if not task:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Task not found", status_code=404)

    handover = db.query_one("SELECT * FROM handovers WHERE handover_id = ?", (task["handover_id"],))
    if not handover:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)

    if handover["status"] == "revoked":
        raise ContinuityException(
            code=ErrorCode.HANDOVER_REVOKED,
            message="This handover has been withdrawn by the project manager.",
            status_code=403,
        )

    # Validate tester role matches handover recipient_role
    membership = db.query_one(
        """
        SELECT * FROM project_memberships 
        WHERE project_id = ? AND user_id = ? AND membership_status = 'active'
        """,
        (handover["project_id"], tester_id),
    )
    if not membership or membership["role"] != "incoming_member" or membership["recipient_role"] != handover["recipient_role"]:
        raise ContinuityException(
            code=ErrorCode.FORBIDDEN,
            message="Only incoming members matching the recipient role can submit cold-start results",
            status_code=403,
        )

    if outcome == ColdStartOutcome.NEEDS_HELP:
        if not missing_information or not missing_information.strip():
            raise ContinuityException(
                code=ErrorCode.VALIDATION_ERROR,
                message="Needs Help outcome requires missing_information feedback note",
                status_code=422,
            )

    existing = db.query_one(
        "SELECT * FROM cold_start_results WHERE task_id = ? AND tester_id = ?",
        (task_id, tester_id),
    )
    if existing:
        # Check idempotency: identical retry returns stored result, different returns 409 IDEMPOTENCY_CONFLICT
        is_same = (
            existing["outcome"] == outcome.value
            and existing["time_seconds"] == time_seconds
            and existing["hints_used"] == hints_used
            and (existing.get("missing_information") or None) == (missing_information.strip() if missing_information else None)
        )
        if is_same:
            return existing
        else:
            raise ContinuityException(
                code=ErrorCode.IDEMPOTENCY_CONFLICT,
                message="A result has already been submitted for this task with different values",
                status_code=409,
            )

    result_id = str(uuid.uuid4())
    now = get_utc_now()
    clean_missing = missing_information.strip() if missing_information else None

    with db.transaction() as cur:
        cur.execute(
            """
            INSERT INTO cold_start_results (
                result_id, task_id, tester_id, outcome, time_seconds,
                hints_used, missing_information, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (result_id, task_id, tester_id, outcome.value, time_seconds, hints_used, clean_missing, now),
        )
        record_audit(
            cur,
            actor_id=tester_id,
            project_id=handover["project_id"],
            action="cold_start.submitted",
            entity_type="cold_start_result",
            entity_id=result_id,
            summary=f"Submitted cold-start result {result_id} outcome {outcome.value}",
        )

    return db.query_one("SELECT * FROM cold_start_results WHERE result_id = ?", (result_id,))


def get_cold_start_summary(handover_id: str) -> Dict[str, Any]:
    handover = db.query_one("SELECT * FROM handovers WHERE handover_id = ?", (handover_id,))
    if not handover:
        raise ContinuityException(ErrorCode.NOT_FOUND, "Handover not found", status_code=404)

    tasks = db.query_all("SELECT task_id FROM cold_start_tasks WHERE handover_id = ?", (handover_id,))
    task_ids = [t["task_id"] for t in tasks]

    if not task_ids:
        return {
            "handover_id": handover_id,
            "tasks_total": 0,
            "results_total": 0,
            "pass_count": 0,
            "needs_help_count": 0,
            "total_time_seconds": 0,
            "hints_used": 0,
            "missing_information": [],
        }

    placeholders = ",".join(["?"] * len(task_ids))
    results = db.query_all(
        f"SELECT * FROM cold_start_results WHERE task_id IN ({placeholders})",
        tuple(task_ids),
    )

    pass_count = sum(1 for r in results if r["outcome"] == "pass")
    needs_help_count = sum(1 for r in results if r["outcome"] == "needs_help")
    total_time = sum(r["time_seconds"] for r in results)
    hints_used = sum(r["hints_used"] for r in results)
    missing_info = [r["missing_information"] for r in results if r.get("missing_information")]

    return {
        "handover_id": handover_id,
        "tasks_total": len(tasks),
        "results_total": len(results),
        "pass_count": pass_count,
        "needs_help_count": needs_help_count,
        "total_time_seconds": total_time,
        "hints_used": hints_used,
        "missing_information": missing_info,
    }
