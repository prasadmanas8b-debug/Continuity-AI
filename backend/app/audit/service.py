import uuid
from typing import Optional
import sqlite3

from app.db.session import db, get_utc_now


def record_audit(
    cur: Optional[sqlite3.Cursor],
    actor_id: Optional[str],
    project_id: Optional[str],
    action: str,
    entity_type: str,
    entity_id: Optional[str],
    summary: str,
):
    audit_id = str(uuid.uuid4())
    now = get_utc_now()
    # Summaries must never contain source text or secrets
    if cur:
        cur.execute(
            """
            INSERT INTO audit_log (audit_id, project_id, actor_id, action, entity_type, entity_id, summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (audit_id, project_id, actor_id, action, entity_type, entity_id, summary, now),
        )
    else:
        with db.transaction() as cur_tx:
            cur_tx.execute(
                """
                INSERT INTO audit_log (audit_id, project_id, actor_id, action, entity_type, entity_id, summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (audit_id, project_id, actor_id, action, entity_type, entity_id, summary, now),
            )
    return audit_id
