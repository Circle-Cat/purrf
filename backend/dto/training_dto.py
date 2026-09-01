from datetime import datetime
from backend.common.mentorship_enums import TrainingStatus, TrainingCategory
from backend.dto.base_dto import BaseDto


class TrainingDto(BaseDto):
    id: int
    # None for a course that is not one of the four seed categories. Until the
    # profile section learns to show a course name, such a row renders with a
    # blank name there -- unreachable for now, because assigning a
    # category-less course needs a verified package.
    category: TrainingCategory | None = None
    completed_timestamp: datetime | None = None
    status: TrainingStatus
    deadline: datetime | None = None
    link: str | None = None
