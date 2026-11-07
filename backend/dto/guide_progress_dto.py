from datetime import datetime

from backend.common.onboarding_guide_enums import GuideProgressStatus
from backend.dto.base_dto import BaseDto


class GuideProgressDto(BaseDto):
    """Where the caller stands with one onboarding guide."""

    guide_key: str
    status: GuideProgressStatus
    snooze_count: int
    updated_at: datetime


class GuideProgressUpdateDto(BaseDto):
    """The body of a write: what the caller just did with the guide."""

    status: GuideProgressStatus
