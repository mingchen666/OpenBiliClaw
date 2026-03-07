"""Recommendation Engine — ranking, expression, and delivery.

Handles the final stage: taking discovered content and presenting it
to the user in a warm, friend-like manner with deep personal insights.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openbiliclaw.discovery.engine import DiscoveredContent
    from openbiliclaw.llm.base import LLMProvider
    from openbiliclaw.soul.profile import SoulProfile

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """A recommendation ready to present to the user."""

    content: DiscoveredContent
    expression: str = ""  # Friend-style recommendation reason
    topic_label: str = ""  # Personal topic (not generic categories)
    confidence: float = 0.0  # How confident the agent is in this rec
    presented: bool = False
    feedback: str | None = None  # User feedback after seeing it


@dataclass
class PersonalTopic:
    """A deeply personalized recommendation topic.

    Not generic labels like "Weekend Pack" but personal ones like:
    "你最近在探索摄影——这几个视频从你习惯的'搞明白原理'的角度讲构图"
    """

    title: str = ""
    description: str = ""
    recommendations: list[Recommendation] = field(default_factory=list)


class RecommendationEngine:
    """Produces warm, personalized recommendations.

    The engine takes discovered content and transforms it into
    friend-style recommendations with:
    - "我觉得" — subjective, personal judgment
    - "我理解你" — demonstrates deep understanding
    - Personal insights connecting content to the user's soul
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def generate_recommendations(
        self,
        discovered: list[DiscoveredContent],
        profile: SoulProfile,
        limit: int = 10,
    ) -> list[Recommendation]:
        """Generate friend-style recommendations from discovered content.

        Args:
            discovered: Content discovered by the discovery engine.
            profile: User's soul profile for personalization.
            limit: Maximum number of recommendations.

        Returns:
            List of personalized recommendations.
        """
        # TODO: Rank by soul-based relevance
        # TODO: Generate friend-style expression for each
        # TODO: Deduplicate against recommendation history
        return []

    async def generate_personal_topic(
        self,
        recommendations: list[Recommendation],
        profile: SoulProfile,
    ) -> PersonalTopic:
        """Create a deeply personalized recommendation topic.

        The topic is unique to this user — not "周末放松包" but something
        that connects to their specific personality and current state.

        Args:
            recommendations: Recommendations to group into a topic.
            profile: User's soul profile.

        Returns:
            A PersonalTopic with a custom title and description.
        """
        # TODO: Use LLM to create a personal topic narrative
        return PersonalTopic()

    async def generate_expression(
        self,
        content: DiscoveredContent,
        profile: SoulProfile,
    ) -> str:
        """Generate a friend-style recommendation expression.

        The expression should feel like a close friend recommending something:
        warm, insightful, personal, with genuine understanding of why this
        specific person would enjoy this specific content.

        Args:
            content: The content being recommended.
            profile: User's soul profile.

        Returns:
            Natural language recommendation expression.
        """
        # TODO: Use LLM with soul context + content info
        return ""
