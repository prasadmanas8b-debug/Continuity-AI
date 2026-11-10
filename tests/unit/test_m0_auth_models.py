import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pydantic import ValidationError
from starlette.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from app.core.auth import create_access_token, decode_access_token
from app.core.errors import ContinuityException
from app.db.session import db, get_utc_now
from app.main import app
from app.schemas.enums import ErrorCode, FactType, RecipientRole, UserRole
from app.schemas.models import Project, ProjectCreateRequest, User


class TestM0AuthAndModels(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.client = TestClient(app)

    def test_valid_model(self):
        u = User(user_id="usr-123", display_name="Alice", email="alice@example.com")
        self.assertEqual(u.user_id, "usr-123")
        self.assertEqual(u.display_name, "Alice")

    def test_missing_required_field(self):
        with self.assertRaises(ValidationError):
            User(user_id="usr-123")  # missing display_name

    def test_invalid_enum(self):
        with self.assertRaises(ValidationError):
            ProjectCreateRequest(name="Test", role="superadmin")  # invalid

    def test_unknown_field_forbidden(self):
        with self.assertRaises(ValidationError):
            User(user_id="usr-123", display_name="Alice", extra_field_injected="forbidden")

    def test_timestamp_roundtrip_utc(self):
        now_str = get_utc_now()
        dt = datetime.fromisoformat(now_str.replace("Z", "+00:00"))
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_jwt_create_and_decode(self):
        token, exp = create_access_token("user-test-001", expires_hours=2)
        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], "user-test-001")
        self.assertTrue("exp" in payload)

    def test_jwt_expired(self):
        token, _ = create_access_token("user-test-001", expires_hours=-1)
        with self.assertRaises(ContinuityException) as ctx:
            decode_access_token(token)
        self.assertEqual(ctx.exception.code, ErrorCode.UNAUTHENTICATED)

    def test_auth_required_on_protected_routes(self):
        resp = self.client.get("/api/v1/projects")
        self.assertEqual(resp.status_code, 401)
        data = resp.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], ErrorCode.UNAUTHENTICATED.value)

    def test_health_and_meta_unauthenticated(self):
        resp_h = self.client.get("/health")
        self.assertEqual(resp_h.status_code, 200)
        self.assertEqual(resp_h.json(), {"status": "ok"})

        resp_m = self.client.get("/api/v1/meta")
        self.assertEqual(resp_m.status_code, 200)
        self.assertEqual(resp_m.json()["contract_version"], "1.0.0")

    def test_revoked_member_gets_404(self):
        now = get_utc_now()
        with db.transaction() as cur:
            cur.execute("INSERT OR IGNORE INTO users (user_id, display_name, email, created_at) VALUES ('rev-user', 'Revoked User', 'rev@test.com', ?)", (now,))
            cur.execute("INSERT OR IGNORE INTO projects (project_id, name, created_at, updated_at) VALUES ('p-rev-test', 'Revoked Project', ?, ?)", (now, now))
            cur.execute("INSERT OR IGNORE INTO project_memberships (project_id, user_id, role, membership_status, created_at) VALUES ('p-rev-test', 'rev-user', 'contributor', 'revoked', ?)", (now,))

        token, _ = create_access_token("rev-user")
        resp = self.client.get("/api/v1/projects/p-rev-test", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error"]["code"], ErrorCode.NOT_FOUND.value)


if __name__ == "__main__":
    unittest.main()
