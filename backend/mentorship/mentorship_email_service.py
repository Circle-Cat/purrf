import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from backend.common.exceptions import ConflictError
from backend.common.kit_client import KitApiError
from backend.common.kit_html_checks import (
    find_invalid_hrefs,
    fingerprint_of,
    targets_only_tag,
)
from backend.common.mentorship_email_enums import (
    MentorshipEmailRecipientResult,
    MentorshipEmailSendStatus,
    MentorshipEmailStage,
)
from backend.dto.mentorship_email_dto import (
    EmailConfirmDto,
    EmailNotifiedDto,
    EmailPreviewDto,
    EmailRecipientDto,
    EmailScheduledStageDto,
    EmailSendCreateDto,
    EmailSendDto,
    KitDraftDto,
)
from backend.mentorship.mentorship_email_prepare_service import PREPARE_LEASE

# Marks the broadcasts Purrf creates, so they never show up as drafts to copy.
PURRF_DESCRIPTION_PREFIX = "Purrf · "
PACIFIC = ZoneInfo("America/Los_Angeles")
STAGE_LABELS = {
    MentorshipEmailStage.ROUND_RECRUITMENT: "New round invitation",
    MentorshipEmailStage.ADMISSION: "Admission & onboarding",
    MentorshipEmailStage.ONBOARDING_REMINDER: "Onboarding reminder",
    MentorshipEmailStage.MATCH_RESULT: "Match result",
    MentorshipEmailStage.FIRST_CONTACT_REMINDER: "First contact reminder",
    MentorshipEmailStage.MENTOR_CHECK_IN: "Mentor check-in",
    MentorshipEmailStage.MIDTERM_REMINDER: "Mid-term reminder",
    MentorshipEmailStage.FINAL_FOLLOWUP: "Final follow-up",
    MentorshipEmailStage.FEEDBACK_INVITE: "Feedback invitation",
}


def draft_problem(draft: dict) -> str | None:
    """Why a Kit draft cannot be sent as it is, or None. Checked when drafts are
    listed, so a bad one can be turned off before anyone picks it, and again on
    create, since the draft may have changed in Kit since."""
    if not (draft.get("subject") or "").strip():
        return "it has no subject"
    bad = find_invalid_hrefs(draft.get("content") or "")
    if bad:
        return "links Kit cannot send: " + ", ".join(repr(h) for h in bad)
    return None


