from enum import StrEnum

OPS_ALERT_SUBJECT_TYPE = "gmail_sync_state"


class OpsEvent(StrEnum):
    """Operations events. Recipients are holders of ops.maintain; see backend/ops."""

    GMAIL_SYNC_ALERT = "ops.gmail_sync_alert"
