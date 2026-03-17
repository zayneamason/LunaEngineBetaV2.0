"""
Centralized path resolution for Luna Engine.

Under normal Python, paths resolve relative to this file's location.
Under Nuitka (compiled binary), paths resolve relative to the executable.
The LUNA_BASE_PATH env var overrides both.
"""

import os
import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def project_root() -> Path:
    """Return the Luna Engine project root directory."""
    env = os.environ.get("LUNA_BASE_PATH")
    if env:
        return Path(env).resolve()
    if getattr(sys, "frozen", False) or hasattr(sys, "__compiled__"):
        return Path(sys.executable).parent
    # core/paths.py -> luna -> src -> PROJECT_ROOT
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def _data_root() -> Path:
    """User data directory — separate from binary in Tauri mode.

    If LUNA_DATA_DIR is set (e.g. ~/Library/Application Support/Luna/),
    config and data live there. Otherwise, fall back to project_root().
    """
    env = os.environ.get("LUNA_DATA_DIR")
    if env:
        return Path(env).resolve()
    return project_root()


def config_dir() -> Path:
    return _data_root() / "config"


def data_dir() -> Path:
    return _data_root() / "data"


def system_dir() -> Path:
    """System data — ships with every install. Read-only at runtime."""
    return data_dir() / "system"


def user_dir() -> Path:
    """User data — created at runtime. The owner's soul."""
    return data_dir() / "user"


def local_dir() -> Path:
    """Local/dev data — never ships. Gitignored."""
    return data_dir() / "local"


def tools_dir() -> Path:
    return project_root() / "Tools"


def scripts_dir() -> Path:
    return project_root() / "scripts"


def frontend_dir() -> Path:
    return project_root() / "frontend" / "dist"