class MentorshipEmailService:
    """Entry service for mentorship sends through Kit. Methods called by the
    controller commit their own transaction."""

    def __init__(
        self,
        mentorship_email_repository,
        user_emails_repository,
        mentorship_round_repository,
        kit_client,
        sender_address: str | None,
        logger,
        clock=None,
    ):
        self.repo = mentorship_email_repository
        self.user_emails_repository = user_emails_repository
        self.round_repository = mentorship_round_repository
        self.kit = kit_client
        self.sender_address = sender_address
        self.logger = logger
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    async def list_drafts(self) -> list[KitDraftDto]:
        drafts = await asyncio.to_thread(self.kit.list_draft_broadcasts)
        items = [
            KitDraftDto(
                id=d["id"],
                subject=d.get("subject") or "",
                created_at=d.get("created_at"),
                problem=draft_problem(d),
            )
            for d in drafts
            if not (d.get("description") or "").startswith(PURRF_DESCRIPTION_PREFIX)
        ]
        oldest = datetime.min.replace(tzinfo=timezone.utc)
        items.sort(key=lambda d: (d.created_at or oldest, d.id), reverse=True)
        return items

    async def create_send(
        self, session, body: EmailSendCreateDto, created_by: int
    ) -> EmailSendDto:
        if not self.sender_address:
            raise ValueError("Kit sending address is not configured.")
        round_row = await self.round_repository.get_by_round_id(session, body.round_id)
        if round_row is None:
            raise ValueError(f"Round {body.round_id} does not exist.")
        draft = await self._read_source_draft(body.kit_draft_id)
        problem = draft_problem(draft)
        if problem:
            raise ValueError(
                f"This Kit draft cannot be sent: {problem}. Fix it in Kit first."
            )
        user_ids = list(dict.fromkeys(body.user_ids))
        emails = await self.user_emails_repository.get_contact_emails_by_user_ids(
            session, user_ids
        )

        # The tag starts empty, so the copy reaches nobody until it is filled
        # after the admin confirms; a stray click on Send in Kit is harmless.
        tag_name = await self._free_tag_name(self.tag_name(round_row.name, body.stage))
        tag_id = await asyncio.to_thread(self.kit.create_tag, tag_name)
        try:
            broadcast = await self._copy_draft(draft, tag_name, tag_id)
        except Exception:
            self.logger.error(
                "Kit draft was not created; empty tag %r (id %s) is left in Kit",
                tag_name,
                tag_id,
            )
            raise
        try:
            send = await self.repo.create_send(
                session,
                round_id=body.round_id,
                stage=body.stage.value,
                kit_draft_id=body.kit_draft_id,
                kit_draft_subject=draft["subject"],
                created_by=created_by,
                sender_address=self.sender_address,
                kit_tag_name=tag_name,
                kit_tag_id=tag_id,
                kit_broadcast_id=broadcast["id"],
                recipients=[(uid, emails.get(uid)) for uid in user_ids],
            )
            counts = await self.repo.count_by_result(session, send.send_id)
            await session.commit()
        except Exception:
            self.logger.error(
                "Kit send was not stored; empty tag %r (id %s) and draft broadcast %s are left in Kit",
                tag_name,
                tag_id,
                broadcast["id"],
            )
            raise
        return self.to_dto(send, counts)

    async def _read_source_draft(self, draft_id: int) -> dict:
        try:
            draft = await asyncio.to_thread(self.kit.get_broadcast, draft_id)
        except KitApiError as exc:
            if exc.status == 404:
                raise ValueError(
                    "This Kit draft no longer exists. Pick another one."
                ) from exc
            raise
        if draft.get("status") != "draft":
            raise ValueError(
                "This Kit broadcast is no longer a draft. Pick another one."
            )
        if (draft.get("description") or "").startswith(PURRF_DESCRIPTION_PREFIX):
            raise ValueError(
                "This Kit draft was made by Purrf for another send. Pick another one."
            )
        return draft

    async def _copy_draft(self, draft: dict, tag_name: str, tag_id: int) -> dict:
        # A new broadcast, so the business's draft stays untouched and can be
        # picked again for a later send.
        return await asyncio.to_thread(
            self.kit.create_broadcast,
            {
                "content": draft.get("content") or "",
                "subject": draft["subject"],
                "preview_text": draft.get("preview_text"),
                "description": f"{PURRF_DESCRIPTION_PREFIX}{tag_name}",
                "public": False,
                "send_at": None,
                "email_address": self.sender_address,
                "email_template_id": (draft.get("email_template") or {}).get("id"),
                "allow_starting_point": True,
                "subscriber_filter": [
                    {
                        "all": [{"type": "tag", "ids": [tag_id]}],
                        "any": None,
                        "none": None,
                    }
                ],
            },
        )

    def tag_name(self, round_name: str, stage: MentorshipEmailStage) -> str:
        """Readable Kit tag kept after sending, so the business can find or
        exclude these recipients in Kit."""
        day = self.clock().astimezone(PACIFIC).strftime("%m-%d")
        return f"purrf · {round_name} · {STAGE_LABELS[stage]} · {day}"

    async def _free_tag_name(self, base: str) -> str:
        # Kit hands back the existing tag for a taken name, which would pull an
        # earlier send's recipients into this broadcast.
        taken = await asyncio.to_thread(self.kit.list_tag_names)
        name, n = base, 2
        while name in taken:
            name = f"{base} #{n}"
            n += 1
        return name

    def _resume_needed(self, send) -> bool:
        # A preparing send whose worker went quiet (killed pod): the read that
        # sees it asks the controller to start the worker again.
        stale = (
            send.prepare_claimed_at is None
            or send.prepare_claimed_at < self.clock() - PREPARE_LEASE
        )
        return send.status == MentorshipEmailSendStatus.PREPARING and stale

    def to_dto(self, send, counts) -> EmailSendDto:
        return EmailSendDto(
            send_id=send.send_id,
            round_id=send.round_id,
            stage=send.stage,
            kit_draft_id=send.kit_draft_id,
            kit_draft_subject=send.kit_draft_subject,
            kit_tag_name=send.kit_tag_name,
            status=send.status,
            failure_code=send.failure_code,
            sender_address=send.sender_address,
            kit_broadcast_id=send.kit_broadcast_id,
            error_message=send.error_message,
            send_at=send.send_at,
            created_at=send.created_at,
            counts={str(k): v for k, v in counts.items()},
            resume_needed=self._resume_needed(send),
        )

    MIN_CONFIRM_LEAD = timedelta(minutes=30)
    DUPLICATE_WINDOW = timedelta(days=7)

    async def _load(self, session, send_id: int):
        send = await self.repo.get_send(session, send_id, for_update=True)
        if send is None:
            raise ValueError(f"Send {send_id} does not exist.")
        return send

    async def _read_draft(self, send) -> dict:
        try:
            return await asyncio.to_thread(
                self.kit.get_broadcast, send.kit_broadcast_id
            )
        except KitApiError as exc:
            if exc.status == 404:
                raise ConflictError(
                    "The Kit draft was deleted. Cancel this send and start a new one.",
                    code="draft_gone",
                ) from exc
            raise

    def _recipient_dto(self, r) -> EmailRecipientDto:
        return EmailRecipientDto(
            user_id=r.user_id,
            email=r.email,
            result=r.result,
            failure_reason=r.failure_reason,
        )

    def _check_send_time(self, send_at) -> None:
        if send_at <= self.clock() + self.MIN_CONFIRM_LEAD:
            raise ValueError(
                "Pick a send time at least 30 minutes from now, so there is time to add the recipients in Kit."
            )

    async def refresh_preview(self, session, send_id: int) -> EmailPreviewDto:
        send = await self._load(session, send_id)
        if send.status != MentorshipEmailSendStatus.DRAFT:
            raise ConflictError("This send is no longer a draft.", code="not_draft")
        broadcast = await self._read_draft(send)
        counts = await self.repo.count_by_result(session, send.send_id)
        recipients = await self.repo.list_recipients(session, send.send_id)
        recent = await self.repo.recent_recipient_user_ids(
            session,
            round_id=send.round_id,
            stage=send.stage,
            since=self.clock() - self.DUPLICATE_WINDOW,
            exclude_send_id=send.send_id,
        )
        selected = {r.user_id for r in recipients}
        fingerprint = fingerprint_of(broadcast)
        send.preview_fingerprint = fingerprint
        send.preview_subject = broadcast.get("subject")
        send.preview_html = broadcast.get("content")
        send.updated_at = self.clock()
        dto = EmailPreviewDto(
            send=self.to_dto(send, counts),
            subject=broadcast.get("subject") or "",
            html=broadcast.get("content") or "",
            sender_address=broadcast.get("email_address") or "",
            filter_ok=targets_only_tag(broadcast, send.kit_tag_id, send.sender_address),
            recipient_count=counts.get(MentorshipEmailRecipientResult.PENDING, 0),
            invalid_hrefs=find_invalid_hrefs(broadcast.get("content") or ""),
            no_email=[
                self._recipient_dto(r)
                for r in recipients
                if r.failure_reason == "no_email"
            ],
            recently_sent_user_ids=sorted(recent & selected),
            preview_token=fingerprint,
        )
        await session.commit()
        return dto

    async def confirm(
        self, session, send_id: int, body: EmailConfirmDto
    ) -> EmailSendDto:
        send = await self._load(session, send_id)
        if send.status != MentorshipEmailSendStatus.DRAFT:
            raise ConflictError("This send is no longer a draft.", code="not_draft")
        if body.preview_token != send.preview_fingerprint:
            raise ConflictError(
                "Refresh the preview before confirming.", code="stale_preview"
            )
        self._check_send_time(body.send_at)
        broadcast = await self._read_draft(send)
        if not targets_only_tag(broadcast, send.kit_tag_id, send.sender_address):
            raise ConflictError(
                "The recipients or sender of this draft were changed in Kit. Cancel and start again.",
                code="draft_tampered",
            )
        if fingerprint_of(broadcast) != send.preview_fingerprint:
            raise ConflictError(
                "The draft changed in Kit after the preview. Refresh the preview.",
                code="content_changed",
            )
        bad = find_invalid_hrefs(broadcast.get("content") or "")
        if bad:
            raise ValueError(
                "Fix these links in Kit first: " + ", ".join(repr(h) for h in bad)
            )
        send.send_at = body.send_at
        send.status = MentorshipEmailSendStatus.PREPARING
        send.prepare_claimed_at = None
        send.failure_code = None
        send.error_message = None
        send.updated_at = self.clock()
        counts = await self.repo.count_by_result(session, send.send_id)
        await session.commit()
        return self.to_dto(send, counts)

    async def cancel(self, session, send_id: int) -> EmailSendDto:
        send = await self._load(session, send_id)
        allowed = {
            MentorshipEmailSendStatus.DRAFT,
            MentorshipEmailSendStatus.PREPARING,
            MentorshipEmailSendStatus.FAILED,
            MentorshipEmailSendStatus.SCHEDULED,
        }
        if send.status not in allowed:
            raise ConflictError(
                "This send can no longer be cancelled.", code="not_cancellable"
            )
        if (
            send.status == MentorshipEmailSendStatus.SCHEDULED
            and send.send_at
            and send.send_at <= self.clock()
        ):
            raise ConflictError(
                "Kit has already started sending this email.", code="already_sending"
            )
        if send.kit_broadcast_id:
            try:
                await asyncio.to_thread(
                    self.kit.delete_broadcast, send.kit_broadcast_id
                )
            except KitApiError as exc:
                if exc.status == 422:
                    raise ConflictError(
                        "Kit has already started sending this email.",
                        code="already_sending",
                    ) from exc
                raise
        if send.kit_tag_id and not send.tag_deleted:
            await asyncio.to_thread(self.kit.delete_tag, send.kit_tag_id)
            send.tag_deleted = True
        send.status = MentorshipEmailSendStatus.CANCELLED
        send.updated_at = self.clock()
        counts = await self.repo.count_by_result(session, send.send_id)
        await session.commit()
        return self.to_dto(send, counts)

    async def list_notified(
        self, session, round_id: int
    ) -> tuple[list[EmailNotifiedDto], list[int]]:
        """Who Kit actually emailed in this round, per stage, and per stage the
        latest send confirmed for them and still to go out; plus the ids of
        preparing sends whose worker went quiet and needs starting again."""
        # No background job follows a scheduled send; this read is what moves
        # it to sent or aborted once its time has come.
        sends = await self.repo.list_sends(
            session,
            round_id,
            [MentorshipEmailSendStatus.SCHEDULED, MentorshipEmailSendStatus.PREPARING],
        )
        now = self.clock()
        changed = False
        for send in sends:
            if (
                send.status == MentorshipEmailSendStatus.SCHEDULED
                and send.send_at is not None
                and send.send_at <= now
            ):
                changed = await self._sync_one(send) or changed
        stages: dict[int, list[str]] = {}
        scheduled: dict[int, dict[str, EmailScheduledStageDto]] = {}
        for user_id, stage in await self.repo.list_sent_stages(session, round_id):
            stages.setdefault(user_id, []).append(stage)
        # One per stage, the latest; the list shows only that, and a person's
        # timeline has the rest.
        for user_id, stage, send_at in await self.repo.list_scheduled_stages(
            session, round_id
        ):
            latest = scheduled.setdefault(user_id, {}).get(stage)
            if latest is None or send_at > latest.send_at:
                scheduled[user_id][stage] = EmailScheduledStageDto(
                    stage=stage, send_at=send_at
                )
        if changed:
            await session.commit()
        notified = [
            EmailNotifiedDto(
                user_id=user_id,
                stages=stages.get(user_id, []),
                scheduled=list(scheduled.get(user_id, {}).values()),
            )
            for user_id in sorted(stages.keys() | scheduled.keys())
        ]
        return notified, [s.send_id for s in sends if self._resume_needed(s)]

    async def _sync_one(self, send) -> bool:
        """Catch a scheduled send up with Kit. The per-send tag is kept on
        purpose: the business uses it in Kit to find or exclude these
        recipients."""
        try:
            stats = await asyncio.to_thread(
                self.kit.get_broadcast_stats, send.kit_broadcast_id
            )
        except Exception as e:
            # Reads must not fail because Kit is down or answers oddly; the row
            # stays as it was.
            self.logger.warning("Kit sync skipped for send %s: %r", send.send_id, e)
            return False
        kit_status = stats.get("status") if isinstance(stats, dict) else None
        if kit_status == "completed":
            send.status = MentorshipEmailSendStatus.SENT
        elif kit_status == "aborted":
            send.status = MentorshipEmailSendStatus.ABORTED
            send.error_message = (
                "Kit refused to send this email. The reason is shown only in Kit."
            )
        else:
            return False
        send.updated_at = self.clock()
        return True
