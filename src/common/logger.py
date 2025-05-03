from src.common.environment_constants import LOG_LEVEL
import logging
import os

_logger_initialized = False


def _setup_logger():
    """
    Configure and set up the logging system with environment-specified log level.

    This function initializes the basic configuration for Python's logging module.
    It retrieves the log level from the 'LOG_LEVEL' environment variable (defaulting to 'INFO'
    if not set), and sets up a standard logging format including timestamp, log level,
    and message.

    Environment Variables:
        LOG_LEVEL (str): The desired logging level (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
                        Case-insensitive. Defaults to 'INFO' if not specified.

    Returns:
        None
    """
    global _logger_initialized
    if _logger_initialized:
        return

    log_level = os.environ.get(LOG_LEVEL, "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")
    _logger_initialized = True


def get_logger(name=__name__):
    """
    Returns a configured logger instance.

    Args:
        name (str, optional): The name of the logger. Defaults to the name of the calling module.

    Returns:
        logging.Logger: A configured logger instance.
    """
    _setup_logger()
    return logging.getLogger(name)
