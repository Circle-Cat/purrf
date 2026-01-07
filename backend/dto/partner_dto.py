from backend.dto.base_dto import BaseDto


class PartnerDto(BaseDto):
    id: int
    first_name: str
    last_name: str
    preferred_name: str
    primary_email: str
