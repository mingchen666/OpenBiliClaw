"""Prompt builders for LLM-backed tasks."""

from __future__ import annotations

import json


def build_socratic_dialogue_prompt(
    *,
    user_message: str,
    core_memory_text: str,
    history: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Build chat messages for Socratic dialogue generation."""
    system_prompt = "\n\n".join(
        [
            "你是 OpenBiliClaw，一个像朋友一样理解用户的 AI 伙伴。",
            "请使用苏格拉底式对话风格：温和、追问动机、确认理解，不要像客服。",
            "以下是当前用户的 core memory，请把它作为理解用户的背景，而不是机械复述：",
            core_memory_text,
        ]
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


def render_preference_summary(preference_summary: dict[str, object]) -> str:
    """Render preference summary into stable text."""
    if not preference_summary:
        return "（暂无偏好摘要）"
    return json.dumps(preference_summary, ensure_ascii=False, indent=2)


def build_preference_analysis_prompt(
    *,
    events: list[dict[str, object]],
    existing_preference: dict[str, object],
) -> list[dict[str, str]]:
    """Build a structured prompt for extracting user preferences from events."""
    system_prompt = """
<task>
你要从一批用户行为事件中提取稳定偏好画像。
</task>

<rules>
1. 只能根据提供的事件推断，不要猜测没有证据的结论。
2. 输出必须是严格 JSON，不要附带解释。
3. 如果证据不足，返回空数组、默认值或较低权重。
4. 兴趣标签控制在 5~15 个以内，weight 在 0~1 之间。
</rules>

<output_schema>
{
  "interests": [{"name": "历史", "category": "知识", "weight": 0.8, "source": "watch history"}],
  "style": {
    "preferred_duration": "long",
    "preferred_pace": "moderate",
    "quality_sensitivity": 0.5,
    "humor_preference": 0.3,
    "depth_preference": 0.9
  },
  "context": {
    "weekday_patterns": "",
    "weekend_patterns": "",
    "time_of_day_patterns": "",
    "session_type": "deep_dive"
  },
  "exploration_openness": 0.6,
  "disliked_topics": ["低质标题党"],
  "favorite_up_users": ["某个UP主"]
}
</output_schema>

<examples>
输入事件里如果多次出现长视频、纪录片、深度讲解，
可以提高 “历史/纪录片/知识” 相关标签和 depth_preference。
</examples>
""".strip()
    user_prompt = "\n\n".join(
        [
            "<existing_preference>",
            json.dumps(existing_preference, ensure_ascii=False, indent=2),
            "</existing_preference>",
            "<event_batch>",
            json.dumps(events, ensure_ascii=False, indent=2),
            "</event_batch>",
        ]
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_soul_profile_prompt(
    *,
    history_summary: dict[str, object],
    preference_summary: dict[str, object],
) -> list[dict[str, str]]:
    """Build a structured prompt for initial soul-profile generation."""
    system_prompt = """
<task>
你要基于用户历史摘要和偏好摘要，生成一份谨慎、温和、像长期观察后的朋友所写的人格画像。
</task>

<rules>
1. 只能根据给定材料推断，不要做医学化、病理化、断言式结论。
2. 输出必须是严格 JSON，不要附带解释。
3. 人格描述至少 200 个中文字符。
4. core_traits 控制在 3 到 5 条，deep_needs 和 values 保持简洁。
</rules>

<output_schema>
{
  "personality_portrait": "至少 200 字的自然语言人格描述",
  "core_traits": ["理性", "好奇", "谨慎"],
  "values": ["真实", "成长"],
  "life_stage": "处于探索与积累阶段",
  "deep_needs": ["被理解", "持续成长"]
}
</output_schema>
""".strip()
    user_prompt = "\n\n".join(
        [
            "<history_summary>",
            json.dumps(history_summary, ensure_ascii=False, indent=2),
            "</history_summary>",
            "<preference_summary>",
            json.dumps(preference_summary, ensure_ascii=False, indent=2),
            "</preference_summary>",
        ]
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_awareness_prompt(
    *,
    events: list[dict[str, object]],
    preference_summary: dict[str, object],
    soul_profile: dict[str, object],
) -> list[dict[str, str]]:
    """Build a structured prompt for recent awareness-note generation."""
    system_prompt = """
<task>
你要基于近期用户行为，生成少量谨慎的近期观察笔记。
</task>

<rules>
1. 输出必须是严格 JSON 数组，不要附带解释。
2. observation 只能描述观察到的行为倾向，不要下人格定论。
3. trend 和 emotion_guess 必须使用保守表述。
4. 如果证据不足，可以返回空数组。
</rules>

<output_schema>
[
  {
    "date": "2026-03-08",
    "observation": "最近连续浏览高信息密度内容。",
    "trend": "更偏向深度解释而非轻量消遣。",
    "emotion_guess": "可能处于主动吸收和整理信息的阶段。"
  }
]
</output_schema>
""".strip()
    user_prompt = "\n\n".join(
        [
            "<recent_events>",
            json.dumps(events, ensure_ascii=False, indent=2),
            "</recent_events>",
            "<preference_summary>",
            json.dumps(preference_summary, ensure_ascii=False, indent=2),
            "</preference_summary>",
            "<soul_profile>",
            json.dumps(soul_profile, ensure_ascii=False, indent=2),
            "</soul_profile>",
        ]
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_insight_prompt(
    *,
    awareness_notes: list[dict[str, object]],
    preference_summary: dict[str, object],
    soul_profile: dict[str, object],
) -> list[dict[str, str]]:
    """Build a structured prompt for insight-hypothesis generation."""
    system_prompt = """
<task>
你要基于近期觉察、偏好摘要和用户画像，生成谨慎的解释性假设。
</task>

<rules>
1. 输出必须是严格 JSON 数组，不要附带解释。
2. hypothesis 是假设，不是结论，措辞必须保守。
3. 每条必须附 1~3 条 evidence。
4. confidence 保持在 0~1，且不要过高。
</rules>

<output_schema>
[
  {
    "hypothesis": "用户可能通过深度内容获得掌控感。",
    "evidence": ["最近连续浏览高信息密度内容。"],
    "confidence": 0.62
  }
]
</output_schema>
""".strip()
    user_prompt = "\n\n".join(
        [
            "<awareness_notes>",
            json.dumps(awareness_notes, ensure_ascii=False, indent=2),
            "</awareness_notes>",
            "<preference_summary>",
            json.dumps(preference_summary, ensure_ascii=False, indent=2),
            "</preference_summary>",
            "<soul_profile>",
            json.dumps(soul_profile, ensure_ascii=False, indent=2),
            "</soul_profile>",
        ]
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
