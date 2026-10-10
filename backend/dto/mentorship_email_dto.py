from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, Field, StringConstraints

from backend.common.mentorship_email_enums import (
    MentorshipEmailRecipientResult,
    MentorshipEmailSendStatus,
    MentorshipEmailStage,
)
from backend.dto.base_dto import BaseDto
from backend.dto.participant_detail_dto import NOTE_MAX_LENGTH


class KitDraftDto(BaseDto):
    id: int
    subject: str
    created_at: datetime | None
    # Why the draft cannot be sent as it is; None when it can.
    problem: str | None = None


class EmailSendCreateDto(BaseDto):
    round_id: int
    stage: MentorshipEmailStage
    kit_draft_id: int
    user_ids: list[int] = Field(min_length=1, max_length=2000)


class EmailConfirmDto(BaseDto):
    send_at: AwareDatetime
    preview_token: str


class EmailRecipientDto(BaseDto):
    user_id: int
    email: str | None
    result: MentorshipEmailRecipientResult
    failure_reason: str | None


class EmailSendDto(BaseDto):
    send_id: int
    round_id: int
    stage: str
    kit_draft_id: int
    kit_draft_subject: str
    kit_tag_name: str
    status: MentorshipEmailSendStatus
    failure_code: str | None
    sender_address: str
    kit_broadcast_id: int | None
    error_message: str | None
    send_at: datetime | None
    created_at: datetime | None
    counts: dict[str, int]
    resume_needed: bool


class EmailScheduledStageDto(BaseDto):
    stage: str
    send_at: datetime


class EmailNotifiedDto(BaseDto):
    user_id: int
    stages: list[str]
    # At most one per stage, the latest still to go out; a stage in both lists
    # shows as scheduled.
    scheduled: list[EmailScheduledStageDto]
    # Stages an admin marked notified by hand: the notification went out
    # some other way.
    manual: list[str] = Field(default_factory=list)


class EmailPersonSendDto(BaseDto):
    """One send to one person that has played out: Kit sent it to them, or it
    did not reach them, with why."""

    send_id: int
    stage: str
    subject: str
    delivered: bool
    reason: str | None
    at: datetime


class EmailPreviewDto(BaseDto):
    send: EmailSendDto
    subject: str
    html: str
    sender_address: str
    filter_ok: bool
    recipient_count: int
    invalid_hrefs: list[str]
    no_email: list[EmailRecipientDto]
    recently_sent_user_ids: list[int]
    preview_token: str


# The most people one mark covers; a list page holds fewer.
MARK_MAX_PEOPLE = 500


class NotificationMarkDto(BaseDto):
    """Marking people notified when the notification went out some other
    way. The body says how; it is the only record there is."""

    user_ids: list[int] = Field(min_length=1, max_length=MARK_MAX_PEOPLE)
    stage: MentorshipEmailStage
    body: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=NOTE_MAX_LENGTH
        ),
    ]


class NotificationMarkSkipDto(BaseDto):
    user_id: int
    # ``already_notified`` or ``not_offered``.
    reason: str


class NotificationMarkResultDto(BaseDto):
    marked: list[int]
    skipped: list[NotificationMarkSkipDto]
