"""Desktop application entry point for OpenBiliClaw.

This module bootstraps the local backend server as a standalone
desktop application packaged via PyInstaller.

The layout differs between onedir and macOS ``.app`` bundle outputs:

* **onedir** (``dist/OpenBiliClaw/OpenBiliClaw``) — the executable lives
  next to user-writable ``data/``, ``logs/``, and ``config.toml``.
* **macOS .app** (``OpenBiliClaw.app/Contents/MacOS/OpenBiliClaw``) —
  the bundle itself is treated as read-only.  User data must live
  outside the bundle, by macOS convention in
  ``~/Library/Application Support/OpenBiliClaw``.  The bundled default
  template ``config.example.toml`` is placed under ``Contents/Resources``
  by PyInstaller and seeded into the user's data dir on first launch.
"""

from __future__ import annotations

import os
import shutil
import sys
import webbrowser
from pathlib import Path


def _is_macos_app_bundle(exe_dir: Path) -> bool:
    """True when the executable sits inside ``.app/Contents/MacOS``."""
    return exe_dir.name == "MacOS" and exe_dir.parent.name == "Contents"


def _macos_app_bundle_root(exe_dir: Path) -> Path:
    """Return the ``.app`` directory when running from a macOS bundle."""
    return exe_dir.parent.parent


def _user_data_root() -> Path:
    """Return the writable user-data root on macOS."""
    return Path.home() / "Library" / "Application Support" / "OpenBiliClaw"


def _resolve_runtime_paths() -> tuple[Path, Path]:
    """Return ``(project_root, bundled_resources)`` based on launch mode.

    ``project_root`` is where ``config.toml`` / ``data/`` / ``logs/`` live.
    ``bundled_resources`` is the read-only directory holding the default
    ``config.example.toml`` shipped with the package.
    """
    if not getattr(sys, "frozen", False):
        # Development fallback
        repo_root = Path(__file__).resolve().parent.parent
        return repo_root, repo_root

    exe_dir = Path(sys.executable).resolve().parent
    if _is_macos_app_bundle(exe_dir):
        project_root = _user_data_root()
        bundled_resources = exe_dir.parent / "Resources"
        return project_root, bundled_resources

    # onedir layout: everything sits alongside the executable
    return exe_dir, exe_dir


def _seed_default_config(project_root: Path, bundled_resources: Path) -> None:
    """Copy the bundled ``config.example.toml`` into ``project_root`` on first run."""
    config_path = project_root / "config.toml"
    if config_path.exists():
        return
    example_candidates = [
        project_root / "config.example.toml",
        bundled_resources / "config.example.toml",
    ]
    for example in example_candidates:
        if example.exists():
            shutil.copyfile(example, config_path)
            print(f"[OpenBiliClaw] 已生成默认配置: {config_path}")
            return


def main() -> None:
    project_root, bundled_resources = _resolve_runtime_paths()
    project_root.mkdir(parents=True, exist_ok=True)
    os.environ["OPENBILICLAW_PROJECT_ROOT"] = str(project_root)

    # Ensure data & log directories exist
    (project_root / "data").mkdir(exist_ok=True)
    (project_root / "logs").mkdir(exist_ok=True)

    # Seed a default config.toml if the user hasn't created one yet
    _seed_default_config(project_root, bundled_resources)

    print(f"[OpenBiliClaw] 数据目录: {project_root}")
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
