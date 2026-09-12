from pydantic import Field

from backend.dto.base_request_dto import BaseRequestDto


class MatchingRunCreateDto(BaseRequestDto):
    """Who takes part in a matching run.

    Roles are not stated here: the backend reads each person's registered role
    for the round, so a caller cannot match somebody as the wrong one.
    """

    round_id: int
    participant_ids: list[int] = Field(min_length=2)
    # YYYY-MM-DD to score as though it were that day. Years of experience are
    # measured from it, so a rerun only reproduces when the date comes with it.
    run_date: str | None = None
