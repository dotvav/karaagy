"""Tests for SQLite database persistence (metrics and threads)."""

import json
import time
from pathlib import Path

from karaagy.config import settings
from karaagy.core.database import DatabaseManager, get_db_connection
from karaagy.core.threads import ThreadManager, ThreadState
from karaagy.models.threads import CreateThreadMessageRequest, ThreadMessage


def test_database_init_and_tables(tmp_path: Path) -> None:
    """Test SQLite tables and indexes are created properly."""
    db_file = tmp_path / "custom_karaagy.db"
    settings.database_path = db_file
    DatabaseManager.init_db()

    assert db_file.exists()
    with get_db_connection() as conn:
        tables = [
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        ]
        assert "hourly_metrics" in tables
        assert "threads" in tables
        assert "thread_messages" in tables


def test_record_and_aggregate_hourly_metrics(tmp_path: Path) -> None:
    """Test recording requests/tokens into hourly buckets with atomic upsert."""
    settings.database_path = tmp_path / "metrics_test.db"
    DatabaseManager.init_db()

    now = 1794123600.0  # reference epoch
    hour_base = int(now - (now % 3600))

    # Record 3 events in same hour
    DatabaseManager.record_metric(
        success=True, prompt_tokens=100, completion_tokens=50, timestamp=now
    )
    DatabaseManager.record_metric(
        success=True, prompt_tokens=200, completion_tokens=80, timestamp=now + 60
    )
    DatabaseManager.record_metric(
        success=False, prompt_tokens=50, completion_tokens=0, timestamp=now + 120
    )

    # Record 1 event in previous hour
    DatabaseManager.record_metric(
        success=True, prompt_tokens=400, completion_tokens=120, timestamp=now - 3600
    )

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM hourly_metrics WHERE hour_timestamp = ?;",
            (hour_base,),
        ).fetchone()
        assert row is not None
        assert row["total_requests"] == 3
        assert row["successful_requests"] == 2
        assert row["failed_requests"] == 1
        assert row["prompt_tokens"] == 350
        assert row["completion_tokens"] == 130


def test_get_hourly_metrics_full_series(tmp_path: Path) -> None:
    """Test retrieving continuous 7-day (168h) series zero-filled with summary stats."""
    settings.database_path = tmp_path / "metrics_series.db"
    DatabaseManager.init_db()

    # Record an event in current hour
    current_ts = time.time()
    DatabaseManager.record_metric(
        success=True, prompt_tokens=500, completion_tokens=150, timestamp=current_ts
    )

    res = DatabaseManager.get_hourly_metrics(days=7)
    assert res["days"] == 7
    assert len(res["series"]) == 168

    summary = res["summary"]
    assert summary["days"] == 7
    assert summary["total_requests"] >= 1
    assert summary["successful_requests"] >= 1
    assert summary["total_prompt_tokens"] >= 500
    assert summary["total_completion_tokens"] >= 150
    assert summary["peak_hourly_requests"] >= 1
    assert summary["peak_hourly_tokens"] >= 650


def test_prune_old_metrics(tmp_path: Path) -> None:
    """Test purging metrics older than retention period."""
    settings.database_path = tmp_path / "metrics_prune.db"
    DatabaseManager.init_db()

    old_ts = time.time() - (40 * 86400)  # 40 days ago
    recent_ts = time.time() - (5 * 86400)  # 5 days ago

    DatabaseManager.record_metric(success=True, timestamp=old_ts)
    DatabaseManager.record_metric(success=True, timestamp=recent_ts)

    pruned = DatabaseManager.prune_metrics(retention_days=30)
    assert pruned == 1

    with get_db_connection() as conn:
        count = conn.execute("SELECT count(*) as cnt FROM hourly_metrics;").fetchone()["cnt"]
        assert count == 1


def test_thread_crud_and_cascade(tmp_path: Path) -> None:
    """Test saving, loading, listing, and cascade-deleting threads in SQLite."""
    settings.database_path = tmp_path / "threads_test.db"
    DatabaseManager.init_db()

    thread_id = "thread_test_123"
    state = ThreadState(
        id=thread_id,
        created_at=int(time.time()),
        last_active_at=int(time.time()),
        conversation_id="convo_xyz",
        metadata={"project": "karaagy"},
        messages=[
            ThreadMessage(
                id="msg_1",
                thread_id=thread_id,
                role="user",
                content=[{"type": "text", "text": {"value": "Hello"}}],
                created_at=1000,
            )
        ],
    )

    DatabaseManager.save_thread(state)

    # Add message
    new_msg = ThreadMessage(
        id="msg_2",
        thread_id=thread_id,
        role="assistant",
        content=[{"type": "text", "text": {"value": "Hi there!"}}],
        created_at=2000,
    )
    DatabaseManager.add_thread_message(thread_id, new_msg)

    # Load thread
    loaded = DatabaseManager.load_thread(thread_id)
    assert loaded is not None
    assert loaded.id == thread_id
    assert loaded.conversation_id == "convo_xyz"
    assert loaded.metadata["project"] == "karaagy"
    assert len(loaded.messages) == 2

    # List messages
    msgs_desc = DatabaseManager.list_thread_messages(thread_id, limit=10, order="desc")
    assert len(msgs_desc) == 2
    assert msgs_desc[0].id == "msg_2"
    assert msgs_desc[1].id == "msg_1"

    # Delete thread (cascade)
    deleted = DatabaseManager.delete_thread(thread_id)
    assert deleted is True
    assert DatabaseManager.load_thread(thread_id) is None

    with get_db_connection() as conn:
        msg_count = conn.execute(
            "SELECT count(*) as cnt FROM thread_messages WHERE thread_id = ?;",
            (thread_id,),
        ).fetchone()["cnt"]
        assert msg_count == 0


