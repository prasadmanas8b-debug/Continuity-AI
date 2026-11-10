import dns from "node:dns"; dns.setDefaultResultOrder("ipv4first");
/**
 * Continuity AI — Frontend TypeScript realApi.ts + client.ts Live E2E Verification
 * Compiles src/api/client.ts and src/api/realApi.ts via TypeScript and executes
 * the full 9-step Judge Journey and S0–S11 API contract against http://localhost:8000/api/v1.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FE_ROOT = path.resolve(__dirname, '..');

function loadTsModule(relPath, deps = {}) {
  const fullPath = path.join(FE_ROOT, relPath);
  let code = fs.readFileSync(fullPath, 'utf-8');
  code = code.replace(/import\.meta/g, '({ env: { VITE_API_MODE: "real", VITE_API_BASE_URL: "http://localhost:8000/api/v1" } })');
  const transpiled = ts.transpileModule(code, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.CommonJS,
      esModuleInterop: true,
    },
  }).outputText;
  const mod = { exports: {} };
  const fn = new Function('exports', 'require', 'module', transpiled);
  fn(mod.exports, (req) => deps[req] || {}, mod);
  return mod.exports;
}

const clientMod = loadTsModule('src/api/client.ts');
const realApiMod = loadTsModule('src/api/realApi.ts', { './client': clientMod });
const { realApi } = realApiMod;
const { getAuthToken, ApiError } = clientMod;

console.log('=== Continuity AI — Frontend realApi.ts Live Full-Stack E2E Test ===');

// 0. Health & Meta
const health = await realApi.getHealth();
assert.equal(health.status, 'ok');
const meta = await realApi.getMeta();
assert.equal(meta.contract_version, '1.0.0');
console.log('  [PASS] S0 Handshake: /health & /api/v1/meta verified (contract_version=1.0.0)');

// 1. S0 Demo Login
const demoUsers = await realApi.listDemoUsers();
assert.equal(demoUsers.length, 4);
const loginRes = await realApi.demoLogin('user-manager-001');
assert.ok(loginRes.access_token);
assert.equal(getAuthToken(), loginRes.access_token);
console.log('  [PASS] Step 1 (S0 Login): demoLogin stored Bearer token via client.ts setAuthToken');

// 2. S1 & S2 & S3 Projects and Sources
const projs = await realApi.listProjects();
assert.ok(projs.items.length >= 1);
const projId = projs.items[0].project_id;
const srcs = await realApi.listSources(projId);
assert.equal(srcs.items.length, 5);
const excerpt = await realApi.getSourceExcerpt(srcs.items[0].source_id, 0, 100);
assert.ok(excerpt.text.length > 0);

// S2 Upload Error Envelope Check (EMPTY_FILE -> ApiError)
let emptyCaught = false;
try {
  await realApi.uploadSource(projId, {
    file: { name: 'empty.txt', size: 0, type: 'text/plain', content: '' },
  });
} catch (err) {
  assert.ok(err instanceof ApiError);
  assert.equal(err.code, 'EMPTY_FILE');
  assert.equal(err.userMessage, 'The file is empty. Choose a file that contains text.');
  emptyCaught = true;
}
assert.ok(emptyCaught, 'EMPTY_FILE error envelope mapped by client.ts');
console.log('  [PASS] Step 2 (S1/S2/S3 Sources): 5 seeded sources, excerpt viewer, and ApiError envelope verified');

// 3. S4 & S5 Extraction and Claims
const extRun = await realApi.startExtraction(projId);
const polledRun = await realApi.getExtractionRun(extRun.run_id);
assert.equal(polledRun.status, 'succeeded');
assert.equal(polledRun.claims_created, 12);

const allClaims = await realApi.listClaims(projId);
assert.equal(allClaims.items.length, 12);
const restricted = allClaims.items.filter((c) => c.sensitivity === 'restricted');
assert.equal(restricted.length, 1);
assert.equal(restricted[0].item_id, 'staging_db_credentials');
console.log('  [PASS] Step 3 (S4/S5 Extraction & Claims): 12 claims extracted, 1 restricted credential claim isolated');

// 4. S6 Conflict Review
const conflicts = await realApi.listConflicts(projId);
const loginConflict = conflicts.items.find((c) => c.item_id === 'login_authentication');
assert.ok(loginConflict);
assert.equal(loginConflict.is_critical, true);
assert.equal(loginConflict.claims.length, 2);
console.log('  [PASS] Step 4 (S6 Conflicts): Side-by-side login_authentication contradiction detected');

// 5. S7 Human Review & Optimistic Concurrency
const jwtClaim = allClaims.items.find((c) => c.item_id === 'jwt_sessions');
const revEdit = await realApi.reviewClaim(jwtClaim.claim_id, {
  decision: 'edit',
  reviewed_statement: 'Use stateless JWT sessions (HS256) instead of server sessions.',
  reason: 'Clarified HS256 signing in review.',
  expected_version: jwtClaim.version,
});
assert.equal(revEdit.claim.review_status, 'edited');
assert.equal(revEdit.claim.original_statement, 'Use JWT sessions instead of server sessions.');

const freshClaims = await realApi.listClaims(projId);
for (const c of freshClaims.items) {
  if (['login_tests', 'login_testing_ownership', 'staging_database', 'password_reset'].includes(c.item_id) && c.review_status === 'pending') {
    await realApi.reviewClaim(c.claim_id, {
      decision: 'accept',
      reviewed_statement: null,
      reason: null,
      expected_version: c.version,
    });
  } else if (c.item_id === 'login_authentication' && c.review_status === 'pending') {
    await realApi.reviewClaim(c.claim_id, {
      decision: 'unresolved',
      reviewed_statement: null,
      reason: 'Keep open until OAuth callback check completes on staging.',
      expected_version: c.version,
    });
  }
}
console.log('  [PASS] Step 5 (S7 Review): Edited, accepted, and unresolved reviews recorded with original_statement intact');

// 6. S8 Handover Builder & Approval Override Gate
const beDraft = await realApi.createHandover(projId, 'backend_developer');
const elig = await realApi.getHandoverEligibility(beDraft.handover_id);
assert.equal(elig.can_approve_without_override, false);
assert.equal(elig.eligible_claim_count, 8);

let blockedCaught = false;
try {
  await realApi.approveHandover(beDraft.handover_id, null);
} catch (err) {
  assert.ok(err instanceof ApiError);
  assert.equal(err.code, 'APPROVAL_BLOCKED_CONFLICT');
  blockedCaught = true;
}
assert.ok(blockedCaught);

const beApproved = await realApi.approveHandover(
  beDraft.handover_id,
  'Sharing handover with login_authentication conflict explicitly marked Disputed for incoming backend developer.'
);
assert.equal(beApproved.status, 'approved');
assert.ok(beApproved.approval_override);
console.log('  [PASS] Step 6 (S8 Handover Approval): 409 APPROVAL_BLOCKED_CONFLICT enforced & override approval succeeded (8 claims)');

// 7. S9 Incoming Backend Developer View
await realApi.demoLogin('user-incoming-backend-001');
const beDetail = await realApi.getHandoverDetail(beDraft.handover_id);
assert.equal(beDetail.recipient_role, 'backend_developer');
assert.equal(beDetail.included_claim_count, 8);
assert.ok(beDetail.approval_override);
assert.ok(!JSON.stringify(beDetail).includes('staging_db_password'));
console.log('  [PASS] Step 7 (S9 Backend Handover View): Incoming backend developer sees 8 permitted claims + override banner');

// 8. S10 & S11 Cold-Start Test & Summary
const csTasks = await realApi.listColdStartTasks(beDraft.handover_id);
assert.equal(csTasks.length, 3);
assert.ok(!JSON.stringify(csTasks).includes('expected_reference'));

await realApi.submitColdStartResult(csTasks[0].task_id, {
  outcome: 'needs_help',
  time_seconds: 70,
  hints_used: 1,
  missing_information: 'Login authentication status is disputed between Nov 2 and Nov 6 notes.',
});
await realApi.submitColdStartResult(csTasks[1].task_id, {
  outcome: 'pass',
  time_seconds: 45,
  hints_used: 0,
  missing_information: null,
});
await realApi.submitColdStartResult(csTasks[2].task_id, {
  outcome: 'pass',
  time_seconds: 38,
  hints_used: 0,
  missing_information: null,
});

await realApi.demoLogin('user-manager-001');
const csSummary = await realApi.getColdStartSummary(beDraft.handover_id);
assert.equal(csSummary.tasks_total, 3);
assert.equal(csSummary.results_total, 3);
assert.equal(csSummary.pass_count, 2);
assert.equal(csSummary.needs_help_count, 1);
console.log('  [PASS] Step 8 (S10/S11 Cold-Start): 3 tasks completed without answer-key leak & manager summary verified');

// 9. S9 Designer Role-Isolation Check
for (const c of freshClaims.items) {
  if (c.audience_roles.includes('designer') && c.review_status === 'pending') {
    await realApi.reviewClaim(c.claim_id, {
      decision: 'accept',
      reviewed_statement: null,
      reason: null,
      expected_version: c.version,
    });
  }
}
const desDraft = await realApi.createHandover(projId, 'designer');
const desApproved = await realApi.approveHandover(desDraft.handover_id, null);
assert.equal(desApproved.status, 'approved');

await realApi.demoLogin('user-incoming-designer-001');
const desDetail = await realApi.getHandoverDetail(desDraft.handover_id);
assert.equal(desDetail.recipient_role, 'designer');
assert.equal(desDetail.included_claim_count, 2);
const desRaw = JSON.stringify(desDetail);
assert.ok(!desRaw.includes('staging_db_password'));
assert.ok(!desRaw.includes('login_authentication'));

let crossRoleBlocked = false;
try {
  await realApi.getHandoverDetail(beDraft.handover_id);
} catch (err) {
  assert.ok(err instanceof ApiError);
  assert.equal(err.status, 404);
  crossRoleBlocked = true;
}
assert.ok(crossRoleBlocked);
console.log('  [PASS] Step 9 (S9 Designer Isolation): Designer sees only 2 design claims; backend handover returns 404');

console.log('\nAll 9 End-to-End Judge Journey steps passed via frontend realApi.ts!');
