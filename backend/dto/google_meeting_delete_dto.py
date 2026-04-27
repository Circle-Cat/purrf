from backend.dto.base_request_dto import BaseRequestDto


class PairMeetingDeleteDto(BaseRequestDto):
    round_id: int
    partner_id: int
    meeting_ids: list[str]


class GoogleMeetingDeleteDto(BaseRequestDto):
    deletions: list[PairMeetingDeleteDto]
