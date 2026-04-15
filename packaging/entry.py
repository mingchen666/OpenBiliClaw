"""Desktop application entry point for OpenBiliClaw.

This module bootstraps the local backend server as a standalone
desktop application packaged via PyInstaller.
"""

from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path


def _resolve_app_root() -> Path:
    """Determine the application root directory.

    When frozen by PyInstaller the executable lives inside the bundle
    directory.  We use the *directory containing the executable* as
    the project root so that ``config.toml``, ``data/``, and ``logs/``
    are siblings of the application bundle.
    """
    if getattr(sys, "frozen", False):
        # Running from PyInstaller bundle
        return Path(sys.executable).resolve().parent
    # Development fallback
    return Path(__file__).resolve().parent.parent


def main() -> None:
    app_root = _resolve_app_root()
    os.environ["OPENBILICLAW_PROJECT_ROOT"] = str(app_root)

    # Ensure data & log directories exist
    (app_root / "data").mkdir(exist_ok=True)
    (app_root / "logs").mkdir(exist_ok=True)

    # Copy default config if needed
    config_path = app_root / "config.toml"
    example_path = app_root / "config.example.toml"
    if not config_path.exists() and example_path.exists():
        import shutil
        shutil.copyfile(example_path, config_path)
        print(f"[OpenBiliClaw] 已生成默认配置: {config_path}")

    print(f"[OpenBiliClaw] 数据目录: {app_root}")
    print("[OpenBiliClaw] 正在启动后端服务 http://127.0.0.1:8420 ...")

    # Open browser to a simple status page (optional)
    try:
        webbrowser.open("http://127.0.0.1:8420/api/health")
    except Exception:
        pass

    # Start the server
    import uvicorn
    from openbiliclaw.api.app import create_app

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8420, log_level="info")


if __name__ == "__main__":
    main()
