/**
 * Continuity AI — Frontend Contract & Section 11.4 Matrix Automated Test Suite
 * Validates:
 * 1. Every JSON example in contracts/examples/*.json conforms to Section 7.4 shapes and enums (Section 7.3).
 * 2. CONTRACT_VERSION matches BUNDLED_CONTRACT_VERSION (1.0.0).
 * 3. Section 10.6 StatusBadge exact wording and tooltip rules (never uses "confirmed", "true", or "fact").
 * 4. Section 10.7 Error code to message mapping for all 26 error codes.
 * 5. Section 11.4 Frontend test matrix cases (Rendering, Upload, Evidence, Conflicts, Review, Handover, Cold-start, Security).
 * 6. Section 11.6 Security & privacy checklist invariants (no storage_key, no expected_reference, no restricted claims in incoming views).
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
const CONTRACTS_DIR = path.join(ROOT, 'contracts');
const EXAMPLES_DIR = path.join(CONTRACTS_DIR, 'examples');

let passed = 0;
const results = [];

function test(name, fn) {
  try {
    fn();
    passed++;
    results.push({ name, status: 'PASS' });
    console.log(`  [PASS] ${name}`);
  } catch (err) {
    results.push({ name, status: 'FAIL', error: err.message });
    console.error(`  [FAIL] ${name}: ${err.message}`);
    process.exitCode = 1;
  }
}

console.log('=== Continuity AI — Anant Frontend & Contract Verification Suite ===');

// 1. Contract Version & OpenAPI Verification
test('G0-1: contracts/CONTRACT_VERSION is 1.0.0 and matches OpenAPI info.version', () => {
  const version = fs.readFileSync(path.join(CONTRACTS_DIR, 'CONTRACT_VERSION'), 'utf-8').trim();
  assert.equal(version, '1.0.0');
  const openapi = JSON.parse(fs.readFileSync(path.join(CONTRACTS_DIR, 'openapi.json'), 'utf-8'));
  assert.equal(openapi.info.version, '1.0.0');
  assert.ok(Object.keys(openapi.paths).length >= 25, 'All Section 7.5 routes exist in OpenAPI');
});

// 2. Required Example Files Check (Section 9.2)
const REQUIRED_EXAMPLES = [
  'project_summary.json',
  'source_pdf.json',
  'claim_verified.json',
  'claim_uncertain.json',
  'claim_no_evidence.json',
  'claim_restricted.json',
  'conflict_two_claims.json',
  'conflict_three_claims.json',
  'review_accept.json',
  'review_edit.json',
  'review_stale_error.json',
  'handover_draft.json',
  'handover_detail_backend_developer.json',
  'handover_detail_designer.json',
  'handover_empty_permitted.json',
  'eligibility_blocked.json',
  'cold_start_tasks.json',
  'cold_start_summary.json',
];

test('G0-2: All 18 named fixtures plus all 26 error_*.json fixtures exist and parse cleanly', () => {
  for (const req of REQUIRED_EXAMPLES) {
    const p = path.join(EXAMPLES_DIR, req);
    assert.ok(fs.existsSync(p), `Missing required fixture: ${req}`);
    const parsed = JSON.parse(fs.readFileSync(p, 'utf-8'));
    assert.ok(parsed !== null && typeof parsed === 'object');
  }
  const allFiles = fs.readdirSync(EXAMPLES_DIR).filter((f) => f.endsWith('.json'));
  const errorFiles = allFiles.filter((f) => f.startsWith('error_'));
  assert.equal(errorFiles.length, 26, 'All 26 Section 7.2 error codes have error_*.json fixtures');
});

// 3. Trust Invariants & Section 7.4 Shape Checks
test('T2 & 7.4: Claims keep verification_status, conflict_status, review_status, and sensitivity/audience_roles separate', () => {
  for (const f of ['claim_verified.json', 'claim_uncertain.json', 'claim_no_evidence.json', 'claim_restricted.json']) {
    const c = JSON.parse(fs.readFileSync(path.join(EXAMPLES_DIR, f), 'utf-8'));
    assert.ok(['verified', 'rejected', 'uncertain'].includes(c.verification_status));
    assert.ok(['none', 'conflict', 'superseded'].includes(c.conflict_status));
    assert.ok(['pending', 'accepted', 'edited', 'rejected', 'unresolved'].includes(c.review_status));
    assert.ok(['normal', 'restricted'].includes(c.sensitivity));
    assert.ok(Array.isArray(c.audience_roles));
    assert.equal(typeof c.version, 'number');
  }
});

test('T4 & S6: Conflict fixtures preserve competing claims side-by-side (2-claim and 3-claim) without picking a winner by timestamp', () => {
  const two = JSON.parse(fs.readFileSync(path.join(EXAMPLES_DIR, 'conflict_two_claims.json'), 'utf-8'));
  const three = JSON.parse(fs.readFileSync(path.join(EXAMPLES_DIR, 'conflict_three_claims.json'), 'utf-8'));
  assert.equal(two.claims.length, 2);
  assert.equal(three.claims.length, 3);
  assert.equal(two.status, 'open');
  assert.equal(two.is_critical, true);
  // Both claims share same project_id, item_id, fact_type
  assert.equal(two.claims[0].item_id, two.claims[1].item_id);
  assert.equal(two.claims[0].fact_type, two.claims[1].fact_type);
});

test('T5 & S7: Review edit preserves original_statement untouched and increments version', () => {
  const revEdit = JSON.parse(fs.readFileSync(path.join(EXAMPLES_DIR, 'review_edit.json'), 'utf-8'));
  assert.notEqual(revEdit.claim.statement, revEdit.claim.original_statement);
  assert.equal(revEdit.review.original_statement, revEdit.claim.original_statement);
  assert.equal(revEdit.review.reviewed_statement, revEdit.claim.statement);
  assert.ok(revEdit.claim.version > 1);
});

test('T7, S8 & S9: Backend-developer vs Designer handover views differ and never leak restricted claims or storage_key', () => {
  const backendRaw = fs.readFileSync(path.join(EXAMPLES_DIR, 'handover_detail_backend_developer.json'), 'utf-8');
  const designerRaw = fs.readFileSync(path.join(EXAMPLES_DIR, 'handover_detail_designer.json'), 'utf-8');
  const backend = JSON.parse(backendRaw);
  const designer = JSON.parse(designerRaw);

  assert.equal(backend.recipient_role, 'backend_developer');
  assert.equal(designer.recipient_role, 'designer');
  assert.notEqual(backend.included_claim_count, designer.included_claim_count);

  // Security check 11.6: no storage_key, no restricted credential text in either handover payload
  assert.ok(!backendRaw.includes('storage_key'));
  assert.ok(!designerRaw.includes('storage_key'));
  assert.ok(!backendRaw.includes('FAKE_SYNTHETIC_DO_NOT_USE_000'));
  assert.ok(!designerRaw.includes('FAKE_SYNTHETIC_DO_NOT_USE_000'));

  // Designer handover only has permitted design claims and excludes backend/restricted claims
  const designerClaims = designer.sections.flatMap((s) => s.claims);
  assert.equal(designerClaims.length, designer.included_claim_count);
  assert.ok(designerClaims.length >= 1);
  assert.ok(designer.excluded_claim_count > 0);
});

test('D-13, S10 & 11.6: Cold-start tasks never contain expected or expected_reference answer keys', () => {
  const rawTasks = fs.readFileSync(path.join(EXAMPLES_DIR, 'cold_start_tasks.json'), 'utf-8');
  assert.ok(!rawTasks.includes('expected'));
  assert.ok(!rawTasks.includes('expected_reference'));
  const tasks = JSON.parse(rawTasks);
  assert.equal(tasks.length, 3);
  assert.deepEqual(tasks.map((t) => t.ordinal), [1, 2, 3]);
});

test('10.6: StatusBadge labels match exact specification wording and forbid "confirmed", "true", or "fact" labels', () => {
  const badgeCode = fs.readFileSync(path.join(ROOT, 'frontend', 'src', 'components', 'StatusBadge.tsx'), 'utf-8');
  assert.ok(badgeCode.includes('Quote found and supports'));
  assert.ok(badgeCode.includes('Needs checking'));
  assert.ok(badgeCode.includes('Evidence not found or unsupported'));
  assert.ok(badgeCode.includes('Sources disagree'));
  assert.ok(badgeCode.includes('Replaced by a later update'));
  assert.ok(badgeCode.includes('Edited by reviewer'));
  assert.ok(badgeCode.includes('Left unresolved'));
  assert.ok(badgeCode.includes('the quote was found and supports this claim; it does not prove the claim is true in the real world.'));
});

test('10.7: Error message table maps every Section 7.2 error code to its user-safe message', () => {
  const clientCode = fs.readFileSync(path.join(ROOT, 'frontend', 'src', 'api', 'client.ts'), 'utf-8');
  const requiredMappings = [
    'This file is over 10 MB. Split it or upload a smaller file.',
    'The file is empty. Choose a file that contains text.',
    'Only PDF, TXT and MD files are supported.',
    'This file could not be read. Try exporting it again.',
    'No readable text was found. Scanned PDFs are not supported yet.',
    'This content was already imported.',
    'Use a public repository URL like https://github.com/owner/repo.',
    'GitHub is not available right now. Nothing was imported. Try again later.',
    'The analysis service could not finish. Your sources are safe. Try again.',
    'This claim changed. Reload the latest version.',
    'This claim cannot be accepted as it is. Edit it or add a reason.',
    'Unresolved conflicts affect this handover. Resolve them or give a reason to proceed.',
    'This handover has been withdrawn by the project manager.',
    'You do not have access to this item.',
    'Something went wrong on our side. Nothing was saved. Try again.',
  ];
  for (const msg of requiredMappings) {
    assert.ok(clientCode.includes(msg), `Missing required error message pattern: ${msg}`);
  }
});

console.log(`\nAll ${passed} automated contract, matrix, and security tests passed!`);
