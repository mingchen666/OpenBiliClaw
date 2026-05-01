"""Regression tests for the unified cross-source event format.

The v0.3.22 unification consolidated B站 / 小红书 / future-source
event producers behind ``build_event()`` so the soul-pipeline LLM
analyzers see one consistent shape — including a natural-language
``context`` field they can read directly. These tests pin the
contract so future regressions don't silently re-fragment it.
"""

from __future__ import annotations

from openbiliclaw.cli import _history_item_to_event
from openbiliclaw.sources.event_format import (
    SOURCE_BILIBILI,
    SOURCE_XIAOHONGSHU,
    build_event,
    format_event_context,
)
from openbiliclaw.sources.xhs_tasks import xhs_bootstrap_notes_to_events

# ---------------------------------------------------------------------------
# format_event_context: deterministic Chinese sentence builder


def test_format_context_bilibili_view_with_author() -> None:
    text = format_event_context(
        event_type="view",
        source_platform=SOURCE_BILIBILI,
        title="讲透历史叙事",
        author="历史实验室",
    )
    assert text == "在B 站看了《讲透历史叙事》,作者:历史实验室"


def test_format_context_xiaohongshu_like_with_author() -> None:
    text = format_event_context(
        event_type="like",
        source_platform=SOURCE_XIAOHONGSHU,
        title="手冲咖啡入门",
        author="豆子老师",
    )
    assert text == "在小红书点赞了《手冲咖啡入门》,作者:豆子老师"


def test_format_context_unknown_event_type_falls_back() -> None:
    """Unknown event_type strings shouldn't crash — they fall through
    to a generic verb so the rendered sentence is still readable."""
    text = format_event_context(
        event_type="custom_action",
        source_platform=SOURCE_BILIBILI,
        title="一个新行为",
    )
    assert "B 站" in text
    assert "《一个新行为》" in text
    assert "记录了" in text  # generic fallback verb


def test_format_context_missing_title_uses_placeholder() -> None:
    text = format_event_context(
        event_type="favorite",
        source_platform=SOURCE_BILIBILI,
        title="",
    )
    assert text == "在B 站收藏了一条内容"


# ---------------------------------------------------------------------------
# build_event: shape contract (the actual unification point)


def test_build_event_emits_unified_shape() -> None:
    event = build_event(
        event_type="favorite",
        source_platform=SOURCE_BILIBILI,
        title="某个 UP 主的视频",
        url="https://www.bilibili.com/video/BVxxxx",
        author="某 UP 主",
        metadata={"folder": "技术", "bvid": "BVxxxx"},
    )
    # Required keys
    assert event["event_type"] == "favorite"
    assert event["title"] == "某个 UP 主的视频"
    assert event["url"] == "https://www.bilibili.com/video/BVxxxx"
    assert event["context"]  # non-empty natural-language description
    # Metadata invariants
    assert event["metadata"]["source_platform"] == SOURCE_BILIBILI
    assert event["metadata"]["author"] == "某 UP 主"
    # Source-specific extras preserved
    assert event["metadata"]["folder"] == "技术"
    assert event["metadata"]["bvid"] == "BVxxxx"


def test_build_event_explicit_context_wins_over_auto_generated() -> None:
    event = build_event(
        event_type="favorite",
        source_platform=SOURCE_XIAOHONGSHU,
        title="手冲咖啡入门",
        author="豆子老师",
        context="自定义描述",
    )
    assert event["context"] == "自定义描述"


def test_build_event_url_omitted_when_empty() -> None:
    """URL is optional — events without one (e.g. follow events) shouldn't
    carry a key with empty-string value."""
    event = build_event(
        event_type="follow",
        source_platform=SOURCE_BILIBILI,
        title="某 UP",
        author="某 UP",
    )
    assert "url" not in event


def test_build_event_metadata_source_platform_explicit_wins() -> None:
    """If a producer passes source_platform inside metadata, that value
    wins over the parameter — supports edge cases where metadata is
    pre-filled by an upstream layer."""
    event = build_event(
        event_type="view",
        source_platform=SOURCE_BILIBILI,
        title="...",
        metadata={"source_platform": "web"},
    )
    assert event["metadata"]["source_platform"] == "web"


# ---------------------------------------------------------------------------
# Producers all converge on the unified shape


def _has_unified_shape(event: dict) -> bool:
    """Every cross-source event must satisfy these invariants."""
    if not isinstance(event, dict):
        return False
    for key in ("event_type", "title", "context", "metadata"):
        if key not in event:
            return False
    if not isinstance(event["metadata"], dict):
        return False
    if not event["metadata"].get("source_platform"):
        return False
    return isinstance(event["context"], str) and bool(event["context"])


def test_bilibili_history_event_has_unified_shape() -> None:
    """v0.3.22+: B站 history events must carry context + source_platform
    just like 小红书 events did from day one."""
    item = {
        "history": {"bvid": "BV1A", "view_at": 1710000000},
        "title": "讲透历史叙事",
        "author_name": "历史实验室",
    }
    event = _history_item_to_event(item)
    assert _has_unified_shape(event)
    assert event["metadata"]["source_platform"] == SOURCE_BILIBILI
    assert event["event_type"] == "view"
    assert "历史实验室" in event["context"]
    assert "讲透历史叙事" in event["context"]
    assert event["url"].endswith("/BV1A")
    # Author canonical-name field is consistent with xhs events
    assert event["metadata"]["author"] == "历史实验室"


def test_xiaohongshu_bootstrap_events_have_unified_shape() -> None:
    notes = [
        {
            "scope": "saved",
            "title": "手冲咖啡入门",
            "url": "https://www.xiaohongshu.com/explore/abc",
            "author": "豆子老师",
        },
        {
            "scope": "liked",
            "title": "意式拉花教程",
            "url": "https://www.xiaohongshu.com/explore/def",
            "author": "拿铁猫",
        },
    ]
    events = xhs_bootstrap_notes_to_events(notes)
    assert len(events) == 2
    for event in events:
        assert _has_unified_shape(event)
        assert event["metadata"]["source_platform"] == SOURCE_XIAOHONGSHU
        assert "小红书" in event["context"]
        assert event["metadata"]["author"]
    # The two scopes map to distinct event_types
    assert {e["event_type"] for e in events} == {"favorite", "like"}
    # Scope-specific natural-language label is preserved
    assert "收藏" in events[0]["context"]
    assert "点赞" in events[1]["context"]


def test_bilibili_and_xiaohongshu_events_share_consumer_contract() -> None:
    """A consumer reading {event_type, title, context, metadata.source_platform,
    metadata.author} should not need to special-case which source produced the
    event. This is the core unification invariant."""
    bili = _history_item_to_event(
        {
            "history": {"bvid": "BV1", "view_at": 1},
            "title": "B站标题",
            "author_name": "B站作者",
        }
    )
    xhs = xhs_bootstrap_notes_to_events(
        [{"scope": "saved", "title": "小红书标题", "author": "小红书作者"}]
    )[0]

    consumer_view_keys = {"event_type", "title", "context"}
    consumer_metadata_keys = {"source_platform", "author"}

    for event in (bili, xhs):
        assert consumer_view_keys.issubset(event.keys())
        assert consumer_metadata_keys.issubset(event["metadata"].keys())
