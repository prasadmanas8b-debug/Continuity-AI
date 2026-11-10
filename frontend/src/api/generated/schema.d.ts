/**
 * AUTO-GENERATED FROM contracts/openapi.json (CONTRACT_VERSION = 1.0.0)
 * DO NOT EDIT MANUALLY.
 */

export type UserRole = 'manager' | 'contributor' | 'incoming_member';
export type RecipientRole = 'backend_developer' | 'designer';
export type SourceType = 'github' | 'pdf' | 'txt' | 'md' | 'docx' | 'task_export';
export type IngestionStatus = 'pending' | 'processed' | 'failed' | 'archived';
export type Sensitivity = 'normal' | 'restricted';
export type FactType = 'decision' | 'owner' | 'status' | 'blocker' | 'dependency' | 'risk' | 'next_action' | 'question';
export type VerificationStatus = 'verified' | 'rejected' | 'uncertain';
export type ConflictStatus = 'none' | 'conflict' | 'superseded';
export type ReviewStatus = 'pending' | 'accepted' | 'edited' | 'rejected' | 'unresolved';
export type QuoteMatchStatus = 'found' | 'not_found' | 'unchecked';
export type SupportStatus = 'supports' | 'partial' | 'does_not_support' | 'unchecked';
export type ConflictType = 'contradiction' | 'possible_supersession' | 'missing_information';
export type ConflictRecordStatus = 'open' | 'resolved' | 'unresolved';
export type ReviewDecision = 'accept' | 'edit' | 'reject' | 'unresolved';
export type HandoverStatus = 'draft' | 'approved' | 'shared' | 'revoked';
export type ExtractionRunStatus = 'queued' | 'running' | 'succeeded' | 'failed';
export type ColdStartOutcome = 'pass' | 'needs_help';
export type UncertaintyLabel = 'none' | 'uncertain' | 'unresolved' | 'conflicted';
export type SectionKey =
  | 'current_status'
  | 'decisions'
  | 'responsibilities'
  | 'blockers_dependencies'
  | 'risks'
  | 'next_actions'
  | 'unresolved_questions';

export type ErrorCode =
  | 'UNAUTHENTICATED'
  | 'FORBIDDEN'
  | 'HANDOVER_REVOKED'
  | 'NOT_FOUND'
  | 'STALE_VERSION'
  | 'DUPLICATE_SOURCE'
  | 'IDEMPOTENCY_CONFLICT'
  | 'EXTRACTION_IN_PROGRESS'
  | 'APPROVAL_BLOCKED_CONFLICT'
  | 'HANDOVER_IMMUTABLE'
  | 'HANDOVER_NOT_APPROVED'
  | 'FILE_TOO_LARGE'
  | 'UNSUPPORTED_FILE_TYPE'
  | 'VALIDATION_ERROR'
  | 'EMPTY_FILE'
  | 'CORRUPT_FILE'
  | 'NO_EXTRACTABLE_TEXT'
  | 'CLAIM_NOT_ACCEPTABLE'
  | 'GITHUB_URL_INVALID'
  | 'GITHUB_RATE_LIMITED'
  | 'GITHUB_UNAVAILABLE'
  | 'AI_BAD_OUTPUT'
  | 'AI_UNAVAILABLE'
  | 'STORAGE_UNAVAILABLE'
  | 'DATABASE_UNAVAILABLE'
  | 'INTERNAL_ERROR';

export interface ErrorEnvelope {
  error: {
    code: ErrorCode;
    message: string;
    details: Record<string, unknown> | null;
    request_id: string;
  };
}

export interface PaginatedList<T> {
  items: T[];
  total: number;
}

export interface MetaResponse {
  contract_version: string;
  app_version: string;
  auth_mode: 'demo';
  llm_mode: 'live' | 'fake';
}

export interface User {
  user_id: string;
  display_name: string;
  email: string | null;
}

export interface Membership {
  project_id: string;
  role: UserRole;
  recipient_role: RecipientRole | null;
}

export interface ProjectMember {
  user_id: string;
  display_name: string;
  email: string | null;
  role: UserRole;
  recipient_role: RecipientRole | null;
  membership_status: 'active' | 'revoked';
  created_at: string;
  revoked_at: string | null;
}

export interface MemberRevokeResponse {
  status: string;
}

export interface DemoLoginResponse {
  access_token: string;
  token_type: 'bearer';
  expires_at: string;
  user: User;
  memberships: Membership[];
}

