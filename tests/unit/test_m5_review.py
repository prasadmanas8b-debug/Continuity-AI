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
from app.schemas.enums import ErrorCode, FactType, ReviewDecision, ReviewStatus, VerificationStatus


class TestM5Review(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.client = TestClient(app)
        self.project_id = f"proj-m5-{uuid.uuid4()}"
        self.manager_id = f"user-mgr-{uuid.uuid4()}"
        self.contributor_id = f"user-contrib-{uuid.uuid4()}"
        self.run_id = f"run-m5-{uuid.uuid4()}"
        now = get_utc_now()
        with db.transaction() as cur:
            cur.execute("INSERT OR IGNORE INTO users (user_id, display_name, email, created_at) VALUES (?, 'Mgr', ?, ?)", (self.manager_id, f"{self.manager_id}@test.com", now))
            cur.execute("INSERT OR IGNORE INTO users (user_id, display_name, email, created_at) VALUES (?, 'Contrib', ?, ?)", (self.contributor_id, f"{self.contributor_id}@test.com", now))
            cur.execute("INSERT OR IGNORE INTO projects (project_id, name, created_at, updated_at) VALUES (?, 'M5 Proj', ?, ?)", (self.project_id, now, now))
            cur.execute("INSERT OR IGNORE INTO project_memberships (project_id, user_id, role, membership_status, created_at) VALUES (?, ?, 'manager', 'active', ?)", (self.project_id, self.manager_id, now))
            cur.execute("INSERT OR IGNORE INTO project_memberships (project_id, user_id, role, membership_status, created_at) VALUES (?, ?, 'contributor', 'active', ?)", (self.project_id, self.contributor_id, now))
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
        contrib_token, _ = create_access_token(self.contributor_id)
        self.mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
        self.contrib_headers = {"Authorization": f"Bearer {contrib_token}"}

    def _insert_claim(self, verif="verified", statement="Login authentication is incomplete.") -> str:
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
                ) VALUES (?, ?, 'txt', 's.txt', 's.txt', 'k', ?, 100, 'normal', '[]', 'processed', NULL, NULL, '{}', ?)
                """,
                (sid, self.project_id, f"h-{sid}", now),
            )
            cur.execute("INSERT INTO source_texts (source_id, text, page_offsets) VALUES (?, ?, '[0]')", (sid, statement))
            cur.execute(
                """
                INSERT INTO claims (
                    claim_id, project_id, extraction_run_id, item_id, fact_type,
                    original_statement, statement, owner, verification_status,
                    conflict_status, review_status, sensitivity, audience_roles,
                    version, archived, created_at, updated_at
                ) VALUES (?, ?, ?, 'login_auth', 'status', ?, ?, NULL, ?, 'none', 'pending', 'normal', '[]', 1, 0, ?, ?)
                """,
                (cid, self.project_id, self.run_id, statement, statement, verif, now, now),
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

    def test_accept_verified_claim(self):
        cid = self._insert_claim(verif="verified")
        resp = self.client.post(
            f"/api/v1/claims/{cid}/reviews",
            headers=self.mgr_headers,
            json={"decision": "accept", "expected_version": 1},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["review"]["decision"], "accept")
        self.assertEqual(data["claim"]["review_status"], "accepted")
        self.assertEqual(data["claim"]["version"], 2)

    def test_stale_version_returns_409(self):
        cid = self._insert_claim(verif="verified")
        # Send expected_version 99 which does not match current version 1
        resp = self.client.post(
            f"/api/v1/claims/{cid}/reviews",
            headers=self.mgr_headers,
            json={"decision": "accept", "expected_version": 99},
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["error"]["code"], ErrorCode.STALE_VERSION.value)

    def test_edit_preserves_original_statement(self):
        original_text = "Login authentication is incomplete."
        cid = self._insert_claim(verif="verified", statement=original_text)
        new_text = "Login authentication backend is mostly complete."
        resp = self.client.post(
            f"/api/v1/claims/{cid}/reviews",
            headers=self.mgr_headers,
            json={
                "decision": "edit",
                "reviewed_statement": new_text,
                "reason": "Updating based on recent standup remarks.",
                "expected_version": 1,
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["claim"]["statement"], new_text)
        self.assertEqual(data["claim"]["original_statement"], original_text)

    def test_blank_edit_blocked_422(self):
        cid = self._insert_claim(verif="verified")
        resp = self.client.post(
            f"/api/v1/claims/{cid}/reviews",
            headers=self.mgr_headers,
            json={
                "decision": "edit",
                "reviewed_statement": "   ",
                "reason": "Blank statement test",
                "expected_version": 1,
            },
        )
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["error"]["code"], ErrorCode.VALIDATION_ERROR.value)

    def test_accept_rejected_verification_blocked_422(self):
        cid = self._insert_claim(verif="rejected")
        resp = self.client.post(
            f"/api/v1/claims/{cid}/reviews",
            headers=self.mgr_headers,
            json={"decision": "accept", "expected_version": 1},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["error"]["code"], ErrorCode.CLAIM_NOT_ACCEPTABLE.value)

    def test_contributor_forbidden_403(self):
        cid = self._insert_claim(verif="verified")
        resp = self.client.post(
            f"/api/v1/claims/{cid}/reviews",
            headers=self.contrib_headers,
            json={"decision": "accept", "expected_version": 1},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["error"]["code"], ErrorCode.FORBIDDEN.value)


if __name__ == "__main__":
    unittest.main()
