from datetime import datetime
from pydantic import Field
from backend.dto.base_dto import BaseDto


class EmailEntryDto(BaseDto):
    email_id: int
    email: str
    otp_confirmed: bool
    is_primary: bool
    added_at: datetime
    linked_identity_count: int
    is_corp: bool
    last_login_at: datetime | None = None
    # True on the address a row-less passwordless session signed in with. A
    # google/social session is flagged on its IdentityDto instead, so exactly
    # one row carries the flag whichever way the caller signed in.
    is_current_session: bool = False


class IdentityDto(BaseDto):
    identity_id: int
    subject_identifier: str
    email_claim: str | None = None
    linked_at: datetime | None = None
    last_used_at: datetime | None = None
    is_current_session: bool = False


class EmailsViewDto(BaseDto):
    emails: list[EmailEntryDto] = Field(default_factory=list)
    internal_identities: list[IdentityDto] = Field(default_factory=list)
    external_identities: list[IdentityDto] = Field(default_factory=list)
