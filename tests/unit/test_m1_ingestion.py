import io
import os
import sys
import unittest
import uuid
from reportlab.pdfgen import canvas
from starlette.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from app.core.auth import create_access_token
from app.db.session import db, get_utc_now
from app.main import app
from app.schemas.enums import ErrorCode


class TestM1Ingestion(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.client = TestClient(app)
        self.manager_id = f"user-mgr-{uuid.uuid4()}"
        self.project_id = f"proj-m1-{uuid.uuid4()}"
        now = get_utc_now()
        with db.transaction() as cur:
            cur.execute("INSERT OR IGNORE INTO users (user_id, display_name, email, created_at) VALUES (?, 'Mgr', ?, ?)", (self.manager_id, f"{self.manager_id}@test.com", now))
            cur.execute("INSERT OR IGNORE INTO projects (project_id, name, created_at, updated_at) VALUES (?, 'M1 Proj', ?, ?)", (self.project_id, now, now))
            cur.execute("INSERT OR IGNORE INTO project_memberships (project_id, user_id, role, membership_status, created_at) VALUES (?, ?, 'manager', 'active', ?)", (self.project_id, self.manager_id, now))
        token, _ = create_access_token(self.manager_id)
        self.headers = {"Authorization": f"Bearer {token}"}

    def _make_pdf(self, text: str) -> bytes:
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 700, text)
        c.showPage()
        c.save()
        return buf.getvalue()

    def test_valid_txt_upload(self):
        resp = self.client.post(
            f"/api/v1/projects/{self.project_id}/sources/upload",
            headers=self.headers,
            files={"file": ("notes.txt", b"Hello Project Continuity", "text/plain")},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["filename"], "notes.txt")
        self.assertEqual(data["source_type"], "txt")

    def test_valid_pdf_upload(self):
        pdf_bytes = self._make_pdf("Authentication login status is pending.")
        resp = self.client.post(
            f"/api/v1/projects/{self.project_id}/sources/upload",
            headers=self.headers,
            files={"file": ("project.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["filename"], "project.pdf")
        self.assertEqual(data["source_type"], "pdf")

    def test_empty_file_rejected(self):
        resp = self.client.post(
            f"/api/v1/projects/{self.project_id}/sources/upload",
            headers=self.headers,
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["error"]["code"], ErrorCode.EMPTY_FILE.value)

    def test_unsupported_file_type(self):
        resp = self.client.post(
            f"/api/v1/projects/{self.project_id}/sources/upload",
            headers=self.headers,
            files={"file": ("data.docx", b"docx binary content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        self.assertEqual(resp.status_code, 415)
        self.assertEqual(resp.json()["error"]["code"], ErrorCode.UNSUPPORTED_FILE_TYPE.value)

    def test_extension_content_mismatch_pdf(self):
        resp = self.client.post(
            f"/api/v1/projects/{self.project_id}/sources/upload",
            headers=self.headers,
            files={"file": ("fake.pdf", b"This is plain text pretending to be PDF", "application/pdf")},
        )
        self.assertEqual(resp.status_code, 415)
        self.assertEqual(resp.json()["error"]["code"], ErrorCode.UNSUPPORTED_FILE_TYPE.value)

    def test_corrupt_pdf(self):
        corrupt = b"%PDF-1.4\nCorrupt header and broken xref data"
        resp = self.client.post(
            f"/api/v1/projects/{self.project_id}/sources/upload",
            headers=self.headers,
            files={"file": ("corrupt.pdf", corrupt, "application/pdf")},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["error"]["code"], ErrorCode.CORRUPT_FILE.value)

    def test_duplicate_source_409(self):
        content = b"Unique content for duplicate test 12345"
        resp1 = self.client.post(
            f"/api/v1/projects/{self.project_id}/sources/upload",
            headers=self.headers,
            files={"file": ("doc1.txt", content, "text/plain")},
        )
        self.assertEqual(resp1.status_code, 201)
        source_id_1 = resp1.json()["source_id"]

        resp2 = self.client.post(
            f"/api/v1/projects/{self.project_id}/sources/upload",
            headers=self.headers,
            files={"file": ("doc2.txt", content, "text/plain")},
        )
        self.assertEqual(resp2.status_code, 409)
        err = resp2.json()["error"]
        self.assertEqual(err["code"], ErrorCode.DUPLICATE_SOURCE.value)
        self.assertEqual(err["details"]["existing_source_id"], source_id_1)

    def test_path_traversal_filename_sanitized(self):
        resp = self.client.post(
            f"/api/v1/projects/{self.project_id}/sources/upload",
            headers=self.headers,
            files={"file": ("../../etc/passwd.txt", b"Safe text file content", "text/plain")},
        )
        self.assertEqual(resp.status_code, 201)
        self.assertNotIn("..", resp.json()["filename"])
        self.assertNotIn("/", resp.json()["filename"])

    def test_github_invalid_url(self):
        resp = self.client.post(
            f"/api/v1/projects/{self.project_id}/sources/github",
            headers=self.headers,
            json={"repo_url": "https://evil.com/repo"},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["error"]["code"], ErrorCode.GITHUB_URL_INVALID.value)

    def test_github_fixture_mode_import(self):
        resp = self.client.post(
            f"/api/v1/projects/{self.project_id}/sources/github",
            headers=self.headers,
            json={"repo_url": "https://github.com/continuity-ai/roomiez"},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertTrue(len(data["sources"]) > 0)
        self.assertEqual(data["sources"][0]["source_type"], "github")


if __name__ == "__main__":
    unittest.main()
