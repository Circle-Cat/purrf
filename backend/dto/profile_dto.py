from dataclasses import dataclass, field

from backend.dto.education_dto import EducationDto
from backend.dto.work_history_dto import WorkHistoryDto
from backend.dto.training_dto import TrainingDto
from backend.dto.user_dto import UserDto


@dataclass
class ProfileDto:
    id: int
    user: UserDto | None = None
    workHistory: list[WorkHistoryDto] = field(default_factory=list)
    education: list[EducationDto] = field(default_factory=list)
    training: list[TrainingDto] = field(default_factory=list)
