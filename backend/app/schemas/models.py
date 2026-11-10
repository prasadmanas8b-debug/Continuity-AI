from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Extra, Field

from app.schemas.enums import (
    ColdStartOutcome,
    ConflictRecordStatus,
    ConflictStatus,
    ConflictType,
    ErrorCode,
    ExtractionRunStatus,
    FactType,
    HandoverStatus,
    IngestionStatus,
    QuoteMatchStatus,
    RecipientRole,
    ReviewDecision,
    ReviewStatus,
    SectionKey,
    Sensitivity,
    SourceType,
    SupportStatus,
    UncertaintyLabel,
    UserRole,
    VerificationStatus,
)


import warnings
warnings.filterwarnings("ignore", message=".*Valid config keys have changed in V2.*")

class BaseSchema(BaseModel):
    class Config:
        extra = Extra.forbid
        allow_population_by_field_name = True


# --- Error Envelope ---
class ErrorDetail(BaseSchema):
    code: str
    message: str
    details: Optional[Any] = None
    request_id: str


class ErrorEnvelope(BaseSchema):
    error: ErrorDetail


# --- Meta & Health ---
class HealthResponse(BaseSchema):
    status: str = "ok"


class MetaResponse(BaseSchema):
    contract_version: str
    app_version: str
    auth_mode: str = "demo"
    llm_mode: str = "fake"  # live or fake


# --- Auth & Users ---
class User(BaseSchema):
    user_id: str
    display_name: str
    email: Optional[str] = None


class ProjectMembershipSummary(BaseSchema):
    project_id: str
    role: UserRole
    recipient_role: Optional[RecipientRole] = None


class DemoLoginRequest(BaseSchema):
    user_id: str


class DemoLoginResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    user: User
    memberships: List[ProjectMembershipSummary] = []


class CurrentUserResponse(BaseSchema):
    user: User
    memberships: List[ProjectMembershipSummary] = []


# --- Projects ---
class ProjectCreateRequest(BaseSchema):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None


class Project(BaseSchema):
    project_id: str
    name: str
    description: Optional[str] = None
    created_at: str
    updated_at: str


class ProjectSummary(Project):
    source_count: int = 0
    claim_count: int = 0
    open_conflict_count: int = 0
    pending_review_count: int = 0
    latest_handover_version: Optional[int] = None
    my_role: UserRole


class ProjectListResponse(BaseSchema):
    items: List[ProjectSummary]
    total: int


class MemberItem(BaseSchema):
    user_id: str
    display_name: str
    email: Optional[str] = None
    role: UserRole
    recipient_role: Optional[RecipientRole] = None
    membership_status: str
    created_at: str
    revoked_at: Optional[str] = None


class ProjectMembersResponse(BaseSchema):
    items: List[MemberItem]
    total: int


class MemberRevokeResponse(BaseSchema):
    status: str = "revoked"


# --- Sources ---
class Source(BaseSchema):
    source_id: str
    project_id: str
    source_type: SourceType
    filename: str
    source_reference: str
    content_hash: str
    sensitivity: Sensitivity
    audience_roles: List[str] = []
    ingestion_status: IngestionStatus
    error_message: Optional[str] = None
    document_date: Optional[str] = None
    size_bytes: int
    created_at: str


class SourceListResponse(BaseSchema):
    items: List[Source]
    total: int


class SourceExcerptResponse(BaseSchema):
    text: str
    char_start: int
    char_end: int


class GitHubImportRequest(BaseSchema):
    repo_url: str
    sensitivity: Optional[Sensitivity] = Sensitivity.NORMAL
    audience_roles: Optional[List[str]] = []


class GitHubSkippedFile(BaseSchema):
    path: str
    reason: str


class GitHubImportResponse(BaseSchema):
    sources: List[Source]
    skipped: List[GitHubSkippedFile] = []


# --- Extraction ---
class ExtractionRunCreateRequest(BaseSchema):
    source_ids: Optional[List[str]] = None


class ExtractionRun(BaseSchema):
    run_id: str
    project_id: str
    status: ExtractionRunStatus
    source_ids: List[str] = []
    claims_created: int = 0
    claims_rejected_by_validation: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: str
    finished_at: Optional[str] = None


# --- Evidence & Claims ---
class EvidenceLocator(BaseSchema):
    page: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    path: Optional[str] = None
    commit_sha: Optional[str] = None


class Evidence(BaseSchema):
    evidence_id: str
    source_id: str
    source_label: str
    source_date: Optional[str] = None
    exact_quote: str
    locator: EvidenceLocator
    quote_match_status: QuoteMatchStatus
    support_status: SupportStatus
    support_note: Optional[str] = None


