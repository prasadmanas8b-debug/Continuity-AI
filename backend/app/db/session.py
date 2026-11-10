import os
import sqlite3
import json
import threading
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional
from datetime import datetime, timezone

from app.core.config import settings

# Thread-local storage for database connections
_local = threading.local()
_db_lock = threading.RLock()


def get_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_db_path() -> str:
    from pathlib import Path
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///"):]
    elif url.startswith("sqlite://"):
        path = url[len("sqlite://"):]
    else:
        path = "continuity.db"
    if path in ("./continuity.db", "continuity.db"):
        return str(repo_root / "continuity.db")
    return path


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path()

    def get_connection(self) -> sqlite3.Connection:
        if not hasattr(_local, "conn") or _local.conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
            conn.row_factory = dict_factory
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            _local.conn = conn
            _local.tx_depth = 0
        return _local.conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        with _db_lock:
            conn = self.get_connection()
            depth = getattr(_local, "tx_depth", 0)
            if depth == 0:
                conn.execute("BEGIN IMMEDIATE")
            _local.tx_depth = depth + 1
            cursor = conn.cursor()
            try:
                yield cursor
                _local.tx_depth -= 1
                if _local.tx_depth == 0:
                    conn.commit()
            except Exception:
                _local.tx_depth -= 1
                if _local.tx_depth == 0:
                    conn.rollback()
                raise

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        with _db_lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor

    def query_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def query_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()

    def init_db(self):
        """Create all tables with strict schema from Section 8.1"""
        with self.transaction() as cur:
            cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                email TEXT UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS project_memberships (
                project_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('manager', 'contributor', 'incoming_member')),
                recipient_role TEXT CHECK (recipient_role IN ('backend_developer', 'designer') OR recipient_role IS NULL),
                membership_status TEXT NOT NULL DEFAULT 'active' CHECK (membership_status IN ('active', 'revoked')),
                created_at TEXT NOT NULL,
                revoked_at TEXT,
                PRIMARY KEY (project_id, user_id),
                FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                source_type TEXT NOT NULL CHECK (source_type IN ('github', 'pdf', 'docx', 'txt', 'md', 'task_export')),
                filename TEXT NOT NULL,
                source_reference TEXT NOT NULL,
                storage_key TEXT,
                content_hash TEXT NOT NULL,
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                sensitivity TEXT NOT NULL DEFAULT 'normal' CHECK (sensitivity IN ('normal', 'restricted')),
                audience_roles TEXT NOT NULL DEFAULT '[]',
                ingestion_status TEXT NOT NULL CHECK (ingestion_status IN ('pending', 'processed', 'failed', 'archived')),
                error_message TEXT,
                document_date TEXT,
                source_metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_proj_hash_active 
                ON sources(project_id, content_hash) 
                WHERE ingestion_status <> 'archived';

            CREATE TABLE IF NOT EXISTS source_texts (
                source_id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                page_offsets TEXT NOT NULL DEFAULT '[0]',
                FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS extraction_runs (
                run_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
                source_ids TEXT NOT NULL DEFAULT '[]',
                claims_created INTEGER NOT NULL DEFAULT 0,
                claims_rejected_by_validation INTEGER NOT NULL DEFAULT 0,
                llm_provider TEXT,
                llm_model TEXT,
                prompt_version TEXT,
                error_code TEXT,
                error_message TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                started_by TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,
                FOREIGN KEY (started_by) REFERENCES users(user_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS claims (
                claim_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                extraction_run_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                fact_type TEXT NOT NULL CHECK (fact_type IN ('decision', 'owner', 'status', 'blocker', 'dependency', 'risk', 'next_action', 'question')),
                original_statement TEXT NOT NULL,
                statement TEXT NOT NULL,
                owner TEXT,
                verification_status TEXT NOT NULL DEFAULT 'uncertain' CHECK (verification_status IN ('verified', 'rejected', 'uncertain')),
                conflict_status TEXT NOT NULL DEFAULT 'none' CHECK (conflict_status IN ('none', 'conflict', 'superseded')),
                review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'accepted', 'edited', 'rejected', 'unresolved')),
                sensitivity TEXT NOT NULL DEFAULT 'normal' CHECK (sensitivity IN ('normal', 'restricted')),
                audience_roles TEXT NOT NULL DEFAULT '[]',
                version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
                archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,
                FOREIGN KEY (extraction_run_id) REFERENCES extraction_runs(run_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                exact_quote TEXT NOT NULL,
                locator TEXT NOT NULL,
                quote_match_status TEXT NOT NULL DEFAULT 'unchecked' CHECK (quote_match_status IN ('found', 'not_found', 'unchecked')),
                support_status TEXT NOT NULL DEFAULT 'unchecked' CHECK (support_status IN ('supports', 'partial', 'does_not_support', 'unchecked')),
                support_note TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE RESTRICT,
                FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS conflicts (
                conflict_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                fact_type TEXT NOT NULL,
                conflict_type TEXT NOT NULL CHECK (conflict_type IN ('contradiction', 'possible_supersession', 'missing_information')),
                status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'unresolved')),
                is_critical INTEGER NOT NULL DEFAULT 0,
                summary TEXT NOT NULL,
                resolution_note TEXT,
                detection_key TEXT NOT NULL,
                resolved_by TEXT,
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,
                FOREIGN KEY (resolved_by) REFERENCES users(user_id) ON DELETE RESTRICT,
                UNIQUE (project_id, detection_key)
            );

            CREATE TABLE IF NOT EXISTS conflict_claims (
                conflict_id TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                PRIMARY KEY (conflict_id, claim_id),
                FOREIGN KEY (conflict_id) REFERENCES conflicts(conflict_id) ON DELETE RESTRICT,
                FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS reviews (
                review_id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                reviewer_id TEXT NOT NULL,
                decision TEXT NOT NULL CHECK (decision IN ('accept', 'edit', 'reject', 'unresolved')),
                original_statement TEXT NOT NULL,
                reviewed_statement TEXT,
                reason TEXT,
                claim_version_after INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE RESTRICT,
                FOREIGN KEY (reviewer_id) REFERENCES users(user_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS handovers (
                handover_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                version INTEGER NOT NULL CHECK (version >= 1),
                status TEXT NOT NULL CHECK (status IN ('draft', 'approved', 'shared', 'revoked')),
                recipient_role TEXT NOT NULL CHECK (recipient_role IN ('backend_developer', 'designer')),
                approved_by TEXT,
                approved_at TEXT,
                approval_override TEXT,
                excluded_claim_count INTEGER NOT NULL DEFAULT 0 CHECK (excluded_claim_count >= 0),
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,
                FOREIGN KEY (approved_by) REFERENCES users(user_id) ON DELETE RESTRICT,
                FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE RESTRICT,
                UNIQUE (project_id, recipient_role, version)
            );

            CREATE TABLE IF NOT EXISTS handover_claims (
                handover_id TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                section_key TEXT NOT NULL,
                item_id TEXT NOT NULL,
                fact_type TEXT NOT NULL,
                statement_snapshot TEXT NOT NULL,
                owner_snapshot TEXT,
                verification_status_snapshot TEXT NOT NULL,
                review_status_snapshot TEXT NOT NULL,
                uncertainty_label TEXT NOT NULL CHECK (uncertainty_label IN ('none', 'uncertain', 'unresolved', 'conflicted')),
                evidence_snapshot TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (handover_id, claim_id),
                FOREIGN KEY (handover_id) REFERENCES handovers(handover_id) ON DELETE RESTRICT,
                FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS cold_start_tasks (
                task_id TEXT PRIMARY KEY,
                handover_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL CHECK (ordinal >= 1 AND ordinal <= 3),
                task_prompt TEXT NOT NULL,
                expected_reference TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (handover_id) REFERENCES handovers(handover_id) ON DELETE RESTRICT,
                UNIQUE (handover_id, ordinal)
            );

            CREATE TABLE IF NOT EXISTS cold_start_results (
                result_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                tester_id TEXT NOT NULL,
                outcome TEXT NOT NULL CHECK (outcome IN ('pass', 'needs_help')),
                time_seconds INTEGER NOT NULL CHECK (time_seconds >= 0 AND time_seconds <= 86400),
                hints_used INTEGER NOT NULL CHECK (hints_used >= 0),
                missing_information TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES cold_start_tasks(task_id) ON DELETE RESTRICT,
                FOREIGN KEY (tester_id) REFERENCES users(user_id) ON DELETE RESTRICT,
                UNIQUE (task_id, tester_id)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                audit_id TEXT PRIMARY KEY,
                project_id TEXT,
                actor_id TEXT,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,
                FOREIGN KEY (actor_id) REFERENCES users(user_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS idempotency_keys (
                key TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                route TEXT NOT NULL,
                request_hash TEXT,
                response_status INTEGER NOT NULL,
                response_body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (key, actor_id, route)
            );

            -- Indexes per Section 8.2
            CREATE INDEX IF NOT EXISTS idx_sources_proj_date ON sources(project_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_claims_proj_item ON claims(project_id, item_id, fact_type);
            CREATE INDEX IF NOT EXISTS idx_claims_proj_review ON claims(project_id, review_status);
            CREATE INDEX IF NOT EXISTS idx_claims_proj_verify ON claims(project_id, verification_status);
            CREATE INDEX IF NOT EXISTS idx_evidence_claim ON evidence(claim_id);
            CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence(source_id);
            CREATE INDEX IF NOT EXISTS idx_reviews_claim_date ON reviews(claim_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_conflicts_proj_status ON conflicts(project_id, status);
            CREATE INDEX IF NOT EXISTS idx_handovers_proj_role_ver ON handovers(project_id, recipient_role, version);
            CREATE INDEX IF NOT EXISTS idx_handover_claims_section ON handover_claims(handover_id, section_key, sort_order);
            CREATE INDEX IF NOT EXISTS idx_audit_proj_date ON audit_log(project_id, created_at);
            """)


db = Database()
