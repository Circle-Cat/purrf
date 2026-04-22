from pydantic import Field
from backend.dto.base_request_dto import BaseRequestDto


class FeedbackCreateDto(BaseRequestDto):
    sessions_completed: int | None = Field(default=None, ge=1, le=20)
    most_valuable_aspects: str | None = Field(default=None, max_length=300)
    challenges: str | None = Field(default=None, max_length=300)
    program_rating: int | None = Field(default=None, ge=1, le=5)
