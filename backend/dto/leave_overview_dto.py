from decimal import Decimal

from backend.dto.base_dto import BaseDto


class LeaveHeldDto(BaseDto):
    """One person the engine pays, and the balance they are holding.

    Hours are strings fixed to two decimals for the same reason they are
    everywhere else in this feature: the encoder turns a Decimal into a float
    and 78.46 comes back as 78.45999999999999.

    ``name`` is empty when the account cannot be read. One unreadable account
    must not take a whole administrative page down.
    """

    user_id: int
    ldap: str
    name: str | None
    level: str | None
    annual_hours: int
    balance_hours: str


class LeaveExcludedDto(BaseDto):
    """Everybody a run leaves out, kept apart by reason.

    Not one list and not a count. Somebody left out of every run is invisible
    in their own balance -- it simply stays where it was -- and each of these
    groups needs a different thing done about it: a leaver needs nothing, a
    missing hire date is an Azure fix, an unresolved ldap is a purrf account
    that does not exist, and an unreadable profile is a bug.
    """

    left: list[str]
    no_hire_date: list[str]
    unreadable: list[str]
    unresolved: list[str]
    not_internal: list[str]


class LeaveOverviewDto(BaseDto):
    """What an administrator sees: who is paid, and who is being missed.

    ``profile_count`` is how many directory profiles the run considered, so a
    page can say "42 of 45" rather than leaving the reader to add up the
    exclusion lists and hope they match.
    """

    people: list[LeaveHeldDto]
    excluded: LeaveExcludedDto
    profile_count: int

    @classmethod
    def of(cls, overview) -> "LeaveOverviewDto":
        """Builds one from the engine's report.

        Args:
            overview (LeaveOverview): What the engine returned.

        Returns:
            The read model.
        """
        return cls(
            people=[
                LeaveHeldDto(
                    user_id=held.user_id,
                    ldap=held.ldap,
                    name=held.name,
                    level=held.level,
                    annual_hours=held.annual_hours,
                    balance_hours=f"{Decimal(held.balance):.2f}",
                )
                for held in overview.people
            ],
            excluded=LeaveExcludedDto(
                left=list(overview.excluded.left),
                no_hire_date=list(overview.excluded.no_hire_date),
                unreadable=list(overview.excluded.unreadable),
                unresolved=list(overview.excluded.unresolved),
                not_internal=list(overview.excluded.not_internal),
            ),
            profile_count=overview.profile_count,
        )
