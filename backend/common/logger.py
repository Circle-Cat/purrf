from backend.common.environment_constants import LOG_LEVEL
import logging
import os
import sys
from datetime import datetime, timezone

from pythonjsonlogger.json import JsonFormatter

_logger_initialized = False


class CloudJsonFormatter(JsonFormatter):
    """
    JSON log formatter aligned with Google Cloud Logging semantics.

    Outputs structured JSON logs to stdout with fields compatible with
    Google Cloud Logging for severity-based filtering and dashboarding.
    """

    def add_fields(self, log_record, record, message_dict) -> None:
        super().add_fields(log_record, record, message_dict)

        log_record["timestamp"] = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat()
        log_record["severity"] = record.levelname.upper()

        if not record.name.startswith("backend"):
            log_record["name"] = record.name

        if record.exc_info:
            log_record["stack_trace"] = self.formatException(record.exc_info)

        log_record.pop("levelname", None)
        log_record.pop("exc_info", None)


def _setup_logger():
    """
    Configure structured JSON logging for Google Cloud Logging compatibility.

    Initializes the root logger with a JSON formatter that outputs to stdout.
    Overrides Uvicorn loggers for consistent structured output.

    Environment Variables:
        LOG_LEVEL (str): The desired logging level (e.g., 'DEBUG', 'INFO', 'WARNING',
                        'ERROR', 'CRITICAL'). Case-insensitive. Defaults to 'INFO'.
    """
    global _logger_initialized
    if _logger_initialized:
        return

    log_level = os.environ.get(LOG_LEVEL, "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    formatter = CloudJsonFormatter(
        fmt="%(timestamp)s %(severity)s %(message)s",
        json_ensure_ascii=False,
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    for name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = [handler]
        uvicorn_logger.propagate = False

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
