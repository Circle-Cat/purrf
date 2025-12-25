from pydantic import Field
from backend.dto.base_dto import BaseDto
from backend.dto.education_dto import EducationDto
from backend.dto.work_history_dto import WorkHistoryDto
from backend.dto.training_dto import TrainingDto
from backend.dto.users_dto import UsersDto


class ProfileDto(BaseDto):
    id: int
    user: UsersDto | None = None
    work_history: list[WorkHistoryDto] = Field(default_factory=list)
    education: list[EducationDto] = Field(default_factory=list)
    training: list[TrainingDto] = Field(default_factory=list)
