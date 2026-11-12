"""SQLite database persistence for gateway metrics, threads, and assistant messages."""

import json
import logging
import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from karaagy.config import settings
from karaagy.models.threads import ThreadMessage, ThreadState

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Provide a contextual SQLite connection configured with WAL and foreign keys."""
    db_path = settings.resolve_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(db_path),
        timeout=15.0,
        check_same_thread=False,
        autocommit=True,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    try:
        yield conn
    finally:
        conn.close()


class DatabaseManager:
    """Manages SQLite tables and atomic operations for metrics and threads."""

    @classmethod
    def init_db(cls) -> None:
        """Create database tables and indexes if they do not already exist."""
        with get_db_connection() as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS hourly_metrics (
                        hour_timestamp INTEGER PRIMARY KEY,
                        total_requests INTEGER NOT NULL DEFAULT 0,
                        successful_requests INTEGER NOT NULL DEFAULT 0,
                        failed_requests INTEGER NOT NULL DEFAULT 0,
                        prompt_tokens INTEGER NOT NULL DEFAULT 0,
                        completion_tokens INTEGER NOT NULL DEFAULT 0
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS threads (
                        id TEXT PRIMARY KEY,
                        created_at INTEGER NOT NULL,
                        last_active_at INTEGER NOT NULL,
                        conversation_id TEXT,
                        metadata TEXT NOT NULL DEFAULT '{}'
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_threads_last_active_at
                    ON threads(last_active_at);
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS thread_messages (
                        id TEXT PRIMARY KEY,
                        thread_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_thread_messages_thread_id
                    ON thread_messages(thread_id, created_at);
                    """
                )
        logger.debug("Initialized SQLite database at %s", settings.resolve_database_path())

    @classmethod
    def record_metric(
        cls,
        success: bool,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        timestamp: float | None = None,
    ) -> None:
        """Upsert request and token counts into hourly bucket."""
        ts = timestamp if timestamp is not None else time.time()
        hour_ts = int(ts - (ts % 3600))
        succ_val = 1 if success else 0
        fail_val = 0 if success else 1

        with get_db_connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO hourly_metrics (
                        hour_timestamp,
                        total_requests,
                        successful_requests,
                        failed_requests,
                        prompt_tokens,
                        completion_tokens
                    ) VALUES (?, 1, ?, ?, ?, ?)
                    ON CONFLICT(hour_timestamp) DO UPDATE SET
                        total_requests = total_requests + 1,
                        successful_requests = successful_requests + excluded.successful_requests,
                        failed_requests = failed_requests + excluded.failed_requests,
                        prompt_tokens = prompt_tokens + excluded.prompt_tokens,
                        completion_tokens = completion_tokens + excluded.completion_tokens;
                    """,
                    (hour_ts, succ_val, fail_val, prompt_tokens, completion_tokens),
                )

    @classmethod
    def get_hourly_metrics(cls, days: int = 7) -> dict[str, Any]:
        """Fetch continuous time-series metrics for the past N days (zero-filled)."""
        now_ts = time.time()
        current_hour = int(now_ts - (now_ts % 3600))
        hours_count = max(1, days * 24)
        start_hour = current_hour - (hours_count - 1) * 3600

        rows_by_ts: dict[int, sqlite3.Row] = {}
        with get_db_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    hour_timestamp,
                    total_requests,
                    successful_requests,
                    failed_requests,
                    prompt_tokens,
                    completion_tokens
                FROM hourly_metrics
                WHERE hour_timestamp >= ? AND hour_timestamp <= ?
                ORDER BY hour_timestamp ASC;
                """,
                (start_hour, current_hour),
            )
            for row in cursor.fetchall():
                rows_by_ts[int(row["hour_timestamp"])] = row

        series: list[dict[str, Any]] = []
        tot_req = 0
        tot_succ = 0
        tot_fail = 0
        tot_prompt = 0
        tot_comp = 0
        peak_req = 0
        peak_tokens = 0

        for i in range(hours_count):
            slot_ts = start_hour + (i * 3600)
            dt = datetime.fromtimestamp(slot_ts, tz=UTC)
            row = rows_by_ts.get(slot_ts)
            if row is not None:
                reqs = int(row["total_requests"])
                succ = int(row["successful_requests"])
                fail = int(row["failed_requests"])
                prompt = int(row["prompt_tokens"])
                comp = int(row["completion_tokens"])
            else:
                reqs = 0
                succ = 0
                fail = 0
                prompt = 0
                comp = 0

            slot_tokens = prompt + comp
            tot_req += reqs
            tot_succ += succ
            tot_fail += fail
            tot_prompt += prompt
            tot_comp += comp
            if reqs > peak_req:
                peak_req = reqs
            if slot_tokens > peak_tokens:
                peak_tokens = slot_tokens

            series.append(
                {
                    "timestamp": slot_ts,
                    "iso": dt.isoformat(),
                    "date": dt.strftime("%Y-%m-%d"),
                    "hour": dt.strftime("%H:00"),
                    "label": dt.strftime("%d/%m %H:00"),
                    "total_requests": reqs,
                    "successful_requests": succ,
                    "failed_requests": fail,
                    "prompt_tokens": prompt,
                    "completion_tokens": comp,
                    "total_tokens": slot_tokens,
                }
            )

        success_rate = round((tot_succ / tot_req * 100), 1) if tot_req > 0 else 100.0

        return {
            "days": days,
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {
                "days": days,
                "total_requests": tot_req,
                "successful_requests": tot_succ,
                "failed_requests": tot_fail,
                "success_rate_percent": success_rate,
                "total_prompt_tokens": tot_prompt,
                "total_completion_tokens": tot_comp,
                "total_tokens": tot_prompt + tot_comp,
                "peak_hourly_requests": peak_req,
                "peak_hourly_tokens": peak_tokens,
            },
            "series": series,
        }

    @classmethod
    def prune_metrics(cls, retention_days: int = 30) -> int:
        """Purge hourly metrics older than retention period."""
        cutoff = int(time.time() - (retention_days * 86400))
        with get_db_connection() as conn:
            with conn:
                cursor = conn.execute(
                    "DELETE FROM hourly_metrics WHERE hour_timestamp < ?;",
                    (cutoff,),
                )
                return cursor.rowcount

    # -------------------------------------------------------------------------
    # Thread persistence methods
    # -------------------------------------------------------------------------

    @classmethod
    def save_thread(cls, state: ThreadState) -> None:
        """Persist or update thread state and all contained messages."""
        with get_db_connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO threads (id, created_at, last_active_at, conversation_id, metadata)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        last_active_at = excluded.last_active_at,
                        conversation_id = excluded.conversation_id,
                        metadata = excluded.metadata;
                    """,
                    (
                        state.id,
                        state.created_at,
                        state.last_active_at,
                        state.conversation_id,
                        json.dumps(state.metadata),
                    ),
                )
                for msg in state.messages:
                    conn.execute(
                        """
                        INSERT INTO thread_messages (id, thread_id, role, content, metadata, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            role = excluded.role,
                            content = excluded.content,
                            metadata = excluded.metadata;
                        """,
                        (
                            msg.id,
                            msg.thread_id,
                            msg.role,
                            json.dumps(msg.content),
                            json.dumps(msg.metadata),
                            msg.created_at,
                        ),
                    )

    @classmethod
    def load_thread(cls, thread_id: str) -> ThreadState | None:
        """Load a thread and its messages from SQLite."""
        with get_db_connection() as conn:
            t_row = conn.execute(
                "SELECT id, created_at, last_active_at, conversation_id, metadata FROM threads WHERE id = ?;",
                (thread_id,),
            ).fetchone()
            if not t_row:
                return None

            m_rows = conn.execute(
                """
                SELECT id, thread_id, role, content, metadata, created_at
                FROM thread_messages
                WHERE thread_id = ?
                ORDER BY created_at ASC;
                """,
                (thread_id,),
            ).fetchall()

            messages: list[ThreadMessage] = []
            for r in m_rows:
                try:
                    content_val = json.loads(r["content"])
                except Exception:
                    content_val = [{"type": "text", "text": {"value": str(r["content"])}}]
                try:
                    meta_val = json.loads(r["metadata"])
                except Exception:
                    meta_val = {}

                messages.append(
                    ThreadMessage(
                        id=r["id"],
                        thread_id=r["thread_id"],
                        role=r["role"],
                        content=content_val,
                        metadata=meta_val,
                        created_at=r["created_at"],
                    )
                )

            try:
                meta = json.loads(t_row["metadata"])
            except Exception:
                meta = {}

            return ThreadState(
                id=t_row["id"],
                created_at=t_row["created_at"],
                last_active_at=t_row["last_active_at"],
                conversation_id=t_row["conversation_id"],
                metadata=meta,
                messages=messages,
            )

    @classmethod
    def delete_thread(cls, thread_id: str) -> bool:
        """Delete thread by ID (cascades to messages)."""
        with get_db_connection() as conn:
            with conn:
                cursor = conn.execute("DELETE FROM threads WHERE id = ?;", (thread_id,))
                return bool(cursor.rowcount > 0)

    @classmethod
    def add_thread_message(cls, thread_id: str, message: ThreadMessage) -> None:
        """Append a message to a thread and touch last_active_at timestamp."""
        now = int(time.time())
        with get_db_connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO thread_messages (id, thread_id, role, content, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        role = excluded.role,
                        content = excluded.content,
                        metadata = excluded.metadata;
                    """,
                    (
                        message.id,
                        message.thread_id,
                        message.role,
                        json.dumps(message.content),
                        json.dumps(message.metadata),
                        message.created_at,
                    ),
                )
                conn.execute(
                    "UPDATE threads SET last_active_at = ? WHERE id = ?;",
                    (now, thread_id),
                )

    @classmethod
    def list_thread_messages(
        cls, thread_id: str, limit: int = 50, order: str = "desc"
    ) -> list[ThreadMessage]:
        """Retrieve paginated messages for a thread."""
        order_dir = "DESC" if order.lower() == "desc" else "ASC"
        with get_db_connection() as conn:
            m_rows = conn.execute(
                f"""
                SELECT id, thread_id, role, content, metadata, created_at
                FROM thread_messages
                WHERE thread_id = ?
                ORDER BY created_at {order_dir}
                LIMIT ?;
                """,
                (thread_id, limit),
            ).fetchall()

            messages: list[ThreadMessage] = []
            for r in m_rows:
                try:
                    content_val = json.loads(r["content"])
                except Exception:
                    content_val = [{"type": "text", "text": {"value": str(r["content"])}}]
                try:
                    meta_val = json.loads(r["metadata"])
                except Exception:
                    meta_val = {}

                messages.append(
                    ThreadMessage(
                        id=r["id"],
                        thread_id=r["thread_id"],
                        role=r["role"],
                        content=content_val,
                        metadata=meta_val,
                        created_at=r["created_at"],
                    )
                )
            return messages

    @classmethod
    def get_thread_counts(cls, ttl_seconds: float) -> dict[str, int]:
        """Return counts of total threads and active/living threads within TTL."""
        cutoff = int(time.time() - ttl_seconds)
        with get_db_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*),
                    COALESCE(SUM(CASE WHEN last_active_at >= ? THEN 1 ELSE 0 END), 0)
                FROM threads;
                """,
                (cutoff,),
            )
            row = cursor.fetchone()
            total = int(row[0]) if row and row[0] is not None else 0
            active = int(row[1]) if row and row[1] is not None else 0
            return {"active_threads": active, "total_threads": total}

    @classmethod
    def get_expired_threads(cls, ttl_seconds: float) -> list[tuple[str, str | None]]:
        """Return list of (thread_id, conversation_id) for threads older than TTL."""
        cutoff = int(time.time() - ttl_seconds)
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT id, conversation_id FROM threads WHERE last_active_at < ?;",
                (cutoff,),
            )
            return [(r["id"], r["conversation_id"]) for r in cursor.fetchall()]

    @classmethod
    def delete_threads_batch(cls, thread_ids: list[str]) -> int:
        """Delete multiple threads by ID list."""
        if not thread_ids:
            return 0
        placeholders = ",".join("?" for _ in thread_ids)
        with get_db_connection() as conn:
            with conn:
                cursor = conn.execute(
                    f"DELETE FROM threads WHERE id IN ({placeholders});",
                    thread_ids,
                )
                return cursor.rowcount

    @classmethod
    def migrate_legacy_json_threads(cls, storage_dir: Path) -> int:
        """Import legacy JSON files from karaagy_threads/ into SQLite and unlink them."""
        if not storage_dir.exists():
            return 0

        migrated_count = 0
        for json_file in storage_dir.glob("thread_*.json"):
            try:
                raw_data = json.loads(json_file.read_text(encoding="utf-8"))
                state = ThreadState(**raw_data)
                cls.save_thread(state)
                json_file.unlink(missing_ok=True)
                migrated_count += 1
                logger.info("Migrated legacy thread file %s to SQLite", json_file.name)
            except Exception as e:
                logger.warning("Failed to migrate legacy thread file %s: %s", json_file, e)

        return migrated_count
