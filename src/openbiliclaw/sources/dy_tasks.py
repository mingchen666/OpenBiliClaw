"""Douyin (douyin.com) bootstrap event-conversion helpers.

This module is the Python-side entry point for Douyin signals captured by
the browser extension. It is **deliberately independent** of
``xhs_tasks.py`` — no imports cross between them, the per-platform
constants are defined here, and the ``DyTaskQueue`` class (added in a
later task) will own its own SQLite table. The only intentional shared
layer is ``event_format.py``: Douyin events emit ``event_type`` values
from the canonical vocabulary so soul-engine can analyze cross-source
events uniformly.

See ``docs/plans/2026-05-06-douyin-bootstrap-import-design.md`` for the
architecture rationale and the open-source prior-art notes that
informed the URL / endpoint catalog used elsewhere in the dy_ tree.
"""

from __future__ import annotations

from typing import Any

# Map each Douyin bootstrap scope to its canonical event_type. Scopes
# are the ones the extension's MAIN-world fetch-tap can observe in a
# logged-in user's tab; see design doc §Scope.
DY_BOOTSTRAP_SCOPE_EVENT_TYPES: dict[str, str] = {
    "dy_post": "view",       # user posted it — weak taste signal but is one
    "dy_collect": "favorite",  # 收藏夹: most deliberate
    "dy_like": "like",       # 喜欢过 tab
    "dy_follow": "follow",   # 关注列表 — interest in a creator's catalog
}

# Per-scope signal strength fed into the preference layer. Numbers
# match the design doc; collect ranks highest because it's the most
# deliberate save-for-later action; post ranks lowest because the user
# being the author doesn't strongly indicate consumption preference.
DY_BOOTSTRAP_SIGNAL_STRENGTH: dict[str, float] = {
    "dy_post": 0.4,
    "dy_collect": 1.0,
    "dy_like": 0.85,
    "dy_follow": 0.6,
}

# Human-readable scope labels used in the natural-language context the
# preference / awareness LLM prompts read. Action verbs come from the
# event taxonomy; this label adds the "在抖音上" framing.
DY_BOOTSTRAP_SCOPE_LABELS: dict[str, str] = {
    "dy_post": "发布",
    "dy_collect": "收藏",
    "dy_like": "点赞",
    "dy_follow": "关注",
}


def dy_bootstrap_videos_to_events(
    videos: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert extension-collected Douyin bootstrap items into events.

    Routes through ``event_format.build_event`` so the resulting dict is
    shape-identical to B站 / 小红书 events. Items missing both ``title``
    and ``url`` are dropped; items with an unknown scope are dropped.

    For ``dy_follow`` scope, ``creator_sec_uid`` (rather than
    ``aweme_id``) is the natural identity key, so we propagate that
    instead under the same metadata field name.
    """
    from openbiliclaw.sources.event_format import SOURCE_DOUYIN, build_event

    events: list[dict[str, Any]] = []
    for item in videos:
        if not isinstance(item, dict):
            continue
        scope = str(item.get("scope", "")).strip()
        event_type = DY_BOOTSTRAP_SCOPE_EVENT_TYPES.get(scope)
        if event_type is None:
            continue

        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        if not title and not url:
            continue

        author = str(item.get("author", "")).strip()
        label = DY_BOOTSTRAP_SCOPE_LABELS[scope]
        # Custom context — scope label is more precise than the generic
        # event_type verb. Mirrors the wording style preference / soul
        # prompts already grew up reading from the XHS path.
        context = f"抖音{label}：{title or url}"
        if author:
            context = f"{context} 作者：{author}"

        # Identity key differs by scope.
        identity_key = "creator_sec_uid" if scope == "dy_follow" else "aweme_id"
        identity_value = str(item.get(identity_key, "")).strip()

        # scope_short strips the "dy_" prefix so import_source reads
        # "dy_bootstrap_collect" rather than "dy_bootstrap_dy_collect".
        scope_short = scope.removeprefix("dy_") if scope.startswith("dy_") else scope

        metadata: dict[str, Any] = {
            identity_key: identity_value,
            "author_sec_uid": str(item.get("author_sec_uid", "")).strip(),
            "cover_url": str(item.get("cover_url", "")).strip(),
            "import_source": f"dy_bootstrap_{scope_short}",
            "signal_strength": DY_BOOTSTRAP_SIGNAL_STRENGTH[scope],
        }

        events.append(
            build_event(
                event_type=event_type,
                source_platform=SOURCE_DOUYIN,
                title=title,
                url=url,
                author=author,
                context=context,
                metadata=metadata,
            )
        )
    return events
