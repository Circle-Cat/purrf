from datetime import datetime

from pydantic import AwareDatetime, Field

from backend.common.mentorship_email_enums import (
    MentorshipEmailRecipientResult,
    MentorshipEmailSendStatus,
    MentorshipEmailStage,
)
from backend.dto.base_dto import BaseDto


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


class EmailNotifiedDto(BaseDto):
    user_id: int
    stages: list[str]


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
