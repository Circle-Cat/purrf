from backend.dto.base_dto import BaseDto
from pydantic import Field
from backend.dto.partner_dto import PartnerDto
from backend.common.mentorship_enums import MatchStatus


class MatchesDto(BaseDto):
    round_id: int
    current_status: MatchStatus
    partners: list[PartnerDto] = Field(default_factory=list)
