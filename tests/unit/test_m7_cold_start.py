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
from app.schemas.enums import ColdStartOutcome, ErrorCode, FactType


class TestM7ColdStart(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.client = TestClient(app)
        self.project_id = f"proj-m7-{uuid.uuid4()}"
        self.manager_id = f"user-mgr-{uuid.uuid4()}"
        self.backend_dev_id = f"user-dev-{uuid.uuid4()}"
        self.run_id = f"run-m7-{uuid.uuid4()}"
        now = get_utc_now()
        with db.transaction() as cur:
            cur.execute("INSERT OR IGNORE INTO users (user_id, display_name, email, created_at) VALUES (?, 'Mgr', ?, ?)", (self.manager_id, f"{self.manager_id}@test.com", now))
            cur.execute("INSERT OR IGNORE INTO users (user_id, display_name, email, created_at) VALUES (?, 'Dev', ?, ?)", (self.backend_dev_id, f"{self.backend_dev_id}@test.com", now))
            cur.execute("INSERT OR IGNORE INTO projects (project_id, name, created_at, updated_at) VALUES (?, 'M7 Proj', ?, ?)", (self.project_id, now, now))
            cur.execute("INSERT OR IGNORE INTO project_memberships (project_id, user_id, role, membership_status, created_at) VALUES (?, ?, 'manager', 'active', ?)", (self.project_id, self.manager_id, now))
            cur.execute("INSERT OR IGNORE INTO project_memberships (project_id, user_id, role, recipient_role, membership_status, created_at) VALUES (?, ?, 'incoming_member', 'backend_developer', 'active', ?)", (self.project_id, self.backend_dev_id, now))

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
        self.mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
        self.dev_headers = {"Authorization": f"Bearer {dev_token}"}

        # Seed claims and approve handover to generate cold-start tasks
        self._setup_approved_handover()

    def _setup_approved_handover(self):
        cid1 = str(uuid.uuid4())
        cid2 = str(uuid.uuid4())
        cid3 = str(uuid.uuid4())
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
            cur.execute("INSERT INTO source_texts (source_id, text, page_offsets) VALUES (?, 'Full text', '[0]')", (sid,))

            # 1. Status claim
            cur.execute(
                """
                INSERT INTO claims (
                    claim_id, project_id, extraction_run_id, item_id, fact_type,
                    original_statement, statement, owner, verification_status,
                    conflict_status, review_status, sensitivity, audience_roles,
                    version, archived, created_at, updated_at
                ) VALUES (?, ?, ?, 'login_authentication', 'status', 'Login auth is complete.', 'Login auth is complete.', NULL, 'verified', 'none', 'accepted', 'normal', '[\"backend_developer\"]', 1, 0, ?, ?)
                """,
                (cid1, self.project_id, self.run_id, now, now),
            )
            # 2. Next action claim
            cur.execute(
                """
                INSERT INTO claims (
                    claim_id, project_id, extraction_run_id, item_id, fact_type,
                    original_statement, statement, owner, verification_status,
                    conflict_status, review_status, sensitivity, audience_roles,
                    version, archived, created_at, updated_at
                ) VALUES (?, ?, ?, 'login_tests', 'next_action', 'Write test suites.', 'Write test suites.', 'Ravi', 'verified', 'none', 'accepted', 'normal', '[\"backend_developer\"]', 1, 0, ?, ?)
                """,
                (cid2, self.project_id, self.run_id, now, now),
            )
            # 3. Dependency claim
            cur.execute(
                """
                INSERT INTO claims (
                    claim_id, project_id, extraction_run_id, item_id, fact_type,
                    original_statement, statement, owner, verification_status,
                    conflict_status, review_status, sensitivity, audience_roles,
                    version, archived, created_at, updated_at
                ) VALUES (?, ?, ?, 'login_tests', 'dependency', 'Needs staging.', 'Needs staging.', NULL, 'verified', 'none', 'accepted', 'normal', '[\"backend_developer\"]', 1, 0, ?, ?)
                """,
                (cid3, self.project_id, self.run_id, now, now),
            )

            for cid in (cid1, cid2, cid3):
                cur.execute(
                    """
                    INSERT INTO evidence (
                        evidence_id, claim_id, source_id, exact_quote, locator,
                        quote_match_status, support_status, support_note, created_at
                    ) VALUES (?, ?, ?, 'Full text', '{\"page\": 1}', 'found', 'supports', NULL, ?)
                    """,
                    (str(uuid.uuid4()), cid, sid, now),
                )

        # Create draft and approve
        resp_draft = self.client.post(
            f"/api/v1/projects/{self.project_id}/handovers",
            headers=self.mgr_headers,
            json={"recipient_role": "backend_developer"},
        )
        self.handover_id = resp_draft.json()["handover_id"]
        self.client.post(
            f"/api/v1/handovers/{self.handover_id}/approve",
            headers=self.mgr_headers,
            json={"override_reason": None},
        )

    def test_answer_key_protection_never_leaks(self):
        resp = self.client.get(
            f"/api/v1/handovers/{self.handover_id}/cold-start/tasks",
            headers=self.dev_headers,
        )
        self.assertEqual(resp.status_code, 200)
        tasks = resp.json()
        self.assertTrue(len(tasks) >= 2)
        raw_text = resp.text
        # Assert expected and expected_reference never leak to client
        self.assertNotIn("expected_reference", raw_text)
        self.assertNotIn("expected_status", raw_text)
        self.assertNotIn("expected_owner", raw_text)

    def test_submit_pass_and_needs_help_results(self):
        resp_tasks = self.client.get(
            f"/api/v1/handovers/{self.handover_id}/cold-start/tasks",
            headers=self.dev_headers,
        )
        tasks = resp_tasks.json()
        task1 = tasks[0]
        task2 = tasks[1]

        # 1. Submit Pass result
        resp_res1 = self.client.post(
            f"/api/v1/cold-start/tasks/{task1['task_id']}/results",
            headers=self.dev_headers,
            json={
                "outcome": "pass",
                "time_seconds": 45,
                "hints_used": 0,
                "missing_information": None,
            },
        )
        self.assertEqual(resp_res1.status_code, 201)
        self.assertEqual(resp_res1.json()["outcome"], "pass")

        # 2. Submit Needs Help without note -> 422
        resp_fail = self.client.post(
            f"/api/v1/cold-start/tasks/{task2['task_id']}/results",
            headers=self.dev_headers,
            json={
                "outcome": "needs_help",
                "time_seconds": 60,
                "hints_used": 1,
                "missing_information": "",
            },
        )
        self.assertEqual(resp_fail.status_code, 422)

        # 3. Submit Needs Help with note -> 201
        resp_res2 = self.client.post(
            f"/api/v1/cold-start/tasks/{task2['task_id']}/results",
            headers=self.dev_headers,
            json={
                "outcome": "needs_help",
                "time_seconds": 90,
                "hints_used": 1,
                "missing_information": "Could not identify which staging database cluster to point to.",
            },
        )
        self.assertEqual(resp_res2.status_code, 201)

        # 4. Check manager cold-start summary
        resp_sum = self.client.get(
            f"/api/v1/handovers/{self.handover_id}/cold-start/summary",
            headers=self.mgr_headers,
        )
        self.assertEqual(resp_sum.status_code, 200)
        summary = resp_sum.json()
        self.assertEqual(summary["pass_count"], 1)
        self.assertEqual(summary["needs_help_count"], 1)
        self.assertEqual(summary["total_time_seconds"], 135)
        self.assertEqual(len(summary["missing_information"]), 1)


if __name__ == "__main__":
    unittest.main()
