#!/usr/bin/env python3
import json
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

SEED_SOURCES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "sources"))
os.makedirs(SEED_SOURCES_DIR, exist_ok=True)

def generate_pdf():
    pdf_path = os.path.join(SEED_SOURCES_DIR, "project_notes.pdf")
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(72, 720, "Project Roomiez Notes - November 2, 2026")
    c.drawString(72, 690, "Login authentication is incomplete.")
    c.drawString(72, 660, "Password reset is blocked until the email service is configured.")
    c.showPage()
    c.save()
    print("Generated project_notes.pdf")

def generate_text_sources():
    # 1. meeting_notes.txt (dated 6 November)
    meeting_path = os.path.join(SEED_SOURCES_DIR, "meeting_notes.txt")
    with open(meeting_path, "w", encoding="utf-8") as f:
        f.write(
            "Project Roomiez Meeting Notes - November 6, 2026\n"
            "Login authentication has been completed.\n"
            "Decision: use JWT sessions instead of server sessions.\n"
            "Question: who will configure the email service?\n"
        )
    print("Generated meeting_notes.txt")

    # 2. task_notes.md (dated 7 November)
    task_path = os.path.join(SEED_SOURCES_DIR, "task_notes.md")
    with open(task_path, "w", encoding="utf-8") as f:
        f.write(
            "# Project Roomiez Tasks - November 7, 2026\n"
            "Next action: write end-to-end tests for login authentication.\n"
            "Dependency: tests need the staging environment.\n"
            "Ravi owns login testing; instructions are in docs/testing.md.\n"
            "Risk: staging database is shared and may be reset.\n"
        )
    print("Generated task_notes.md")

    # 3. design_notes.md (dated 7 November)
    design_path = os.path.join(SEED_SOURCES_DIR, "design_notes.md")
    with open(design_path, "w", encoding="utf-8") as f:
        f.write(
            "# Design Notes - November 7, 2026\n"
            "Decision: signup screen uses the blue primary button.\n"
            "Status: signup mockups are approved.\n"
        )
    print("Generated design_notes.md")

    # 4. credentials_note.txt (dated 7 November)
    cred_path = os.path.join(SEED_SOURCES_DIR, "credentials_note.txt")
    with open(cred_path, "w", encoding="utf-8") as f:
        f.write(
            "Internal Staging Database Credentials - November 7, 2026\n"
            "Database connection password is staging_db_password_secret_token_prod_temp_2026.\n"
        )
    print("Generated credentials_note.txt")

def generate_expected_claims():
    expected_path = os.path.join(os.path.dirname(__file__), "expected_claims.json")
    data = {
        "scenario": "Roomiez",
        "expected_claims": [
            {
                "item_id": "login_authentication",
                "fact_type": "status",
                "statement": "Login authentication is incomplete.",
                "source": "project_notes.pdf",
                "quote": "Login authentication is incomplete.",
                "audience": ["backend_developer"]
            },
            {
                "item_id": "login_authentication",
                "fact_type": "status",
                "statement": "Login authentication has been completed.",
                "source": "meeting_notes.txt",
                "quote": "Login authentication has been completed.",
                "audience": ["backend_developer"]
            },
            {
                "item_id": "jwt_sessions",
                "fact_type": "decision",
                "statement": "Use JWT sessions instead of server sessions.",
                "source": "meeting_notes.txt",
                "quote": "Decision: use JWT sessions instead of server sessions.",
                "audience": ["backend_developer"]
            },
            {
                "item_id": "email_service_configuration",
                "fact_type": "question",
                "statement": "Who will configure the email service?",
                "source": "meeting_notes.txt",
                "quote": "Question: who will configure the email service?",
                "audience": ["backend_developer"]
            },
            {
                "item_id": "login_tests",
                "fact_type": "next_action",
                "statement": "Write end-to-end tests for login authentication.",
                "source": "task_notes.md",
                "quote": "Next action: write end-to-end tests for login authentication.",
                "owner": "Ravi",
                "audience": ["backend_developer"]
            },
            {
                "item_id": "login_tests",
                "fact_type": "dependency",
                "statement": "Tests need the staging environment.",
                "source": "task_notes.md",
                "quote": "Dependency: tests need the staging environment.",
                "audience": ["backend_developer"]
            },
            {
                "item_id": "login_testing_ownership",
                "fact_type": "owner",
                "statement": "Ravi owns login testing and instructions are in docs/testing.md.",
                "source": "task_notes.md",
                "quote": "Ravi owns login testing; instructions are in docs/testing.md.",
                "owner": "Ravi",
                "audience": ["backend_developer"]
            },
            {
                "item_id": "staging_database",
                "fact_type": "risk",
                "statement": "Staging database is shared and may be reset.",
                "source": "task_notes.md",
                "quote": "Risk: staging database is shared and may be reset.",
                "audience": ["backend_developer"]
            },
            {
                "item_id": "signup_button_color",
                "fact_type": "decision",
                "statement": "Signup screen uses the blue primary button.",
                "source": "design_notes.md",
                "quote": "Decision: signup screen uses the blue primary button.",
                "audience": ["designer"]
            },
            {
                "item_id": "signup_mockups",
                "fact_type": "status",
                "statement": "Signup mockups are approved.",
                "source": "design_notes.md",
                "quote": "Status: signup mockups are approved.",
                "audience": ["designer"]
            },
            {
                "item_id": "staging_db_credentials",
                "fact_type": "decision",
                "statement": "Database connection password is staging_db_password_secret_token_prod_temp_2026.",
                "source": "credentials_note.txt",
                "quote": "Database connection password is staging_db_password_secret_token_prod_temp_2026.",
                "sensitivity": "restricted"
            }
        ],
        "expected_conflicts": [
            {
                "item_id": "login_authentication",
                "fact_type": "status",
                "conflict_type": "contradiction",
                "is_critical": True
            }
        ]
    }
    with open(expected_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Generated expected_claims.json")

if __name__ == "__main__":
    generate_pdf()
    generate_text_sources()
    generate_expected_claims()
