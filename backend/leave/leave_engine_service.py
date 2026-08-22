"""The two scheduled leave jobs.

Both are deliberately thin: the arithmetic lives in
:mod:`backend.leave.leave_accrual` and is pinned by its own cases. What is here
is the judgement around it -- who the engine pays, who it leaves out and why,
and the order the annual job does its two steps in.

Every mistake either job can make is a wrong number rather than an error, and
the worst of them is leaving somebody out: an unpaid person looks exactly like
a person with nothing owed. So each reason for skipping somebody is named and
comes back in the run's report.

A second run is harmless without either job looking for its own rows. The
target formula counts what it has already granted, so the difference is zero
the second time; the ledger's partial unique index is the backstop for two runs
landing at once, not the mechanism.
"""

import datetime
import json
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.leave_enums import LeaveEntryType
from backend.entity.leave_ledger_entity import LeaveLedgerEntity
from backend.leave.leave_accrual import (
    NO_HOURS,
    accrual_start_date,
    carryover_effective_date,
    carryover_forfeit_hours,
    format_hours,
    weekly_accrual_hours,
)
from backend.common.name_utils import partner_display_name
from backend.leave.leave_clock import business_today
from backend.leave.leave_policy import MAX_CARRYOVER_HOURS

LEAVE_EMPLOYMENT_KEY = "leave:employment"


@dataclass(frozen=True)
class _Participant:
    """One person the engine can act on, with their profile already parsed."""

    ldap: str
    user_id: int
    annual_hours: int
    hire_date: datetime.date
    # Reporting only. The accrual reads the annual figure, never the label:
    # a level that cannot be parsed still accrues on whatever hours it has.
    level: str | None = None
    # Data gaps the nightly sync recorded. A different class from the exclusion
    # lists: these people are paid every week and are still broken, so nothing
    # about the run itself mentions them.
    problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Excluded:
    """Everyone left out of a run, by reason. Sorted, so two runs read alike."""

    left: tuple[str, ...]
    no_hire_date: tuple[str, ...]
    unreadable: tuple[str, ...]
    unresolved: tuple[str, ...]
    not_internal: tuple[str, ...]


@dataclass(frozen=True)
class AccrualRunReport:
    """What one weekly run did."""

    considered: int
    paid: int
    hours: str
    skipped_left: tuple[str, ...]
    skipped_no_hire_date: tuple[str, ...]
    unreadable: tuple[str, ...]
    unresolved: tuple[str, ...]
    not_internal: tuple[str, ...]


@dataclass(frozen=True)
class AnnualCloseReport:
    """What one annual close did, in the order it did it."""

    closing_year: int
    considered: int
    settled: int
    settled_hours: str
    forfeited: int
    forfeited_hours: str
    skipped_left: tuple[str, ...]
    skipped_no_hire_date: tuple[str, ...]
    unreadable: tuple[str, ...]
    unresolved: tuple[str, ...]
    not_internal: tuple[str, ...]


@dataclass(frozen=True)
class _Held:
    """One person the engine pays, and the balance they are holding."""

    ldap: str
    user_id: int
    name: str | None
    level: str | None
    annual_hours: int
    balance: Decimal
    # Kept on the row rather than gathered into its own list: these people are
    # already here, and a second list would be two places to read.
    problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class LeaveOverview:
    """What an administrator sees: who is paid, and who is being missed."""

    people: tuple[_Held, ...]
    excluded: "_Excluded"
    profile_count: int


