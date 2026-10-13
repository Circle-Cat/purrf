"""DTOs for email with one person: threads, messages, compose choices."""

from datetime import datetime
from typing import Literal

from pydantic import field_validator

from backend.dto.base_dto import BaseDto

# Thread and message subjects are String(998); a reply adds "Re: ".
SUBJECT_MAX_LENGTH = 990
TEXT_BODY_MAX_LENGTH = 10_000


class EmailAttachmentDto(BaseDto):
    """One inbound attachment as listed; its index is its position in the message."""

    name: str
    size: int = 0


def _attachment_entry(entry) -> dict:
    """Name and size of one stored entry, whatever shape an older sync left."""
    if isinstance(entry, EmailAttachmentDto):
        return {"name": entry.name, "size": entry.size}
    if not isinstance(entry, dict):
        return {"name": "attachment", "size": 0}
    size = entry.get("size")
    return {
        "name": entry.get("name") or entry.get("filename") or "attachment",
        "size": size if isinstance(size, int) else 0,
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
