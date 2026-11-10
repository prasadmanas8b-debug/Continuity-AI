import { Api, ApiError, BUNDLED_CONTRACT_VERSION, ERROR_MESSAGE_MAP, setAuthToken } from '../client';
import { CONTRACT_FIXTURES, defaultMockConfig } from './scenarios';
import type {
  AuditEntry,
  Claim,
  ClaimDetail,
  ColdStartResult,
  ColdStartSummary,
  ColdStartTask,
  Conflict,
  DemoLoginResponse,
  Eligibility,
  ErrorCode,
  ExtractionRun,
  GithubImportResponse,
  Handover,
  HandoverDetail,
  MemberRevokeResponse,
  MetaResponse,
  Project,
  ProjectMember,
  ProjectSummary,
  ReviewResponse,
  Source,
  User,
} from '../generated/schema';

async function delay(): Promise<void> {
  const ms = defaultMockConfig.simulatedLatencyMs;
  await new Promise((resolve) => setTimeout(resolve, ms));
  if (defaultMockConfig.forcedErrorCode) {
    const code: ErrorCode = defaultMockConfig.forcedErrorCode;
    throw new ApiError({
      error: {
        code,
        message: ERROR_MESSAGE_MAP[code],
        details: null,
        request_id: `req_mock_${code.toLowerCase()}`,
      },
    });
  }
}

