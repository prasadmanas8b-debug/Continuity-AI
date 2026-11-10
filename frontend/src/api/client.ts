import type {
  AuditEntry,
  Claim,
  ClaimDetail,
  ColdStartResult,
  ColdStartResultRequest,
  ColdStartSummary,
  ColdStartTask,
  Conflict,
  ConflictResolutionRequest,
  DemoLoginResponse,
  Eligibility,
  ErrorCode,
  ErrorEnvelope,
  ExtractionRun,
  GithubImportResponse,
  Handover,
  HandoverDetail,
  MemberRevokeResponse,
  Membership,
  MetaResponse,
  PaginatedList,
  Project,
  ProjectMember,
  ProjectSummary,
  RecipientRole,
  ReviewRequest,
  ReviewResponse,
  Sensitivity,
  Source,
  SourceExcerptResponse,
  User,
} from './generated/schema';

export const BUNDLED_CONTRACT_VERSION = '1.0.0';

const rawEnv =
  typeof import.meta !== 'undefined' && (import.meta as unknown as { env?: Record<string, string> }).env
    ? (import.meta as unknown as { env: Record<string, string> }).env
    : {};

export const API_BASE_URL: string =
  rawEnv.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export const API_ORIGIN: string =
  API_BASE_URL.replace(/\/api\/v1\/?$/, '') || 'http://localhost:8000';

export type ApiMode = 'real' | 'mock';

let currentApiMode: ApiMode = rawEnv.VITE_API_MODE === 'mock' ? 'mock' : 'real';

export function getApiMode(): ApiMode {
  return currentApiMode;
}

export function setApiMode(mode: ApiMode): void {
  currentApiMode = mode;
}

/**
 * Exact Section 10.7 Error code to user-facing message mapping.
 * Never shows stack traces or raw server text.
 */
export const ERROR_MESSAGE_MAP: Record<ErrorCode, string> = {
  FILE_TOO_LARGE: 'This file is over 10 MB. Split it or upload a smaller file.',
  EMPTY_FILE: 'The file is empty. Choose a file that contains text.',
  UNSUPPORTED_FILE_TYPE: 'Only PDF, TXT and MD files are supported.',
  CORRUPT_FILE: 'This file could not be read. Try exporting it again.',
  NO_EXTRACTABLE_TEXT: 'No readable text was found. Scanned PDFs are not supported yet.',
  DUPLICATE_SOURCE: 'This content was already imported.',
  GITHUB_URL_INVALID: 'Use a public repository URL like https://github.com/owner/repo.',
  GITHUB_RATE_LIMITED: 'GitHub is not available right now. Nothing was imported. Try again later.',
  GITHUB_UNAVAILABLE: 'GitHub is not available right now. Nothing was imported. Try again later.',
  AI_UNAVAILABLE: 'The analysis service could not finish. Your sources are safe. Try again.',
  AI_BAD_OUTPUT: 'The analysis service could not finish. Your sources are safe. Try again.',
  STALE_VERSION: 'This claim changed. Reload the latest version.',
  CLAIM_NOT_ACCEPTABLE: 'This claim cannot be accepted as it is. Edit it or add a reason.',
  APPROVAL_BLOCKED_CONFLICT: 'Unresolved conflicts affect this handover. Resolve them or give a reason to proceed.',
  HANDOVER_REVOKED: 'This handover has been withdrawn by the project manager.',
  NOT_FOUND: 'You do not have access to this item.',
  FORBIDDEN: 'You do not have access to this item.',
  DATABASE_UNAVAILABLE: 'Something went wrong on our side. Nothing was saved. Try again.',
  STORAGE_UNAVAILABLE: 'Something went wrong on our side. Nothing was saved. Try again.',
  INTERNAL_ERROR: 'Something went wrong on our side. Nothing was saved. Try again.',
  UNAUTHENTICATED: 'Your session has expired. Please choose a demo user to log in.',
  IDEMPOTENCY_CONFLICT: 'A request with this idempotency key was already submitted with different data.',
  EXTRACTION_IN_PROGRESS: 'An extraction run is already in progress for this project.',
  HANDOVER_IMMUTABLE: 'Approved or revoked handovers are immutable snapshots and cannot be modified.',
  HANDOVER_NOT_APPROVED: 'This handover is still a draft and has not been approved yet.',
  VALIDATION_ERROR: 'Please check the required fields and try again.',
};

export class ApiError extends Error {
  public readonly code: ErrorCode;
  public readonly userMessage: string;
  public readonly details: Record<string, unknown> | null;
  public readonly requestId: string;
  public readonly status: number;

  constructor(envelope: ErrorEnvelope, status = 400) {
    const code = envelope.error.code;
    const mappedMessage = ERROR_MESSAGE_MAP[code] ?? envelope.error.message;
    super(mappedMessage);
    this.name = 'ApiError';
    this.code = code;
    this.userMessage = mappedMessage;
    this.details = envelope.error.details;
    this.requestId = envelope.error.request_id;
    this.status = status;
  }
}

