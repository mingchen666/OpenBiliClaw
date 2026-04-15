#!/usr/bin/env python3
"""Build script for OpenBiliClaw desktop application.

Usage:
    python packaging/build.py          # Build for current platform
    python packaging/build.py --clean  # Clean previous builds first
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
SPEC_FILE = PROJECT_ROOT / "packaging" / "openbiliclaw.spec"


def ensure_pyinstaller() -> None:
    """Ensure PyInstaller is installed."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[build] Installing PyInstaller ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def clean() -> None:
    """Remove previous build artifacts."""
    for d in [DIST_DIR, PROJECT_ROOT / "build"]:
        if d.exists():
            print(f"[build] Removing {d}")
            shutil.rmtree(d)


def build() -> None:
    """Run PyInstaller."""
    ensure_pyinstaller()
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(SPEC_FILE),
        "--distpath", str(DIST_DIR),
        "--workpath", str(PROJECT_ROOT / "build"),
        "--noconfirm",
    ]
    print(f"[build] Running: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(PROJECT_ROOT))

    output = DIST_DIR / "OpenBiliClaw"
    if output.exists():
        # Copy config.example.toml into the output directory
        example = PROJECT_ROOT / "config.example.toml"
        if example.exists():
            shutil.copyfile(example, output / "config.example.toml")

        print()
        print("=" * 60)
        print(f"  Build complete!  {platform.system()} / {platform.machine()}")
        print(f"  Output: {output}")
        print()
        print("  To run:")
        if platform.system() == "Windows":
            print(f"    {output / 'OpenBiliClaw.exe'}")
        elif platform.system() == "Darwin":
            app_bundle = DIST_DIR / "OpenBiliClaw.app"
            if app_bundle.exists():
                print(f"    open {app_bundle}")
            else:
                print(f"    {output / 'OpenBiliClaw'}")
        else:
            print(f"    {output / 'OpenBiliClaw'}")
        print("=" * 60)
    else:
        print("[build] WARNING: Expected output directory not found!")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build OpenBiliClaw desktop app")
    parser.add_argument("--clean", action="store_true", help="Clean previous builds first")
    args = parser.parse_args()

    if args.clean:
        clean()
    build()


if __name__ == "__main__":
    main()
