"""Names of log lines that Cloud Monitoring alerts on.

A line is logged with ``extra={"monitor_event": <name>, ...}`` and matched by
``jsonPayload.monitor_event`` in terraform/modules/purrf_instance/monitoring.tf.
Log through these names rather than string literals, and change a filter there
whenever a name here changes: nothing checks the two agree.
"""

from enum import StrEnum


class MonitorEvent(StrEnum):
    """Every ``monitor_event`` value the backend logs."""

    CHAT_SUBSCRIPTION_STATUS = "subscription.status"
    GMAIL_SYNC_ALERT = "gmail_sync.alert"
