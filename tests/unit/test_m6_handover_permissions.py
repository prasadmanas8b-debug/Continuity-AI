import json
import os
import sys
import unittest
import uuid
from starlette.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from app.core.auth import create_access_token
from app.db.session import db, get_utc_now
from app.main import app
from app.schemas.enums import ErrorCode, FactType, RecipientRole, ReviewStatus, UserRole, VerificationStatus


class TestM6HandoverPermissions(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.client = TestClient(app)
        self.project_id = f"proj-m6-{uuid.uuid4()}"
        self.manager_id = f"user-mgr-{uuid.uuid4()}"
        self.backend_dev_id = f"user-dev-{uuid.uuid4()}"
        self.designer_id = f"user-des-{uuid.uuid4()}"
        self.run_id = f"run-m6-{uuid.uuid4()}"
        now = get_utc_now()
        with db.transaction() as cur:
            cur.execute("INSERT OR IGNORE INTO users (user_id, display_name, email, created_at) VALUES (?, 'Mgr', ?, ?)", (self.manager_id, f"{self.manager_id}@test.com", now))
            cur.execute("INSERT OR IGNORE INTO users (user_id, display_name, email, created_at) VALUES (?, 'Dev', ?, ?)", (self.backend_dev_id, f"{self.backend_dev_id}@test.com", now))
            cur.execute("INSERT OR IGNORE INTO users (user_id, display_name, email, created_at) VALUES (?, 'Des', ?, ?)", (self.designer_id, f"{self.designer_id}@test.com", now))

            cur.execute("INSERT OR IGNORE INTO projects (project_id, name, created_at, updated_at) VALUES (?, 'M6 Proj', ?, ?)", (self.project_id, now, now))
            cur.execute("INSERT OR IGNORE INTO project_memberships (project_id, user_id, role, membership_status, created_at) VALUES (?, ?, 'manager', 'active', ?)", (self.project_id, self.manager_id, now))
            cur.execute("INSERT OR IGNORE INTO project_memberships (project_id, user_id, role, recipient_role, membership_status, created_at) VALUES (?, ?, 'incoming_member', 'backend_developer', 'active', ?)", (self.project_id, self.backend_dev_id, now))
            cur.execute("INSERT OR IGNORE INTO project_memberships (project_id, user_id, role, recipient_role, membership_status, created_at) VALUES (?, ?, 'incoming_member', 'designer', 'active', ?)", (self.project_id, self.designer_id, now))
            cur.execute(
                """
                INSERT INTO extraction_runs (
                    run_id, project_id, status, source_ids, claims_created,
                    claims_rejected_by_validation, llm_provider, llm_model,
                    prompt_version, error_code, error_message, started_at, finished_at, started_by
                ) VALUES (?, ?, 'succeeded', '[]', 0, 0, 'fake', 'fake-v1', 'v1', NULL, NULL, ?, ?, ?)
                """,
                (self.run_id, self.project_id, now, now, self.manager_id),
            )

        mgr_token, _ = create_access_token(self.manager_id)
        dev_token, _ = create_access_token(self.backend_dev_id)
        des_token, _ = create_access_token(self.designer_id)

        self.mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
        self.dev_headers = {"Authorization": f"Bearer {dev_token}"}
        self.des_headers = {"Authorization": f"Bearer {des_token}"}

    def _insert_claim(self, item_id: str, fact_type: FactType, statement: str, review_status="accepted", sensitivity="normal", audience=["backend_developer"], verif="verified") -> str:
        cid = str(uuid.uuid4())
        sid = str(uuid.uuid4())
        now = get_utc_now()
        with db.transaction() as cur:
            cur.execute(
                """
                INSERT INTO sources (
                    source_id, project_id, source_type, filename, source_reference,
                    storage_key, content_hash, size_bytes, sensitivity, audience_roles,
                    ingestion_status, error_message, document_date, source_metadata, created_at
                ) VALUES (?, ?, 'txt', 's.txt', 's.txt', 'k', ?, 100, ?, '[]', 'processed', NULL, NULL, '{}', ?)
                """,
                (sid, self.project_id, f"h-{sid}", sensitivity, now),
            )
            cur.execute("INSERT INTO source_texts (source_id, text, page_offsets) VALUES (?, ?, '[0]')", (sid, statement))
            cur.execute(
                """
                INSERT INTO claims (
                    claim_id, project_id, extraction_run_id, item_id, fact_type,
                    original_statement, statement, owner, verification_status,
                    conflict_status, review_status, sensitivity, audience_roles,
                    version, archived, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, 'none', ?, ?, ?, 1, 0, ?, ?)
                """,
                (cid, self.project_id, self.run_id, item_id, fact_type.value, statement, statement, verif, review_status, sensitivity, json.dumps(audience), now, now),
            )
            cur.execute(
                """
                INSERT INTO evidence (
                    evidence_id, claim_id, source_id, exact_quote, locator,
                    quote_match_status, support_status, support_note, created_at
                ) VALUES (?, ?, ?, ?, '{\"page\": 1}', 'found', 'supports', NULL, ?)
                """,
                (str(uuid.uuid4()), cid, sid, statement, now),
            )
        return cid

    def test_create_and_approve_handover_flow(self):
        # Insert one backend claim
        c1 = self._insert_claim("login", FactType.STATUS, "Login authentication is complete.", review_status="accepted", audience=["backend_developer"])

        # 1. Manager creates draft handover for backend_developer
        resp_draft = self.client.post(
            f"/api/v1/projects/{self.project_id}/handovers",
            headers=self.mgr_headers,
            json={"recipient_role": "backend_developer"},
        )
        self.assertEqual(resp_draft.status_code, 201)
        draft_id = resp_draft.json()["handover_id"]
        self.assertEqual(resp_draft.json()["status"], "draft")
        self.assertEqual(resp_draft.json()["version"], 1)

        # 2. Incoming dev cannot access draft handover (404)
        resp_dev_draft = self.client.get(f"/api/v1/handovers/{draft_id}", headers=self.dev_headers)
        self.assertEqual(resp_dev_draft.status_code, 404)

        # 3. Manager approves handover
        resp_app = self.client.post(
            f"/api/v1/handovers/{draft_id}/approve",
            headers=self.mgr_headers,
            json={"override_reason": None},
        )
        self.assertEqual(resp_app.status_code, 200)
        self.assertEqual(resp_app.json()["status"], "approved")

        # 4. Incoming dev CAN access approved handover
        resp_dev = self.client.get(f"/api/v1/handovers/{draft_id}", headers=self.dev_headers)
        self.assertEqual(resp_dev.status_code, 200)
        dev_data = resp_dev.json()
        self.assertEqual(dev_data["recipient_role"], "backend_developer")
        self.assertEqual(dev_data["included_claim_count"], 1)

        # 5. Designer gets 404 (wrong role)
        resp_des = self.client.get(f"/api/v1/handovers/{draft_id}", headers=self.des_headers)
        self.assertEqual(resp_des.status_code, 404)

    def test_open_critical_conflict_blocks_approval_without_override(self):
        c1 = self._insert_claim("auth_state", FactType.STATUS, "Auth state is incomplete.", review_status="unresolved", audience=["backend_developer"])
        now = get_utc_now()
        # Create an open critical conflict
        conf_id = str(uuid.uuid4())
        with db.transaction() as cur:
            cur.execute(
                """
                INSERT INTO conflicts (
                    conflict_id, project_id, item_id, fact_type, conflict_type,
                    status, is_critical, summary, resolution_note, detection_key,
                    resolved_by, created_at, resolved_at
                ) VALUES (?, ?, 'auth_state', 'status', 'contradiction', 'open', 1, 'Critical status conflict', NULL, 'k-crit', NULL, ?, NULL)
                """,
                (conf_id, self.project_id, now),
            )
            cur.execute("INSERT INTO conflict_claims (conflict_id, claim_id) VALUES (?, ?)", (conf_id, c1))

        resp_draft = self.client.post(
            f"/api/v1/projects/{self.project_id}/handovers",
            headers=self.mgr_headers,
            json={"recipient_role": "backend_developer"},
        )
        self.assertEqual(resp_draft.status_code, 201)
        hid = resp_draft.json()["handover_id"]

        # Attempt approve without override -> 409 APPROVAL_BLOCKED_CONFLICT
        resp_fail = self.client.post(
            f"/api/v1/handovers/{hid}/approve",
            headers=self.mgr_headers,
            json={"override_reason": None},
        )
        self.assertEqual(resp_fail.status_code, 409)
        self.assertEqual(resp_fail.json()["error"]["code"], ErrorCode.APPROVAL_BLOCKED_CONFLICT.value)

        # Approve with valid override reason (at least 10 chars) -> 200
        resp_succ = self.client.post(
            f"/api/v1/handovers/{hid}/approve",
            headers=self.mgr_headers,
            json={"override_reason": "Proceeding with known open discrepancy for newcomer awareness."},
        )
        self.assertEqual(resp_succ.status_code, 200)
        self.assertEqual(resp_succ.json()["status"], "approved")

    def test_revoked_handover_returns_403(self):
        c1 = self._insert_claim("login", FactType.STATUS, "Login is complete.", review_status="accepted", audience=["backend_developer"])
        resp_draft = self.client.post(
            f"/api/v1/projects/{self.project_id}/handovers",
            headers=self.mgr_headers,
            json={"recipient_role": "backend_developer"},
        )
        hid = resp_draft.json()["handover_id"]
        self.client.post(f"/api/v1/handovers/{hid}/approve", headers=self.mgr_headers, json={"override_reason": None})

        # Revoke handover
        resp_rev = self.client.post(f"/api/v1/handovers/{hid}/revoke", headers=self.mgr_headers)
        self.assertEqual(resp_rev.status_code, 200)
        self.assertEqual(resp_rev.json()["status"], "revoked")

        # Read revoked handover -> 403 HANDOVER_REVOKED
        resp_read = self.client.get(f"/api/v1/handovers/{hid}", headers=self.dev_headers)
        self.assertEqual(resp_read.status_code, 403)
        self.assertEqual(resp_read.json()["error"]["code"], ErrorCode.HANDOVER_REVOKED.value)


if __name__ == "__main__":
    unittest.main()
