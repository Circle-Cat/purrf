"""DTOs for email with one person: threads, messages, compose choices."""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto

# Thread and message subjects are String(998); a reply adds "Re: ".
SUBJECT_MAX_LENGTH = 990
TEXT_BODY_MAX_LENGTH = 10_000


class EmailAttachmentDto(BaseDto):
    """One inbound attachment as listed; its index is its position in the message."""

    name: str
    size: int = 0
    # Set on an inline part: the body shows it where it says cid:<content_id>.
    content_id: str | None = None


def _attachment_entry(entry) -> dict:
    """Name, size and Content-ID of one stored entry, whatever shape an older
    sync left."""
    if isinstance(entry, EmailAttachmentDto):
        return entry.model_dump()
    if not isinstance(entry, dict):
        return {"name": "attachment", "size": 0}
    size = entry.get("size")
    content_id = entry.get("contentId")
    return {
        "name": entry.get("name") or entry.get("filename") or "attachment",
        "size": size if isinstance(size, int) else 0,
        "content_id": content_id if isinstance(content_id, str) else None,
    }


class EmailMessageDto(BaseDto):
    """One message in an email thread.

    Maps from ``EmailMessageEntity`` (``from_attributes``). Both body columns
    are exposed; the frontend prefers ``body_html`` and falls back to
    ``body_text`` (an inbound reply may carry only one).
    """

    message_id: int
    direction: str
    from_address: str | None = None
    to_addresses: str | None = None
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    snippet: str | None = None
    sent_by_user_id: int | None = None
    sent_by_name: str | None = None
    gmail_internal_date: datetime | None = None
    created_at: datetime
    # Set only on a delivery-failure report: the addresses it names, or "".
    failed_recipients: str | None = None
    # Set only on inbound mail: human, auto_reply or bounce.
    inbound_kind: str | None = None
    attachments: list[EmailAttachmentDto] = []

    @field_validator("attachments", mode="before")
    @classmethod
    def _list_attachments(cls, value):
        """Every stored entry, malformed ones included, so indexes stay aligned."""
        return [_attachment_entry(entry) for entry in value or []]


class OpenBounceDto(BaseDto):
    """A delivery failure no later outbound mail has answered."""

    bounced_to: str


class EmailThreadDto(BaseDto):
    """One email conversation with its messages, oldest first.

    Maps from ``EmailThreadEntity``; ``messages`` is assembled by the service
    (the entity carries no ORM relationship).
    """

    thread_id: int
    subject: str | None = None
    synced_at: datetime | None = None
    created_at: datetime
    messages: list[EmailMessageDto]
    needs_reply: bool = False
    open_bounce: OpenBounceDto | None = None
    # The address replies in this thread go out as.
    reply_alias: str | None = None
    # The address a Reply in this thread goes to.
    reply_to: str | None = None


class EmailRecipientOptionDto(BaseDto):
    """An address the compose box may send to, and why it is offered."""

    address: str
    label: Literal["Primary contact", "Alternative"]


class EmailConversationDto(BaseDto):
    """Every thread with one person in one context, and what the viewer may do.

    ``default_to`` is the preselected recipient; ``recipient_options`` the
    only addresses a new email may go to.
    """

    threads: list[EmailThreadDto]
    default_to: str | None = None
    can_send: bool = False
    sender_address: str | None = None
    recipient_options: list[EmailRecipientOptionDto] = []


class EmailSendRequestDto(BaseDto):
    """Compose payload of the recruiting Emails tab POST.

    Without ``thread_id`` it is a new email to ``to``. With it, a reply:
    ``to`` and ``subject`` are ignored and ``last_seen_message_id`` is required.
    """

    to: list[str] = []
    subject: str
    body: str
    thread_id: int | None = None
    last_seen_message_id: int | None = None


class TextEmailSendRequestDto(BaseRequestDto):
    """A new plain-text email to one or more of the person's addresses."""

    to: list[str] = Field(min_length=1)
    subject: str = Field(min_length=1, max_length=SUBJECT_MAX_LENGTH)
    body: str = Field(min_length=1, max_length=TEXT_BODY_MAX_LENGTH)


class TextEmailReplyRequestDto(BaseRequestDto):
    """A plain-text reply; ``last_seen_message_id`` is the newest message on screen."""

    body: str = Field(min_length=1, max_length=TEXT_BODY_MAX_LENGTH)
    last_seen_message_id: int


class EmailRefreshDto(BaseDto):
    """The conversation after a refresh, and how many inbound messages it found."""

    conversation: EmailConversationDto
    new_replies: int


class EmailTemplateDto(BaseDto):
    """One preset email template, already rendered for a given application.

    ``subject`` is placeholder-free; ``body_html`` has ``{{...}}`` substituted
    but still carries ``[UPPERCASE]`` markers for the sender to fill in.
    """

    key: str
    label: str
    subject: str
    body_html: str


class EmailTemplateCatalogDto(BaseDto):
    """The rendered templates plus the signature block on its own.

    The signature is shipped separately as well as inside each template body:
    the composer prefills it into an empty body, so a message written from
    scratch — or any reply, which never applies a template — still goes out
    signed.
    """

    templates: list[EmailTemplateDto]
    signature_html: str
