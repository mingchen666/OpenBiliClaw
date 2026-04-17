"""Tests for the DiscoveredContent multi-source compatibility layer (Phase 0)."""

from __future__ import annotations

from openbiliclaw.discovery.engine import DiscoveredContent


class TestDiscoveredContentMultisourceFields:
    """Verify __post_init__ auto-populates multi-source fields from legacy Bilibili fields."""

    def test_bvid_populates_content_id(self) -> None:
        item = DiscoveredContent(bvid="BV1abc123")
        assert item.content_id == "BV1abc123"

    def test_bvid_populates_source_platform(self) -> None:
        item = DiscoveredContent(bvid="BV1abc123")
        assert item.source_platform == "bilibili"

    def test_bvid_populates_content_url(self) -> None:
        item = DiscoveredContent(bvid="BV1abc123")
        assert item.content_url == "https://www.bilibili.com/video/BV1abc123"

    def test_up_name_populates_author_name(self) -> None:
        item = DiscoveredContent(bvid="BV1x", up_name="老番茄")
        assert item.author_name == "老番茄"

    def test_explicit_content_id_not_overwritten(self) -> None:
        item = DiscoveredContent(bvid="BV1x", content_id="custom-id")
        assert item.content_id == "custom-id"

    def test_explicit_source_platform_not_overwritten(self) -> None:
        item = DiscoveredContent(bvid="BV1x", source_platform="xiaohongshu")
        assert item.source_platform == "xiaohongshu"

    def test_explicit_content_url_not_overwritten(self) -> None:
        item = DiscoveredContent(bvid="BV1x", content_url="https://example.com/note/123")
        assert item.content_url == "https://example.com/note/123"

    def test_explicit_author_name_not_overwritten(self) -> None:
        item = DiscoveredContent(up_name="UP主", author_name="Custom Author")
        assert item.author_name == "Custom Author"

    def test_no_bvid_leaves_fields_empty(self) -> None:
        item = DiscoveredContent()
        assert item.content_id == ""
        assert item.source_platform == ""
        assert item.content_url == ""
        assert item.author_name == ""

    def test_non_bilibili_content_from_scratch(self) -> None:
        """Non-Bilibili content created directly with new fields."""
        item = DiscoveredContent(
            content_id="note_abc123",
            content_url="https://www.xiaohongshu.com/explore/abc123",
            source_platform="xiaohongshu",
            author_name="小红书用户",
            title="机械键盘开箱",
        )
        assert item.bvid == ""
        assert item.up_name == ""
        assert item.content_id == "note_abc123"
        assert item.source_platform == "xiaohongshu"
        assert item.content_url == "https://www.xiaohongshu.com/explore/abc123"
        assert item.author_name == "小红书用户"
        assert item.title == "机械键盘开箱"


class TestPlatformPromptLabels:
    """Verify prompt label helpers produce correct platform-specific text."""

    def test_bilibili_content_label(self) -> None:
        from openbiliclaw.llm.prompts import _platform_content_label

        assert _platform_content_label("bilibili") == "B 站内容"

    def test_non_bilibili_content_label(self) -> None:
        from openbiliclaw.llm.prompts import _platform_content_label

        assert _platform_content_label("xiaohongshu") == "内容"
        assert _platform_content_label("web") == "内容"

    def test_bilibili_friend_label(self) -> None:
        from openbiliclaw.llm.prompts import _platform_friend_label

        assert _platform_friend_label("bilibili") == "老B友"

    def test_non_bilibili_friend_label(self) -> None:
        from openbiliclaw.llm.prompts import _platform_friend_label

        assert _platform_friend_label("xiaohongshu") == "朋友"
        assert _platform_friend_label("web") == "朋友"
