"""Request and response DTOs for the Inbox (one page over every service's mail)."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.common.communication_enums import InboxService
from backend.dto.base_dto import BaseDto


class InboxQueryDto(BaseDto):
    """List filters. ``archived`` adds archived threads; it does not select them."""

    service: InboxService | None = None
    needs_reply: bool = False
    unassigned: bool = False
    archived: bool = False
    q: str | None = None


class InboxPersonDto(BaseDto):
    user_id: int
    name: str


class InboxRoundAssignmentDto(BaseDto):
    kind: Literal["round"] = "round"
    round_id: int
    round_name: str | None = None


class InboxApplicationAssignmentDto(BaseDto):
    kind: Literal["application"] = "application"
    application_id: int
    job_title: str | None = None


class InboxThreadRowDto(BaseDto):
    """One thread in the list; every flag is derived, none is stored."""

    thread_id: int
    service: InboxService
    subject: str | None = None
    snippet: str | None = None
    last_activity_at: datetime
    sender: str | None = None
    person: InboxPersonDto | None = None
    matched_by: Literal["primary", "alternative"] | None = None
    needs_reply: bool
    archived: bool
    unassigned: bool
    no_matching_user: bool
    machine_tag: Literal["auto_reply", "bounce"] | None = None
    assignment: InboxRoundAssignmentDto | InboxApplicationAssignmentDto | None = None
    moved_from: InboxService | None = None


class InboxCountsDto(BaseDto):
    needs_reply: int
    unassigned: int


class InboxServiceCountDto(BaseDto):
    key: InboxService
    needs_reply: int


class InboxListDto(BaseDto):
    """``counts`` cover the selected service without archived threads, ignoring
    ``q``; ``services`` lists every visible service whatever is selected."""

    threads: list[InboxThreadRowDto]
    counts: InboxCountsDto
    services: list[InboxServiceCountDto]


class InboxAttachmentDto(BaseDto):
    """``attachment_id`` is the index into the message's stored attachments."""

    name: str | None = None
    size: int | None = None
    attachment_id: int


class InboxMessageDto(BaseDto):
    message_id: int
    direction: str
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    at: datetime
    body_html: str | None = None
    body_text: str | None = None
    inbound_kind: str | None = None
    attachments: list[InboxAttachmentDto] = []
    sent_by_name: str | None = None


class InboxOpenBounceDto(BaseDto):
    bounced_to: str


class InboxThreadDetailDto(InboxThreadRowDto):
    """A row plus its messages, oldest first, and what the viewer can do."""

    messages: list[InboxMessageDto]
    latest_message_id: int | None = None
    reply_alias: str | None = None
    can_assign: bool
    can_move: bool
    tracked: bool
    open_bounce: InboxOpenBounceDto | None = None
    moved_at: datetime | None = None