export const mockApi: Api = {
  getHealth: async () => {
    await delay();
    return { status: 'ok' };
  },
  getMeta: async (): Promise<MetaResponse> => {
    await delay();
    return {
      contract_version: defaultMockConfig.contractVersionOverride ?? BUNDLED_CONTRACT_VERSION,
      app_version: '1.0.0',
      auth_mode: 'demo',
      llm_mode: defaultMockConfig.llmMode,
    };
  },
  listDemoUsers: async (): Promise<User[]> => {
    await delay();
    return [
      { user_id: 'user-manager-001', display_name: 'Manas Prasad (Manager)', email: 'manas@example.com' },
      { user_id: 'user-contributor-001', display_name: 'Sarah Chen (Contributor)', email: 'sarah@example.com' },
      { user_id: 'user-incoming-backend-001', display_name: 'Alex Rivera (Incoming Backend Dev)', email: 'alex@example.com' },
      { user_id: 'user-incoming-designer-001', display_name: 'Jordan Lee (Incoming Designer)', email: 'jordan@example.com' },
    ];
  },
  demoLogin: async (userId: string): Promise<DemoLoginResponse> => {
    await delay();
    const token = `demo_jwt_${userId}`;
    setAuthToken(token);
    return {
      access_token: token,
      token_type: 'bearer',
      expires_at: new Date(Date.now() + 8 * 3600 * 1000).toISOString(),
      user: { user_id: userId, display_name: 'Demo User', email: null },
      memberships: [
        {
          project_id: CONTRACT_FIXTURES.projectSummary.project_id,
          role: 'manager',
          recipient_role: null,
        },
      ],
    };
  },
  getMe: async () => {
    await delay();
    return {
      user: { user_id: 'user-manager-001', display_name: 'Manas Prasad (Manager)', email: 'manas@example.com' },
      memberships: [{ project_id: CONTRACT_FIXTURES.projectSummary.project_id, role: 'manager', recipient_role: null }],
    };
  },
  listProjects: async () => {
    await delay();
    return { items: [CONTRACT_FIXTURES.projectSummary as ProjectSummary], total: 1 };
  },
  createProject: async (payload): Promise<Project> => {
    await delay();
    return {
      project_id: `proj_${Date.now()}`,
      name: payload.name,
      description: payload.description,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
  },
  getProject: async () => {
    await delay();
    return CONTRACT_FIXTURES.projectSummary as ProjectSummary;
  },
  listMembers: async (): Promise<{ items: ProjectMember[]; total: number }> => {
    await delay();
    return { items: [], total: 0 };
  },
  revokeMember: async (): Promise<MemberRevokeResponse> => {
    await delay();
    return { status: 'revoked' };
  },
  listSources: async () => {
    await delay();
    return { items: [CONTRACT_FIXTURES.sourcePdf as Source], total: 1 };
  },
  uploadSource: async () => {
    await delay();
    return CONTRACT_FIXTURES.sourcePdf as Source;
  },
  importGithub: async (): Promise<GithubImportResponse> => {
    await delay();
    return {
      sources: [CONTRACT_FIXTURES.sourcePdf as Source],
      skipped: [{ path: 'docs/diagram.png', reason: 'Unsupported file extension' }],
    };
  },
  getSource: async () => {
    await delay();
    return CONTRACT_FIXTURES.sourcePdf as Source;
  },
  getSourceExcerpt: async (_sourceId, charStart, charEnd) => {
    await delay();
    return {
      text: 'Login authentication is incomplete. Password reset is blocked until the email service is configured.',
      char_start: charStart,
      char_end: charEnd,
    };
  },
  archiveSource: async () => {
    await delay();
    return { ...(CONTRACT_FIXTURES.sourcePdf as Source), ingestion_status: 'archived' };
  },
  startExtraction: async (projectId): Promise<ExtractionRun> => {
    await delay();
    return {
      run_id: 'cccc1111-2222-4333-8444-000000000001',
      project_id: projectId,
      status: 'running',
      source_ids: [CONTRACT_FIXTURES.sourcePdf.source_id],
      claims_created: 0,
      claims_rejected_by_validation: 0,
      error_code: null,
      error_message: null,
      started_at: new Date().toISOString(),
      finished_at: null,
    };
  },
  getExtractionRun: async (runId): Promise<ExtractionRun> => {
    await delay();
    return {
      run_id: runId,
      project_id: CONTRACT_FIXTURES.projectSummary.project_id,
      status: 'succeeded',
      source_ids: [CONTRACT_FIXTURES.sourcePdf.source_id],
      claims_created: 14,
      claims_rejected_by_validation: 1,
      error_code: null,
      error_message: null,
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
    };
  },
  listClaims: async () => {
    await delay();
    return {
      items: [
        CONTRACT_FIXTURES.claimVerified as Claim,
        CONTRACT_FIXTURES.claimUncertain as Claim,
        CONTRACT_FIXTURES.claimNoEvidence as Claim,
      ],
      total: 3,
    };
  },
  getClaim: async (): Promise<ClaimDetail> => {
    await delay();
    return { ...(CONTRACT_FIXTURES.claimVerified as Claim), review_history: [] };
  },
  reviewClaim: async (): Promise<ReviewResponse> => {
    await delay();
    return CONTRACT_FIXTURES.reviewEdit as ReviewResponse;
  },
  listConflicts: async () => {
    await delay();
    return { items: [CONTRACT_FIXTURES.conflictTwoClaims as Conflict], total: 1 };
  },
  getConflict: async () => {
    await delay();
    return CONTRACT_FIXTURES.conflictTwoClaims as Conflict;
  },
  resolveConflict: async (_conflictId, payload) => {
    await delay();
    return {
      ...(CONTRACT_FIXTURES.conflictTwoClaims as Conflict),
      status: payload.status,
      resolution_note: payload.resolution_note,
    };
  },
  listHandovers: async () => {
    await delay();
    return { items: [CONTRACT_FIXTURES.handoverDraft as Handover], total: 1 };
  },
  createHandover: async () => {
    await delay();
    return CONTRACT_FIXTURES.handoverDraft as Handover;
  },
  refreshHandover: async () => {
    await delay();
    return CONTRACT_FIXTURES.handoverDraft as Handover;
  },
  getHandoverEligibility: async (): Promise<Eligibility> => {
    await delay();
    return CONTRACT_FIXTURES.eligibilityBlocked as Eligibility;
  },
  approveHandover: async () => {
    await delay();
    return { ...(CONTRACT_FIXTURES.handoverDraft as Handover), status: 'approved' };
  },
  revokeHandover: async () => {
    await delay();
    return { ...(CONTRACT_FIXTURES.handoverDraft as Handover), status: 'revoked' };
  },
  getHandoverDetail: async (): Promise<HandoverDetail> => {
    await delay();
    return CONTRACT_FIXTURES.handoverDetailBackendDeveloper as HandoverDetail;
  },
  listColdStartTasks: async (): Promise<ColdStartTask[]> => {
    await delay();
    return CONTRACT_FIXTURES.coldStartTasks as ColdStartTask[];
  },
  submitColdStartResult: async (taskId, payload): Promise<ColdStartResult> => {
    await delay();
    return {
      result_id: `res_${Date.now()}`,
      task_id: taskId,
      tester_id: 'user-incoming-backend-001',
      outcome: payload.outcome,
      time_seconds: payload.time_seconds,
      hints_used: payload.hints_used,
      missing_information: payload.missing_information,
      created_at: new Date().toISOString(),
    };
  },
  getColdStartSummary: async (): Promise<ColdStartSummary> => {
    await delay();
    return CONTRACT_FIXTURES.coldStartSummary as ColdStartSummary;
  },
  listAudit: async (): Promise<{ items: AuditEntry[]; total: number }> => {
    await delay();
    return { items: [], total: 0 };
  },
};
