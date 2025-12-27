from datetime import date
from backend.dto.base_dto import BaseDto


class TimelineDto(BaseDto):
    start_date: date
    end_date: date


class RoundsDto(BaseDto):
    id: int
    name: str
    required_meetings: int
    timeline: TimelineDto | None
