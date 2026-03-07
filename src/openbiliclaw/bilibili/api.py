"""Bilibili API Client.

Primary interface for interacting with Bilibili, prioritizing the official
and reverse-engineered API for speed and efficiency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)


def _json_object(value: Any) -> dict[str, Any]:
    """Coerce a JSON value into an object for strict typing."""
    return cast("dict[str, Any]", value)


def _json_list(value: Any) -> list[dict[str, Any]]:
    """Coerce a JSON value into a list of objects for strict typing."""
    return cast("list[dict[str, Any]]", value)


@dataclass
class VideoInfo:
    """Basic video information from Bilibili."""

    bvid: str = ""
    aid: int = 0
    title: str = ""
    description: str = ""
    duration: int = 0  # seconds
    cover_url: str = ""
    up_name: str = ""
    up_mid: int = 0
    view_count: int = 0
    like_count: int = 0
    coin_count: int = 0
    favorite_count: int = 0
    share_count: int = 0
    danmaku_count: int = 0
    tags: list[str] | None = None
    pub_date: str = ""


class BilibiliAPIClient:
    """Client for Bilibili's web API.

    This is the primary data access layer (API-first approach).
    For operations not supported by the API, use BilibiliBrowser.
    """

    _BASE_URL = "https://api.bilibili.com"

    def __init__(self, cookie: str = "") -> None:
        self._cookie = cookie
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.bilibili.com",
            },
            timeout=30.0,
        )
        if cookie:
            self._client.headers["Cookie"] = cookie

    @property
    def is_authenticated(self) -> bool:
        """Whether we have a valid authentication cookie."""
        return bool(self._cookie)

    async def get_video_info(self, bvid: str) -> VideoInfo:
        """Get video information by BV ID.

        Args:
            bvid: Bilibili video BV ID.

        Returns:
            VideoInfo dataclass.
        """
        resp = await self._client.get(
            f"{self._BASE_URL}/x/web-interface/view",
            params={"bvid": bvid},
        )
        resp.raise_for_status()
        payload = _json_object(resp.json())
        data = _json_object(payload["data"])
        stat = _json_object(data.get("stat", {}))
        owner = _json_object(data.get("owner", {}))

        return VideoInfo(
            bvid=data.get("bvid", bvid),
            aid=data.get("aid", 0),
            title=data.get("title", ""),
            description=data.get("desc", ""),
            duration=data.get("duration", 0),
            cover_url=data.get("pic", ""),
            up_name=owner.get("name", ""),
            up_mid=owner.get("mid", 0),
            view_count=stat.get("view", 0),
            like_count=stat.get("like", 0),
            coin_count=stat.get("coin", 0),
            favorite_count=stat.get("favorite", 0),
            share_count=stat.get("share", 0),
            danmaku_count=stat.get("danmaku", 0),
            pub_date=data.get("pubdate", ""),
        )

    async def search(
        self, keyword: str, page: int = 1, page_size: int = 20
    ) -> list[dict[str, Any]]:
        """Search for videos by keyword.

        Args:
            keyword: Search query.
            page: Page number.
            page_size: Results per page.

        Returns:
            List of search result dicts.
        """
        resp = await self._client.get(
            f"{self._BASE_URL}/x/web-interface/search/type",
            params={
                "keyword": keyword,
                "search_type": "video",
                "page": page,
                "page_size": page_size,
            },
        )
        resp.raise_for_status()
        payload = _json_object(resp.json())
        data = _json_object(payload.get("data", {}))
        return _json_list(data.get("result", []))

    async def get_user_history(self, max_items: int = 100) -> list[dict[str, Any]]:
        """Get the authenticated user's watch history.

        Requires valid authentication cookie.

        Args:
            max_items: Maximum number of history items to fetch.

        Returns:
            List of history item dicts.
        """
        if not self.is_authenticated:
            logger.warning("Cannot fetch history without authentication.")
            return []

        # TODO: Implement pagination for history API
        resp = await self._client.get(
            f"{self._BASE_URL}/x/web-interface/history/cursor",
            params={"max": max_items, "type": "archive"},
        )
        resp.raise_for_status()
        payload = _json_object(resp.json())
        data = _json_object(payload.get("data", {}))
        return _json_list(data.get("list", []))

    async def get_favorites(self, media_id: int) -> list[dict[str, Any]]:
        """Get content from a favorites folder.

        Args:
            media_id: Favorites folder media ID.

        Returns:
            List of favorite item dicts.
        """
        resp = await self._client.get(
            f"{self._BASE_URL}/x/v3/fav/resource/list",
            params={"media_id": media_id, "pn": 1, "ps": 20},
        )
        resp.raise_for_status()
        payload = _json_object(resp.json())
        data = _json_object(payload.get("data", {}))
        return _json_list(data.get("medias", []))

    async def get_related_videos(self, bvid: str) -> list[dict[str, Any]]:
        """Get related/recommended videos for a given video.

        Args:
            bvid: Source video BV ID.

        Returns:
            List of related video dicts.
        """
        resp = await self._client.get(
            f"{self._BASE_URL}/x/web-interface/archive/related",
            params={"bvid": bvid},
        )
        resp.raise_for_status()
        payload = _json_object(resp.json())
        return _json_list(payload.get("data", []))

    async def get_ranking(self, rid: int = 0) -> list[dict[str, Any]]:
        """Get ranking/trending videos.

        Args:
            rid: Region ID (0 for all).

        Returns:
            List of ranking item dicts.
        """
        resp = await self._client.get(
            f"{self._BASE_URL}/x/web-interface/ranking/v2",
            params={"rid": rid, "type": "all"},
        )
        resp.raise_for_status()
        payload = _json_object(resp.json())
        data = _json_object(payload.get("data", {}))
        return _json_list(data.get("list", []))

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
