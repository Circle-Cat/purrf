import os
from urllib.parse import urlparse

from backend.common.environment_constants import (
    GERRIT_URL,  # Base URL of the Gerrit server
    GERRIT_USER,  # Admin username required to connect to Gerrit
    GERRIT_HTTP_PASS,  # HTTP password required to connect to Gerrit
    GERRIT_WEBHOOK_REMOTE_NAME,  # Identifier name for the webhook in Gerrit
    GERRIT_WEBHOOK_TARGET_URL,  # The target URL to which Gerrit will send webhook events
    GERRIT_WEBHOOK_EVENTS,  # List of Gerrit events to subscribe to (comma-separated)
    GERRIT_WEBHOOK_PROJECT,  # Gerrit project to subscribe the webhook for (defaults to 'All-Projects')
)
from backend.notification_management.gerrit_subscription_service import (
    GerritSubscriptionService,
)
from backend.common.logger import get_logger
from backend.common.gerrit_client import GerritClient

logger = get_logger()


def require_env(var_name: str, default: str | None = None) -> str:
    """Fetch env var or raise ValueError if missing."""
    value = os.getenv(var_name, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {var_name}")
    return value


def validate_url(url: str, var_name: str) -> str:
    """Ensure the URL looks valid, else raise ValueError."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL in {var_name}: {url}")
    return url


def run_gerrit_webhook_registration():
    """
    Registers or updates a Webhook subscription on a Gerrit server.
    Reads configuration from environment variables.
    """
    logger = get_logger()

    # Required Gerrit connection
    gerrit_url = validate_url(require_env(GERRIT_URL), GERRIT_URL)
    gerrit_user = require_env(GERRIT_USER)
    gerrit_password = require_env(GERRIT_HTTP_PASS)

    # Webhook settings
    subscribe_url = validate_url(
        require_env(GERRIT_WEBHOOK_TARGET_URL), GERRIT_WEBHOOK_TARGET_URL
    )
    project = os.getenv(GERRIT_WEBHOOK_PROJECT, "All-Projects")
    remote_name = os.getenv(GERRIT_WEBHOOK_REMOTE_NAME, "gerrit-webhook")

    raw_events = os.getenv(
        GERRIT_WEBHOOK_EVENTS,
        "patchset-created,change-merged,change-abandoned,comment-added,change-restored,project-created",
    )
    events = [e.strip() for e in raw_events.split(",") if e.strip()]
    if not events:
        raise ValueError("No valid events configured for webhook")

    logger.info(
        "Initializing Gerrit subscription with config: "
        f"url={gerrit_url}, user={gerrit_user}, project={project}, "
        f"remote={remote_name}, target={subscribe_url}, events={events}"
    )

    # Build client and service
    gerrit_client = GerritClient(
        base_url=gerrit_url, username=gerrit_user, http_password=gerrit_password
    )
    gerrit_subscription_service = GerritSubscriptionService(
        logger=logger,
        gerrit_client=gerrit_client,
        project=project,
        remote_name=remote_name,
        subscribe_url=subscribe_url,
        events=events,
    )

    # Run registration
    result = gerrit_subscription_service.register_webhook()
    logger.info(f"Webhook registration result: {result}")
    return result
