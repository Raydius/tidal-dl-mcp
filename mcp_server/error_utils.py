"""
Error handling utilities for TIDAL MCP server.

Provides standardized error responses with full logging.
"""
from logging_config import logger


def create_error_response(
    exception: Exception,
    context: str = "",
    user_message: str = None
) -> dict:
    """
    Create a standardized error response with full logging.

    The full exception (including stack trace) is logged to stderr/file,
    while a clean message is returned to the user.

    Args:
        exception: The caught exception
        context: Description of what was being attempted (e.g., "tidal_login")
        user_message: Optional custom message for the user.
                      If not provided, uses a generic message with the exception.

    Returns:
        Dictionary with status="error" and message for the user
    """
    # Log the full exception with stack trace
    logger.exception(f"Error in {context}: {exception}")

    # Create user-facing message
    if user_message:
        message = user_message
    elif context:
        message = f"Failed to {context}: {str(exception)}"
    else:
        message = f"An error occurred: {str(exception)}"

    return {
        "status": "error",
        "message": message,
        "error_type": type(exception).__name__
    }


def log_and_return_error(message: str, context: str = "") -> dict:
    """
    Log an error message and return a standardized error response.

    Use this for errors that aren't exceptions (e.g., validation failures).

    Args:
        message: The error message
        context: Description of what was being attempted

    Returns:
        Dictionary with status="error" and the message
    """
    if context:
        logger.error(f"Error in {context}: {message}")
    else:
        logger.error(message)

    return {
        "status": "error",
        "message": message
    }
