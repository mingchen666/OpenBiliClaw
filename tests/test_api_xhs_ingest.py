"""Tests for the xhs observed-URL ingestion endpoint.

POST /api/sources/xhs/observed-urls accepts a batch of xhs note URLs
that the extension passively collected and schedules enrichment via the
XiaohongshuAdapter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Build a minimal TestClient with a real database but mocked adapter."""
    from types import SimpleNamespace

    from openbiliclaw.storage.database import Database

    db = Database(tmp_path / "test.db")
    db.initialize()

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
    monkeypatch.setattr("openbiliclaw.llm.build_llm_registry", lambda config: "registry")
    monkeypatch.setattr("openbiliclaw.bilibili.auth.resolve_runtime_cookie", lambda **_: "")

    from openbiliclaw.api.app import create_app

    app = create_app(database=db)
    return TestClient(app)


class TestXhsObservedUrls:
    def test_ingest_valid_urls(self, app_client: TestClient) -> None:
        response = app_client.post(
            "/api/sources/xhs/observed-urls",
            json={
                "urls": [
                    "https://www.xiaohongshu.com/explore/abc123?xsec_token=ZZZ",
                    "https://www.xiaohongshu.com/explore/def456?xsec_token=YYY",
                ],
                "page_type": "search",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["accepted"] == 2

    def test_rejects_empty_url_list(self, app_client: TestClient) -> None:
        response = app_client.post(
            "/api/sources/xhs/observed-urls",
            json={"urls": [], "page_type": "search"},
        )
        assert response.status_code == 422

    def test_rejects_too_many_urls(self, app_client: TestClient) -> None:
        urls = [f"https://www.xiaohongshu.com/explore/{i:024x}" for i in range(60)]
        response = app_client.post(
            "/api/sources/xhs/observed-urls",
            json={"urls": urls, "page_type": "search"},
        )
        assert response.status_code == 422

    def test_filters_invalid_url_shapes(self, app_client: TestClient) -> None:
        response = app_client.post(
            "/api/sources/xhs/observed-urls",
            json={
                "urls": [
                    "https://www.xiaohongshu.com/explore/abc123",
                    "https://example.com/bad",
                    "not-even-a-url",
                ],
                "page_type": "explore",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["accepted"] == 1  # only the valid xhs URL

    def test_stores_observations_in_db(
        self, app_client: TestClient, tmp_path: Path
    ) -> None:
        from openbiliclaw.storage.database import Database

        db = Database(tmp_path / "test.db")
        db.initialize()

        app_client.post(
            "/api/sources/xhs/observed-urls",
            json={
                "urls": ["https://www.xiaohongshu.com/explore/abc123"],
                "page_type": "search",
            },
        )

        rows = db.conn.execute("SELECT * FROM xhs_observed_urls").fetchall()
        assert len(rows) >= 1
        assert rows[0]["url"] == "https://www.xiaohongshu.com/explore/abc123"
        assert rows[0]["page_type"] == "search"