class ReviewRecord(BaseSchema):
    review_id: str
    claim_id: str
    reviewer_id: str
    reviewer_name: str
    decision: ReviewDecision
    original_statement: str
    reviewed_statement: Optional[str] = None
    reason: Optional[str] = None
    claim_version_after: int
    created_at: str


class Claim(BaseSchema):
    claim_id: str
    project_id: str
    item_id: str
    fact_type: FactType
    statement: str
    original_statement: str
    owner: Optional[str] = None
    verification_status: VerificationStatus
    conflict_status: ConflictStatus
    review_status: ReviewStatus
    sensitivity: Sensitivity
    audience_roles: List[str] = []
    version: int = 1
    evidence: List[Evidence] = []
    conflict_ids: List[str] = []
    extraction_run_id: str
    created_at: str
    updated_at: str


class ClaimDetail(Claim):
    review_history: List[ReviewRecord] = []


class ClaimListResponse(BaseSchema):
    items: List[Claim]
    total: int


class ReviewRequest(BaseSchema):
    decision: ReviewDecision
    reviewed_statement: Optional[str] = None
    reason: Optional[str] = None
    expected_version: int


class ReviewResponse(BaseSchema):
    review: ReviewRecord
    claim: Claim


# --- Conflicts ---
class Conflict(BaseSchema):
    conflict_id: str
    project_id: str
    item_id: str
    fact_type: FactType
    conflict_type: ConflictType
    status: ConflictRecordStatus
    is_critical: bool
    summary: str
    resolution_note: Optional[str] = None
    claims: List[Claim] = []
    created_at: str
    resolved_at: Optional[str] = None


class ConflictListResponse(BaseSchema):
    items: List[Conflict]
    total: int


class ConflictResolutionRequest(BaseSchema):
    status: ConflictRecordStatus
    resolution_note: Optional[str] = None
    superseded_claim_id: Optional[str] = None


# --- Handovers ---
class ApprovalOverride(BaseSchema):
    reason: str
    conflict_ids: List[str] = []


class HandoverCreateRequest(BaseSchema):
    recipient_role: RecipientRole


class HandoverApproveRequest(BaseSchema):
    override_reason: Optional[str] = None


class Handover(BaseSchema):
    handover_id: str
    project_id: str
    version: int
    status: HandoverStatus
    recipient_role: RecipientRole
    included_claim_count: int
    excluded_claim_count: int
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    approval_override: Optional[ApprovalOverride] = None
    created_at: str


class HandoverListResponse(BaseSchema):
    items: List[Handover]
    total: int


class HandoverEvidence(BaseSchema):
    evidence_id: str
    source_label: str
    source_date: Optional[str] = None
    exact_quote: str
    locator: EvidenceLocator
    support_status: SupportStatus


class HandoverClaim(BaseSchema):
    claim_id: str
    item_id: str
    fact_type: FactType
    statement: str
    owner: Optional[str] = None
    verification_status: VerificationStatus
    review_status: ReviewStatus
    uncertainty_label: UncertaintyLabel
    evidence: List[HandoverEvidence] = []


class HandoverSection(BaseSchema):
    section_key: SectionKey
    title: str
    claims: List[HandoverClaim] = []


class HandoverOpenConflict(BaseSchema):
    conflict_id: str
    summary: str
    claim_ids: List[str] = []


class HandoverDetail(Handover):
    project_name: str
    project_overview: Optional[str] = None
    sections: List[HandoverSection] = []
    open_conflicts: List[HandoverOpenConflict] = []


class EligibilityConflictSummary(BaseSchema):
    conflict_id: str
    summary: str


class Eligibility(BaseSchema):
    eligible_claim_count: int
    excluded_claim_count: int
    open_critical_conflicts: List[EligibilityConflictSummary] = []
    can_approve_without_override: bool


# --- Cold Start ---
class ColdStartTask(BaseSchema):
    task_id: str
    handover_id: str
    ordinal: int
    task_prompt: str


class ColdStartResultRequest(BaseSchema):
    outcome: ColdStartOutcome
    time_seconds: int = Field(..., ge=0, le=86400)
    hints_used: int = Field(..., ge=0)
    missing_information: Optional[str] = None


class ColdStartResult(BaseSchema):
    result_id: str
    task_id: str
    tester_id: str
    outcome: ColdStartOutcome
    time_seconds: int
    hints_used: int
    missing_information: Optional[str] = None
    created_at: str


class ColdStartSummary(BaseSchema):
    handover_id: str
    tasks_total: int
    results_total: int
    pass_count: int
    needs_help_count: int
    total_time_seconds: int
    hints_used: int
    missing_information: List[str] = []


# --- Audit ---
class AuditEntry(BaseSchema):
    audit_id: str
    project_id: Optional[str] = None
    actor_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    summary: str
    created_at: str


class AuditListResponse(BaseSchema):
    items: List[AuditEntry]
    total: int
