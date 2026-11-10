import {
  API_BASE_URL,
  API_ORIGIN,
  Api,
  ApiError,
  getAuthToken,
  setAuthToken,
} from './client';
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
  ReviewResponse,
  Source,
  SourceExcerptResponse,
  User,
} from './generated/schema';

function resolveUrl(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  if (path === '/health') {
    return `${API_ORIGIN}/health`;
  }
  if (path.startsWith('/api/v1')) {
    const suffix = path.slice('/api/v1'.length);
    return `${API_BASE_URL.replace(/\/$/, '')}${suffix}`;
  }
  return `${API_BASE_URL.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  idempotencyKey?: string
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined),
  };

  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }

  const response = await fetch(resolveUrl(path), {
    ...options,
    headers,
  });

  if (!response.ok) {
    let envelope: ErrorEnvelope;
    try {
      envelope = (await response.json()) as ErrorEnvelope;
    } catch {
      envelope = {
        error: {
          code: 'INTERNAL_ERROR',
          message: 'Something went wrong on our side. Nothing was saved. Try again.',
          details: null,
          request_id: response.headers.get('X-Request-ID') || 'req_network_fallback',
        },
      };
    }
    throw new ApiError(envelope, response.status);
  }

  return (await response.json()) as T;
}

export const realApi: Api = {
  getHealth: () => request<{ status: 'ok' }>('/health'),
  getMeta: () => request<MetaResponse>('/api/v1/meta'),
  listDemoUsers: () => request<User[]>('/api/v1/auth/demo-users'),
  demoLogin: async (userId) => {
    const res = await request<DemoLoginResponse>('/api/v1/auth/demo-login', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    });
    if (res.access_token) {
      setAuthToken(res.access_token);
    }
    return res;
  },
  getMe: () => request<{ user: User; memberships: Membership[] }>('/api/v1/me'),
  listProjects: (limit = 100, offset = 0) =>
    request<PaginatedList<ProjectSummary>>(`/api/v1/projects?limit=${limit}&offset=${offset}`),
  createProject: (payload, idempotencyKey) =>
    request<Project>(
      '/api/v1/projects',
      { method: 'POST', body: JSON.stringify(payload) },
      idempotencyKey
    ),
  getProject: (projectId) => request<ProjectSummary>(`/api/v1/projects/${projectId}`),
  listMembers: (projectId) =>
    request<PaginatedList<ProjectMember>>(`/api/v1/projects/${projectId}/members`),
  revokeMember: (projectId, userId) =>
    request<MemberRevokeResponse>(`/api/v1/projects/${projectId}/members/${userId}/revoke`, {
      method: 'POST',
    }),
  listSources: (projectId) =>
    request<PaginatedList<Source>>(`/api/v1/projects/${projectId}/sources`),
  uploadSource: (projectId, payload, idempotencyKey) => {
    const form = new FormData();
    if (typeof File !== 'undefined' && payload.file instanceof File) {
      form.append('file', payload.file, payload.file.name);
    } else {
      const f = payload.file as {
        name: string;
        size: number;
        type: string;
        content: string | Uint8Array | ArrayBuffer | Blob;
      };
      const blob =
        f.content instanceof Blob
          ? f.content
          : new Blob([f.content as BlobPart], { type: f.type || 'text/plain' });
      form.append('file', blob, f.name);
    }
    if (payload.document_date) form.append('document_date', payload.document_date);
    if (payload.sensitivity) form.append('sensitivity', payload.sensitivity);
    if (payload.audience_roles && payload.audience_roles.length > 0) {
      form.append('audience_roles', payload.audience_roles.join(','));
    }
    return request<Source>(
      `/api/v1/projects/${projectId}/sources/upload`,
      { method: 'POST', body: form },
      idempotencyKey
    );
  },
  importGithub: (projectId, payload, idempotencyKey) =>
    request<GithubImportResponse>(
      `/api/v1/projects/${projectId}/sources/github`,
      { method: 'POST', body: JSON.stringify(payload) },
      idempotencyKey
    ),
  getSource: (sourceId) => request<Source>(`/api/v1/sources/${sourceId}`),
  getSourceExcerpt: (sourceId, charStart, charEnd) =>
    request<SourceExcerptResponse>(
      `/api/v1/sources/${sourceId}/excerpt?char_start=${charStart}&char_end=${charEnd}`
    ),
  archiveSource: (sourceId) =>
    request<Source>(`/api/v1/sources/${sourceId}/archive`, { method: 'POST' }),
  startExtraction: (projectId, sourceIds) =>
    request<ExtractionRun>(`/api/v1/projects/${projectId}/extractions`, {
      method: 'POST',
      body: JSON.stringify(sourceIds ? { source_ids: sourceIds } : {}),
    }),
  getExtractionRun: (runId) => request<ExtractionRun>(`/api/v1/extractions/${runId}`),
  listClaims: (projectId, filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v && v !== 'ALL') params.set(k, v);
    });
    const qs = params.toString() ? `?${params.toString()}` : '';
    return request<PaginatedList<Claim>>(`/api/v1/projects/${projectId}/claims${qs}`);
  },
  getClaim: (claimId) => request<ClaimDetail>(`/api/v1/claims/${claimId}`),
  reviewClaim: (claimId, payload, idempotencyKey) =>
    request<ReviewResponse>(
      `/api/v1/claims/${claimId}/reviews`,
      { method: 'POST', body: JSON.stringify(payload) },
      idempotencyKey
    ),
  listConflicts: (projectId, status) => {
    const qs = status && status !== 'ALL' ? `?status=${encodeURIComponent(status)}` : '';
    return request<PaginatedList<Conflict>>(`/api/v1/projects/${projectId}/conflicts${qs}`);
  },
  getConflict: (conflictId) => request<Conflict>(`/api/v1/conflicts/${conflictId}`),
  resolveConflict: (conflictId, payload) =>
    request<Conflict>(`/api/v1/conflicts/${conflictId}/resolution`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listHandovers: (projectId) =>
    request<PaginatedList<Handover>>(`/api/v1/projects/${projectId}/handovers`),
  createHandover: (projectId, recipientRole, idempotencyKey) =>
    request<Handover>(
      `/api/v1/projects/${projectId}/handovers`,
      { method: 'POST', body: JSON.stringify({ recipient_role: recipientRole }) },
      idempotencyKey
    ),
  refreshHandover: (handoverId) =>
    request<Handover>(`/api/v1/handovers/${handoverId}/refresh`, { method: 'POST' }),
  getHandoverEligibility: (handoverId) =>
    request<Eligibility>(`/api/v1/handovers/${handoverId}/eligibility`),
  approveHandover: (handoverId, overrideReason, idempotencyKey) =>
    request<Handover>(
      `/api/v1/handovers/${handoverId}/approve`,
      { method: 'POST', body: JSON.stringify({ override_reason: overrideReason }) },
      idempotencyKey
    ),
  revokeHandover: (handoverId) =>
    request<Handover>(`/api/v1/handovers/${handoverId}/revoke`, { method: 'POST' }),
  getHandoverDetail: (handoverId) =>
    request<HandoverDetail>(`/api/v1/handovers/${handoverId}`),
  listColdStartTasks: (handoverId) =>
    request<ColdStartTask[]>(`/api/v1/handovers/${handoverId}/cold-start/tasks`),
  submitColdStartResult: (taskId, payload, idempotencyKey) =>
    request<ColdStartResult>(
      `/api/v1/cold-start/tasks/${taskId}/results`,
      { method: 'POST', body: JSON.stringify(payload) },
      idempotencyKey
    ),
  getColdStartSummary: (handoverId) =>
    request<ColdStartSummary>(`/api/v1/handovers/${handoverId}/cold-start/summary`),
  listAudit: (projectId) =>
    request<PaginatedList<AuditEntry>>(`/api/v1/projects/${projectId}/audit`),
};
