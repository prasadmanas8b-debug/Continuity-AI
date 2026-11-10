# Continuity AI — Evidence-First Project Knowledge Handover (Unified Full-Stack Release)

[![Contract Version](https://img.shields.io/badge/Contract%20Version-1.0.0-blue.svg)](contracts/CONTRACT_VERSION)
[![Backend Tests](https://img.shields.io/badge/Backend%20Tests-51%20Passed-brightgreen.svg)](docs/TEST_EVIDENCE.md)
[![Frontend & E2E Tests](https://img.shields.io/badge/Frontend%20%26%20E2E-18%20Passed-brightgreen.svg)](docs/TEST_EVIDENCE.md)
[![API Mode](https://img.shields.io/badge/VITE__API__MODE-real-emerald.svg)](#quick-start)

Continuity AI reconstructs project state from authorised sources (`PDF`, `TXT`, `MD`, and limited public GitHub repositories), links every claim to an exact supporting quote with precise character locators, surfaces contradictions side-by-side without picking unverified winners by timestamp, supports human review with optimistic concurrency (`expected_version`), generates immutable role-filtered handover snapshots (`backend_developer` vs `designer`), and verifies onboarding readiness through a 3-task Cold-Start Test.

## 1. Quick Start (Unified Full-Stack Setup)

### Prerequisites
- **Backend**: Python 3.11+ (`fastapi`, `uvicorn`, `pydantic`, `pypdf`, `reportlab`, `httpx`, `python-multipart`)
- **Frontend**: Node.js 18+ / 20+ (`npm`)

### Step 1 — Seed & Start the FastAPI Backend (`http://localhost:8000`)
From the repository root:
```bash
# 1. Install backend dependencies (if not already installed)
pip install -r backend/requirements.txt

# 2. Seed (or reset) the SQLite database with the synthetic Roomiez scenario
PYTHONPATH=backend python3 -m app.seed --reset

# 3. Start the FastAPI server on port 8000
PYTHONPATH=backend python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Step 2 — Start the React + TypeScript Frontend (`http://localhost:5173`)
In a second terminal:
```bash
cd frontend

# Ensure VITE_API_MODE=real and VITE_API_BASE_URL=http://localhost:8000/api/v1 (pre-configured in frontend/.env)
npm run dev
```
Open `http://localhost:5173` in your browser. The header displays `LIVE API (http://localhost:8000/api/v1)`, `DEMO AUTH`, and `REPLAY` (`CONTRACT v1.0.0`).

### Step 3 — Run All Automated Verification Suites
```bash
# 1. Backend Contract, Unit & Integration Suite (51 tests)
python3 tests/test_runner.py

# 2. Frontend TypeScript Typecheck & Contract/Matrix Suite (9 tests)
cd frontend && npm run typecheck && npm test && npm run build && cd ..

# 3. Live HTTP Full-Stack 9-Step Judge Journey (with backend running on :8000)
python3 smoke_live_test.py
node frontend/tests/run_e2e_live_journey.mjs
```

## 2. Demo Personas & 9-Step Judge Journey (Section 3.5)

| Persona | User ID | Role | Recipient Role |
| :--- | :--- | :--- | :--- |
| **Manas Prasad** | `user-manager-001` | `manager` | `null` |
| **Sarah Chen** | `user-contributor-001` | `contributor` | `null` |
| **Alex Rivera** | `user-incoming-backend-001` | `incoming_member` | `backend_developer` |
| **Jordan Lee** | `user-incoming-designer-001` | `incoming_member` | `designer` |

1. **S0 Login as Manager**: Sign in as `user-manager-001` (`POST /api/v1/auth/demo-login`), storing the Bearer token in memory and `sessionStorage`.
2. **S1, S2 & S3 Sources**: Inspect the 5 seeded sources (`project_notes.pdf`, `meeting_notes.txt`, `task_notes.md`, `design_notes.md`, `credentials_note.txt`), view character-offset excerpts (`GET /api/v1/sources/{id}/excerpt`), or test upload/GitHub error envelopes (`EMPTY_FILE`, `FILE_TOO_LARGE`, `UNSUPPORTED_FILE_TYPE`, `DUPLICATE_SOURCE`, `GITHUB_URL_INVALID`).
3. **S4 & S5 Extraction & Claims**: Trigger `POST /api/v1/projects/proj-roomiez-001/extractions` (202 async polling) to extract 12 claims across 8 `fact_type` categories, automatically flagging `staging_db_credentials` as `restricted`.
4. **S6 Conflict Review**: Inspect the critical contradiction on `login_authentication` (`"Login authentication is incomplete."` from Nov 2 vs `"Login authentication has been completed."` from Nov 6) displayed side-by-side without picking a winner by timestamp.
5. **S7 Human Review**: Edit `jwt_sessions` (preserving `original_statement`), accept verified backend claims, and mark `login_authentication` as `unresolved` with `expected_version` optimistic concurrency (`409 STALE_VERSION`).
6. **S8 Handover Approval Override Gate**: Create a `backend_developer` handover draft; verify default approval is blocked (`409 APPROVAL_BLOCKED_CONFLICT`) until a >=10 character manager `override_reason` is supplied.
7. **S9 Incoming Backend View**: Switch to `user-incoming-backend-001` (`Alex Rivera`) to view the 8 approved `backend_developer` claims, the open-conflict override banner, `Disputed` badge, and neutral `excluded_claim_count` line.
8. **S10 & S11 Cold-Start Test & Summary**: Complete the 3 deterministic tasks (`needs_help` with required `missing_information` note + `pass`), confirming zero `expected_reference` answer-key leakage, and inspect aggregate manager metrics on `S11`.
9. **S9 Designer Role-Isolation Check**: Approve the `designer` handover and switch to `user-incoming-designer-001` (`Jordan Lee`); confirm only the 2 design claims (`signup_button_color`, `signup_mockups`) are visible, restricted credentials (`staging_db_password`) are completely absent, and cross-role access to the backend handover returns `404 NOT_FOUND`.
