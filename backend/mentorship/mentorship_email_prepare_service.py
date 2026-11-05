import asyncio
from datetime import datetime, timedelta, timezone

from backend.common.exceptions import RateLimitedError
from backend.common.kit_client import KitApiError
from backend.common.kit_html_checks import fingerprint_of, targets_only_tag
from backend.common.mentorship_email_enums import (
    MENTORSHIP_EMAIL_SEND_SUBJECT_TYPE,
    MentorshipEmailFailure,
    MentorshipEmailRecipientResult,
    MentorshipEmailSendStatus,
)
from backend.common.mentorship_enums import MentorshipEvent
from backend.common.name_utils import display_name_of
from backend.notification_management.event_recorder import record_event

PREPARE_LEASE = timedelta(minutes=10)
BATCH_SIZE = 20
RATE_LIMIT_PAUSE_SECONDS = 60
RATE_LIMIT_RETRIES = 3
COUNT_CHECKS = 6
COUNT_CHECK_PAUSE_SECONDS = 30
MIN_SCHEDULE_LEAD = timedelta(minutes=2)

# Kit subscriber state -> (result, failure_reason). Only "active" reaches Kit's
# recipient count; any state not listed is recorded as an import failure.
_STATE_TO_RESULT = {
    "active": (MentorshipEmailRecipientResult.HANDED_TO_KIT, None),
    "cancelled": (MentorshipEmailRecipientResult.UNSUBSCRIBED, None),
    "bounced": (MentorshipEmailRecipientResult.BOUNCED, None),
    "complained": (MentorshipEmailRecipientResult.UNSUBSCRIBED, "complained"),
    "inactive": (MentorshipEmailRecipientResult.UNSUBSCRIBED, "inactive"),
}


def _same_instant(kit_value, when: datetime) -> bool:
    """Kit may write the time with milliseconds or +00:00 instead of Z."""
    if not kit_value:
        return False
    try:
        parsed = datetime.fromisoformat(kit_value)
    except (TypeError, ValueError):
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed == when


class _Stop(Exception):
    """The admin cancelled while we were importing."""


