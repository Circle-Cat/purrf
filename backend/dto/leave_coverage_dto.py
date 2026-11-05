from decimal import Decimal

from backend.dto.base_dto import BaseDto


def _hours(value: Decimal | None) -> str | None:
    """Two decimals as text, or nothing.

    Never a number: the encoder turns a Decimal into a float and 78.46 comes
    back as 78.45999999999999.
    """
    return None if value is None else f"{Decimal(value):.2f}"


class LeaveCoverageDto(BaseDto):
    """Where the signed-in account stands with the leave feature.

    Whether it applies at all is a separate answer from anything about hours.
    "Not covered" and "covered with nothing yet" both look like an empty
    ledger, and a screen that cannot tell them apart shows somebody outside the
    population a balance of zero -- which reads as an entitlement of nothing
    rather than as a feature with nothing to do with them. So the figures are
    absent, not zero, when the feature does not apply.

    ``available_hours`` is the balance less the hours already held by undecided
    requests. That is the same definition the overdraft mark uses, so a card
    cannot say somebody can afford leave that filing would then flag.

    ``used_hours`` covers this calendar year only, and is shown as an amount
    spent even though the ledger stores it negative.
    """

    is_covered: bool
    available_hours: str | None
    pending_hours: str | None
    used_hours: str | None

    @classmethod
    def of(cls, standing) -> "LeaveCoverageDto":
        """Builds one from the service's report.

        Args:
            standing (LeaveStanding): What the service returned.

        Returns:
            The read model.
        """
        return cls(
            is_covered=standing.is_covered,
            available_hours=_hours(standing.available),
            pending_hours=_hours(standing.pending),
            used_hours=_hours(standing.used),
        )
