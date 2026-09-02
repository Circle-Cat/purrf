from datetime import datetime
from backend.common.mentorship_enums import TrainingStatus, TrainingCategory
from backend.dto.base_dto import BaseDto


class TrainingDto(BaseDto):
    id: int
    # Null for a row the catalogue holds no course for; such a row cannot be
    # opened, so the profile page has nothing to link to.
    course_id: int | None = None
    # The course's own name. Null alongside course_id, and the only thing that
    # names a course outside the four seed categories.
    name: str | None = None
    # None for a course outside the four seed categories.
    category: TrainingCategory | None = None
    completed_timestamp: datetime | None = None
    status: TrainingStatus
    deadline: datetime | None = None
    link: str | None = None
