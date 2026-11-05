from backend.dto.base_request_dto import BaseRequestDto
from backend.common.mentorship_enums import MeetingNoteTag


class V2MeetingUpdateItemDto(BaseRequestDto):
    meeting_id: str
    is_completed: bool | None = None
    note: list[MeetingNoteTag] | None = None


class V2MeetingBatchUpdateDto(BaseRequestDto):
    updates: list[V2MeetingUpdateItemDto] = []
    deletes: list[str] = []
