"""Recruiting-side email synchronisation.

The shared :class:`~backend.communication.email_conversation_service.EmailConversationService`
knows how to sync one ``(user, context)`` pair and nothing else — no
permissions, no recruiting concepts. This service is the recruiting half: it
decides *which* applications are worth syncing and records the domain
consequence of a sync (an ``email_received`` timeline event per inbound
reply).

Every entry point into a sync goes through here — the Gmail push (via the
email context registry), the daily catch-up, and a full resync (automatic when
the push cursor expires, or triggered by an ops.maintain holder) — so the
timeline-writing rule lives in exactly one place.

A full resync walks every application still worth watching, asking each tracked
thread which messages it is missing; it is the repair path for anything the
push cursor could not cover.
"""

import logging
from datetime import datetime, timedelta, timezone

from backend.common.communication_enums import ContextType, EmailDirection
from backend.common.recruiting_enums import RecruitingEvent
from backend.notification_management.event_recorder import record_event

# A terminal application keeps getting swept for this long, so a reply that
# lands just after a rejection is still captured.
_TERMINAL_SYNC_WINDOW = timedelta(days=7)


class EmailSyncService:
    def __init__(
        self,
        email_conversation_service,
        application_repository,
        logger,
    ):
        """
        Args:
            email_conversation_service (EmailConversationService): Shared,
                domain-agnostic Gmail sync.
            application_repository (ApplicationRepository): Supplies the
                eligibility query.
            logger: Application logger. A sweep's outcome is only visible
                here — see ``_sweep``.
        """
        self._conversation_service = email_conversation_service
        self._application_repo = application_repository
        self._logger = logger

    async def sync_tracked_thread(self, session, thread):
        """Sync one changed APPLICATION thread and write its timeline events.

        The Gmail push and the daily catch-up come in here through the email
        context registry. The whole application's conversation is synced, not
        just this thread, because that is the unit ``_sync_by_ids`` records
        timeline events for. Does not commit.

        Args:
            session (AsyncSession): The active DB session.
            thread (EmailThreadEntity): The thread that changed.

        Returns:
            int: Messages newly persisted.

        Raises:
            ValueError: If the thread does not belong to an application.
        """
        if thread.context_type != ContextType.APPLICATION:
            raise ValueError(f"not an application thread: {thread.context_type!r}")
        new_messages = await self._sync_by_ids(
            session, thread.context_id, thread.user_id
        )
        return len(new_messages)

    async def _sync_by_ids(self, session, application_id, user_id):
        """Sync one application's email threads and log the new inbound replies.

        Writes an ``email_received`` timeline event per newly-persisted INBOUND
        message, backdated to when the mail actually arrived. Outbound messages
        picked up by a sync are deliberately not logged — the send path already
        wrote an ``email_sent`` event when we sent them.

        Does **not** commit: the caller owns the transaction boundary (each
        sweep commits per application so one failure cannot undo its
        predecessors).

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
                event_type=RecruitingEvent.EMAIL_RECEIVED,
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

        Asks each tracked thread "which messages am I missing?", so it
        repairs any gap regardless of age.

        Args:
            session (AsyncSession): The active DB session.

        Returns:
            dict: ``{"scanned", "synced", "failed", "newMessages"}``.
        """
        due = await self._application_repo.list_due_email_sync_applications(
            session, self._terminal_cutoff()
        )
        return await self._sweep(session, due)

    async def resync_all(self, session):
        """Full resync of every application in scope. Commits per application."""
        return await self.sync_due_applications(session)

    @staticmethod
    def _terminal_cutoff():
        """Oldest ``stage_entered_at`` still swept for a terminal application."""
        return datetime.now(timezone.utc) - _TERMINAL_SYNC_WINDOW

    async def _sweep(self, session, due):
        """Sync each application in ``due``, isolating and counting failures.

        Each application is its own unit of work: synced, then committed, then
        the next one. A failure is caught, logged and counted, and the sweep
        moves on.

        For a pass over everything, one rate-limited or deleted thread must
        not cost every later application its sync, with nobody watching.

        Committing per application follows from that: a shared transaction
        would let a late failure roll back work that already succeeded.

        Args:
            session (AsyncSession): The active DB session.
            due (list[ApplicationEntity]): The applications to sync.

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

        # Failures are isolated above, so this line is the only place the
        # outcome shows up. WARNING when anything failed makes it greppable.
        self._logger.log(
            logging.WARNING if failed else logging.INFO,
            "[EmailSync] reconcile sweep finished: scanned=%d synced=%d "
            "failed=%d new_messages=%d",
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
