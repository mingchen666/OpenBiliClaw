"""Tests for discovery engine orchestration."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from openbiliclaw.discovery.engine import ContentDiscoveryEngine, DiscoveredContent
from openbiliclaw.soul.profile import SoulProfile
from openbiliclaw.storage.database import Database

from .test_explore_strategy import (
    FakeBilibiliClient as FakeExploreBilibiliClient,
)
from .test_explore_strategy import (
    FakeLLMService as FakeExploreLLMService,
)
from .test_related_chain_strategy import (
    FakeLLMService as FakeRelatedLLMService,
)
from .test_related_chain_strategy import (
    FakeMemoryManager,
    FakeRelatedClient,
    _event,
)
from .test_search_strategy import FakeBilibiliClient, FakeLLMService, _build_profile
from .test_trending_strategy import FakeLLMService as FakeTrendingLLMService
from .test_trending_strategy import FakeRankingClient


@pytest.mark.asyncio
async def test_discovery_engine_runs_registered_search_strategy() -> None:
    from openbiliclaw.discovery.strategies.strategies import SearchStrategy

    engine = ContentDiscoveryEngine()
    strategy = SearchStrategy(
        llm_service=FakeLLMService('{"queries": ["纪录片 原理"]}'),
        bilibili_client=FakeBilibiliClient(
            {
                "纪录片 原理": [
                    {"bvid": "BV1A", "title": "纪录片", "author": "UP1", "mid": 1}
                ]
            }
        ),
    )
    engine.register_strategy(strategy)

    results = await engine.discover(_build_profile())

    assert len(results) == 1
    assert results[0].bvid == "BV1A"
    assert results[0].source_strategy == "search"


@pytest.mark.asyncio
async def test_discovery_engine_handles_empty_strategy_results() -> None:
    from openbiliclaw.discovery.strategies.strategies import SearchStrategy

    engine = ContentDiscoveryEngine()
    engine.register_strategy(
        SearchStrategy(
            llm_service=FakeLLMService('{"queries": []}'),
            bilibili_client=FakeBilibiliClient({}),
        )
    )

    results = await engine.discover(SoulProfile())

    assert results == []


@pytest.mark.asyncio
async def test_discovery_engine_runs_registered_trending_strategy() -> None:
    from openbiliclaw.discovery.engine import ContentDiscoveryEngine
    from openbiliclaw.discovery.strategies.strategies import TrendingStrategy

    engine = ContentDiscoveryEngine(
        llm_service=FakeTrendingLLMService(
            [
                '{"rids": [36]}',
                '{"score": 0.83, "reason": "符合你的深度内容偏好。"}',
            ]
        )
    )
    engine.register_strategy(
        TrendingStrategy(
            bilibili_client=FakeRankingClient(
                {
                    0: [{"bvid": "BV1A", "title": "全站榜", "author": "UP1", "mid": 1}],
                    36: [],
                }
            ),
            llm_service=engine._llm_service,
            score_threshold=0.65,
        )
    )

    results = await engine.discover(_build_profile())

    assert len(results) == 1
    assert results[0].bvid == "BV1A"
    assert results[0].source_strategy == "trending"


@pytest.mark.asyncio
async def test_discovery_engine_runs_related_chain_strategy() -> None:
    from openbiliclaw.discovery.engine import ContentDiscoveryEngine
    from openbiliclaw.discovery.strategies.strategies import RelatedChainStrategy

    engine = ContentDiscoveryEngine(
        llm_service=FakeRelatedLLMService(
            ['{"score": 0.84, "reason": "延续了近期观看兴趣。"}']
        )
    )
    engine.register_strategy(
        RelatedChainStrategy(
            bilibili_client=FakeRelatedClient(
                {
                    "BV1SEED": [
                        {
                            "bvid": "BV1REL",
                            "title": "相关推荐",
                            "owner": {"name": "UPR", "mid": 10},
                        }
                    ]
                }
            ),
            llm_service=engine._llm_service,
            memory_manager=FakeMemoryManager(events=[_event("BV1SEED")]),
        )
    )

    results = await engine.discover(_build_profile())

    assert len(results) == 1
    assert results[0].bvid == "BV1REL"
    assert results[0].source_strategy == "related_chain"


@pytest.mark.asyncio
async def test_discovery_engine_runs_explore_strategy() -> None:
    from openbiliclaw.discovery.engine import ContentDiscoveryEngine
    from openbiliclaw.discovery.strategies.strategies import ExploreStrategy

    engine = ContentDiscoveryEngine(
        llm_service=FakeExploreLLMService(
            [
                """
                {
                  "domains": [
                    {
                      "domain": "城市空间与建筑叙事",
                      "why_it_might_resonate": "你偏好理解复杂系统。",
                      "novelty_level": 0.7,
                      "queries": ["城市 建筑 纪录片"]
                    }
                  ]
                }
                """,
                '{"score": 0.84, "reason": "这个陌生主题仍然符合你的理解欲。"}',
            ]
        )
    )
    engine.register_strategy(
        ExploreStrategy(
            llm_service=engine._llm_service,
            bilibili_client=FakeExploreBilibiliClient(
                {
                    "城市 建筑 纪录片": [
                        {"bvid": "BV1EXP", "title": "城市建筑", "author": "UPX", "mid": 9}
                    ]
                }
            ),
            score_threshold=0.65,
        )
    )

    results = await engine.discover(_build_profile())

    assert len(results) == 1
    assert results[0].bvid == "BV1EXP"
    assert results[0].source_strategy == "explore"


class _RecordingStrategy:
    def __init__(
        self,
        name: str,
        result: list[DiscoveredContent],
        *,
        delay: float = 0.0,
        should_fail: bool = False,
        started: list[str] | None = None,
    ) -> None:
        self._name = name
        self._result = result
        self._delay = delay
        self._should_fail = should_fail
        self._started = started if started is not None else []

    @property
    def name(self) -> str:
        return self._name

    async def discover(
        self, profile: SoulProfile, limit: int = 20
    ) -> list[DiscoveredContent]:
        self._started.append(self._name)
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._should_fail:
            raise RuntimeError(f"boom: {self._name}")
        return self._result[:limit]


@pytest.mark.asyncio
async def test_discovery_engine_runs_strategies_concurrently_and_tolerates_failures() -> None:
    started: list[str] = []
    engine = ContentDiscoveryEngine()
    engine.register_strategy(
        _RecordingStrategy(
            "slow-search",
            [DiscoveredContent(bvid="BV1A", relevance_score=0.72, source_strategy="search")],
            delay=0.02,
            started=started,
        )
    )
    engine.register_strategy(
        _RecordingStrategy(
            "fast-failing",
            [],
            delay=0.0,
            should_fail=True,
            started=started,
        )
    )
    engine.register_strategy(
        _RecordingStrategy(
            "fast-trending",
            [DiscoveredContent(bvid="BV1B", relevance_score=0.81, source_strategy="trending")],
            delay=0.0,
            started=started,
        )
    )

    results = await engine.discover(_build_profile(), limit=20)

    assert started == ["slow-search", "fast-failing", "fast-trending"]
    assert [item.bvid for item in results] == ["BV1B", "BV1A"]


@pytest.mark.asyncio
async def test_discovery_engine_keeps_highest_scored_duplicate() -> None:
    engine = ContentDiscoveryEngine()
    engine.register_strategy(
        _RecordingStrategy(
            "search",
            [
                DiscoveredContent(
                    bvid="BV1DUP",
                    title="低分版本",
                    relevance_score=0.52,
                    source_strategy="search",
                )
            ],
        )
    )
    engine.register_strategy(
        _RecordingStrategy(
            "trending",
            [
                DiscoveredContent(
                    bvid="BV1DUP",
                    title="高分版本",
                    relevance_score=0.91,
                    source_strategy="trending",
                )
            ],
        )
    )

    results = await engine.discover(_build_profile(), limit=20)

    assert len(results) == 1
    assert results[0].title == "高分版本"
    assert results[0].source_strategy == "trending"


@pytest.mark.asyncio
async def test_discovery_engine_caches_final_results() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(Path(tmpdir) / "test.db")
        db.initialize()

        engine = ContentDiscoveryEngine(database=db)
        engine.register_strategy(
            _RecordingStrategy(
                "search",
                [
                    DiscoveredContent(
                        bvid="BV1A",
                        title="缓存内容 A",
                        up_name="UPA",
                        relevance_score=0.88,
                        source_strategy="search",
                    ),
                    DiscoveredContent(
                        bvid="BV1B",
                        title="缓存内容 B",
                        up_name="UPB",
                        relevance_score=0.74,
                        source_strategy="explore",
                    ),
                ],
            )
        )

        results = await engine.discover(_build_profile(), limit=20)
        cached = db.get_cached_content(limit=10)

        assert [item.bvid for item in results] == ["BV1A", "BV1B"]
        assert [item["bvid"] for item in cached] == ["BV1A", "BV1B"]
        assert cached[0]["source"] == "search"
