from datetime import datetime, timedelta, timezone

from backend.common.monitor_events import MonitorEvent

_SUPPRESS_FOR = timedelta(hours=6)


class OpsAlertService:
    """Logs that the Gmail sync needs a person; Cloud Monitoring alerts on it.

    The alert goes out from Cloud Monitoring rather than as a Purrf
    notification: when the trouble is Gmail itself, a notification email about
    it could never be sent.

    One alert per kind per six hours: a failure that repeats on every push
    would otherwise alert the same people every few minutes.
    """

    def __init__(self, logger):
        self._logger = logger

    async def raise_alert(self, session, state, kind: str, detail: str) -> bool:
        """Log an alert unless the same kind was raised recently.

        Args:
            session (AsyncSession): Session inside the caller's open
                transaction. Unused: the state below is written through it by
                the caller.
            state (GmailSyncStateEntity): The mailbox the alert is about; its
                ``last_alert_kind`` and ``last_alert_at`` are updated.
            kind (str): What went wrong, for example ``"sync_failed"``.
            detail (str): Human-readable cause.

        Returns:
            bool: True if the alert was logged, False if it was suppressed.
        """
        now = datetime.now(timezone.utc)
        if (
            state.last_alert_kind == kind
            and state.last_alert_at
            and now - state.last_alert_at < _SUPPRESS_FOR
        ):
            return False
        state.last_alert_kind, state.last_alert_at = kind, now
        self._logger.warning(
            "[GmailSync] alert %s for %s: %s",
            kind,
            state.email_address,
            detail,
            extra={
                # Cloud Monitoring alerts on this, so the alert reaches people
                # even when Purrf cannot send mail.
                "monitor_event": MonitorEvent.GMAIL_SYNC_ALERT,
                "kind": kind,
                "mailbox": state.email_address,
            },
        )
        return True
