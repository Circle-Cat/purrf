"""DTOs for the recruiting blacklist admin page (list + unblock)."""

from datetime import datetime

from backend.dto.base_dto import BaseDto


class BlacklistEntryDto(BaseDto):
    """One blocked user, for the blacklist admin page's list."""

    user_id: int
    name: str
    email: str
    reason: str
    blocked_at: datetime
