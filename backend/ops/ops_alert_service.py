from datetime import datetime, timedelta, timezone

from backend.common.ops_enums import OPS_ALERT_SUBJECT_TYPE, OpsEvent
from backend.notification_management.event_recorder import record_event

_SUPPRESS_FOR = timedelta(hours=6)
_DETAIL_LIMIT = 500


class OpsAlertService:
    """Tells ops.maintain holders that the Gmail sync needs a person.

    One alert per kind per six hours: a failure that repeats on every push
    would otherwise email the same people every few minutes.
    """

    def __init__(self, logger):
        self._logger = logger

    async def raise_alert(self, session, state, kind: str, detail: str) -> bool:
        """Record an alert event unless the same kind was raised recently.

        Args:
            session (AsyncSession): Session inside the caller's open transaction.
            state (GmailSyncStateEntity): The mailbox the alert is about; its
                ``last_alert_kind`` and ``last_alert_at`` are updated.
            kind (str): What went wrong, for example ``"sync_failed"``.
            detail (str): Human-readable cause, truncated to 500 characters.

        Returns:
            bool: True if an event was recorded, False if it was suppressed.
        """
        now = datetime.now(timezone.utc)
        if (
            state.last_alert_kind == kind
            and state.last_alert_at
            and now - state.last_alert_at < _SUPPRESS_FOR
        ):
            return False
        await record_event(
            session,
            subject_type=OPS_ALERT_SUBJECT_TYPE,
            subject_id=state.id,
            actor_id=None,
            event_type=OpsEvent.GMAIL_SYNC_ALERT,
            details={
                "kind": kind,
                "detail": detail[:_DETAIL_LIMIT],
                "mailbox": state.email_address,
            },
        )
        state.last_alert_kind, state.last_alert_at = kind, now
        self._logger.warning(
            "[GmailSync] alert %s for %s: %s", kind, state.email_address, detail
        )
        return True
