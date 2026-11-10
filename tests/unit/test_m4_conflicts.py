import json
import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from app.conflicts.service import detect_conflicts_for_project, detect_information_gaps
from app.db.session import db, get_utc_now
from app.schemas.enums import ConflictRecordStatus, ConflictType, FactType, ReviewStatus, VerificationStatus


class TestM4Conflicts(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.project_id = f"proj-m4-{uuid.uuid4()}"
        self.manager_id = f"user-mgr-{uuid.uuid4()}"
        self.run_id = f"run-m4-{uuid.uuid4()}"
        now = get_utc_now()
        with db.transaction() as cur:
            cur.execute("INSERT OR IGNORE INTO users (user_id, display_name, email, created_at) VALUES (?, 'Mgr', ?, ?)", (self.manager_id, f"{self.manager_id}@test.com", now))
            cur.execute("INSERT OR IGNORE INTO projects (project_id, name, created_at, updated_at) VALUES (?, 'M4 Proj', ?, ?)", (self.project_id, now, now))
            cur.execute("INSERT OR IGNORE INTO project_memberships (project_id, user_id, role, membership_status, created_at) VALUES (?, ?, 'manager', 'active', ?)", (self.project_id, self.manager_id, now))
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

    def _insert_claim(self, item_id: str, fact_type: FactType, statement: str, owner: str = None, verif="verified", quote="quote", date="2026-11-02") -> str:
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
                ) VALUES (?, ?, 'txt', 's.txt', 's.txt', 'k', ?, 100, 'normal', '[]', 'processed', NULL, ?, '{}', ?)
                """,
                (sid, self.project_id, f"h-{sid}", date, now),
            )
            cur.execute("INSERT INTO source_texts (source_id, text, page_offsets) VALUES (?, ?, '[0]')", (sid, statement))
            cur.execute(
                """
                INSERT INTO claims (
                    claim_id, project_id, extraction_run_id, item_id, fact_type,
                    original_statement, statement, owner, verification_status,
                    conflict_status, review_status, sensitivity, audience_roles,
                    version, archived, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'none', 'pending', 'normal', '[]', 1, 0, ?, ?)
                """,
                (cid, self.project_id, self.run_id, item_id, fact_type.value, statement, statement, owner, verif, now, now),
            )
            cur.execute(
                """
                INSERT INTO evidence (
                    evidence_id, claim_id, source_id, exact_quote, locator,
                    quote_match_status, support_status, support_note, created_at
                ) VALUES (?, ?, ?, ?, '{\"page\": 1}', 'found', 'supports', NULL, ?)
                """,
                (str(uuid.uuid4()), cid, sid, quote, now),
            )
        return cid

    def test_contradiction_detected_both_preserved_no_winner(self):
        c1 = self._insert_claim("login_module", FactType.STATUS, "Login authentication is incomplete.", date="2026-11-02")
        c2 = self._insert_claim("login_module", FactType.STATUS, "Login authentication has been completed.", date="2026-11-06")

        detect_conflicts_for_project(self.project_id)

        confs = db.query_all("SELECT * FROM conflicts WHERE project_id = ?", (self.project_id,))
        self.assertEqual(len(confs), 1)
        conf = confs[0]
        self.assertEqual(conf["conflict_type"], ConflictType.CONTRADICTION.value)
        self.assertTrue(bool(conf["is_critical"]))

        # Check that both claims are preserved and marked with conflict status
        claim1 = db.query_one("SELECT * FROM claims WHERE claim_id = ?", (c1,))
        claim2 = db.query_one("SELECT * FROM claims WHERE claim_id = ?", (c2,))
        self.assertEqual(claim1["conflict_status"], "conflict")
        self.assertEqual(claim2["conflict_status"], "conflict")

    def test_gap_g1_missing_owner(self):
        c = self._insert_claim("api_test", FactType.NEXT_ACTION, "Run integration tests for API.", owner=None)
        detect_information_gaps(self.project_id)
        confs = db.query_all("SELECT * FROM conflicts WHERE project_id = ? AND conflict_type = 'missing_information'", (self.project_id,))
        self.assertEqual(len(confs), 1)
        self.assertFalse(bool(confs[0]["is_critical"]))
        self.assertIn("Missing owner", confs[0]["summary"])

    def test_gap_g2_blocker_without_dependency_or_next_action(self):
        c = self._insert_claim("db_migration", FactType.BLOCKER, "Database migration is blocked by cloud provider downtime.", owner="Dev")
        detect_information_gaps(self.project_id)
        confs = db.query_all("SELECT * FROM conflicts WHERE project_id = ? AND conflict_type = 'missing_information'", (self.project_id,))
        self.assertTrue(any("Blocker on item db_migration" in c["summary"] for c in confs))


if __name__ == "__main__":
    unittest.main()
