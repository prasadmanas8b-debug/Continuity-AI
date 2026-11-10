import os
import sys
import unittest
import uuid
from pathlib import Path
from starlette.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from app.db.session import db, get_utc_now
from app.main import app
from app.schemas.enums import ErrorCode, RecipientRole, ReviewDecision, Sensitivity, UserRole
from app.seed import seed_database

SEED_SOURCES_DIR = Path(__file__).resolve().parent.parent.parent / "seed" / "sources"


class TestJudgeJourney(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reset DB tables cleanly for fresh journey
        with db.transaction() as cur:
            cur.execute("DELETE FROM idempotency_keys")
            cur.execute("DELETE FROM audit_log")
            cur.execute("DELETE FROM cold_start_results")
            cur.execute("DELETE FROM cold_start_tasks")
            cur.execute("DELETE FROM handover_claims")
            cur.execute("DELETE FROM handovers")
            cur.execute("DELETE FROM reviews")
            cur.execute("DELETE FROM conflict_claims")
            cur.execute("DELETE FROM conflicts")
            cur.execute("DELETE FROM evidence")
            cur.execute("DELETE FROM claims")
            cur.execute("DELETE FROM extraction_runs")
            cur.execute("DELETE FROM source_texts")
            cur.execute("DELETE FROM sources")
            cur.execute("DELETE FROM project_memberships")
            cur.execute("DELETE FROM projects")
            cur.execute("DELETE FROM users")

        seed_database()
        cls.client = TestClient(app)

    def test_complete_judge_journey_end_to_end(self):
        # Step 1: Log in as manager
        login_resp = self.client.post("/api/v1/auth/demo-login", json={"user_id": "user-manager-001"})
        self.assertEqual(login_resp.status_code, 200)
        mgr_data = login_resp.json()
        mgr_token = mgr_data["access_token"]
        mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

        # Check seeded project
        projects_resp = self.client.get("/api/v1/projects", headers=mgr_headers)
        self.assertEqual(projects_resp.status_code, 200)
        projects = projects_resp.json()["items"]
        self.assertTrue(len(projects) > 0)
        project_id = projects[0]["project_id"]

        # Step 2: Sources are already uploaded by seed
        sources_resp = self.client.get(f"/api/v1/projects/{project_id}/sources", headers=mgr_headers)
        self.assertEqual(sources_resp.status_code, 200)
        sources = sources_resp.json()["items"]
        self.assertTrue(len(sources) >= 4)

        # Step 3: Start extraction -> claims appear with evidence and verification labels
        extract_resp = self.client.post(f"/api/v1/projects/{project_id}/extractions", headers=mgr_headers, json={})
        self.assertEqual(extract_resp.status_code, 202)
        run_id = extract_resp.json()["run_id"]

        poll_resp = self.client.get(f"/api/v1/extractions/{run_id}", headers=mgr_headers)
        self.assertEqual(poll_resp.status_code, 200)
        self.assertEqual(poll_resp.json()["status"], "succeeded")
        claims_created = poll_resp.json()["claims_created"]
        self.assertTrue(claims_created > 0)

        # Claims workspace check
        claims_resp = self.client.get(f"/api/v1/projects/{project_id}/claims", headers=mgr_headers)
        self.assertEqual(claims_resp.status_code, 200)
        claims = claims_resp.json()["items"]
        self.assertTrue(len(claims) >= 5)

        # Step 4: Open conflict (login status: incomplete vs completed)
        conflicts_resp = self.client.get(f"/api/v1/projects/{project_id}/conflicts", headers=mgr_headers)
        self.assertEqual(conflicts_resp.status_code, 200)
        conflicts = conflicts_resp.json()["items"]
        login_conf = next((c for c in conflicts if c["item_id"] == "login_authentication"), None)
        self.assertIsNotNone(login_conf)
        self.assertTrue(login_conf["is_critical"])
        self.assertEqual(len(login_conf["claims"]), 2)

        # Step 5: Review claims: accept JWT decision, leave conflict unresolved
        jwt_claim = next((c for c in claims if c["item_id"] == "jwt_sessions"), None)
        self.assertIsNotNone(jwt_claim)
        rev_jwt = self.client.post(
            f"/api/v1/claims/{jwt_claim['claim_id']}/reviews",
            headers=mgr_headers,
            json={"decision": "accept", "expected_version": jwt_claim["version"]},
        )
        self.assertEqual(rev_jwt.status_code, 201)

        # Accept other backend claims to ensure eligibility
        for c in claims:
            if c["item_id"] in ("login_tests", "login_testing_ownership", "staging_database") and c["review_status"] == "pending":
                self.client.post(
                    f"/api/v1/claims/{c['claim_id']}/reviews",
                    headers=mgr_headers,
                    json={"decision": "accept", "expected_version": c["version"]},
                )

        # Review conflict claim 1 as unresolved
        conf_claim_1 = login_conf["claims"][0]
        self.client.post(
            f"/api/v1/claims/{conf_claim_1['claim_id']}/reviews",
            headers=mgr_headers,
            json={"decision": "unresolved", "reason": "Leaving open until team retests auth", "expected_version": conf_claim_1["version"]},
        )

        # Step 6: Create handover for backend_developer -> approve (override reason required while critical conflict is open)
        create_ho_resp = self.client.post(
            f"/api/v1/projects/{project_id}/handovers",
            headers=mgr_headers,
            json={"recipient_role": "backend_developer"},
        )
        self.assertEqual(create_ho_resp.status_code, 201)
        backend_ho_id = create_ho_resp.json()["handover_id"]

        # Attempt approve without override -> blocked (409)
        block_resp = self.client.post(
            f"/api/v1/handovers/{backend_ho_id}/approve",
            headers=mgr_headers,
            json={"override_reason": None},
        )
        self.assertEqual(block_resp.status_code, 409)
        self.assertEqual(block_resp.json()["error"]["code"], ErrorCode.APPROVAL_BLOCKED_CONFLICT.value)

        # Approve with override reason -> success
        app_resp = self.client.post(
            f"/api/v1/handovers/{backend_ho_id}/approve",
            headers=mgr_headers,
            json={"override_reason": "Proceeding with known open discrepancy regarding login completion."},
        )
        self.assertEqual(app_resp.status_code, 200)
        self.assertEqual(app_resp.json()["status"], "approved")

        # Step 7: Log in as incoming backend developer -> see only authorised, approved items with evidence and uncertainty
        login_dev = self.client.post("/api/v1/auth/demo-login", json={"user_id": "user-incoming-backend-001"})
        dev_token = login_dev.json()["access_token"]
        dev_headers = {"Authorization": f"Bearer {dev_token}"}

        dev_ho_resp = self.client.get(f"/api/v1/handovers/{backend_ho_id}", headers=dev_headers)
        self.assertEqual(dev_ho_resp.status_code, 200)
        dev_ho = dev_ho_resp.json()
        self.assertEqual(dev_ho["recipient_role"], "backend_developer")
        self.assertIsNotNone(dev_ho["approval_override"])
        self.assertTrue(len(dev_ho["sections"]) > 0)

        # Step 8: Run three-task cold-start test -> results saved
        tasks_resp = self.client.get(f"/api/v1/handovers/{backend_ho_id}/cold-start/tasks", headers=dev_headers)
        self.assertEqual(tasks_resp.status_code, 200)
        tasks = tasks_resp.json()
        self.assertTrue(len(tasks) >= 2)

        # Submit task 1 as pass
        res1 = self.client.post(
            f"/api/v1/cold-start/tasks/{tasks[0]['task_id']}/results",
            headers=dev_headers,
            json={"outcome": "pass", "time_seconds": 35, "hints_used": 0, "missing_information": None},
        )
        self.assertEqual(res1.status_code, 201)

        # Step 9: Log in as incoming designer -> see a different, filtered view; restricted backend credential absent
        create_des_ho = self.client.post(
            f"/api/v1/projects/{project_id}/handovers",
            headers=mgr_headers,
            json={"recipient_role": "designer"},
        )
        des_ho_id = create_des_ho.json()["handover_id"]
        des_claims = [c for c in claims if "designer" in c["audience_roles"]]
        for dc in des_claims:
            self.client.post(
                f"/api/v1/claims/{dc['claim_id']}/reviews",
                headers=mgr_headers,
                json={"decision": "accept", "expected_version": dc["version"]},
            )
        self.client.post(f"/api/v1/handovers/{des_ho_id}/approve", headers=mgr_headers, json={"override_reason": None})

        # Login as designer
        login_des = self.client.post("/api/v1/auth/demo-login", json={"user_id": "user-incoming-designer-001"})
        des_token = login_des.json()["access_token"]
        des_headers = {"Authorization": f"Bearer {des_token}"}

        des_ho_resp = self.client.get(f"/api/v1/handovers/{des_ho_id}", headers=des_headers)
        self.assertEqual(des_ho_resp.status_code, 200)
        des_ho = des_ho_resp.json()
        self.assertEqual(des_ho["recipient_role"], "designer")

        # Designer view raw text check: no backend passwords or backend-only items present
        raw_des_text = des_ho_resp.text
        self.assertNotIn("staging_db_password", raw_des_text)
        self.assertNotIn("login_authentication", raw_des_text)

        # Designer attempting to access backend handover -> 404
        forbidden_cross_read = self.client.get(f"/api/v1/handovers/{backend_ho_id}", headers=des_headers)
        self.assertEqual(forbidden_cross_read.status_code, 404)


if __name__ == "__main__":
    unittest.main()
