"""Content Discovery Engine.

Coordinates multiple discovery strategies to find content
that matches the user's soul profile.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openbiliclaw.soul.profile import SoulProfile

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredContent:
    """A piece of content discovered by the engine."""

    bvid: str = ""  # Bilibili video ID
    title: str = ""
    up_name: str = ""  # UP主 name
    up_mid: int = 0  # UP主 ID
    cover_url: str = ""
    duration: int = 0  # seconds
    view_count: int = 0
    like_count: int = 0
    tags: list[str] = field(default_factory=list)
    description: str = ""
    source_strategy: str = ""  # Which strategy found this
    relevance_score: float = 0.0  # 0.0 - 1.0 (based on user soul)
    relevance_reason: str = ""  # Why this is relevant to the user


class DiscoveryStrategy(ABC):
    """Base class for content discovery strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name."""
        ...

    @abstractmethod
    async def discover(
        self, profile: SoulProfile, limit: int = 20
    ) -> list[DiscoveredContent]:
        """Execute the discovery strategy.

        Args:
            profile: Current user soul profile for relevance guidance.
            limit: Maximum number of items to return.

        Returns:
            List of discovered content items.
        """
        ...


class ContentDiscoveryEngine:
    """Orchestrates multiple discovery strategies.

    Available strategies:
    - Search: keyword-based search from user interests
    - Related: follow related recommendation chains
    - Trending: scan trending/ranking content
    - Comments: mine recommendations from comment sections
    - UPTrack: track followed/discovered UP主
    - Explore: cross-domain surprise discovery
    """

    def __init__(self) -> None:
        self._strategies: list[DiscoveryStrategy] = []

    def register_strategy(self, strategy: DiscoveryStrategy) -> None:
        """Register a discovery strategy."""
        self._strategies.append(strategy)
        logger.info("Registered discovery strategy: %s", strategy.name)

    async def discover(
        self, profile: SoulProfile, strategies: list[str] | None = None
    ) -> list[DiscoveredContent]:
        """Run discovery with selected (or all) strategies.

        Args:
            profile: User soul profile for relevance evaluation.
            strategies: Optional list of strategy names to run.
                       If None, runs all registered strategies.

        Returns:
            Combined, deduplicated, and scored list of discovered content.
        """
        results: list[DiscoveredContent] = []

        active = self._strategies
        if strategies:
            active = [s for s in self._strategies if s.name in strategies]

        for strategy in active:
            try:
                items = await strategy.discover(profile)
                results.extend(items)
                logger.info("Strategy '%s' found %d items.", strategy.name, len(items))
            except Exception:
                logger.exception("Strategy '%s' failed.", strategy.name)

        # Deduplicate by bvid
        seen: set[str] = set()
        unique: list[DiscoveredContent] = []
        for item in results:
            if item.bvid not in seen:
                seen.add(item.bvid)
                unique.append(item)

        # Sort by relevance
        unique.sort(key=lambda x: x.relevance_score, reverse=True)
        return unique

    async def evaluate_content(
        self, content: DiscoveredContent, profile: SoulProfile
    ) -> float:
        """Evaluate how relevant a piece of content is for the user.

        The core evaluation is based on the user's Soul — their deep personality
        and interests — not just surface-level metrics.

        Args:
            content: Content to evaluate.
            profile: User's soul profile.

        Returns:
            Relevance score (0.0 - 1.0).
        """
        # TODO: LLM-based evaluation against soul profile
        return 0.0