class MentorshipEmailPrepareService:
    """Runs after the admin confirms: imports the recipients into Kit, tags them,
    checks the draft is still the one confirmed, and schedules it. Runs off the
    request path and may be killed at any point, so each step records its result
    before the next starts and a rerun picks up where the last one stopped."""

    def __init__(
        self,
        database,
        mentorship_email_repository,
        mentorship_round_repository,
        kit_client,
        logger,
        clock=None,
        pause=None,
    ):
        self.database = database
        self.repo = mentorship_email_repository
        self.rounds = mentorship_round_repository
        self.kit = kit_client
        self.logger = logger
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.pause = pause or asyncio.sleep

    async def run(self, send_id: int) -> None:
        try:
            async with self.database.session() as session:
                if not await self.repo.claim_for_prepare(
                    session, send_id, now=self.clock(), lease=PREPARE_LEASE
                ):
                    self.logger.info(
                        "[KitEmail] send %s: prepare lease not taken", send_id
                    )
                    return
                await session.commit()
                send = await self.repo.get_send(session, send_id)
                try:
                    await self._import(session, send)
                except _Stop:
                    self.logger.info(
                        "[KitEmail] send %s: cancelled during import", send_id
                    )
                    return
                await self._finalize(session, send)
        except Exception as exc:
            self.logger.exception("[KitEmail] send %s: prepare failed", send_id)
            await self._mark_failed(send_id, exc)

    async def _import(self, session, send) -> None:
        pending = await self.repo.list_pending_recipients_with_greeting_name(
            session, send.send_id
        )
        for index, (recipient, first_name) in enumerate(pending):
            if index and index % BATCH_SIZE == 0:
                await self._checkpoint(session, send)
                current = await self.repo.get_send(session, send.send_id)
                if current.status == MentorshipEmailSendStatus.CANCELLED:
                    raise _Stop()
            await self._import_one(session, send, recipient, first_name)
        await self._checkpoint(session, send)

    async def _import_one(
        self, session, send, recipient, first_name: str | None
    ) -> None:
        tag_id = send.kit_tag_id
        try:
            result = await self._kit(
                self.kit.tag_subscriber_by_email, tag_id, recipient.email
            )
            if not result.found:
                # A cancel deletes the tag, after which Kit answers 404 for
                # everyone; creating then would overwrite existing subscribers.
                current = await self.repo.get_send(session, send.send_id)
                if current.status != MentorshipEmailSendStatus.PREPARING:
                    raise _Stop()
                await self._kit(self.kit.create_subscriber, recipient.email, first_name)
                result = await self._kit(
                    self.kit.tag_subscriber_by_email, tag_id, recipient.email
                )
        except KitApiError as exc:
            recipient.result = MentorshipEmailRecipientResult.IMPORT_FAILED
            recipient.failure_reason = f"kit_{exc.status}"
            return
        if not result.found:
            recipient.result = MentorshipEmailRecipientResult.IMPORT_FAILED
            recipient.failure_reason = "kit_not_found"
            return
        recipient.kit_subscriber_id = result.subscriber_id
        recipient.result, recipient.failure_reason = _STATE_TO_RESULT.get(
            result.state,
            (
                MentorshipEmailRecipientResult.IMPORT_FAILED,
                f"kit_state_{result.state}",
            ),
        )

    async def _finalize(self, session, send) -> None:
        if send.send_at is None:
            return await self._fail(
                session,
                send,
                MentorshipEmailFailure.KIT_ERROR,
                "This send has no send time set.",
            )
        send_at_utc = send.send_at.astimezone(timezone.utc)
        send_at_iso = send_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            broadcast = await self._kit(self.kit.get_broadcast, send.kit_broadcast_id)
        except KitApiError as exc:
            if exc.status != 404:
                raise
            return await self._fail(
                session,
                send,
                MentorshipEmailFailure.DRAFT_GONE,
                "The Kit draft was deleted. Cancel this send and start a new one.",
                clear_broadcast=True,
            )
        if not targets_only_tag(broadcast, send.kit_tag_id, send.sender_address):
            return await self._fail(
                session,
                send,
                MentorshipEmailFailure.DRAFT_TAMPERED,
                "The recipients or sender of the draft were changed in Kit.",
            )
        if fingerprint_of(broadcast) != send.preview_fingerprint:
            return await self._fail(
                session,
                send,
                MentorshipEmailFailure.DRAFT_CHANGED,
                "The draft changed in Kit after you confirmed. Preview it and confirm again.",
            )
        counts = await self.repo.count_by_result(session, send.send_id)
        expected = counts.get(MentorshipEmailRecipientResult.HANDED_TO_KIT, 0)
        if expected == 0:
            return await self._fail(
                session,
                send,
                MentorshipEmailFailure.NO_RECIPIENTS,
                "Nobody can receive this email: every recipient is unsubscribed, bounced or failed to import.",
            )
        stats = {}
        for attempt in range(COUNT_CHECKS):
            stats = await self._kit(self.kit.get_broadcast_stats, send.kit_broadcast_id)
            if stats.get("recipients") == expected:
                break
            if attempt < COUNT_CHECKS - 1:
                await self.pause(COUNT_CHECK_PAUSE_SECONDS)
        else:
            return await self._fail(
                session,
                send,
                MentorshipEmailFailure.COUNT_MISMATCH,
                f"Kit counts {stats.get('recipients')} recipients but {expected} were handed to Kit. Retry in a few minutes.",
            )
        # Re-read under a row lock and keep it until the final commit, so a cancel
        # cannot land between this check and the SCHEDULED write.
        locked = await self.repo.get_send(session, send.send_id, for_update=True)
        if locked.status != MentorshipEmailSendStatus.PREPARING:
            self.logger.info(
                "[KitEmail] send %s: no longer preparing, leaving Kit untouched",
                send.send_id,
            )
            await session.rollback()
            return
        if not _same_instant(broadcast.get("send_at"), send_at_utc):
            if send.send_at <= self.clock() + MIN_SCHEDULE_LEAD:
                return await self._fail(
                    session,
                    send,
                    MentorshipEmailFailure.TIME_PASSED,
                    "The send time passed while recipients were being added. Pick a new time and retry.",
                )
            body = {
                "content": broadcast.get("content"),
                "subject": broadcast.get("subject"),
                "description": broadcast.get("description"),
                "preview_text": broadcast.get("preview_text"),
                "public": False,
                "email_address": send.sender_address,
                "email_template_id": (broadcast.get("email_template") or {}).get("id"),
                "allow_starting_point": True,
                "subscriber_filter": broadcast.get("subscriber_filter"),
                "send_at": send_at_iso,
            }
            updated = await self._kit(
                self.kit.update_broadcast, send.kit_broadcast_id, body
            )
            if updated.get("email_address") != send.sender_address or not _same_instant(
                updated.get("send_at"), send_at_utc
            ):
                detail = (
                    f"Kit did not keep the schedule as sent (send_at={updated.get('send_at')!r}, "
                    f"from={updated.get('email_address')!r}). "
                )
                try:
                    await self._kit(
                        self.kit.update_broadcast,
                        send.kit_broadcast_id,
                        {**body, "send_at": None},
                    )
                    detail += "The schedule was undone in Kit."
                except Exception:
                    self.logger.exception(
                        "[KitEmail] send %s: could not unschedule", send.send_id
                    )
                    detail += "Undoing the schedule failed: the draft in Kit may still be scheduled and must be checked."
                    return await self._fail(
                        session,
                        send,
                        MentorshipEmailFailure.KIT_ERROR,
                        detail,
                        may_still_be_scheduled=True,
                    )
                return await self._fail(
                    session, send, MentorshipEmailFailure.KIT_ERROR, detail
                )
        send.status = MentorshipEmailSendStatus.SCHEDULED
        send.kit_recipient_count = stats.get("recipients")
        send.prepare_claimed_at = None
        send.updated_at = self.clock()
        await self._announce(session, send, handed=expected)
        await session.commit()

    async def _kit(self, fn, *args):
        # Full speed until Kit answers 429 (120 calls per rolling 60 s per key,
        # shared with anything else using it); a minute's wait clears it.
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            try:
                return await asyncio.to_thread(fn, *args)
            except RateLimitedError:
                if attempt == RATE_LIMIT_RETRIES:
                    raise
                await self.pause(RATE_LIMIT_PAUSE_SECONDS)

    async def _checkpoint(self, session, send) -> None:
        now = self.clock()
        send.prepare_claimed_at = now
        send.updated_at = now
        await session.commit()

    async def _fail(
        self,
        session,
        send,
        code: MentorshipEmailFailure,
        message: str,
        clear_broadcast: bool = False,
        may_still_be_scheduled: bool = False,
    ) -> None:
        current = await self.repo.get_send(session, send.send_id, for_update=True)
        if current.status != MentorshipEmailSendStatus.PREPARING:
            await session.rollback()
            return
        if clear_broadcast:
            send.kit_broadcast_id = None
        send.status = MentorshipEmailSendStatus.FAILED
        send.failure_code = code
        send.error_message = message
        send.prepare_claimed_at = None
        send.updated_at = self.clock()
        await self._announce(
            session, send, may_still_be_scheduled=may_still_be_scheduled
        )
        await session.commit()

    async def _announce(
        self,
        session,
        send,
        handed: int | None = None,
        may_still_be_scheduled: bool = False,
    ) -> None:
        """Tell whoever created the send how preparing ended, in the transaction
        that records the outcome. A failure here is logged and swallowed: the
        outcome in Kit stands either way and must still be recorded."""
        try:
            async with session.begin_nested():
                round_entity = await self.rounds.get_by_round_id(session, send.round_id)
                details = {
                    "status": str(send.status),
                    "roundName": getattr(round_entity, "name", None),
                    "stage": send.stage,
                    "subject": send.kit_draft_subject,
                }
                if send.status == MentorshipEmailSendStatus.SCHEDULED:
                    unreached = await self.repo.list_unreached_recipients_with_users(
                        session, send.send_id
                    )
                    details |= {
                        "sendAt": send.send_at.astimezone(timezone.utc).isoformat(),
                        "handedCount": handed,
                        "notHanded": [
                            {
                                "name": display_name_of(user) or recipient.email,
                                "result": str(recipient.result),
                                "failureReason": recipient.failure_reason,
                            }
                            for recipient, user in unreached
                        ],
                    }
                else:
                    details |= {
                        "failureCode": str(send.failure_code),
                        "errorMessage": send.error_message,
                        "mayStillBeScheduled": may_still_be_scheduled,
                    }
                # Nobody acted: the run is the system's, and the creator is the
                # one to tell, so they must not be passed as the actor.
                await record_event(
                    session,
                    subject_type=MENTORSHIP_EMAIL_SEND_SUBJECT_TYPE,
                    subject_id=send.send_id,
                    actor_id=None,
                    event_type=MentorshipEvent.EMAIL_SEND_PREPARED,
                    details=details,
                )
        except Exception:
            self.logger.exception(
                "[KitEmail] send %s: could not record the notification", send.send_id
            )

    async def _mark_failed(self, send_id: int, exc: Exception) -> None:
        try:
            async with self.database.session() as session:
                send = await self.repo.get_send(session, send_id, for_update=True)
                if send is None or send.status != MentorshipEmailSendStatus.PREPARING:
                    return
                await self._fail(
                    session,
                    send,
                    MentorshipEmailFailure.KIT_ERROR,
                    (
                        "Something went wrong talking to Kit; check the draft in Kit"
                        " — it may already be scheduled. Details: " + str(exc)
                    )[:1000],
                    may_still_be_scheduled=True,
                )
        except Exception:
            self.logger.exception(
                "[KitEmail] send %s: could not record failure", send_id
            )
