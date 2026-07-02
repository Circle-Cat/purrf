from typing import Literal
from backend.dto.base_dto import BaseDto
from backend.common.mentorship_enums import MeetingNoteTag


class AdminMeetingDto(BaseDto):
    meeting_id: str
    time_range: str
    is_completed: bool
    note: list[MeetingNoteTag]
    create_datetime: str


class AdminMeetingLogDto(BaseDto):
    round_version: Literal["v1", "v2"]
    meetings: list[AdminMeetingDto]
