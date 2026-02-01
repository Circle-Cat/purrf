from backend.dto.base_request_dto import BaseRequestDto


# Request DTO
class MySummaryRequest(BaseRequestDto):
    start_date: str | None = None
    end_date: str | None = None
