from datetime import datetime
from backend.common.mentorship_enums import CommunicationMethod
from backend.dto.base_dto import BaseDto


class UsersDto(BaseDto):
    id: int
    first_name: str
    last_name: str
    timezone: str
    communication_method: CommunicationMethod
    timezone_updated_at: datetime
    updated_timestamp: datetime
    primary_email: str
    preferred_name: str | None = None
    linkedin_link: str | None = None
