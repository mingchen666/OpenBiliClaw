"""xhs task queue and creator subscription storage.

The task queue bridges the backend's Soul-driven scheduler to the
extension's background dispatcher. The backend enqueues search/creator
tasks; the extension polls for pending tasks, opens a tab, collects
URLs, and posts the result back.

Creator subscriptions track xhs creators the user wants to follow —
a nightly scheduler enqueues one creator task per subscription.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from openbiliclaw.storage.database import Database

logger = logging.getLogger(__name__)


class XhsTaskQueue:
    """Manages the xhs_tasks table."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._db.conn.executescript("""
            CREATE TABLE IF NOT EXISTS xhs_tasks (
                id           TEXT PRIMARY KEY,
                type         TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                status       TEXT NOT NULL DEFAULT 'pending',
                result_json  TEXT,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_xhs_tasks_status
                ON xhs_tasks (status, created_at);
        """)

    def enqueue(
        self,
        task_type: str,
        payload: dict[str, Any],
        *,
        daily_budget: int = 100,
    ) -> bool:
        """Enqueue a task if the daily budget for this type allows it.

        Returns True if enqueued, False if budget exhausted.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        count_today = self._db.conn.execute(
            "SELECT COUNT(*) FROM xhs_tasks WHERE type = ? AND created_at >= ?",
            (task_type, today),
        ).fetchone()[0]

        if count_today >= daily_budget:
            logger.info(
                "xhs task budget exhausted: type=%s, count=%d, budget=%d",
                task_type,
                count_today,
                daily_budget,
            )
            return False

        task_id = str(uuid.uuid4())
        self._db.conn.execute(
            "INSERT INTO xhs_tasks (id, type, payload_json) VALUES (?, ?, ?)",
            (task_id, task_type, json.dumps(payload, ensure_ascii=False)),
        )
        self._db.conn.commit()
        return True

    def next_pending(self) -> dict[str, Any] | None:
        """Return the oldest pending task, or None."""
        row = self._db.conn.execute(
            "SELECT * FROM xhs_tasks WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def complete(self, task_id: str, *, urls: list[str] | None = None) -> None:
        """Mark a task as completed with optional result URLs."""
        result = json.dumps({"urls": urls or []}, ensure_ascii=False)
        self._db.conn.execute(
            "UPDATE xhs_tasks SET status = 'completed', result_json = ?, "
            "completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (result, task_id),
        )
        self._db.conn.commit()

    def fail(self, task_id: str, *, error: str = "") -> None:
        """Mark a task as failed."""
        result = json.dumps({"error": error}, ensure_ascii=False)
        self._db.conn.execute(
            "UPDATE xhs_tasks SET status = 'failed', result_json = ?, "
            "completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (result, task_id),
        )
        self._db.conn.commit()


class XhsCreatorStore:
    """Manages xhs_creator_subscriptions table."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._db.conn.executescript("""
            CREATE TABLE IF NOT EXISTS xhs_creator_subscriptions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id      TEXT NOT NULL UNIQUE,
                creator_url     TEXT NOT NULL,
                display_name    TEXT NOT NULL DEFAULT '',
                added_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_fetched_at TIMESTAMP
            );
        """)

    def add(
        self,
        creator_id: str,
        creator_url: str,
        display_name: str,
    ) -> None:
        """Add a subscription (ignore if duplicate creator_id)."""
        self._db.conn.execute(
            "INSERT OR IGNORE INTO xhs_creator_subscriptions "
            "(creator_id, creator_url, display_name) VALUES (?, ?, ?)",
            (creator_id, creator_url, display_name),
        )
        self._db.conn.commit()

    def list_all(self) -> list[dict[str, Any]]:
        """Return all subscriptions."""
        rows = self._db.conn.execute(
            "SELECT * FROM xhs_creator_subscriptions ORDER BY added_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def delete(self, sub_id: int) -> bool:
        """Delete a subscription by primary key. Returns True if deleted."""
        cursor = self._db.conn.execute(
            "DELETE FROM xhs_creator_subscriptions WHERE id = ?",
            (sub_id,),
        )
        self._db.conn.commit()
        return cursor.rowcount > 0

    def due_for_fetch(self, *, hours: int = 24) -> list[dict[str, Any]]:
        """Return subscriptions whose last_fetched_at is older than ``hours`` ago."""
        rows = self._db.conn.execute(
            "SELECT * FROM xhs_creator_subscriptions "
            "WHERE last_fetched_at IS NULL "
            "   OR last_fetched_at < datetime('now', ?)",
            (f"-{hours} hours",),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_fetched(self, sub_id: int) -> None:
        """Update last_fetched_at to now."""
        self._db.conn.execute(
            "UPDATE xhs_creator_subscriptions "
            "SET last_fetched_at = CURRENT_TIMESTAMP WHERE id = ?",
            (sub_id,),
        )
        self._db.conn.commit()
