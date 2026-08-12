"""Recruiting-side email synchronisation.

The shared :class:`~backend.communication.email_conversation_service.EmailConversationService`
knows how to sync one ``(user, context)`` pair and nothing else — no
permissions, no recruiting concepts. This service is the recruiting half: it
decides *which* applications are worth syncing and records the domain
consequence of a sync (an ``email_received`` timeline event per inbound
reply).

All three entry points into a sync go through here — the recruiter pressing
Refresh (via ``board_service``, which adds the owner gate), the nightly delta
cron, and the weekly reconcile cron — so the timeline-writing rule lives in
exactly one place.

Two scheduled passes share one sweep loop: a nightly delta that only visits
applications whose threads just received mail, and a weekly reconcile that
asks every tracked thread what it is missing — the backstop for anything the
delta's window slid past.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from backend.common.communication_enums import ContextType, EmailDirection
from backend.notification_management.event_recorder import record_event

# A terminal application keeps getting swept for this long, so a reply that
# lands just after a rejection is still captured. Past that it is left to
# manual Refresh, which has no window at all.
_TERMINAL_SYNC_WINDOW = timedelta(days=7)

# How far back the nightly delta asks Gmail. Gmail's ``newer_than:Nd`` operator
# is day-granular and no finer relative form is documented, so this carries a
# day of slack over the once-a-day schedule rather than trying to be exact.
# The slack is free: extra ids are dropped by the eligibility filter and by the
# per-thread id diff, so not one extra message body is fetched. It also buys
# tolerance for a single missed run.
_DELTA_LOOKBACK_DAYS = 2


class EmailSyncService:
    def __init__(
        self,
        gmail_client,
        email_conversation_service,
        application_repository,
        logger,
    ):
        """
        Args:
            gmail_client (GmailClient): Transport. Used only for the nightly
                delta's mailbox-wide recent-thread lookup, which is not a
                per-``(user, context)`` question and so does not belong on the
                shared conversation service.
            email_conversation_service (EmailConversationService): Shared,
                domain-agnostic Gmail sync.
            application_repository (ApplicationRepository): Supplies the
                eligibility query.
            logger: Application logger. A sweep's outcome is only visible
                here — see ``_sweep``.
        """
        self._gmail = gmail_client
        self._conversation_service = email_conversation_service
        self._application_repo = application_repository
        self._logger = logger

    async def sync_application(self, session, application):
        """Sync one application's email threads and log the new inbound replies.

        Thin wrapper over ``_sync_by_ids``: reads the two fields it needs off
        the entity up front and delegates. This is the entry point
        ``board_service.get_application_conversation`` calls with a live
        ``ApplicationEntity`` — that call site depends on this signature and
        must not change.

        Args:
            session (AsyncSession): The active DB session.
            application (ApplicationEntity): The application to sync.

        Returns:
            list[EmailMessageEntity]: The messages newly persisted this call.

        Raises:
            RateLimitedError / RuntimeError: Propagated from the Gmail sync.
        """
        return await self._sync_by_ids(
            session, application.application_id, application.user_id
        )

    async def _sync_by_ids(self, session, application_id, user_id):
        """Sync one application's email threads and log the new inbound replies.

        Writes an ``email_received`` timeline event per newly-persisted INBOUND
        message, backdated to when the mail actually arrived. Outbound messages
        picked up by a sync are deliberately not logged — the send path already
        wrote an ``email_sent`` event when we sent them.

        Does **not** commit: the caller owns the transaction boundary (manual
        Refresh commits once; each sweep commits per application so one
        failure cannot undo its predecessors).

        Takes plain ids rather than an ``ApplicationEntity`` on purpose: this
        must not touch ORM-loaded state, so it stays safe to call after a
        sibling application's ``session.rollback()`` has expired the whole
        identity map (see ``_sweep``).

        Args:
            session (AsyncSession): The active DB session.
            application_id: The application's id.
            user_id: The application owner's user id (the timeline actor).

        Returns:
            list[EmailMessageEntity]: The messages newly persisted this call.

        Raises:
            RateLimitedError / RuntimeError: Propagated from the Gmail sync.
        """
        new_messages = await self._conversation_service.sync_context(
            session, ContextType.APPLICATION, application_id
        )
        for message in new_messages:
            if message.direction != EmailDirection.INBOUND:
                continue
            await record_event(
                session,
                subject_type="application",
                subject_id=application_id,
                actor_id=user_id,
                event_type="recruiting.email_received",
                details={
                    "subject": message.subject,
                    "from": message.from_address,
                    "to": message.to_addresses,
                    "cc": message.cc_addresses,
                    "threadId": message.thread_id,
                    "direction": "inbound",
                },
                created_at=message.gmail_internal_date,
            )
        return new_messages

    async def sync_due_applications(self, session):
        """Reconcile every application whose email threads are worth watching.

        The weekly backstop. Asks each tracked thread "which messages am I
        missing?", so it repairs any gap regardless of age — including
        anything the nightly delta's window slid past.

        Args:
            session (AsyncSession): The active DB session.

        Returns:
            dict: ``{"scanned", "synced", "failed", "newMessages"}``.
        """
        due = await self._application_repo.list_due_email_sync_applications(
            session, self._terminal_cutoff()
        )
        return await self._sweep(session, due, "reconcile")

    async def sync_recent_applications(self, session):
        """Sync only the applications whose threads just received mail.

        The nightly pass. One mailbox-wide Gmail call names the threads that
        changed; everything else is skipped, so the cost stops scaling with the
        number of conversations we track.

        Eligibility is unchanged — the flagged set narrows *which* applications
        are considered, never *whether* one qualifies, so a thread belonging to
        a long-closed application is still ignored.

        Args:
            session (AsyncSession): The active DB session.

        Returns:
            dict: ``{"scanned", "synced", "failed", "newMessages"}``.

        Raises:
            RateLimitedError / RuntimeError: Propagated if the Gmail lookup
                itself fails. Unlike a per-application failure this is not
                isolated — without the flagged set there is no sweep to run.
        """
        flagged = await asyncio.to_thread(
            self._gmail.list_recent_message_thread_ids, _DELTA_LOOKBACK_DAYS
        )
        if not flagged:
            # Skip the query rather than issuing an empty IN (...) that cannot
            # match anything. The summary is still logged: a quiet night has to
            # be distinguishable from a night the job never ran.
            return await self._sweep(session, [], "delta", flagged=0)

        due = await self._application_repo.list_due_email_sync_applications(
            session, self._terminal_cutoff(), gmail_thread_ids=flagged
        )
        return await self._sweep(session, due, "delta", flagged=len(flagged))

    @staticmethod
    def _terminal_cutoff():
        """Oldest ``stage_entered_at`` still swept for a terminal application."""
        return datetime.now(timezone.utc) - _TERMINAL_SYNC_WINDOW

    async def _sweep(self, session, due, job, flagged=None):
        """Sync each application in ``due``, isolating and counting failures.

        Each application is its own unit of work: synced, then committed, then
        the next one. A failure is caught, logged and counted, and the sweep
        moves on.

        That is deliberately the opposite of ``sync_application``'s own
        behaviour, which propagates. For a recruiter pressing Refresh on one
        application, failing loudly is right — they retry and the retry
        self-heals. For a pass over everything, one rate-limited or deleted
        thread must not cost every later application its sync, with nobody
        watching.

        Committing per application follows from that: a shared transaction
        would let a late failure roll back work that already succeeded.

        Args:
            session (AsyncSession): The active DB session.
            due (list[ApplicationEntity]): The applications to sync.
            job (str): ``"delta"`` or ``"reconcile"``, for the summary log —
                both jobs share one log stream and must be distinguishable.
            flagged (int | None): How many threads Gmail's recent-thread
                lookup flagged, before the eligibility join narrowed them
                down to ``due``. Only the delta has this number — the
                reconcile never asks Gmail, so it stays ``None`` and is
                logged as ``"n/a"``. Without it, a delta that silently stopped
                receiving thread ids from Gmail would render the exact same
                summary line as a genuinely quiet mailbox.

        Returns:
            dict: ``{"scanned", "synced", "failed", "newMessages"}``.
        """
        # Snapshot the two fields the loop needs as plain values *before* the
        # loop runs. session.rollback() (below, on a failure) expires every
        # ORM object in the identity map, including every other entity in
        # `due` and the one currently being handled — so reading them off the
        # entities inside the loop (e.g. in the except block, after a
        # rollback) can trigger an implicit refresh SELECT. That SELECT runs
        # outside greenlet_spawn and raises sqlalchemy.exc.MissingGreenlet
        # from inside the except block, uncaught, killing the whole sweep on
        # the first failure — exactly what per-application isolation exists
        # to prevent. Do not "simplify" this back to iterating `due` directly.
        targets = [(a.application_id, a.user_id) for a in due]

        synced = 0
        failed = 0
        new_message_count = 0
        for application_id, user_id in targets:
            try:
                new_messages = await self._sync_by_ids(session, application_id, user_id)
                await session.commit()
                synced += 1
                new_message_count += len(new_messages)
            except Exception:
                await session.rollback()
                self._logger.exception(
                    "[EmailSync] application_id=%s sync failed",
                    application_id,
                )
                failed += 1

        # The endpoint returns 200 even with failures, so the k8s job is always
        # green — this line is the only place the outcome shows up. WARNING
        # when anything failed makes "did tonight go wrong?" greppable.
        self._logger.log(
            logging.WARNING if failed else logging.INFO,
            "[EmailSync] %s sweep finished: flagged=%s scanned=%d synced=%d "
            "failed=%d new_messages=%d",
            job,
            "n/a" if flagged is None else flagged,
            len(due),
            synced,
            failed,
            new_message_count,
        )
        return {
            "scanned": len(due),
            "synced": synced,
            "failed": failed,
            "newMessages": new_message_count,
        }
