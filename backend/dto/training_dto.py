from datetime import datetime
from backend.common.mentorship_enums import TrainingStatus, TrainingCategory
from backend.dto.base_dto import BaseDto


class TrainingDto(BaseDto):
    id: int
    category: TrainingCategory
    completed_timestamp: datetime
    status: TrainingStatus
    deadline: datetime | None = None
    link: str | None = None
