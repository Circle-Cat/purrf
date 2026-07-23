"""Response DTOs for the recruiting Emails tab (thread + message display)."""

from datetime import datetime

from backend.dto.base_dto import BaseDto


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
    cc_addresses: str | None = None
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    snippet: str | None = None
    sent_by_user_id: int | None = None
    gmail_internal_date: datetime | None = None
    created_at: datetime


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


class EmailConversationDto(BaseDto):
    """The full email view for one scenario (e.g. one application).

    Returned by the recruiting Emails tab GET and by POST (send returns the
    refreshed conversation). ``default_to`` is the candidate's contact address,
    for prefilling the compose ``To`` field.
    """

    threads: list[EmailThreadDto]
    default_to: str | None = None


class EmailSendRequestDto(BaseDto):
    """Compose payload for sending / replying (recruiting Emails tab POST).

    ``to`` is the (prefilled-then-editable) recipient list; ``thread_id`` is set
    only when replying into an existing thread.
    """

    to: list[str]
    cc: list[str] = []
    subject: str
    body: str
    thread_id: int | None = None
