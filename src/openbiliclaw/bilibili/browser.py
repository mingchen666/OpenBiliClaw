"""Bilibili Browser automation via agent-browser.

Provides browser-based interaction with Bilibili for operations
that the API doesn't support or where visual context is needed.
Uses Vercel's agent-browser CLI: https://github.com/vercel-labs/agent-browser
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from typing import Any, cast

logger = logging.getLogger(__name__)


class BilibiliBrowser:
    """Browser automation interface using agent-browser.

    This is the secondary access layer, used when:
    - The API doesn't cover a needed operation
    - Visual context (DOM, screenshots) is needed
    - Complex page interactions are required

    Requires agent-browser to be installed:
        npm install -g @anthropic/agent-browser
    """

    def __init__(
        self,
        executable: str = "",
        headed: bool = False,
        cookie: str = "",
    ) -> None:
        self._executable = executable or self._find_executable()
        self._headed = headed
        self._cookie = cookie

    @staticmethod
    def _find_executable() -> str:
        """Find the agent-browser executable."""
        path = shutil.which("agent-browser")
        if path:
            return path
        path = shutil.which("ab")
        if path:
            return path
        return "agent-browser"

    @property
    def is_available(self) -> bool:
        """Check if agent-browser is available."""
        return shutil.which(self._executable) is not None

    async def _run_command(self, *args: str) -> dict[str, Any]:
        """Execute an agent-browser command and return the result.

        Args:
            *args: Command arguments.

        Returns:
            Parsed JSON output from agent-browser.
        """
        cmd = [self._executable, *args]
        if self._headed:
            cmd.append("--headed")

        logger.debug("Running agent-browser: %s", " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error("agent-browser error: %s", error_msg)
            return {"error": error_msg}

        try:
            return cast("dict[str, Any]", json.loads(stdout.decode()))
        except json.JSONDecodeError:
            return {"output": stdout.decode()}

    async def navigate(self, url: str) -> dict[str, Any]:
        """Navigate to a URL.

        Args:
            url: Target URL.

        Returns:
            Page info.
        """
        return await self._run_command("open", url)

    async def get_page_content(self, url: str) -> str:
        """Get the text content of a page.

        Args:
            url: Target URL.

        Returns:
            Page text content.
        """
        result = await self._run_command("open", url, "--text")
        return str(result.get("output", ""))

    async def screenshot(self, url: str, output_path: str) -> str:
        """Take a screenshot of a page.

        Args:
            url: Target URL.
            output_path: Where to save the screenshot.

        Returns:
            Path to the saved screenshot.
        """
        result = await self._run_command("screenshot", url, "-o", output_path)
        return str(result.get("output", output_path))

    async def close(self) -> None:
        """Close any active browser sessions."""
        try:
            await self._run_command("close")
        except Exception:
            logger.debug("No active session to close.")
