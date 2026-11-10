from typing import Any, Dict, List, Optional
from app.schemas.enums import QuoteMatchStatus, RecipientRole, ReviewStatus, Sensitivity, UserRole


def can_read_claim(membership: Dict[str, Any], claim: Dict[str, Any]) -> bool:
    role = membership.get("role")
    if role == UserRole.MANAGER.value:
        return True
    if role == UserRole.CONTRIBUTOR.value:
        return claim.get("sensitivity") == Sensitivity.NORMAL.value
    # Incoming members never read live claims directly
    return False


def filter_valid_handover_evidence(
    evidence_rows: List[Dict[str, Any]],
    source_sensitivity_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    valid = []
    for ev in evidence_rows:
        is_found = ev.get("quote_match_status") == QuoteMatchStatus.FOUND.value
        src_id = ev.get("source_id")
        src_sens = source_sensitivity_map.get(src_id, Sensitivity.NORMAL.value)
        if is_found and src_sens == Sensitivity.NORMAL.value:
            valid.append(ev)
    return valid


def eligible_for_handover(
    claim: Dict[str, Any],
    valid_evidence: List[Dict[str, Any]],
    recipient_role: RecipientRole,
) -> bool:
    # 1. Review status check: accepted, edited, unresolved
    r_status = claim.get("review_status")
    if r_status not in (ReviewStatus.ACCEPTED.value, ReviewStatus.EDITED.value, ReviewStatus.UNRESOLVED.value):
        return False

    # 2. Sensitivity check: never restricted
    if claim.get("sensitivity") == Sensitivity.RESTRICTED.value:
        return False

    # 3. Audience roles check: empty means all recipient roles
    audience = claim.get("audience_roles", [])
    if audience and recipient_role.value not in audience:
        return False

    # 4. Evidence check: must have at least one valid found evidence from normal source
    if not valid_evidence:
        return False

    return True