class LeaveEngineService:
    """Runs the weekly accrual and the annual close."""

    def __init__(
        self,
        logger,
        redis_client,
        retry_utils,
        participant_resolver,
        leave_ledger_repository,
        users_repository,
    ):
        """
        Args:
            logger: Structured logger.
            redis_client: Redis handle holding the employment profiles.
            retry_utils: Transient-failure retry wrapper.
            participant_resolver (LeaveParticipantResolver): ldap to account.
            leave_ledger_repository (LeaveLedgerRepository): Ledger access.
            users_repository (UsersRepository): Names, for the overview.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.retry_utils = retry_utils
        self.participant_resolver = participant_resolver
        self.leave_ledger_repository = leave_ledger_repository
        self.users_repository = users_repository

    async def run_weekly_accrual(
        self, session: AsyncSession, today: datetime.date | None = None
    ) -> AccrualRunReport:
        """Pays everybody the difference between what they are owed and hold.

        Args:
            session: Active async session. Committed once, at the end.
            today: The Beijing date to accrue for. Defaults to today.

        Returns:
            The run's report, including everyone left out and why.
        """
        on = today or business_today()
        participants, excluded, considered = await self._participants(session, on, on)

        entries = []
        for participant in participants:
            owed = await self._owed(session, participant, on.year, on)
            if owed > NO_HOURS:
                entries.append(
                    self._entry(
                        participant.user_id, LeaveEntryType.WEEKLY_ACCRUAL, owed, on
                    )
                )

        await self._write(session, entries)
        report = AccrualRunReport(
            considered=considered,
            paid=len(entries),
            hours=format_hours(sum((entry.hours for entry in entries), NO_HOURS)),
            skipped_left=excluded.left,
            skipped_no_hire_date=excluded.no_hire_date,
            unreadable=excluded.unreadable,
            unresolved=excluded.unresolved,
            not_internal=excluded.not_internal,
        )
        self.logger.info(
            "Leave accrual for %s: %s of %s paid, %s hours.",
            on,
            report.paid,
            report.considered,
            report.hours,
        )
        return report

    async def run_annual_close(
        self, session: AsyncSession, today: datetime.date | None = None
    ) -> AnnualCloseReport:
        """Closes the year that just ended, then applies the carryover ceiling.

        The order matters and is not interchangeable. Week 52 needs 364 elapsed
        days, and the weekly job runs on one fixed weekday, so in most years its
        last run of the year stops a week short and the reset on 1 January puts
        the remainder out of reach. Settling first is what makes the annual
        figure true; trimming first would let the hours it just paid past the
        ceiling unchecked.

        Both steps run for everybody unconditionally rather than looking for a
        year that went wrong: the shortfall is the ordinary case, and a person
        with nothing owed produces no row.

        Args:
            session: Active async session. Committed once, at the end.
            today: The Beijing date the job runs on. Defaults to today. The
                year being closed is the one before it, whichever day in
                January this actually runs.

        Returns:
            The run's report.
        """
        on = today or business_today()
        closing_year = on.year - 1
        closing_day = datetime.date(closing_year, 12, 31)
        participants, excluded, considered = await self._participants(
            session, on, closing_day
        )

        settlements = []
        for participant in participants:
            owed = await self._owed(session, participant, closing_year, closing_day)
            if owed > NO_HOURS:
                settlements.append(
                    self._entry(
                        participant.user_id,
                        LeaveEntryType.WEEKLY_ACCRUAL,
                        owed,
                        closing_day,
                    )
                )
        await self._write(session, settlements, commit=False)

        cap = None if MAX_CARRYOVER_HOURS is None else Decimal(MAX_CARRYOVER_HOURS)
        forfeits = []
        for participant in participants:
            balance = await self.leave_ledger_repository.balance(
                session, participant.user_id
            )
            forfeit = carryover_forfeit_hours(balance, cap)
            if forfeit < NO_HOURS:
                forfeits.append(
                    self._entry(
                        participant.user_id,
                        LeaveEntryType.CARRYOVER_FORFEIT,
                        forfeit,
                        carryover_effective_date(on),
                    )
                )
        await self._write(session, forfeits)

        report = AnnualCloseReport(
            closing_year=closing_year,
            considered=considered,
            settled=len(settlements),
            settled_hours=format_hours(
                sum((entry.hours for entry in settlements), NO_HOURS)
            ),
            forfeited=len(forfeits),
            forfeited_hours=format_hours(
                sum((entry.hours for entry in forfeits), NO_HOURS)
            ),
            skipped_left=excluded.left,
            skipped_no_hire_date=excluded.no_hire_date,
            unreadable=excluded.unreadable,
            unresolved=excluded.unresolved,
            not_internal=excluded.not_internal,
        )
        self.logger.info(
            "Leave annual close of %s: settled %s (%s hours), forfeited %s (%s hours).",
            closing_year,
            report.settled,
            report.settled_hours,
            report.forfeited,
            report.forfeited_hours,
        )
        return report

    async def overview(
        self, session: AsyncSession, today: datetime.date | None = None
    ) -> "LeaveOverview":
        """Everybody the engine pays, what they hold, and who it cannot pay.

        Deliberately built on the same population the accrual walks. An
        overview assembled from its own query could disagree with what the job
        actually pays, and the whole point of the page is to notice that kind of
        gap -- so there is nothing here for it to disagree with.

        The exclusions come along for the same reason: somebody left out of
        every run is invisible in their own balance, which stays at whatever it
        was. Each group names a different fix, so they are kept apart rather
        than counted together.

        Sorted here rather than by the database. Names are sorted in Python
        because the production collation is byte-order, which files every
        capitalised name ahead of every lower-case one.

        Args:
            session: Active async session.
            today: The Beijing date to judge leavers against. Defaults to today.

        Returns:
            The people, their balances, and the exclusions.
        """
        on = today or business_today()
        participants, excluded, profile_count = await self._participants(
            session, on, on
        )

        user_ids = [participant.user_id for participant in participants]
        balances = await self.leave_ledger_repository.balances_by_user_ids(
            session, user_ids
        )
        people_rows = await self.users_repository.get_all_by_ids(
            session, sorted(user_ids)
        )
        name_by_id = {
            person.user_id: partner_display_name(
                first_name=person.first_name,
                last_name=person.last_name,
                preferred_name=person.preferred_name,
            )
            for person in people_rows
        }

        people = [
            _Held(
                ldap=participant.ldap,
                user_id=participant.user_id,
                name=name_by_id.get(participant.user_id),
                level=participant.level,
                annual_hours=participant.annual_hours,
                # Absent rows mean nothing granted yet, which is a balance of
                # zero rather than an unknown one: the engine has them.
                balance=balances.get(participant.user_id, NO_HOURS),
                problems=participant.problems,
            )
            for participant in participants
        ]
        people.sort(key=lambda held: ((held.name or "").casefold(), held.ldap))
        return LeaveOverview(
            people=tuple(people), excluded=excluded, profile_count=profile_count
        )

    async def _participants(
        self, session: AsyncSession, on: datetime.date, until: datetime.date
    ) -> tuple[list[_Participant], _Excluded, int]:
        """Reads the directory and works out who this run can act on.

        Args:
            session: Active async session.
            on: The date the job is running on, for judging who has left.
            until: The last date the run accounts for. The annual close passes
                31 December of the year it is closing.

        Returns:
            The participants, everyone excluded with the reason, and how many
            profiles were considered in total.
        """
        profiles = self.retry_utils.get_retry_on_transient(
            self.redis_client.hgetall, LEAVE_EMPLOYMENT_KEY
        )
        profiles = profiles or {}
        if not profiles:
            self.logger.warning(
                "Leave: no employment profiles cached, so this run pays nobody. "
                "The nightly sync rebuilds them; a missed run is made up by the "
                "next one."
            )

        left, no_hire_date, unreadable = [], [], []
        eligible: dict[str, tuple[int, datetime.date, str | None, tuple]] = {}
        for ldap in sorted(profiles):
            try:
                profile = json.loads(profiles[ldap])
            except (TypeError, ValueError):
                unreadable.append(ldap)
                continue

            if self._has_left(profile, on):
                left.append(ldap)
                continue

            hire_date = _profile_date(profile.get("hire_date"))
            if hire_date is None:
                no_hire_date.append(ldap)
                continue

            eligible[ldap] = (
                int(profile.get("annual_hours") or 0),
                hire_date,
                profile.get("level"),
                tuple(profile.get("problems") or ()),
            )

        resolved = await self.participant_resolver.resolve(session, sorted(eligible))
        # Driven by the eligible set rather than by what came back, so that a
        # resolver answering about somebody this run already excluded cannot
        # put them back in.
        participants = [
            _Participant(
                ldap=ldap,
                user_id=resolved.by_ldap[ldap],
                annual_hours=eligible[ldap][0],
                hire_date=eligible[ldap][1],
                level=eligible[ldap][2],
                problems=eligible[ldap][3],
            )
            for ldap in sorted(eligible)
            if ldap in resolved.by_ldap
        ]
        excluded = _Excluded(
            left=tuple(left),
            no_hire_date=tuple(no_hire_date),
            unreadable=tuple(unreadable),
            unresolved=resolved.unresolved,
            not_internal=resolved.not_internal,
        )
        return participants, excluded, len(profiles)

    def _has_left(self, profile: dict, on: datetime.date) -> bool:
        """Whether this person has stopped accruing by ``on``.

        A leaver is meant to carry a leave date, and one of the five China
        full-timers is a disabled account without one, so the disabled flag has
        to count as well. Both are checked because a leave date can also be set
        ahead of time, before the account is turned off.
        """
        if profile.get("account_enabled") is False:
            return True
        leave_date = _profile_date(profile.get("leave_date"))
        return leave_date is not None and leave_date <= on

    async def _owed(
        self,
        session: AsyncSession,
        participant: _Participant,
        year: int,
        as_of: datetime.date,
    ) -> Decimal:
        """What one person is owed for ``year`` as at ``as_of``.

        ``level_since`` is read as at ``as_of`` rather than as it stands now:
        the annual close is settling a year that has ended, and a promotion
        made since would otherwise split that year at a date outside it.
        """
        granted = await self.leave_ledger_repository.sum_weekly_accrual(
            session, participant.user_id, year
        )
        level_since = await self.leave_ledger_repository.latest_level_change_date(
            session, participant.user_id, on_or_before=as_of
        )
        granted_before = NO_HOURS
        if level_since is not None:
            granted_before = await self.leave_ledger_repository.sum_weekly_accrual(
                session, participant.user_id, year, before=level_since
            )
        return weekly_accrual_hours(
            participant.annual_hours,
            accrual_start_date(year, participant.hire_date),
            as_of,
            granted,
            level_since=level_since,
            granted_before_level_since=granted_before,
        )

    def _entry(
        self,
        user_id: int,
        entry_type: LeaveEntryType,
        hours: Decimal,
        effective_date: datetime.date,
    ) -> LeaveLedgerEntity:
        """Builds a ledger row. ``created_by`` stays NULL: a job wrote it."""
        return LeaveLedgerEntity(
            user_id=user_id,
            entry_type=entry_type,
            hours=hours,
            effective_date=effective_date,
        )

    async def _write(
        self,
        session: AsyncSession,
        entries: list[LeaveLedgerEntity],
        commit: bool = True,
    ) -> None:
        """Appends a batch, flushing so the next step reads it.

        The whole run is one transaction: a partial pay-out would be worse than
        none, since the next run makes a missed one up.
        """
        if entries:
            await self.leave_ledger_repository.add_entries(session, entries)
        if commit:
            await session.commit()


def _profile_date(value: str | None) -> datetime.date | None:
    """Reads a date field off a cached profile.

    The value is already a Beijing calendar day: ``employment_profile`` reduced
    the Graph instant to one before it was cached. Named for what it reads
    rather than what it returns, so it cannot be mistaken for that reduction.
    """
    if not value:
        return None
    return datetime.date.fromisoformat(value)
