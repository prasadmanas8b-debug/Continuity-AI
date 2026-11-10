import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional, Set

from app.audit.service import record_audit
from app.core.errors import ContinuityException
from app.db.session import db, get_utc_now
from app.extraction.llm_provider import ClaimBrief, get_llm_provider
from app.schemas.enums import (
    ConflictRecordStatus,
    ConflictStatus,
    ConflictType,
    ErrorCode,
    FactType,
    ReviewStatus,
    VerificationStatus,
)


def compute_token_set_similarity(s1: str, s2: str) -> float:
    t1 = set(s1.lower().split())
    t2 = set(s2.lower().split())
    if not t1 or not t2:
        return 0.0
    intersection = t1.intersection(t2)
    union = t1.union(t2)
    return len(intersection) / len(union)


def detect_conflicts_for_project(project_id: str, provider=None):
    llm = provider or get_llm_provider()

    # Find candidate claims: non-archived, verification_status = verified, review_status <> rejected
    rows = db.query_all(
        """
        SELECT c.*, e.exact_quote, s.document_date
        FROM claims c
        LEFT JOIN evidence e ON c.claim_id = e.claim_id
        LEFT JOIN sources s ON e.source_id = s.source_id
        WHERE c.project_id = ? AND c.archived = 0 
          AND c.verification_status = 'verified' 
          AND c.review_status <> 'rejected'
        ORDER BY c.created_at ASC
        """,
        (project_id,),
    )

    # Group claims by (item_id, fact_type)
    groups: Dict[tuple, Dict[str, Dict[str, Any]]] = {}
    for r in rows:
        key = (r["item_id"], r["fact_type"])
        cid = r["claim_id"]
        if key not in groups:
            groups[key] = {}
        if cid not in groups[key]:
            groups[key][cid] = {
                "claim_id": cid,
                "project_id": r["project_id"],
                "item_id": r["item_id"],
                "fact_type": r["fact_type"],
                "statement": r["statement"],
                "version": r["version"],
                "quotes": [],
                "dates": [],
            }
        if r.get("exact_quote"):
            groups[key][cid]["quotes"].append(r["exact_quote"])
        if r.get("document_date"):
            groups[key][cid]["dates"].append(r["document_date"])

    # Process each group
    for (item_id, fact_type), claims_map in groups.items():
        claim_list = list(claims_map.values())
        if len(claim_list) < 2:
            continue

        # Check if statements are identical or token-set similarity >= 0.85
        all_consistent = True
        first_stmt = claim_list[0]["statement"]
        for other in claim_list[1:]:
            sim = compute_token_set_similarity(first_stmt, other["statement"])
            if sim < 0.85:
                all_consistent = False
                break

        if all_consistent:
            continue  # No conflict

        # Run comparison
        briefs = [
            ClaimBrief(
                claim_id=c["claim_id"],
                statement=c["statement"],
                exact_quote=c["quotes"][0] if c["quotes"] else "",
                source_date=c["dates"][0] if c["dates"] else None,
            )
            for c in claim_list
        ]

        try:
            comparison = llm.compare_claims(briefs)
        except Exception:
            comparison = None

        if not comparison:
            continue

        conflict_type = (
            ConflictType.CONTRADICTION
            if comparison.relation == "contradiction"
            else ConflictType.POSSIBLE_SUPERSESSION
        )

        critical_fact_types = {
            FactType.DECISION.value,
            FactType.OWNER.value,
            FactType.STATUS.value,
            FactType.BLOCKER.value,
            FactType.DEPENDENCY.value,
            FactType.NEXT_ACTION.value,
        }
        is_critical = (
            conflict_type == ConflictType.CONTRADICTION and fact_type in critical_fact_types
        )

        # Generate stable detection_key: hash of project + item_id + fact_type + sorted claim ids
        sorted_cids = sorted([c["claim_id"] for c in claim_list])
        key_raw = f"{project_id}:{item_id}:{fact_type}:{','.join(sorted_cids)}"
        detection_key = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()

        # Check existing conflict with detection_key
        existing_conflict = db.query_one(
            "SELECT * FROM conflicts WHERE project_id = ? AND detection_key = ?",
            (project_id, detection_key),
        )

        conflict_id = existing_conflict["conflict_id"] if existing_conflict else str(uuid.uuid4())
        now = get_utc_now()

        with db.transaction() as cur:
            if not existing_conflict:
                cur.execute(
                    """
                    INSERT INTO conflicts (
                        conflict_id, project_id, item_id, fact_type, conflict_type,
                        status, is_critical, summary, resolution_note, detection_key,
                        resolved_by, created_at, resolved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        conflict_id,
                        project_id,
                        item_id,
                        fact_type,
                        conflict_type.value,
                        ConflictRecordStatus.OPEN.value,
                        1 if is_critical else 0,
                        comparison.summary,
                        None,
                        detection_key,
                        None,
                        now,
                        None,
                    ),
                )
                for cid in sorted_cids:
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO conflict_claims (conflict_id, claim_id)
                        VALUES (?, ?)
                        """,
                        (conflict_id, cid),
                    )
                    # Involved claims get conflict_status = conflict and version + 1
                    cur.execute(
                        """
                        UPDATE claims 
                        SET conflict_status = 'conflict', version = version + 1, updated_at = ?
                        WHERE claim_id = ?
                        """,
                        (now, cid),
                    )

    # Gap detection (missing_information, never critical, single-claim conflicts)
    detect_information_gaps(project_id)