export interface Project {
  project_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary extends Project {
  source_count: number;
  claim_count: number;
  open_conflict_count: number;
  pending_review_count: number;
  latest_handover_version: number | null;
  my_role: UserRole;
}

export interface Source {
  source_id: string;
  project_id: string;
  source_type: SourceType;
  filename: string;
  source_reference: string;
  content_hash: string;
  sensitivity: Sensitivity;
  audience_roles: RecipientRole[];
  ingestion_status: IngestionStatus;
  error_message: string | null;
  document_date: string | null;
  size_bytes: number;
  created_at: string;
}

export interface GithubImportResponse {
  sources: Source[];
  skipped: Array<{ path: string; reason: string }>;
}

export interface SourceExcerptResponse {
  text: string;
  char_start: number;
  char_end: number;
}

export interface EvidenceLocator {
  page?: number | null;
  char_start?: number | null;
  char_end?: number | null;
  path?: string | null;
  commit_sha?: string | null;
}

export interface Evidence {
  evidence_id: string;
  source_id: string;
  source_label: string;
  source_date: string | null;
  exact_quote: string;
  locator: EvidenceLocator;
  quote_match_status: QuoteMatchStatus;
  support_status: SupportStatus;
  support_note: string | null;
}

export interface Claim {
  claim_id: string;
  project_id: string;
  item_id: string;
  fact_type: FactType;
  statement: string;
  original_statement: string;
  owner: string | null;
  verification_status: VerificationStatus;
  conflict_status: ConflictStatus;
  review_status: ReviewStatus;
  sensitivity: Sensitivity;
  audience_roles: RecipientRole[];
  version: number;
  evidence: Evidence[];
  conflict_ids: string[];
  extraction_run_id: string;
  created_at: string;
  updated_at: string;
}

export interface ReviewRecord {
  review_id: string;
  claim_id: string;
  reviewer_id: string;
  reviewer_name: string;
  decision: ReviewDecision;
  original_statement: string;
  reviewed_statement: string | null;
  reason: string | null;
  claim_version_after: number;
  created_at: string;
}

export interface ClaimDetail extends Claim {
  review_history: ReviewRecord[];
}

export interface ReviewRequest {
  decision: ReviewDecision;
  reviewed_statement: string | null;
  reason: string | null;
  expected_version: number;
}

export interface ReviewResponse {
  review: ReviewRecord;
  claim: Claim;
}

export interface Conflict {
  conflict_id: string;
  project_id: string;
  item_id: string;
  fact_type: FactType;
  conflict_type: ConflictType;
  status: ConflictRecordStatus;
  is_critical: boolean;
  summary: string;
  resolution_note: string | null;
  claims: Claim[];
  created_at: string;
  resolved_at: string | null;
}

export interface ConflictResolutionRequest {
  status: 'resolved' | 'unresolved';
  resolution_note: string | null;
  superseded_claim_id: string | null;
}

export interface ExtractionRun {
  run_id: string;
  project_id: string;
  status: ExtractionRunStatus;
  source_ids: string[];
  claims_created: number;
  claims_rejected_by_validation: number;
  error_code: ErrorCode | null;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface Handover {
  handover_id: string;
  project_id: string;
  version: number;
  status: HandoverStatus;
  recipient_role: RecipientRole;
  included_claim_count: number;
  excluded_claim_count: number;
  approved_by: string | null;
  approved_at: string | null;
  approval_override: {
    reason: string;
    conflict_ids: string[];
  } | null;
  created_at: string;
}

export interface HandoverClaim {
  claim_id: string;
  item_id: string;
  fact_type: FactType;
  statement: string;
  owner: string | null;
  verification_status: VerificationStatus;
  review_status: ReviewStatus;
  uncertainty_label: UncertaintyLabel;
  evidence: Array<{
    evidence_id: string;
    source_label: string;
    source_date: string | null;
    exact_quote: string;
    locator: EvidenceLocator;
    support_status: SupportStatus;
  }>;
}

export interface HandoverDetail extends Handover {
  project_name: string;
  project_overview: string | null;
  sections: Array<{
    section_key: SectionKey;
    title: string;
    claims: HandoverClaim[];
  }>;
  open_conflicts: Array<{
    conflict_id: string;
    summary: string;
    claim_ids: string[];
  }>;
}

export interface Eligibility {
  eligible_claim_count: number;
  excluded_claim_count: number;
  open_critical_conflicts: Array<{
    conflict_id: string;
    summary: string;
  }>;
  can_approve_without_override: boolean;
}

export interface ColdStartTask {
  task_id: string;
  handover_id: string;
  ordinal: number;
  task_prompt: string;
}

export interface ColdStartResultRequest {
  outcome: ColdStartOutcome;
  time_seconds: number;
  hints_used: number;
  missing_information: string | null;
}

export interface ColdStartResult {
  result_id: string;
  task_id: string;
  tester_id: string;
  outcome: ColdStartOutcome;
  time_seconds: number;
  hints_used: number;
  missing_information: string | null;
  created_at: string;
}

export interface ColdStartSummary {
  handover_id: string;
  tasks_total: number;
  results_total: number;
  pass_count: number;
  needs_help_count: number;
  total_time_seconds: number;
  hints_used: number;
  missing_information: string[];
}

export interface AuditEntry {
  audit_id: string;
  project_id: string | null;
  actor_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  summary: string;
  created_at: string;
}
