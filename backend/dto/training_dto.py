from dataclasses import dataclass
from datetime import datetime
from backend.common.mentorship_enums import TrainingStatus, TrainingCategory


@dataclass
class TrainingDto:
    id: int
    category: TrainingCategory
    completedTimestamp: datetime
    status: TrainingStatus
    deadline: datetime | None = None
    link: str | None = None
