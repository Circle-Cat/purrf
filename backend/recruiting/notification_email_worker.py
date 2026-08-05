"""Drains the notification outbox and emails what it finds.

NOT CURRENTLY RUNNING. The app's lifespan no longer starts this worker: a
fixed-interval sweep was rejected as the delivery trigger and no replacement
has been chosen yet. Until one is, ``notification`` rows are committed and
never emailed, and ``email_sent_at`` stays NULL on all of them. The class,
its wiring, and its tests are kept intact so the eventual trigger -- whatever
it turns out to be -- can call ``drain_once`` without rebuilding any of this.
Everything below describes how it behaves *when* something drives it.

It exists so no request path ever waits on Gmail: the request commits a
``notification`` row and returns, and this worker turns that row into an
email out of band.

``_run`` sweeps on startup and then every ``sweep_seconds``, with nothing
telling it a row was written. That interval is the part being reconsidered;
``drain_once`` -- the claim/send/stamp pass itself -- is independent of what
schedules it.

A pass claims rows with ``FOR UPDATE SKIP LOCKED`` and stamps every row it
claims, delivered or not. A recipient with no address and a row that fails
to render are both terminal: retrying them forever would wedge the queue
behind a row that can never succeed, and the in-app notification -- the
authoritative copy -- is already committed either way.

Delivery is at-least-once. A crash after Gmail accepts a message but before
the stamp commits re-sends it on the next pass. That is the deliberate
trade: a rare duplicate notification is cheaper than the two-phase claim
that would be needed to avoid it.
"""

import asyncio
from datetime import datetime, timezone

from backend.recruiting import notification_email_copy


class NotificationEmailWorker:
    """Long-running consumer of the ``notification`` email outbox."""

    def __init__(
        self,
        database,
        notification_repository,
        notification_service,
        user_emails_repository,
        email_service,
        logger,
        sweep_seconds=60,
        batch_size=50,
    ):
        """
        Args:
            database (Database): Opens this worker's own sessions -- it runs
                outside any request, so it cannot borrow one.
            notification_repository (NotificationRepository): Claim and stamp.
            notification_service (RecruitingNotificationService): Resolves a
                row into its display DTO plus the application's stage.
            user_emails_repository (UserEmailsRepository): Recipient
                addresses.
            email_service (NotificationEmailService): Send transport.
            logger (Logger): Where skipped and failed sends go.
            sweep_seconds (int): Interval between sweeps, and therefore the
                worst-case delay before a committed notification is
                emailed.
            batch_size (int): Rows claimed per pass, so a large backlog is
                drained in bounded chunks rather than one long transaction.
        """
        self._database = database
        self._notification_repository = notification_repository
        self._notification_service = notification_service
        self._user_emails_repository = user_emails_repository
        self._email_service = email_service
        self._logger = logger
        self._sweep_seconds = sweep_seconds
        self._batch_size = batch_size
        self._task = None

    def start(self):
        """Spawn the loop. Called from the app's lifespan startup."""
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self):
        """Cancel the loop and wait for it to unwind.

        Called from lifespan shutdown, which is what gives a SIGTERM'd pod a
        chance to finish the pass it is in. Anything still unsent stays in
        the outbox for the next pod.
        """
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run(self):
        """Sweep on startup, then once every sweep interval.

        The startup pass is what clears a backlog left by a pod that was
        preempted mid-delivery. The loop never propagates an exception: a
        failing pass is logged and retried on the next tick, because a
        worker that dies on one bad row stops delivering for everyone.
        """
        while True:
            try:
                await self.drain_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.error(
                    "[NotificationEmailWorker] sweep failed; retrying next tick",
                    exc_info=True,
                )
            await asyncio.sleep(self._sweep_seconds)

    async def drain_once(self):
        """Claim one batch, email it, stamp it. Returns rows processed.

        The claim, the sends, and the stamps share one transaction so the
        rows stay locked for the whole pass -- a concurrent worker skips
        them instead of sending the same mail again.

        Returns:
            int: How many rows this pass claimed (0 when the outbox is
                empty).
        """
        async with self._database.session() as session:
            async with session.begin():
                rows = await self._notification_repository.claim_unemailed(
                    session, self._batch_size
                )
                if not rows:
                    return 0
                await self._deliver(session, rows)
                await self._notification_repository.mark_emailed(
                    session,
                    [row.notification_id for row in rows],
                    datetime.now(timezone.utc),
                )
                return len(rows)

    async def _deliver(self, session, rows):
        """Render and send one claimed batch, swallowing per-row failures.

        Args:
            session (AsyncSession): The pass's session, rows still locked.
            rows (list[NotificationEntity]): The claimed notifications.
        """
        try:
            addresses = (
                await self._user_emails_repository.get_contact_emails_by_user_ids(
                    session, [row.user_id for row in rows]
                )
            )
        except Exception:
            # Without addresses nothing in this batch can be sent. Leave the
            # rows unstamped by letting this propagate: the pass rolls back
            # and the next one retries, which is right for a failure that is
            # about the lookup rather than about any individual row.
            self._logger.error(
                "[NotificationEmailWorker] could not look up recipients for "
                "%d notification(s); retrying next pass",
                len(rows),
                exc_info=True,
            )
            raise
        sends = []
        for row in rows:
            address = addresses.get(row.user_id)
            if not address:
                self._logger.warning(
                    "No email address for user %s; notification %s delivered "
                    "in-app only",
                    row.user_id,
                    row.type,
                )
                continue
            try:
                dto, stage = await self._notification_service.resolve(session, row)
                subject, body = notification_email_copy.render(dto, stage)
            except Exception:
                self._logger.error(
                    "Failed to render notification %s for user %s",
                    row.type,
                    row.user_id,
                    exc_info=True,
                )
                continue
            sends.append(self._email_service.send(address, subject, body))
        # gather so a batch of three costs one round trip's latency rather
        # than three. NotificationEmailService.send already swallows its own
        # failures; return_exceptions is belt-and-braces so an unexpected one
        # here still cannot abort the pass and leave the batch unstamped.
        if sends:
            await asyncio.gather(*sends, return_exceptions=True)
