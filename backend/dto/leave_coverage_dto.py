from backend.dto.base_dto import BaseDto


class LeaveCoverageDto(BaseDto):
    """Whether the leave feature applies to the signed-in account.

    A separate answer from anything about hours, deliberately. "Not covered"
    and "covered with nothing yet" both look like an empty ledger, and a screen
    that cannot tell them apart shows somebody outside the population a balance
    of zero -- which reads as an entitlement of nothing rather than as a
    feature that has nothing to do with them.
    """

    is_covered: bool
