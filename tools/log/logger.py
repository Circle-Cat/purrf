import logging
import os


def setup_logger():
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

    Example:
        import os
        os.environ['LOG_LEVEL'] = 'DEBUG'
        setup_logger()
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")
