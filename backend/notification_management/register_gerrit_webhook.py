"""
This script is designed to register or update a Webhook subscription on a Gerrit server.
It interacts with the Gerrit Webhooks plugin via the Gerrit REST API to send
specified Gerrit events to a configured target URL.

If the Webhook already exists, the script will retrieve and return its existing configuration.

Example usage:
    bazel run //backend/notification_management:register_gerrit_webhook
"""

from backend.notification_management.gerrit_webhook_lib import (
    run_gerrit_webhook_registration,
)

if __name__ == "__main__":
    run_gerrit_webhook_registration()
