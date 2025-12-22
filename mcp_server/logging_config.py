"""
Logging configuration for TIDAL MCP server.

CRITICAL: All output goes to stderr to not interfere with MCP JSON-RPC on stdout.
"""
import sys
import os
import logging
from pathlib import Path


def setup_logging(
    name: str = "tidal-mcp",
    level: str = None,
    log_to_file: bool = None
) -> logging.Logger:
    """
    Configure logging for MCP server.

    All output goes to stderr (required for MCP protocol - stdout is JSON-RPC).

    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR).
               Defaults to TIDAL_MCP_LOG_LEVEL env var or INFO.
        log_to_file: Enable file logging.
                     Defaults to TIDAL_MCP_LOG_FILE env var or False.

    Returns:
        Configured logger instance
    """
    # Read from environment if not specified
    if level is None:
        level = os.environ.get("TIDAL_MCP_LOG_LEVEL", "INFO").upper()

    if log_to_file is None:
        log_to_file = os.environ.get("TIDAL_MCP_LOG_FILE", "false").lower() == "true"

    # Convert string level to logging constant
    log_level = getattr(logging, level, logging.INFO)

    # Get or create logger
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Stderr handler (required for MCP - stdout is JSON-RPC)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(log_level)
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)

    # Optional file handler
    if log_to_file:
        try:
            # Use %APPDATA%\Claude\logs on Windows, ~/.claude/logs elsewhere
            if sys.platform == "win32":
                log_dir = Path(os.environ.get('APPDATA', '.')) / 'Claude' / 'logs'
            else:
                log_dir = Path.home() / '.claude' / 'logs'

            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f'{name}.log'

            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            logger.info(f"File logging enabled: {log_file}")
        except Exception as e:
            logger.warning(f"Could not enable file logging: {e}")

    return logger


# Create a default logger instance for the MCP server
logger = setup_logging("tidal-mcp")
