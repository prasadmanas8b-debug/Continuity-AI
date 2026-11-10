#!/usr/bin/env python3
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.schemas.enums import *
from app.schemas.models import *

EXAMPLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "examples"))
os.makedirs(EXAMPLES_DIR, exist_ok=True)

def save(filename, data):
    path = os.path.join(EXAMPLES_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {filename}")

def build_examples():
    # 1. project_summary.json
    ps = ProjectSummary(
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        name="Project Roomiez",
        description="Roommate finder application",
        created_at="2026-11-02T10:00:00Z",
        updated_at="2026-11-07T12:00:00Z",
        source_count=5,
        claim_count=12,
        open_conflict_count=1,
        pending_review_count=3,
        latest_handover_version=1,
        my_role=UserRole.MANAGER,
    )
    save("project_summary.json", ps.dict())

    # 2. source_pdf.json
    sp = Source(
        source_id="11111111-2222-3333-4444-555555555555",
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        source_type=SourceType.PDF,
        filename="project_notes.pdf",
        source_reference="project_notes.pdf",
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        sensitivity=Sensitivity.NORMAL,
        audience_roles=["backend_developer"],
        ingestion_status=IngestionStatus.PROCESSED,
        error_message=None,
        document_date="2026-11-02",
        size_bytes=10452,
        created_at="2026-11-02T10:05:00Z",
    )
    save("source_pdf.json", sp.dict())

    # 3. claim_verified.json
    ev_ver = Evidence(
        evidence_id="ev-001",
        source_id="11111111-2222-3333-4444-555555555555",
        source_label="project_notes.pdf",
        source_date="2026-11-02",
        exact_quote="Login authentication is incomplete.",
        locator=EvidenceLocator(page=1, char_start=120, char_end=156),
        quote_match_status=QuoteMatchStatus.FOUND,
        support_status=SupportStatus.SUPPORTS,
        support_note="Quote directly supports claim statement.",
    )
    c_ver = Claim(
        claim_id="cl-001",
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        item_id="login_authentication",
        fact_type=FactType.STATUS,
        statement="Login authentication is incomplete.",
        original_statement="Login authentication is incomplete.",
        owner=None,
        verification_status=VerificationStatus.VERIFIED,
        conflict_status=ConflictStatus.CONFLICT,
        review_status=ReviewStatus.PENDING,
        sensitivity=Sensitivity.NORMAL,
        audience_roles=["backend_developer"],
        version=1,
        evidence=[ev_ver],
        conflict_ids=["conf-001"],
        extraction_run_id="run-001",
        created_at="2026-11-02T10:10:00Z",
        updated_at="2026-11-02T10:10:00Z",
    )
    save("claim_verified.json", c_ver.dict())

    # 4. claim_uncertain.json
    ev_unc = Evidence(
        evidence_id="ev-002",
        source_id="11111111-2222-3333-4444-555555555555",
        source_label="project_notes.pdf",
        source_date="2026-11-02",
        exact_quote="Password reset is blocked until the email service is configured.",
        locator=EvidenceLocator(page=1, char_start=200, char_end=265),
        quote_match_status=QuoteMatchStatus.FOUND,
        support_status=SupportStatus.PARTIAL,
        support_note="Interpretation goes beyond explicit source statement.",
    )
    c_unc = Claim(
        claim_id="cl-002",
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        item_id="password_reset",
        fact_type=FactType.BLOCKER,
        statement="Password reset requires SMTP credentials from cloud provider.",
        original_statement="Password reset requires SMTP credentials from cloud provider.",
        owner=None,
        verification_status=VerificationStatus.UNCERTAIN,
        conflict_status=ConflictStatus.NONE,
        review_status=ReviewStatus.PENDING,
        sensitivity=Sensitivity.NORMAL,
        audience_roles=["backend_developer"],
        version=1,
        evidence=[ev_unc],
        conflict_ids=[],
        extraction_run_id="run-001",
        created_at="2026-11-02T10:10:00Z",
        updated_at="2026-11-02T10:10:00Z",
    )
    save("claim_uncertain.json", c_unc.dict())

    # 5. claim_no_evidence.json
    c_no_ev = Claim(
        claim_id="cl-003",
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        item_id="missing_feature",
        fact_type=FactType.STATUS,
        statement="Payment gateway is integrated.",
        original_statement="Payment gateway is integrated.",
        owner=None,
        verification_status=VerificationStatus.REJECTED,
        conflict_status=ConflictStatus.NONE,
        review_status=ReviewStatus.PENDING,
        sensitivity=Sensitivity.NORMAL,
        audience_roles=["backend_developer"],
        version=1,
        evidence=[],
        conflict_ids=[],
        extraction_run_id="run-001",
        created_at="2026-11-02T10:10:00Z",
        updated_at="2026-11-02T10:10:00Z",
    )
    save("claim_no_evidence.json", c_no_ev.dict())

    # 6. claim_restricted.json
    c_restr = Claim(
        claim_id="cl-004",
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        item_id="staging_credentials",
        fact_type=FactType.DECISION,
        statement="Database connection password is staging_db_password_123.",
        original_statement="Database connection password is staging_db_password_123.",
        owner=None,
        verification_status=VerificationStatus.VERIFIED,
        conflict_status=ConflictStatus.NONE,
        review_status=ReviewStatus.PENDING,
        sensitivity=Sensitivity.RESTRICTED,
        audience_roles=[],
        version=1,
        evidence=[
            Evidence(
                evidence_id="ev-003",
                source_id="22222222-3333-4444-5555-666666666666",
                source_label="credentials_note.txt",
                source_date="2026-11-07",
                exact_quote="Database connection password is staging_db_password_123.",
                locator=EvidenceLocator(page=1, char_start=0, char_end=56),
                quote_match_status=QuoteMatchStatus.FOUND,
                support_status=SupportStatus.SUPPORTS,
                support_note="Quote directly supports claim statement.",
            )
        ],
        conflict_ids=[],
        extraction_run_id="run-001",
        created_at="2026-11-07T10:10:00Z",
        updated_at="2026-11-07T10:10:00Z",
    )
    save("claim_restricted.json", c_restr.dict())

    # 7. conflict_two_claims.json
    ev_c1 = Evidence(
        evidence_id="ev-001",
        source_id="11111111-2222-3333-4444-555555555555",
        source_label="project_notes.pdf",
        source_date="2026-11-02",
        exact_quote="Login authentication is incomplete.",
        locator=EvidenceLocator(page=1, char_start=120, char_end=156),
        quote_match_status=QuoteMatchStatus.FOUND,
        support_status=SupportStatus.SUPPORTS,
        support_note="Direct match",
    )
    ev_c2 = Evidence(
        evidence_id="ev-004",
        source_id="33333333-4444-5555-6666-777777777777",
        source_label="meeting_notes.txt",
        source_date="2026-11-06",
        exact_quote="Login authentication has been completed.",
        locator=EvidenceLocator(page=1, char_start=50, char_end=90),
        quote_match_status=QuoteMatchStatus.FOUND,
        support_status=SupportStatus.SUPPORTS,
        support_note="Direct match",
    )
    c1 = Claim(
        claim_id="cl-001",
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        item_id="login_authentication",
        fact_type=FactType.STATUS,
        statement="Login authentication is incomplete.",
        original_statement="Login authentication is incomplete.",
        owner=None,
        verification_status=VerificationStatus.VERIFIED,
        conflict_status=ConflictStatus.CONFLICT,
        review_status=ReviewStatus.PENDING,
        sensitivity=Sensitivity.NORMAL,
        audience_roles=["backend_developer"],
        version=2,
        evidence=[ev_c1],
        conflict_ids=["conf-001"],
        extraction_run_id="run-001",
        created_at="2026-11-02T10:10:00Z",
        updated_at="2026-11-06T11:00:00Z",
    )
    c2 = Claim(
        claim_id="cl-005",
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        item_id="login_authentication",
        fact_type=FactType.STATUS,
        statement="Login authentication has been completed.",
        original_statement="Login authentication has been completed.",
        owner=None,
        verification_status=VerificationStatus.VERIFIED,
        conflict_status=ConflictStatus.CONFLICT,
        review_status=ReviewStatus.PENDING,
        sensitivity=Sensitivity.NORMAL,
        audience_roles=["backend_developer"],
        version=2,
        evidence=[ev_c2],
        conflict_ids=["conf-001"],
        extraction_run_id="run-002",
        created_at="2026-11-06T10:10:00Z",
        updated_at="2026-11-06T11:00:00Z",
    )
    conf_two = Conflict(
        conflict_id="conf-001",
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        item_id="login_authentication",
        fact_type=FactType.STATUS,
        conflict_type=ConflictType.CONTRADICTION,
        status=ConflictRecordStatus.OPEN,
        is_critical=True,
        summary="Conflicting claims regarding completion state detected across sources.",
        resolution_note=None,
        claims=[c1, c2],
        created_at="2026-11-06T11:00:00Z",
        resolved_at=None,
    )
    save("conflict_two_claims.json", conf_two.dict())

    # 8. conflict_three_claims.json
    c3 = Claim(
        claim_id="cl-006",
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        item_id="login_authentication",
        fact_type=FactType.STATUS,
        statement="Login authentication is in progress and pending review.",
        original_statement="Login authentication is in progress and pending review.",
        owner=None,
        verification_status=VerificationStatus.VERIFIED,
        conflict_status=ConflictStatus.CONFLICT,
        review_status=ReviewStatus.PENDING,
        sensitivity=Sensitivity.NORMAL,
        audience_roles=["backend_developer"],
        version=2,
        evidence=[
            Evidence(
                evidence_id="ev-005",
                source_id="44444444-5555-6666-7777-888888888888",
                source_label="slack_summary.txt",
                source_date="2026-11-05",
                exact_quote="Login authentication is in progress and pending review.",
                locator=EvidenceLocator(page=1, char_start=10, char_end=66),
                quote_match_status=QuoteMatchStatus.FOUND,
                support_status=SupportStatus.SUPPORTS,
                support_note="Direct match",
            )
        ],
        conflict_ids=["conf-002"],
        extraction_run_id="run-002",
        created_at="2026-11-05T10:10:00Z",
        updated_at="2026-11-06T11:00:00Z",
    )
    conf_three = Conflict(
        conflict_id="conf-002",
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        item_id="login_authentication",
        fact_type=FactType.STATUS,
        conflict_type=ConflictType.CONTRADICTION,
        status=ConflictRecordStatus.OPEN,
        is_critical=True,
        summary="Three-way contradictory claims regarding login status.",
        resolution_note=None,
        claims=[c1, c2, c3],
        created_at="2026-11-06T11:00:00Z",
        resolved_at=None,
    )
    save("conflict_three_claims.json", conf_three.dict())

    # 9. review_accept.json
    rev_acc = ReviewResponse(
        review=ReviewRecord(
            review_id="rev-001",
            claim_id="cl-001",
            reviewer_id="user-manager-001",
            reviewer_name="Manas Prasad",
            decision=ReviewDecision.ACCEPT,
            original_statement="Login authentication is incomplete.",
            reviewed_statement=None,
            reason=None,
            claim_version_after=2,
            created_at="2026-11-07T14:00:00Z",
        ),
        claim=Claim(
            claim_id="cl-001",
            project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            item_id="login_authentication",
            fact_type=FactType.STATUS,
            statement="Login authentication is incomplete.",
            original_statement="Login authentication is incomplete.",
            owner=None,
            verification_status=VerificationStatus.VERIFIED,
            conflict_status=ConflictStatus.CONFLICT,
            review_status=ReviewStatus.ACCEPTED,
            sensitivity=Sensitivity.NORMAL,
            audience_roles=["backend_developer"],
            version=2,
            evidence=[ev_c1],
            conflict_ids=["conf-001"],
            extraction_run_id="run-001",
            created_at="2026-11-02T10:10:00Z",
            updated_at="2026-11-07T14:00:00Z",
        ),
    )
    save("review_accept.json", rev_acc.dict())

    # 10. review_edit.json
    rev_edit = ReviewResponse(
        review=ReviewRecord(
            review_id="rev-002",
            claim_id="cl-001",
            reviewer_id="user-manager-001",
            reviewer_name="Manas Prasad",
            decision=ReviewDecision.EDIT,
            original_statement="Login authentication is incomplete.",
            reviewed_statement="Login authentication backend is incomplete; email verification is pending.",
            reason="Clarifying exact pending scope based on meeting discussions.",
            claim_version_after=3,
            created_at="2026-11-07T14:15:00Z",
        ),
        claim=Claim(
            claim_id="cl-001",
            project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            item_id="login_authentication",
            fact_type=FactType.STATUS,
            statement="Login authentication backend is incomplete; email verification is pending.",
            original_statement="Login authentication is incomplete.",
            owner=None,
            verification_status=VerificationStatus.UNCERTAIN,
            conflict_status=ConflictStatus.CONFLICT,
            review_status=ReviewStatus.EDITED,
            sensitivity=Sensitivity.NORMAL,
            audience_roles=["backend_developer"],
            version=3,
            evidence=[ev_c1],
            conflict_ids=["conf-001"],
            extraction_run_id="run-001",
            created_at="2026-11-02T10:10:00Z",
            updated_at="2026-11-07T14:15:00Z",
        ),
    )
    save("review_edit.json", rev_edit.dict())

    # 11. review_stale_error.json
    err_stale = ErrorEnvelope(
        error=ErrorDetail(
            code=ErrorCode.STALE_VERSION.value,
            message="This claim changed. Reload the latest version.",
            details={"current_version": 3},
            request_id="req-uuid-001",
        )
    )
    save("review_stale_error.json", err_stale.dict())

    # 12. handover_draft.json
    h_draft = Handover(
        handover_id="ho-draft-001",
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        version=1,
        status=HandoverStatus.DRAFT,
        recipient_role=RecipientRole.BACKEND_DEVELOPER,
        included_claim_count=6,
        excluded_claim_count=2,
        approved_by=None,
        approved_at=None,
        approval_override=None,
        created_at="2026-11-07T15:00:00Z",
    )
    save("handover_draft.json", h_draft.dict())

    # 13. handover_detail_backend_developer.json
    h_detail_backend = HandoverDetail(
        handover_id="ho-approved-001",
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        version=1,
        status=HandoverStatus.APPROVED,
        recipient_role=RecipientRole.BACKEND_DEVELOPER,
        included_claim_count=2,
        excluded_claim_count=2,
        approved_by="user-manager-001",
        approved_at="2026-11-07T16:00:00Z",
        approval_override=ApprovalOverride(
            reason="Overriding login authentication contradiction: login backend merged, testing pending.",
            conflict_ids=["conf-001"],
        ),
        created_at="2026-11-07T15:00:00Z",
        project_name="Project Roomiez",
        project_overview="Roommate finder application",
        sections=[
            HandoverSection(
                section_key=SectionKey.CURRENT_STATUS,
                title="Current Status",
                claims=[
                    HandoverClaim(
                        claim_id="cl-001",
                        item_id="login_authentication",
                        fact_type=FactType.STATUS,
                        statement="Login authentication is incomplete.",
                        owner=None,
                        verification_status=VerificationStatus.VERIFIED,
                        review_status=ReviewStatus.UNRESOLVED,
                        uncertainty_label=UncertaintyLabel.CONFLICTED,
                        evidence=[
                            HandoverEvidence(
                                evidence_id="ev-001",
                                source_label="project_notes.pdf",
                                source_date="2026-11-02",
                                exact_quote="Login authentication is incomplete.",
                                locator=EvidenceLocator(page=1, char_start=120, char_end=156),
                                support_status=SupportStatus.SUPPORTS,
                            )
                        ],
                    )
                ],
            ),
            HandoverSection(
                section_key=SectionKey.DECISIONS,
                title="Decisions and Rationale",
                claims=[
                    HandoverClaim(
                        claim_id="cl-007",
                        item_id="jwt_sessions",
                        fact_type=FactType.DECISION,
                        statement="Use JWT sessions instead of server sessions.",
                        owner=None,
                        verification_status=VerificationStatus.VERIFIED,
                        review_status=ReviewStatus.ACCEPTED,
                        uncertainty_label=UncertaintyLabel.NONE,
                        evidence=[
                            HandoverEvidence(
                                evidence_id="ev-006",
                                source_label="meeting_notes.txt",
                                source_date="2026-11-06",
                                exact_quote="Decision: use JWT sessions instead of server sessions.",
                                locator=EvidenceLocator(page=1, char_start=100, char_end=155),
                                support_status=SupportStatus.SUPPORTS,
                            )
                        ],
                    )
                ],
            ),
        ],
        open_conflicts=[
            HandoverOpenConflict(
                conflict_id="conf-001",
                summary="Conflicting claims regarding completion state detected across sources.",
                claim_ids=["cl-001"],
            )
        ],
    )
    save("handover_detail_backend_developer.json", h_detail_backend.dict())

    # 14. handover_detail_designer.json
    h_detail_designer = HandoverDetail(
        handover_id="ho-approved-002",
        project_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        version=1,
        status=HandoverStatus.APPROVED,
        recipient_role=RecipientRole.DESIGNER,
        included_claim_count=1,
        excluded_claim_count=5,
        approved_by="user-manager-001",
        approved_at="2026-11-07T16:30:00Z",
        approval_override=None,
        created_at="2026-11-07T15:30:00Z",
        project_name="Project Roomiez",
        project_overview="Roommate finder application",
        sections=[
            HandoverSection(
                section_key=SectionKey.DECISIONS,
                title="Decisions and Rationale",
                claims=[
                    HandoverClaim(
                        claim_id="cl-008",
                        item_id="signup_button_color",
                        fact_type=FactType.DECISION,
                        statement="Signup screen uses the blue primary button.",
                        owner=None,
                        verification_status=VerificationStatus.VERIFIED,
                        review_status=ReviewStatus.ACCEPTED,
                        uncertainty_label=UncertaintyLabel.NONE,
                        evidence=[
                            HandoverEvidence(
                                evidence_id="ev-007",
                                source_label="design_notes.md",
                                source_date="2026-11-07",
                                exact_quote="Decision: signup screen uses the blue primary button.",
                                locator=EvidenceLocator(page=1, char_start=0, char_end=53),
                                support_status=SupportStatus.SUPPORTS,
                            )
                        ],
                    )
                ],
            )
        ],
        open_conflicts=[],
    )
    save("handover_detail_designer.json", h_detail_designer.dict())

    # 15. handover_empty_permitted.json
    # Addendum A7: response { items: [], total: 0 } for incoming member whose role has no approved handover
    save("handover_empty_permitted.json", {"items": [], "total": 0})

    # 16. eligibility_blocked.json
    elig_blocked = Eligibility(
        eligible_claim_count=7,
        excluded_claim_count=2,
        open_critical_conflicts=[
            EligibilityConflictSummary(
                conflict_id="conf-001",
                summary="Conflicting claims regarding completion state detected across sources.",
            )
        ],
        can_approve_without_override=False,
    )
    save("eligibility_blocked.json", elig_blocked.dict())

    # 17. cold_start_tasks.json
    tasks = [
        ColdStartTask(
            task_id="task-001",
            handover_id="ho-approved-001",
            ordinal=1,
            task_prompt="Find the current status of login authentication and open its supporting source.",
        ),
        ColdStartTask(
            task_id="task-002",
            handover_id="ho-approved-001",
            ordinal=2,
            task_prompt="Identify the next action for login tests and its dependency.",
        ),
        ColdStartTask(
            task_id="task-003",
            handover_id="ho-approved-001",
            ordinal=3,
            task_prompt="Find who owns login testing ownership and locate the relevant instructions.",
        ),
    ]
    save("cold_start_tasks.json", [t.dict() for t in tasks])

    # 18. cold_start_summary.json
    cs_sum = ColdStartSummary(
        handover_id="ho-approved-001",
        tasks_total=3,
        results_total=3,
        pass_count=2,
        needs_help_count=1,
        total_time_seconds=240,
        hints_used=1,
        missing_information=["Missing clear link to staging database credentials."],
    )
    save("cold_start_summary.json", cs_sum.dict())

    # 19. error_*.json for every error code in 7.2
    for ec in ErrorCode:
        err_envelope = ErrorEnvelope(
            error=ErrorDetail(
                code=ec.value,
                message=f"Example error message for {ec.value}",
                details={"sample": "detail"} if ec == ErrorCode.DUPLICATE_SOURCE else None,
                request_id="example-request-id-1234",
            )
        )
        save(f"error_{ec.value.lower()}.json", err_envelope.dict())

if __name__ == "__main__":
    build_examples()