def detect_information_gaps(project_id: str):
    now = get_utc_now()
    claims = db.query_all(
        """
        SELECT * FROM claims 
        WHERE project_id = ? AND archived = 0 AND review_status <> 'rejected'
        """,
        (project_id,),
    )

    claims_by_item: Dict[str, List[Dict[str, Any]]] = {}
    for c in claims:
        claims_by_item.setdefault(c["item_id"], []).append(c)

    for c in claims:
        cid = c["claim_id"]
        item_id = c["item_id"]
        fact_type = c["fact_type"]

        # G1: a next_action, blocker or dependency claim with owner = null
        if fact_type in (FactType.NEXT_ACTION.value, FactType.BLOCKER.value, FactType.DEPENDENCY.value) and not c.get("owner"):
            det_key = hashlib.sha256(f"{project_id}:gap:G1:{cid}".encode("utf-8")).hexdigest()
            existing = db.query_one("SELECT conflict_id FROM conflicts WHERE project_id = ? AND detection_key = ?", (project_id, det_key))
            if not existing:
                conf_id = str(uuid.uuid4())
                summary = f"Missing owner for {fact_type} on item {item_id}."
                with db.transaction() as cur:
                    cur.execute(
                        """
                        INSERT INTO conflicts (
                            conflict_id, project_id, item_id, fact_type, conflict_type,
                            status, is_critical, summary, resolution_note, detection_key,
                            resolved_by, created_at, resolved_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (conf_id, project_id, item_id, fact_type, ConflictType.MISSING_INFORMATION.value,
                         ConflictRecordStatus.OPEN.value, 0, summary, None, det_key, None, now, None),
                    )
                    cur.execute("INSERT OR IGNORE INTO conflict_claims (conflict_id, claim_id) VALUES (?, ?)", (conf_id, cid))

        # G2: a blocker claim whose item_id has no dependency or next_action claim
        if fact_type == FactType.BLOCKER.value:
            sibling_types = {sibling["fact_type"] for sibling in claims_by_item.get(item_id, [])}
            if FactType.DEPENDENCY.value not in sibling_types and FactType.NEXT_ACTION.value not in sibling_types:
                det_key = hashlib.sha256(f"{project_id}:gap:G2:{cid}".encode("utf-8")).hexdigest()
                existing = db.query_one("SELECT conflict_id FROM conflicts WHERE project_id = ? AND detection_key = ?", (project_id, det_key))
                if not existing:
                    conf_id = str(uuid.uuid4())
                    summary = f"Blocker on item {item_id} lacks an associated dependency or next action."
                    with db.transaction() as cur:
                        cur.execute(
                            """
                            INSERT INTO conflicts (
                                conflict_id, project_id, item_id, fact_type, conflict_type,
                                status, is_critical, summary, resolution_note, detection_key,
                                resolved_by, created_at, resolved_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (conf_id, project_id, item_id, fact_type, ConflictType.MISSING_INFORMATION.value,
                             ConflictRecordStatus.OPEN.value, 0, summary, None, det_key, None, now, None),
                        )
                        cur.execute("INSERT OR IGNORE INTO conflict_claims (conflict_id, claim_id) VALUES (?, ?)", (conf_id, cid))
