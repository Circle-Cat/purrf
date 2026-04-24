from datetime import datetime
from backend.dto.base_dto import BaseDto
from backend.common.mentorship_enums import ParticipantRole, UserTimezone


class MeetingTimeDto(BaseDto):
    meeting_id: str
    start_datetime: datetime
    end_datetime: datetime
    is_completed: bool
    has_unknown_absent: bool | None = None
    absent_user_id: int | None = None
    has_unknown_late: bool | None = None
    late_user_ids: list[int] | None = None
    has_insufficient_duration: bool | None = None
    created_datetime: datetime


class MeetingInfoDto(BaseDto):
    partner_id: int
    participant_role: ParticipantRole
    meeting_time_list: list[MeetingTimeDto]
    completed_meetings_count: int


class MeetingDto(BaseDto):
    round_id: int
    user_timezone: UserTimezone
    meeting_info: list[MeetingInfoDto]
