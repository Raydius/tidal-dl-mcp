"""
Version information for TIDAL MCP server.

Provides version from pyproject.toml and git commit hash.
"""
import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone


# Version from pyproject.toml (updated manually when releasing)
__version__ = "0.1.0"

# Server start time (set when module loads)
_start_time = datetime.now(timezone.utc).isoformat()


def get_git_commit() -> str:
    """
    Get the current git commit hash (short form).

    Returns:
        Short commit hash (7 chars) or 'unknown' if not in a git repo.
    """
    try:
        # Find the project root (where .git is)
        project_root = Path(__file__).parent.parent

        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return "unknown"


def get_git_dirty() -> bool:
    """
    Check if there are uncommitted changes.

    Returns:
        True if working directory has uncommitted changes.
    """
    try:
        project_root = Path(__file__).parent.parent

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return bool(result.stdout.strip())
    except Exception:
        pass

    return False


def get_version_info() -> dict:
    """
    Get complete version information.

    Returns:
        Dictionary with version, commit, dirty status, and start time.
    """
    commit = get_git_commit()
    dirty = get_git_dirty()

    return {
        "version": __version__,
        "commit": commit,
        "dirty": dirty,
        "started_at": _start_time,
        "version_string": f"v{__version__} ({commit}{'*' if dirty else ''})"
    }


def get_version_string() -> str:
    """
    Get a formatted version string for display.

    Returns:
        Formatted string like "v0.1.0 (abc1234)" or "v0.1.0 (abc1234*)" if dirty.
    """
    info = get_version_info()
    return info["version_string"]
