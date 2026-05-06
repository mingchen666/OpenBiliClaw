"""Tests for the Douyin task-queue API endpoints.

Task 2 of the Douyin bootstrap import plan
(``docs/plans/2026-05-06-douyin-bootstrap-import.md``).

The endpoints mirror the XHS pattern in shape — separate table
``dy_tasks`` and separate route prefix ``/api/sources/dy/`` — but
share zero code with the XHS implementation per design-doc
"Module Isolation from XHS".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from pathlib import Path

    from openbiliclaw.storage.database import Database


class RecordingMemoryManager:
    """Captures every event propagated through the soul pipeline."""

    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self._discovery_runtime_state: dict[str, object] = {}

    async def propagate_event(self, event: dict[str, object]) -> None:
        self.events.append(event)

    def load_discovery_runtime_state(self) -> dict[str, object]:
        return dict(self._discovery_runtime_state)

    def save_discovery_runtime_state(self, state: dict[str, object]) -> None:
        self._discovery_runtime_state = dict(state)


@pytest.fixture
def dy_task_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[TestClient, Database, RecordingMemoryManager]:
    """Build an API client with an injectable memory manager for dy task tests."""
    from types import SimpleNamespace

    from openbiliclaw.storage.database import Database

    db = Database(tmp_path / "task.db")
    db.initialize()
    memory = RecordingMemoryManager()

    fake_config = SimpleNamespace(
        data_path=tmp_path,
        bilibili=SimpleNamespace(cookie="", browser_executable="", browser_headed=False),
        sources=SimpleNamespace(
            browser_cdp_url="",
            browser_headed=False,
            xiaohongshu=SimpleNamespace(
                daily_search_budget=20,
                daily_creator_budget=10,
                task_interval_seconds=45,
            ),
        ),
        scheduler=SimpleNamespace(pool_target_count=300, account_sync_interval_hours=24),
    )

    monkeypatch.setattr("openbiliclaw.config.load_config", lambda: fake_config)

    from openbiliclaw.api.app import create_app

    app = create_app(
        database=db,
        memory_manager=memory,
        soul_engine=SimpleNamespace(),
        runtime_controller=SimpleNamespace(memory_manager=memory),
        recommendation_engine=None,
    )
    return TestClient(app), db, memory


def _enqueue_dy_bootstrap_task(db: Database, payload: dict[str, object] | None = None) -> str:
    """Enqueue a bootstrap_profile task via the DyTaskQueue and return its id."""
    from openbiliclaw.sources.dy_tasks import DyTaskQueue

    queue = DyTaskQueue(db)
    task_id = queue.enqueue_with_id(
        "bootstrap_profile",
        payload or {"scopes": ["dy_post", "dy_collect", "dy_like", "dy_follow"]},
        daily_budget=10,
    )
    assert task_id is not None
    return task_id


class TestDyNextTask:
    def test_returns_204_when_no_tasks_pending(
        self,
        dy_task_client: tuple[TestClient, Database, RecordingMemoryManager],
    ) -> None:
        client, _db, _memory = dy_task_client
        response = client.get("/api/sources/dy/next-task")
        assert response.status_code == 204

    def test_returns_pending_task_payload(
        self,
        dy_task_client: tuple[TestClient, Database, RecordingMemoryManager],
    ) -> None:
        client, db, _memory = dy_task_client
        task_id = _enqueue_dy_bootstrap_task(db)

        response = client.get("/api/sources/dy/next-task")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == task_id
        assert body["type"] == "bootstrap_profile"
        assert body["scopes"] == ["dy_post", "dy_collect", "dy_like", "dy_follow"]


class TestDyTaskResult:
    def test_rejects_missing_task_id(
        self,
        dy_task_client: tuple[TestClient, Database, RecordingMemoryManager],
    ) -> None:
        client, _db, _memory = dy_task_client
        response = client.post("/api/sources/dy/task-result", json={"status": "ok"})
        assert response.status_code == 422

    def test_dy_bootstrap_task_result_records_events(
        self,
        dy_task_client: tuple[TestClient, Database, RecordingMemoryManager],
    ) -> None:
        """status=ok with bootstrap_profile videos: marks task complete and
        propagates events through memory."""
        client, db, memory = dy_task_client
        task_id = _enqueue_dy_bootstrap_task(db)

        response = client.post(
            "/api/sources/dy/task-result",
            json={
                "task_id": task_id,
                "status": "ok",
                "videos": [
                    {
                        "scope": "dy_collect",
                        "title": "demo",
                        "url": "https://www.douyin.com/video/aaa",
                        "aweme_id": "aaa",
                        "author": "作者",
                    },
                    {
                        "scope": "dy_like",
                        "title": "liked",
                        "url": "https://www.douyin.com/video/bbb",
                        "aweme_id": "bbb",
                    },
                    {
                        "scope": "dy_follow",
                        "title": "creator",
                        "url": "https://www.douyin.com/user/ccc",
                        "creator_sec_uid": "ccc",
                    },
                ],
                "scope_counts": {"dy_collect": 1, "dy_like": 1, "dy_follow": 1, "dy_post": 0},
            },
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True

        event_types = [e["event_type"] for e in memory.events]
        assert event_types == ["favorite", "like", "follow"]
        assert all(e["metadata"]["source_platform"] == "douyin" for e in memory.events)

        # Task is marked completed.
        from openbiliclaw.sources.dy_tasks import DyTaskQueue

        queue = DyTaskQueue(db)
        task = queue.get(task_id)
        assert task is not None
        assert task["status"] == "completed"

    def test_dy_task_failure_marks_task_failed(
        self,
        dy_task_client: tuple[TestClient, Database, RecordingMemoryManager],
    ) -> None:
        client, db, memory = dy_task_client
        task_id = _enqueue_dy_bootstrap_task(db)

        response = client.post(
            "/api/sources/dy/task-result",
            json={"task_id": task_id, "status": "failed", "error": "captcha"},
        )
        assert response.status_code == 200
        assert memory.events == []  # no events on failure

        from openbiliclaw.sources.dy_tasks import DyTaskQueue

        queue = DyTaskQueue(db)
        task = queue.get(task_id)
        assert task is not None
        assert task["status"] == "failed"

    def test_dy_partial_result_does_not_mark_complete(
        self,
        dy_task_client: tuple[TestClient, Database, RecordingMemoryManager],
    ) -> None:
        """status=partial keeps the task pending so the executor can keep posting."""
        client, db, memory = dy_task_client
        task_id = _enqueue_dy_bootstrap_task(db)

        response = client.post(
            "/api/sources/dy/task-result",
            json={
                "task_id": task_id,
                "status": "partial",
                "videos": [
                    {
                        "scope": "dy_collect",
                        "title": "v1",
                        "url": "https://www.douyin.com/video/v1",
                        "aweme_id": "v1",
                    },
                ],
                "scope_counts": {"dy_collect": 1},
            },
        )
        assert response.status_code == 200
        assert len(memory.events) == 1  # event still propagates incrementally

        from openbiliclaw.sources.dy_tasks import DyTaskQueue

        queue = DyTaskQueue(db)
        task = queue.get(task_id)
        assert task is not None
        assert task["status"] == "pending"  # NOT completed yet
