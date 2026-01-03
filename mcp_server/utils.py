import subprocess
import os
import pathlib
import shutil
import socket
import time
import sys

# Define a configurable port with a default that's less likely to conflict
DEFAULT_PORT = 5050
FLASK_PORT = int(os.environ.get("TIDAL_MCP_PORT", DEFAULT_PORT))

# Define the base URL for your Flask app using the configurable port
FLASK_APP_URL = f"http://127.0.0.1:{FLASK_PORT}"

# Define the path to the Flask app dynamically
CURRENT_DIR = pathlib.Path(__file__).parent.absolute()
FLASK_APP_PATH = os.path.join(CURRENT_DIR, "..", "tidal_api", "app.py")
FLASK_APP_PATH = os.path.normpath(FLASK_APP_PATH)  # Normalize the path

# Find the path to uv executable
def find_uv_executable():
    """Find the uv executable in the path or common locations"""
    # First try to find in PATH
    uv_path = shutil.which("uv")
    if uv_path:
        return uv_path

    # Check common installation locations
    common_locations = [
        os.path.expanduser("~/.local/bin/uv"),  # Linux/macOS local install
        os.path.expanduser("~/AppData/Local/Programs/Python/Python*/Scripts/uv.exe"),  # Windows
        "/usr/local/bin/uv",  # macOS Homebrew
        "/opt/homebrew/bin/uv",  # macOS Apple Silicon Homebrew
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

    # If we can't find it, just return "uv" and let the system try to resolve it
    return "uv"

# Global variable to hold the Flask app process
flask_process = None

# Timeout for Flask startup (seconds)
FLASK_STARTUP_TIMEOUT = 30


def _wait_for_port(port, timeout=FLASK_STARTUP_TIMEOUT):
    """Wait for a port to become available (Flask listening)"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result == 0:
                return True
        except socket.error:
            pass
        time.sleep(0.5)
    return False


def _check_process_alive(process):
    """Check if subprocess is still running"""
    return process.poll() is None


def start_flask_app():
    """Start the Flask app as a subprocess and verify it's ready"""
    global flask_process

    print("Starting TIDAL Flask app...", file=sys.stderr, flush=True)

    # Find uv executable
    uv_executable = find_uv_executable()
    print(f"Using uv executable: {uv_executable}", file=sys.stderr, flush=True)

    # Start the Flask app using uv
    # Stream output to stderr instead of capturing to a pipe - prevents buffer deadlock
    # when the MCP server blocks on HTTP requests without draining the pipe
    flask_process = subprocess.Popen([
        uv_executable, "run",
        "--with", "tidalapi",
        "--with", "flask",
        "--with", "requests",
        "python", FLASK_APP_PATH
    ], stdout=sys.stderr, stderr=sys.stderr)

    # Wait for Flask to start listening on the port (with timeout)
    print(f"Waiting for Flask to start on port {FLASK_PORT}...", file=sys.stderr, flush=True)

    start_time = time.time()
    flask_ready = False

    while time.time() - start_time < FLASK_STARTUP_TIMEOUT:
        # Check if process crashed
        if not _check_process_alive(flask_process):
            # Process died - output already went to stderr, just report the exit code
            print(f"Flask process exited unexpectedly. Exit code: {flask_process.returncode}", file=sys.stderr, flush=True)
            raise RuntimeError(f"Flask backend failed to start. Exit code: {flask_process.returncode}")

        # Check if port is listening
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', FLASK_PORT))
            sock.close()
            if result == 0:
                flask_ready = True
                break
        except socket.error:
            pass

        time.sleep(0.5)

    if not flask_ready:
        # Timeout reached - Flask didn't start in time
        print(f"Flask failed to start within {FLASK_STARTUP_TIMEOUT}s", file=sys.stderr, flush=True)
        if flask_process:
            flask_process.terminate()
        raise RuntimeError(f"Flask backend did not start within {FLASK_STARTUP_TIMEOUT} seconds")

    print(f"TIDAL Flask app started successfully on port {FLASK_PORT}", file=sys.stderr, flush=True)

def shutdown_flask_app():
    """Shutdown the Flask app subprocess when the MCP server exits"""
    global flask_process

    if flask_process:
        print("Shutting down TIDAL Flask app...", file=sys.stderr, flush=True)
        # Try to terminate gracefully first
        flask_process.terminate()
        try:
            # Wait up to 5 seconds for process to terminate
            flask_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # If it doesn't terminate in time, force kill it
            flask_process.kill()
        print("TIDAL Flask app shutdown complete", file=sys.stderr, flush=True)
