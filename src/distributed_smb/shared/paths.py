"""Shared filesystem paths for package resources."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PACKAGE_ROOT / "assets"
MARIO1_ASSETS_DIR = ASSETS_DIR / "mario1"
