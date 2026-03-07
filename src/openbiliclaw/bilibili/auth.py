"""Authentication and cookie management for Bilibili."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages Bilibili authentication state.

    Supports:
    - Cookie-based authentication (from browser)
    - No-login mode (limited functionality)
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._cookie_path = data_dir / "bilibili_cookie.json"
        self._cookie: str = ""

    @property
    def is_authenticated(self) -> bool:
        """Whether we have a valid authentication cookie."""
        return bool(self._cookie)

    @property
    def cookie(self) -> str:
        """Current cookie string."""
        return self._cookie

    def set_cookie(self, cookie: str) -> None:
        """Set and persist the authentication cookie.

        Args:
            cookie: Cookie string from browser.
        """
        self._cookie = cookie
        self._save_cookie()
        logger.info("Cookie set and saved.")

    def load_cookie(self) -> str:
        """Load persisted cookie from disk.

        Returns:
            Cookie string, or empty string if not found.
        """
        if self._cookie_path.exists():
            with open(self._cookie_path) as f:
                data = json.load(f)
                self._cookie = data.get("cookie", "")
                logger.info("Cookie loaded from disk.")
        return self._cookie

    def _save_cookie(self) -> None:
        """Persist cookie to disk."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        with open(self._cookie_path, "w") as f:
            json.dump({"cookie": self._cookie}, f)

    def clear_cookie(self) -> None:
        """Clear stored cookie."""
        self._cookie = ""
        if self._cookie_path.exists():
            self._cookie_path.unlink()
        logger.info("Cookie cleared.")
