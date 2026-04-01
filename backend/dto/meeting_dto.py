from datetime import datetime
from backend.dto.base_dto import BaseDto
from backend.common.mentorship_enums import ParticipantRole, UserTimezone


class MeetingTimeDto(BaseDto):
    meeting_id: str
    start_datetime: datetime
    end_datetime: datetime
    is_completed: bool


class MeetingInfoDto(BaseDto):
    partner_id: int
    participant_role: ParticipantRole
    meeting_time_list: list[MeetingTimeDto]
    completed_meetings_count: int


class MeetingDto(BaseDto):
    round_id: int
    user_timezone: UserTimezone
    meeting_info: list[MeetingInfoDto]
