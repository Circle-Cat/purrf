"""Mailbox-level Gmail sync driven by push notifications and a history cursor.

The cursor (``gmail_sync_state.last_history_id``) belongs to the mailbox, not
to any domain: one ``history.list`` call names every changed thread, and each
tracked thread is handed to whichever domain registered its ``context_type``.
Because the cursor is shared, one domain's failure must not hold back the
others, so a thread that fails to sync is rolled back, logged and skipped
while the cursor still moves forward; unless Gmail says the thread is gone,
ops.maintain holders are told to run a full resync for it. The exception is
an untracked thread the Inbox router could not read because Gmail was busy:
a full resync never sees an untracked thread, so the cursor stays put and the
push is retried. The state row is locked with
``SELECT ... FOR UPDATE`` for the whole run, which makes concurrent pushes for
the same mailbox run one at a time.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from backend.common.exceptions import (
    GmailNotFoundError,
    GmailUnavailableError,
    HistoryExpiredError,
    RateLimitedError,
)

_NO_TOPIC = "GMAIL_WATCH_TOPIC is not set"
_LISTED_THREADS = 10
_RETRYABLE = (GmailUnavailableError, RateLimitedError)


class PushOutcome(StrEnum):
    """What the push endpoint tells Pub/Sub: ACK drops the message, RETRY redelivers it.

    RESYNC is acknowledged like ACK; the caller then runs
    ``run_scheduled_resync`` after the response, because a full resync
    outlasts Pub/Sub's ack deadline. REFUSED comes only from
    ``GmailPushService``, for a caller that is not a provisioned pusher.
    """

    ACK = "ack"
    RETRY = "retry"
    RESYNC = "resync"
    REFUSED = "refused"


def _now():
    return datetime.now(timezone.utc)


def _empty_summary():
    return {"threads": 0, "newMessages": 0, "failed": 0, "unrouted": []}


def _list_threads(gmail_thread_ids):
    listed = ", ".join(gmail_thread_ids[:_LISTED_THREADS])
    more = len(gmail_thread_ids) - _LISTED_THREADS
    return f"{listed} and {more} more" if more > 0 else listed


@dataclass
class _Failures:
    tracked: list = field(default_factory=list)  # a full resync repairs these
    unclaimed: list = field(default_factory=list)  # untracked, not retried
    retry_thread: str | None = None  # untracked, Gmail busy: keep the cursor
    retry_error: Exception | None = None


def _failure_detail(failures):
    parts = []
    if failures.tracked:
        parts.append(
            f"Syncing Gmail threads {_list_threads(failures.tracked)} failed; "
            "a manual full resync repairs them."
        )
    if failures.unclaimed:
        parts.append(
            f"New Gmail threads {_list_threads(failures.unclaimed)} could not be "
            "checked for Inbox mail and will not be retried; a full resync does "
            "not cover them, so look at them in Gmail."
        )
    return " ".join(parts)


def _record_error(state, exc):
    state.last_error = f"{type(exc).__name__}: {exc}"
    state.last_error_at = _now()


class GmailSyncService:
    def __init__(
        self,
        gmail_client,
        state_repository,
        thread_repository,
        context_registry,
        ops_alerts,
        watch_topic,
        database,
        logger,
        inbox_router,
    ):
        """
        Args:
            gmail_client (GmailClient): Synchronous transport, called off the event loop.
            state_repository (GmailSyncStateRepository): The per-mailbox cursor row.
            thread_repository (EmailThreadRepository): Resolves Gmail thread ids to tracked threads.
            context_registry (EmailContextRegistry): Routes a thread to its owning domain.
            ops_alerts: Provides ``async raise_alert(session, state, kind, detail)``.
            watch_topic (str | None): Pub/Sub topic Gmail publishes to. When None,
                the scheduled catch-up and renewal are skipped.
            database (Database): Opens a fresh session to record a failure
                when the caller's session is no longer usable.
            logger: Application logger.
            inbox_router (InboxRouter): Claims untracked threads for the Inbox.
        """
        self._gmail = gmail_client
        self._states = state_repository
        self._threads = thread_repository
        self._registry = context_registry
        self._alerts = ops_alerts
        self._watch_topic = watch_topic
        self._database = database
        self._logger = logger
        self._inbox_router = inbox_router
        self._mailbox = None

    async def mailbox_address(self):
        """Return the address of the mailbox this service syncs, fetched once."""
        if self._mailbox is None:
            profile = await asyncio.to_thread(self._gmail.get_profile)
            self._mailbox = profile["email_address"]
        return self._mailbox

    async def _mailbox_or_alert(self, session, kind):
        """``mailbox_address``, recording and alerting on the only state row if it fails."""
        try:
            return await self.mailbox_address()
        except Exception as exc:
            try:
                state = await self._states.get_single(session)
                if state is None:
                    self._logger.error(
                        "[GmailSync] reading the Gmail profile failed and there is "
                        "no state row to alert on: %s",
                        exc,
                    )
                else:
                    _record_error(state, exc)
                    await self._alerts.raise_alert(
                        session,
                        state=state,
                        kind=kind,
                        detail=f"Reading the Gmail profile failed: {exc}",
                    )
                    await session.commit()
            except Exception:
                self._logger.exception(
                    "[GmailSync] could not record a failed Gmail profile read"
                )
            raise

    async def handle_push(self, session, email_address, history_id):
        """Sync whatever changed since the cursor, in response to a Gmail push.

        Args:
            session (AsyncSession): The active DB session. Committed here.
            email_address (str): Mailbox named in the push.
            history_id (int): The mailbox history id the push reports.

        Returns:
            PushOutcome: RETRY only when Gmail was unavailable or rate limited;
            RESYNC when the cursor expired and ``run_scheduled_resync`` must run.

        Raises:
            Exception: A failed mailbox lookup, after it is recorded and
                alerted on the only state row, if there is one.
        """
        mailbox = await self._mailbox_or_alert(session, "sync_failed")
        if email_address.lower() != mailbox.lower():
            return PushOutcome.ACK
        outcome, _ = await self._sync_from_cursor(session, history_id)
        return outcome

    async def catch_up(self, session):
        """Daily backstop: sync from the cursor as a push would, then report.

        Args:
            session (AsyncSession): The active DB session. Committed here.

        Returns:
            dict: ``{"threads", "newMessages", "failed"}``, plus ``fullResync``
            when the cursor had expired; or ``{"skipped": ...}`` without a topic.

        Raises:
            GmailUnavailableError, RateLimitedError, RuntimeError: Any Gmail
                error, after it is recorded and alerted, so the job fails.
        """
        if self._watch_topic is None:
            return {"skipped": _NO_TOPIC}
        await self._mailbox_or_alert(session, "sync_failed")
        _, summary = await self._sync_from_cursor(session, None)
        self._logger.info("Gmail catch-up finished: %s", summary)
        return summary

    async def renew_watch(self, session):
        """Renew the Gmail watch on the inbox and record its new expiration.

        Args:
            session (AsyncSession): The active DB session. Committed here.

        Returns:
            dict: ``{"expiration": <ISO timestamp>}``, or ``{"skipped": ...}``
            without a topic.

        Raises:
            Exception: Whatever ``watch`` raised, after it is recorded and alerted.
        """
        if self._watch_topic is None:
            return {"skipped": _NO_TOPIC}
        mailbox = await self._mailbox_or_alert(session, "watch_renewal_failed")
        state = await self._states.get_for_update(session, mailbox)
        try:
            watch = await asyncio.to_thread(self._gmail.watch, self._watch_topic)
        except Exception as exc:
            if state is None:
                state = await self._states.create(session, mailbox, None)
            _record_error(state, exc)
            await self._alerts.raise_alert(
                session,
                state=state,
                kind="watch_renewal_failed",
                detail=f"Renewing the Gmail watch failed: {exc}",
            )
            await session.commit()
            raise
        if state is None:
            state = await self._states.create(session, mailbox, watch["history_id"])
        elif state.last_history_id is None:
            state.last_history_id = watch["history_id"]
        state.watch_expiration = watch["expiration"]
        state.last_error = None
        state.last_renewed_at = _now()
        await session.commit()
        return {"expiration": watch["expiration"].isoformat()}

    async def _sync_from_cursor(self, session, push_history_id):
        """Rules 2-6. Returns (outcome, summary). push_history_id is None for catch-up."""
        is_push = push_history_id is not None
        mailbox = await self.mailbox_address()
        state = await self._states.get_for_update(session, mailbox)

        if state is None or state.last_history_id is None:
            profile = await asyncio.to_thread(self._gmail.get_profile)
            if state is None:
                state = await self._states.create(
                    session, mailbox, profile["history_id"]
                )
            else:
                state.last_history_id = profile["history_id"]
            if is_push:
                state.last_push_at = _now()
            await session.commit()
            return PushOutcome.ACK, _empty_summary()

        if is_push and push_history_id <= state.last_history_id:
            state.last_push_at = _now()
            await session.commit()
            return PushOutcome.ACK, _empty_summary()

        cursor = state.last_history_id
        try:
            history = await asyncio.to_thread(self._gmail.list_history, cursor)
        except HistoryExpiredError:
            if is_push:
                return await self._start_push_resync(session, state, cursor)
            result = await self.full_resync(session, alert=True)
            return PushOutcome.ACK, {
                **_empty_summary(),
                "fullResync": result["handlers"],
            }
        except Exception as exc:
            return await self._on_gmail_error(session, state, exc, is_push)

        summary, failures = await self._sync_threads(
            session,
            history["thread_ids"],
            history["sent_only_thread_ids"],
            mailbox,
        )

        # A rolled-back savepoint may have expired the state row; re-read it.
        state = await self._states.get_for_update(session, mailbox)
        if failures.retry_error is not None:
            return await self._keep_cursor_for_retry(
                session, state, failures, is_push, summary
            )
        state.last_history_id = max(state.last_history_id, history["history_id"])
        if is_push:
            state.last_push_at = _now()
        if summary["failed"] == 0:
            state.last_error = None
        if failures.tracked or failures.unclaimed:
            # The cursor has moved past these threads.
            listed = _list_threads(failures.tracked + failures.unclaimed)
            state.last_error = f"Syncing Gmail threads failed: {listed}"
            state.last_error_at = _now()
            await self._alerts.raise_alert(
                session,
                state=state,
                kind="sync_failed",
                detail=_failure_detail(failures),
            )
        if summary["unrouted"]:
            await self._alerts.raise_alert(
                session,
                state=state,
                kind="unrouted_mail",
                detail=(
                    f"New mail in Gmail threads {_list_threads(summary['unrouted'])} "
                    "was addressed to no Inbox alias and stays in Gmail only."
                ),
            )
        await session.commit()
        return PushOutcome.ACK, summary

    async def _sync_threads(self, session, thread_ids, sent_only, mailbox_address):
        """Returns (summary, _Failures). 404s are counted but not listed.

        An untracked thread is offered to the Inbox router first, unless its
        new messages are all our own sent mail; a thread it routes is synced
        from the messages it read, without reading Gmail again. A created
        thread is kept even when its handler then fails, so a full resync can
        still pick it up.
        The loop stops at the first untracked thread Gmail was too busy to
        read, since only a retry from the same cursor reaches it again.
        """
        summary = _empty_summary()
        failures = _Failures()
        for gmail_thread_id in sorted(thread_ids):
            thread = await self._threads.get_by_gmail_thread_id(
                session, gmail_thread_id
            )
            if thread is None and gmail_thread_id in sent_only:
                continue
            claiming = thread is None
            fetched = None
            try:
                if claiming:
                    routed = await self._inbox_router.route(
                        session, gmail_thread_id, mailbox_address
                    )
                    claiming = False
                    if routed.unrouted:
                        summary["unrouted"].append(gmail_thread_id)
                    thread = routed.thread
                    if thread is None:
                        continue
                    fetched = routed.messages
                handler = self._registry.get(thread.context_type)
                if handler is None:
                    continue
                async with session.begin_nested():
                    if fetched is None:
                        new_messages = await handler.sync_tracked_thread(
                            session, thread
                        )
                    else:
                        new_messages = await handler.sync_tracked_thread(
                            session, thread, messages=fetched
                        )
            except Exception as exc:
                self._logger.exception(
                    "Gmail sync failed for thread %s", gmail_thread_id
                )
                summary["failed"] += 1
                if isinstance(exc, GmailNotFoundError):
                    continue
                if claiming and isinstance(exc, _RETRYABLE):
                    failures.retry_thread = gmail_thread_id
                    failures.retry_error = exc
                    break
                (failures.unclaimed if claiming else failures.tracked).append(
                    gmail_thread_id
                )
                continue
            summary["threads"] += 1
            summary["newMessages"] += new_messages
        return summary, failures

    async def _keep_cursor_for_retry(self, session, state, failures, is_push, summary):
        """Leave the cursor where it was so the unread new thread is seen again.

        What already synced is committed; a retry skips it as already stored.
        A push asks Pub/Sub to redeliver, as for a busy ``list_history``;
        the catch-up alerts and raises so the job fails.
        """
        exc = failures.retry_error
        state.last_error = (
            f"Checking new Gmail thread {failures.retry_thread} for Inbox mail "
            f"failed: {type(exc).__name__}: {exc}"
        )
        state.last_error_at = _now()
        if is_push:
            await session.commit()
            return PushOutcome.RETRY, summary
        await self._alerts.raise_alert(
            session,
            state=state,
            kind="sync_failed",
            detail=(
                f"Checking new Gmail thread {failures.retry_thread} for Inbox "
                f"mail failed ({exc}); the cursor stays, so the next sync "
                "retries it."
            ),
        )
        await session.commit()
        raise exc

    async def _on_gmail_error(self, session, state, exc, is_push):
        retryable = isinstance(exc, (GmailUnavailableError, RateLimitedError))
        if is_push and not retryable and not isinstance(exc, RuntimeError):
            raise exc
        _record_error(state, exc)
        if not (is_push and retryable):
            await self._alert_sync_failed(session, state, exc)
        await session.commit()
        if not is_push:
            raise exc
        return (PushOutcome.RETRY if retryable else PushOutcome.ACK), _empty_summary()

    async def _start_push_resync(self, session, state, cursor):
        """Move an expired cursor to a fresh snapshot and hand the resync back.

        The resync itself runs after the push is acknowledged; see
        ``run_scheduled_resync``.
        """
        try:
            profile = await asyncio.to_thread(self._gmail.get_profile)
        except Exception as exc:
            return await self._on_gmail_error(session, state, exc, is_push=True)
        start = profile["history_id"]
        state.last_history_id = max(cursor, start)
        state.last_push_at = _now()
        await self._alerts.raise_alert(
            session,
            state=state,
            kind="history_expired",
            detail=(
                f"Gmail history cursor {cursor} expired; a full resync from "
                f"{start} has been started."
            ),
        )
        await session.commit()
        return PushOutcome.RESYNC, _empty_summary()

    async def full_resync(self, session, *, alert):
        """Re-sync every tracked thread of every domain, then settle the cursor.

        Args:
            session (AsyncSession): The active DB session. Committed here.
            alert (bool): Raise ``history_expired`` first. Set for an expired
                cursor, not for a manual resync.

        Returns:
            dict: ``{"handlers": [<each handler's resync_all result>]}``.

        Raises:
            BaseException: Whatever a handler raised, after it is recorded and alerted.
        """
        # Snapshot before resyncing so mail arriving during the resync is
        # still after the new cursor. The cursor moves to the snapshot before
        # the resync starts: the resync commits and so releases the row lock,
        # and pushes arriving meanwhile must sync incrementally from the
        # snapshot rather than find the expired cursor and resync again.
        mailbox = await self.mailbox_address()
        state = await self._states.get_for_update(session, mailbox)
        profile = await asyncio.to_thread(self._gmail.get_profile)
        start = profile["history_id"]
        if state is None:
            state = await self._states.create(session, mailbox, start)
            cursor = None
        else:
            cursor = state.last_history_id
            state.last_history_id = max(cursor or 0, start)
        if alert:
            await self._alerts.raise_alert(
                session,
                state=state,
                kind="history_expired",
                detail=f"Gmail history cursor {cursor} expired; running a full resync from {start}.",
            )
        await session.commit()
        results = await self._resync_handlers(
            session,
            mailbox,
            start,
            failure=(
                "full resync failed: {exc}; trigger a manual full resync"
                if alert
                else "manual full resync failed: {exc}"
            ),
        )
        return {"handlers": results}

    async def run_scheduled_resync(self, session):
        """Run the full resync a push started by returning ``PushOutcome.RESYNC``.

        The push already moved the cursor to its snapshot and raised
        ``history_expired``, so this only re-syncs every domain.

        Args:
            session (AsyncSession): A session of the caller's own. Committed here.

        Returns:
            dict: ``{"handlers": [<each handler's resync_all result>]}``.

        Raises:
            BaseException: Whatever a handler raised, after it is recorded and alerted.
        """
        mailbox = await self.mailbox_address()
        state = await self._states.get(session, mailbox)
        start = state.last_history_id if state is not None else None
        await session.commit()
        results = await self._resync_handlers(
            session,
            mailbox,
            start,
            failure="full resync failed: {exc}; trigger a manual full resync",
        )
        return {"handlers": results}

    async def _resync_handlers(self, session, mailbox, start, failure):
        # BaseException: a cancelled resync (shutdown, dropped task) must
        # still leave a record and an alert, or the gap is silent.
        try:
            results = [
                await handler.resync_all(session)
                for handler in self._registry.handlers()
            ]
        except BaseException as exc:
            await self._record_resync_failure(
                session, mailbox, exc, failure.format(exc=exc)
            )
            raise
        state = await self._states.get_for_update(session, mailbox)
        if state is not None and start is not None:
            state.last_history_id = max(state.last_history_id or 0, start)
        await session.commit()
        return results

    async def _record_resync_failure(self, session, mailbox, exc, detail):
        try:
            await session.rollback()
            await self._record_and_alert(session, mailbox, exc, detail)
            return
        except Exception:
            self._logger.exception(
                "[GmailSync] recording a failed resync on its own session failed"
            )
        try:
            async with self._database.session() as fresh:
                await self._record_and_alert(fresh, mailbox, exc, detail)
        except Exception:
            self._logger.exception("[GmailSync] could not record a failed resync")

    async def _record_and_alert(self, session, mailbox, exc, detail):
        state = await self._states.get_for_update(session, mailbox)
        if state is None:
            self._logger.error("[GmailSync] %s (no state row to record it on)", detail)
            return
        _record_error(state, exc)
        await self._alerts.raise_alert(
            session, state=state, kind="sync_failed", detail=detail
        )
        await session.commit()

    async def _alert_sync_failed(self, session, state, exc):
        await self._alerts.raise_alert(
            session,
            state=state,
            kind="sync_failed",
            detail=f"Reading Gmail history failed: {exc}",
        )