def test_legacy_json_migration(tmp_path: Path) -> None:
    """Test importing legacy thread_*.json files into SQLite and removing them."""
    settings.database_path = tmp_path / "migrate_test.db"
    DatabaseManager.init_db()

    legacy_dir = tmp_path / "legacy_threads"
    legacy_dir.mkdir(parents=True, exist_ok=True)

    legacy_thread = {
        "id": "thread_legacy_abc",
        "created_at": 1700000000,
        "last_active_at": 1700000000,
        "conversation_id": "legacy_convo_456",
        "metadata": {"legacy": True},
        "messages": [
            {
                "id": "msg_leg_1",
                "object": "thread.message",
                "created_at": 1700000000,
                "thread_id": "thread_legacy_abc",
                "role": "user",
                "content": [{"type": "text", "text": {"value": "Legacy query"}}],
                "metadata": {},
            }
        ],
    }

    json_file = legacy_dir / "thread_legacy_abc.json"
    json_file.write_text(json.dumps(legacy_thread), encoding="utf-8")

    migrated = DatabaseManager.migrate_legacy_json_threads(legacy_dir)
    assert migrated == 1
    assert not json_file.exists()

    loaded = DatabaseManager.load_thread("thread_legacy_abc")
    assert loaded is not None
    assert loaded.conversation_id == "legacy_convo_456"
    assert len(loaded.messages) == 1
    assert loaded.messages[0].content[0]["text"]["value"] == "Legacy query"


def test_thread_manager_prune_expired(tmp_path: Path) -> None:
    """Test ThreadManager prune_expired_threads removes only threads past TTL."""
    settings.database_path = tmp_path / "prune_test.db"
    settings.threads_dir = tmp_path / "threads_prune"
    settings.thread_ttl_seconds = 3600.0  # 1 hour
    DatabaseManager.init_db()

    # Active thread
    active = ThreadManager.create_thread(
        messages=[CreateThreadMessageRequest(role="user", content="Active")]
    )

    # Expired thread
    expired = ThreadManager.create_thread(
        messages=[CreateThreadMessageRequest(role="user", content="Old")]
    )
    with get_db_connection() as conn:
        with conn:
            conn.execute(
                "UPDATE threads SET last_active_at = ? WHERE id = ?;",
                (int(time.time() - 7200), expired.id),
            )

    pruned = ThreadManager.prune_expired_threads()
    assert pruned == 1

    assert ThreadManager.get_thread(active.id) is not None
    assert ThreadManager.get_thread(expired.id) is None


def test_database_and_diagnostics_thread_counts(tmp_path: Path) -> None:
    """Test get_thread_counts and DiagnosticsManager thread counts caching."""
    from karaagy.core.diagnostics import DiagnosticsManager

    settings.database_path = tmp_path / "counts_test.db"
    settings.thread_ttl_seconds = 3600.0  # 1 hour
    DatabaseManager.init_db()
    DiagnosticsManager.invalidate_thread_counts_cache()

    # Empty table
    counts = DatabaseManager.get_thread_counts(settings.thread_ttl_seconds)
    assert counts == {"active_threads": 0, "total_threads": 0}

    # Add 1 active and 1 expired thread
    now = time.time()
    active = ThreadManager.create_thread(
        messages=[CreateThreadMessageRequest(role="user", content="Active")]
    )
    assert active.id is not None
    expired = ThreadManager.create_thread(
        messages=[CreateThreadMessageRequest(role="user", content="Expired")]
    )
    with get_db_connection() as conn:
        with conn:
            conn.execute(
                "UPDATE threads SET last_active_at = ? WHERE id = ?;",
                (int(now - 7200), expired.id),
            )

    counts = DatabaseManager.get_thread_counts(settings.thread_ttl_seconds)
    assert counts == {"active_threads": 1, "total_threads": 2}

    # Test DiagnosticsManager caching
    cached1 = DiagnosticsManager.get_thread_counts()
    assert cached1 == {"active_threads": 1, "total_threads": 2}

    # Manually add another thread to DB directly
    with get_db_connection() as conn:
        with conn:
            conn.execute(
                "INSERT INTO threads (id, created_at, last_active_at, conversation_id, metadata) VALUES (?, ?, ?, ?, ?);",
                ("thread_direct", int(now), int(now), "conv_1", "{}"),
            )

    # Cached call should still return old value due to TTL
    cached2 = DiagnosticsManager.get_thread_counts()
    assert cached2 == {"active_threads": 1, "total_threads": 2}

    # Invalidate cache and call again
    DiagnosticsManager.invalidate_thread_counts_cache()
    fresh = DiagnosticsManager.get_thread_counts()
    assert fresh == {"active_threads": 2, "total_threads": 3}
