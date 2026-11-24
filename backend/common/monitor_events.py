"""Names of log lines that Cloud Monitoring alerts on.

A line is logged with ``extra={"monitor_event": <name>, ...}`` and matched by
``jsonPayload.monitor_event`` in terraform/modules/purrf_instance/monitoring.tf.
monitor_events_test checks the two sides agree, so log through these names
rather than string literals.
"""

from enum import StrEnum


class MonitorEvent(StrEnum):
    """Every ``monitor_event`` value in use."""

    CHAT_SUBSCRIPTION_STATUS = "subscription.status"
    GMAIL_SYNC_ALERT = "gmail_sync.alert"
    # Printed by the cron job script in helm/purrf/templates/cronjobs.yaml,
    # not by the backend.
    CRON_SUCCEEDED = "cron.succeeded"
    CRON_FAILED = "cron.failed"


CRON_EVENTS = frozenset({MonitorEvent.CRON_SUCCEEDED, MonitorEvent.CRON_FAILED})
