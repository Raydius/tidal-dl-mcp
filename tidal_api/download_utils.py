"""
Utility functions for tidal-dl-ng subprocess execution.

tidal-dl-ng is an external CLI tool that handles TIDAL downloads.
These utilities manage subprocess calls to 'tdn' commands.
"""

import subprocess
import os
import shutil


def find_tdn_executable() -> str | None:
    """
    Find the tidal-dl-ng (tdn) executable.
    Returns path if found, None otherwise.

    Reference pattern: mcp_server/utils.py:19-46 (find_uv_executable)
    """
    # First try to find in PATH
    tdn_path = shutil.which("tdn")
    if tdn_path:
        return tdn_path

    # Try full name
    tdn_path = shutil.which("tidal-dl-ng")
    if tdn_path:
        return tdn_path

    # Check common installation locations
    common_locations = [
        os.path.expanduser("~/.local/bin/tdn"),
        os.path.expanduser("~/.local/bin/tidal-dl-ng"),
        "/usr/local/bin/tdn",
        "/usr/local/bin/tidal-dl-ng",
        os.path.expanduser("~/AppData/Local/Programs/Python/Python*/Scripts/tdn.exe"),
        os.path.expanduser("~/AppData/Local/Programs/Python/Python*/Scripts/tidal-dl-ng.exe"),
    ]

    for location in common_locations:
        # Handle wildcards in paths
        if "*" in location:
            import glob
            matches = glob.glob(location)
            for match in matches:
                if os.path.isfile(match) and os.access(match, os.X_OK):
                    return match
        elif os.path.isfile(location) and os.access(location, os.X_OK):
            return location

    return None


def check_tdn_installed() -> dict:
    """
    Check if tidal-dl-ng is installed and return status.
    """
    tdn_path = find_tdn_executable()
    if not tdn_path:
        return {
            "installed": False,
            "message": "tidal-dl-ng is not installed. Install with: pip install tidal-dl-ng"
        }

    # Try to get version to verify it works
    try:
        result = subprocess.run(
            [tdn_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        version = result.stdout.strip() if result.returncode == 0 else "unknown"
        return {
            "installed": True,
            "path": tdn_path,
            "version": version
        }
    except Exception as e:
        return {
            "installed": True,
            "path": tdn_path,
            "version": "unknown",
            "warning": str(e)
        }


def build_tidal_url(content_type: str, content_id: str) -> str:
    """
    Build a TIDAL URL from content type and ID.

    Args:
        content_type: 'track', 'album', 'playlist'
        content_id: The TIDAL content ID

    Returns:
        Full TIDAL URL
    """
    base_url = "https://tidal.com/browse"
    return f"{base_url}/{content_type}/{content_id}"


def execute_tdn_download(url: str, timeout: int = 300) -> dict:
    """
    Execute tdn dl command for a given URL.

    Args:
        url: TIDAL URL to download
        timeout: Maximum time to wait in seconds (default 5 minutes)

    Returns:
        dict with status, message, stdout, stderr
    """
    tdn_path = find_tdn_executable()
    if not tdn_path:
        return {
            "status": "error",
            "message": "tidal-dl-ng is not installed. Install with: pip install tidal-dl-ng"
        }

    try:
        result = subprocess.run(
            [tdn_path, "dl", url],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode == 0:
            return {
                "status": "success",
                "message": "Download completed",
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        else:
            # Check for common error patterns
            output = (result.stdout + result.stderr).lower()
            if "not logged in" in output or "authentication" in output or "login" in output:
                return {
                    "status": "error",
                    "message": "tidal-dl-ng is not authenticated. Please run 'tdn login' in terminal first.",
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
            return {
                "status": "error",
                "message": f"Download failed with exit code {result.returncode}",
                "stdout": result.stdout,
                "stderr": result.stderr
            }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": f"Download timed out after {timeout} seconds"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Download failed: {str(e)}"
        }


def execute_tdn_download_favorites(favorite_type: str, timeout: int = 1800) -> dict:
    """
    Execute tdn dl_fav command for a given favorites type.

    Args:
        favorite_type: One of 'tracks', 'albums', 'artists', 'videos'
        timeout: Maximum time to wait in seconds (default 30 minutes)

    Returns:
        dict with status, message, stdout, stderr
    """
    valid_types = ['tracks', 'albums', 'artists', 'videos']
    if favorite_type.lower() not in valid_types:
        return {
            "status": "error",
            "message": f"Invalid favorite type. Must be one of: {', '.join(valid_types)}"
        }

    tdn_path = find_tdn_executable()
    if not tdn_path:
        return {
            "status": "error",
            "message": "tidal-dl-ng is not installed. Install with: pip install tidal-dl-ng"
        }

    try:
        result = subprocess.run(
            [tdn_path, "dl_fav", favorite_type.lower()],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode == 0:
            return {
                "status": "success",
                "message": f"Downloaded favorite {favorite_type}",
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        else:
            output = (result.stdout + result.stderr).lower()
            if "not logged in" in output or "authentication" in output or "login" in output:
                return {
                    "status": "error",
                    "message": "tidal-dl-ng is not authenticated. Please run 'tdn login' in terminal first.",
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
            return {
                "status": "error",
                "message": f"Download failed with exit code {result.returncode}",
                "stdout": result.stdout,
                "stderr": result.stderr
            }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": f"Download timed out after {timeout} seconds"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Download failed: {str(e)}"
        }
