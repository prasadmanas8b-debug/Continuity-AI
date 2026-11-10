import os
import sys
from pathlib import Path

# Ensure backend root on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import db, get_utc_now
from app.ingestion.service import ingest_uploaded_file
from app.schemas.enums import RecipientRole, Sensitivity, UserRole

DEMO_USERS = [
    {
        "user_id": "user-manager-001",
        "display_name": "Manas Prasad (Manager)",
        "email": "manas@example.com",
        "role": UserRole.MANAGER.value,
        "recipient_role": None,
    },
    {
        "user_id": "user-contributor-001",
        "display_name": "Sarah Chen (Contributor)",
        "email": "sarah@example.com",
        "role": UserRole.CONTRIBUTOR.value,
        "recipient_role": None,
    },
    {
        "user_id": "user-incoming-backend-001",
        "display_name": "Alex Rivera (Incoming Backend Dev)",
        "email": "alex@example.com",
        "role": UserRole.INCOMING_MEMBER.value,
        "recipient_role": RecipientRole.BACKEND_DEVELOPER.value,
    },
    {
        "user_id": "user-incoming-designer-001",
        "display_name": "Jordan Lee (Incoming Designer)",
        "email": "jordan@example.com",
        "role": UserRole.INCOMING_MEMBER.value,
        "recipient_role": RecipientRole.DESIGNER.value,
    },
]

DEMO_PROJECT_ID = "proj-roomiez-001"
DEMO_PROJECT_NAME = "Project Roomiez"
DEMO_PROJECT_DESC = "Roommate finder and rental coordination application"


def reset_database():
    db.init_db()
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


def seed_database(reset: bool = False):
    db.init_db()
    if reset:
        reset_database()

    now = get_utc_now()

    print("Seeding demo users...")
    with db.transaction() as cur:
        for u in DEMO_USERS:
            cur.execute(
                """
                INSERT OR IGNORE INTO users (user_id, display_name, email, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (u["user_id"], u["display_name"], u["email"], now),
            )

        # Seed Project
        cur.execute(
            """
            INSERT OR IGNORE INTO projects (project_id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (DEMO_PROJECT_ID, DEMO_PROJECT_NAME, DEMO_PROJECT_DESC, now, now),
        )

        # Seed Memberships
        for u in DEMO_USERS:
            cur.execute(
                """
                INSERT OR IGNORE INTO project_memberships (
                    project_id, user_id, role, recipient_role, membership_status, created_at
                ) VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (DEMO_PROJECT_ID, u["user_id"], u["role"], u["recipient_role"], now),
            )

    print("Seeded users and project memberships.")

    # Seed sources from seed/sources
    seed_sources_dir = Path(__file__).resolve().parent.parent.parent / "seed" / "sources"
    if not seed_sources_dir.exists():
        print(f"Warning: Seed sources dir {seed_sources_dir} does not exist. Run seed generator first.")
        return

    source_configs = [
        {
            "filename": "project_notes.pdf",
            "document_date": "2026-11-02",
            "sensitivity": Sensitivity.NORMAL,
            "audience": ["backend_developer"],
        },
        {
            "filename": "meeting_notes.txt",
            "document_date": "2026-11-06",
            "sensitivity": Sensitivity.NORMAL,
            "audience": ["backend_developer"],
        },
        {
            "filename": "task_notes.md",
            "document_date": "2026-11-07",
            "sensitivity": Sensitivity.NORMAL,
            "audience": ["backend_developer"],
        },
        {
            "filename": "design_notes.md",
            "document_date": "2026-11-07",
            "sensitivity": Sensitivity.NORMAL,
            "audience": ["designer"],
        },
        {
            "filename": "credentials_note.txt",
            "document_date": "2026-11-07",
            "sensitivity": Sensitivity.NORMAL,
            "audience": [],
        },
    ]

    print("Ingesting seed sources...")
    manager_id = DEMO_USERS[0]["user_id"]
    for sc in source_configs:
        file_path = seed_sources_dir / sc["filename"]
        if not file_path.exists():
            continue
        with open(file_path, "rb") as f:
            raw_bytes = f.read()

        try:
            res = ingest_uploaded_file(
                project_id=DEMO_PROJECT_ID,
                actor_id=manager_id,
                raw_bytes=raw_bytes,
                original_filename=sc["filename"],
                document_date=sc["document_date"],
                sensitivity=sc["sensitivity"],
                audience_roles=sc["audience"],
            )
            print(f"  Ingested {sc['filename']} -> source_id {res['source_id']}")
        except Exception as e:
            print(f"  Note on {sc['filename']}: {e}")

    print("Seed complete! Database ready for demo and automated tests.")


if __name__ == "__main__":
    do_reset = "--reset" in sys.argv
    seed_database(reset=do_reset)
