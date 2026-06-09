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


class IdentityDto(BaseDto):
    identity_id: int
    subject_identifier: str
    email_claim: str | None = None
    linked_at: datetime | None = None
    last_used_at: datetime | None = None
    is_current_session: bool = False


class EmailsViewDto(BaseDto):
    emails: list[EmailEntryDto] = Field(default_factory=list)
    internal_identity: IdentityDto | None = None
    external_identities: list[IdentityDto] = Field(default_factory=list)