/**
 * Token storage rule (Section 10.2 & T10):
 * Keep the demo token in memory with sessionStorage as refresh fallback.
 * Never store source text, quotes, claims, handover content or answer data in browser storage.
 */
let inMemoryToken: string | null = null;
const SESSION_TOKEN_KEY = 'continuity_ai_demo_token';

export function getAuthToken(): string | null {
  if (inMemoryToken) return inMemoryToken;
  try {
    if (typeof sessionStorage !== 'undefined') {
      inMemoryToken = sessionStorage.getItem(SESSION_TOKEN_KEY);
      return inMemoryToken;
    }
  } catch {
    // Ignore storage errors in sandboxed iframes
  }
  return null;
}

export function setAuthToken(token: string | null): void {
  inMemoryToken = token;
  try {
    if (typeof sessionStorage !== 'undefined') {
      if (token) {
        sessionStorage.setItem(SESSION_TOKEN_KEY, token);
      } else {
        sessionStorage.removeItem(SESSION_TOKEN_KEY);
      }
    }
  } catch {
    // Ignore storage errors in sandboxed iframes
  }
}

export type UploadFileInput =
  | File
  | {
      name: string;
      size: number;
      type: string;
      content: string | Uint8Array | ArrayBuffer | Blob;
    };

export interface Api {
  getHealth(): Promise<{ status: 'ok' }>;
  getMeta(): Promise<MetaResponse>;
  listDemoUsers(): Promise<User[]>;
  demoLogin(userId: string): Promise<DemoLoginResponse>;
  getMe(): Promise<{ user: User; memberships: Membership[] }>;
  listProjects(limit?: number, offset?: number): Promise<PaginatedList<ProjectSummary>>;
  createProject(payload: { name: string; description: string | null }, idempotencyKey?: string): Promise<Project>;
  getProject(projectId: string): Promise<ProjectSummary>;
  listMembers(projectId: string): Promise<PaginatedList<ProjectMember>>;
  revokeMember(projectId: string, userId: string): Promise<MemberRevokeResponse>;
  listSources(projectId: string): Promise<PaginatedList<Source>>;
  uploadSource(
    projectId: string,
    payload: {
      file: UploadFileInput;
      document_date?: string | null;
      sensitivity?: Sensitivity;
      audience_roles?: RecipientRole[];
    },
    idempotencyKey?: string
  ): Promise<Source>;
  importGithub(
    projectId: string,
    payload: { repo_url: string; sensitivity?: Sensitivity; audience_roles?: RecipientRole[] },
    idempotencyKey?: string
  ): Promise<GithubImportResponse>;
  getSource(sourceId: string): Promise<Source>;
  getSourceExcerpt(sourceId: string, charStart: number, charEnd: number): Promise<SourceExcerptResponse>;
  archiveSource(sourceId: string): Promise<Source>;
  startExtraction(projectId: string, sourceIds?: string[]): Promise<ExtractionRun>;
  getExtractionRun(runId: string): Promise<ExtractionRun>;
  listClaims(
    projectId: string,
    filters?: {
      verification_status?: string;
      conflict_status?: string;
      review_status?: string;
      fact_type?: string;
      item_id?: string;
    }
  ): Promise<PaginatedList<Claim>>;
  getClaim(claimId: string): Promise<ClaimDetail>;
  reviewClaim(claimId: string, payload: ReviewRequest, idempotencyKey?: string): Promise<ReviewResponse>;
  listConflicts(projectId: string, status?: string): Promise<PaginatedList<Conflict>>;
  getConflict(conflictId: string): Promise<Conflict>;
  resolveConflict(conflictId: string, payload: ConflictResolutionRequest): Promise<Conflict>;
  listHandovers(projectId: string): Promise<PaginatedList<Handover>>;
  createHandover(projectId: string, recipientRole: RecipientRole, idempotencyKey?: string): Promise<Handover>;
  refreshHandover(handoverId: string): Promise<Handover>;
  getHandoverEligibility(handoverId: string): Promise<Eligibility>;
  approveHandover(handoverId: string, overrideReason: string | null, idempotencyKey?: string): Promise<Handover>;
  revokeHandover(handoverId: string): Promise<Handover>;
  getHandoverDetail(handoverId: string): Promise<HandoverDetail>;
  listColdStartTasks(handoverId: string): Promise<ColdStartTask[]>;
  submitColdStartResult(taskId: string, payload: ColdStartResultRequest, idempotencyKey?: string): Promise<ColdStartResult>;
  getColdStartSummary(handoverId: string): Promise<ColdStartSummary>;
  listAudit(projectId: string): Promise<PaginatedList<AuditEntry>>;
}
