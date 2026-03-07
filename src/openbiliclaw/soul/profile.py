"""User profile data models.

Defines the structured representation of user understanding at each layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class InterestTag:
    """A weighted interest tag with time decay."""

    name: str
    category: str  # Top-level category (e.g., "科技", "游戏")
    weight: float = 1.0  # 0.0 - 1.0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    source: str = ""  # How this tag was inferred


@dataclass
class StylePreference:
    """Content style preferences."""

    preferred_duration: str = ""  # "short" | "medium" | "long"
    preferred_pace: str = ""  # "fast" | "moderate" | "slow"
    quality_sensitivity: float = 0.5  # How much production quality matters
    humor_preference: float = 0.5  # Preference for humorous content
    depth_preference: float = 0.5  # Preference for in-depth analysis


@dataclass
class ContextMode:
    """Contextual usage patterns."""

    weekday_patterns: str = ""  # Description of weekday usage
    weekend_patterns: str = ""  # Description of weekend usage
    time_of_day_patterns: str = ""  # Morning vs night preferences
    session_type: str = ""  # "browsing" | "deep_dive" | "background"


@dataclass
class PreferenceLayer:
    """Preference Layer — structured preferences extracted from behavior."""

    interests: list[InterestTag] = field(default_factory=list)
    style: StylePreference = field(default_factory=StylePreference)
    context: ContextMode = field(default_factory=ContextMode)
    exploration_openness: float = 0.5  # How open to new domains (0-1)
    disliked_topics: list[str] = field(default_factory=list)
    favorite_up_users: list[str] = field(default_factory=list)


@dataclass
class AwarenessNote:
    """A single awareness observation."""

    date: str = ""
    observation: str = ""  # What was observed
    trend: str = ""  # What trend this suggests
    emotion_guess: str = ""  # Guessed emotional state


@dataclass
class InsightHypothesis:
    """An insight or hypothesis about the user."""

    hypothesis: str = ""  # The insight itself
    evidence: list[str] = field(default_factory=list)  # Supporting observations
    confidence: float = 0.5  # 0.0 - 1.0
    validated: bool = False  # Has this been confirmed?
    created_at: str = ""


@dataclass
class SoulProfile:
    """Soul Layer — the deepest understanding of who the user is.

    This is the natural language personality portrait that the agent
    maintains, written as if by a close friend who truly understands
    this person.
    """

    # Soul layer — the personality portrait
    personality_portrait: str = ""  # Long-form natural language description
    core_traits: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    life_stage: str = ""  # Current life stage/situation
    deep_needs: list[str] = field(default_factory=list)  # Unmet psychological needs

    # Embedded preference summary (for LLM context)
    preferences: PreferenceLayer = field(default_factory=PreferenceLayer)

    # Recent awareness notes
    recent_awareness: list[AwarenessNote] = field(default_factory=list)

    # Active insights / hypotheses
    active_insights: list[InsightHypothesis] = field(default_factory=list)

    # Metadata
    created_at: str = ""
    updated_at: str = ""
    version: int = 0

    def to_llm_context(self) -> str:
        """Generate a natural language summary for LLM context.

        Returns a rich description that can be injected into LLM prompts
        to give the agent full understanding of the user.
        """
        parts = []

        if self.personality_portrait:
            parts.append(f"## 用户画像\n{self.personality_portrait}")

        if self.core_traits:
            parts.append(f"## 核心特质\n{', '.join(self.core_traits)}")

        if self.deep_needs:
            parts.append(f"## 深层需求\n{', '.join(self.deep_needs)}")

        if self.active_insights:
            insights_text = "\n".join(
                f"- {i.hypothesis} (置信度: {i.confidence:.0%})"
                for i in self.active_insights
            )
            parts.append(f"## 当前洞察\n{insights_text}")

        if self.recent_awareness:
            notes = "\n".join(
                f"- [{n.date}] {n.observation}" for n in self.recent_awareness[:5]
            )
            parts.append(f"## 近期观察\n{notes}")

        return "\n\n".join(parts) if parts else "（尚未建立用户画像）"
