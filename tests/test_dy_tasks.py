"""Tests for the Douyin bootstrap event-conversion helper.

Task 1 of the Douyin bootstrap import plan
(``docs/plans/2026-05-06-douyin-bootstrap-import.md``).
"""

from __future__ import annotations

from openbiliclaw.sources.dy_tasks import dy_bootstrap_videos_to_events
from openbiliclaw.sources.event_format import SOURCE_DOUYIN


def test_dy_bootstrap_videos_to_events_maps_scopes_to_event_types() -> None:
    """Each Douyin scope maps to its canonical event_type."""
    events = dy_bootstrap_videos_to_events(
        [
            {
                "scope": "dy_post",
                "title": "我发布的",
                "url": "https://www.douyin.com/video/aaa",
                "aweme_id": "aaa",
            },
            {
                "scope": "dy_collect",
                "title": "我收藏的",
                "url": "https://www.douyin.com/video/bbb",
                "aweme_id": "bbb",
            },
            {
                "scope": "dy_like",
                "title": "我点赞的",
                "url": "https://www.douyin.com/video/ccc",
                "aweme_id": "ccc",
            },
            {
                "scope": "dy_follow",
                "title": "关注的创作者",
                "url": "https://www.douyin.com/user/ddd",
                "creator_sec_uid": "ddd",
            },
        ]
    )

    assert [e["event_type"] for e in events] == ["view", "favorite", "like", "follow"]
    for event in events:
        assert event["metadata"]["source_platform"] == SOURCE_DOUYIN


def test_dy_bootstrap_videos_to_events_signal_strength_per_scope() -> None:
    """Signal strengths follow the design doc: collect=1.0, like=0.85, follow=0.6, post=0.4."""
    events = dy_bootstrap_videos_to_events(
        [
            {
                "scope": "dy_post",
                "title": "p",
                "url": "https://www.douyin.com/video/p",
                "aweme_id": "p",
            },
            {
                "scope": "dy_collect",
                "title": "c",
                "url": "https://www.douyin.com/video/c",
                "aweme_id": "c",
            },
            {
                "scope": "dy_like",
                "title": "l",
                "url": "https://www.douyin.com/video/l",
                "aweme_id": "l",
            },
            {
                "scope": "dy_follow",
                "title": "f",
                "url": "https://www.douyin.com/user/f",
                "creator_sec_uid": "f",
            },
        ]
    )
    strengths = [e["metadata"]["signal_strength"] for e in events]
    assert strengths == [0.4, 1.0, 0.85, 0.6]


def test_dy_bootstrap_videos_to_events_skips_blank_and_unknown() -> None:
    """Items missing both title and url are dropped; unknown scopes are dropped."""
    events = dy_bootstrap_videos_to_events(
        [
            {"scope": "dy_collect", "title": "", "url": "", "aweme_id": "x"},  # blank — drop
            {"scope": "dy_unknown_scope", "title": "t", "url": "u"},  # unknown scope — drop
            "not-a-dict",  # invalid type — drop
            {
                "scope": "dy_collect",
                "title": "valid",
                "url": "https://www.douyin.com/video/v",
                "aweme_id": "v",
            },
        ]
    )
    assert len(events) == 1
    assert events[0]["title"] == "valid"


def test_dy_bootstrap_videos_to_events_import_source_tag() -> None:
    """import_source metadata is namespaced per scope so analytics can split."""
    events = dy_bootstrap_videos_to_events(
        [
            {
                "scope": "dy_collect",
                "title": "c",
                "url": "https://www.douyin.com/video/c",
                "aweme_id": "c",
            },
        ]
    )
    assert events[0]["metadata"]["import_source"] == "dy_bootstrap_collect"


def test_dy_bootstrap_videos_to_events_passes_through_aweme_metadata() -> None:
    """aweme_id, author, cover_url propagate so downstream curator can dedupe / render."""
    events = dy_bootstrap_videos_to_events(
        [
            {
                "scope": "dy_collect",
                "title": "demo title",
                "url": "https://www.douyin.com/video/zzz",
                "aweme_id": "zzz",
                "author": "作者昵称",
                "author_sec_uid": "sec_uid_xyz",
                "cover_url": "https://example.com/cover.jpg",
            },
        ]
    )
    metadata = events[0]["metadata"]
    assert metadata["aweme_id"] == "zzz"
    assert metadata["cover_url"] == "https://example.com/cover.jpg"
    # build_event places author inside metadata (see event_format.py:200).
    assert metadata["author"] == "作者昵称"


def test_dy_bootstrap_videos_to_events_follow_uses_creator_sec_uid() -> None:
    """For dy_follow scope the metadata key is creator_sec_uid, not aweme_id."""
    events = dy_bootstrap_videos_to_events(
        [
            {
                "scope": "dy_follow",
                "title": "@老白",
                "url": "https://www.douyin.com/user/abc",
                "creator_sec_uid": "abc",
            },
        ]
    )
    metadata = events[0]["metadata"]
    assert metadata["creator_sec_uid"] == "abc"
    assert events[0]["event_type"] == "follow"
