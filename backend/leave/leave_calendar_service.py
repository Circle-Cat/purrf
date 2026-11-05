"""Company holiday calendar: reads by year, and the whole-year write."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.dto.leave_holiday_dto import (
    LeaveCalendarYearDto,
    LeaveHolidaySegmentInputDto,
    LeaveHolidayYearsDto,
    LeavePolicyDto,
)
from backend.leave.leave_calendar_segments import expand_segments, group_into_segments
from backend.leave.leave_clock import business_today
from backend.leave.leave_policy import current_policy


class LeaveCalendarService:
    """The company holiday calendar an admin enters once a year.

    Writes replace a whole year. A segment is a reading of the rows rather than
    a row itself, so there is nothing for a partial update to address, and a
    repeated submission of the same year is harmless.
    """

    def __init__(self, logger, leave_holiday_repository):
        """
        Args:
            logger: Structured logger.
            leave_holiday_repository (LeaveHolidayRepository): Holiday rows.
        """
        self.logger = logger
        self.leave_holiday_repository = leave_holiday_repository

    async def get_year(self, session: AsyncSession, year: int) -> LeaveCalendarYearDto:
        """One year of holidays, grouped into the segments the page shows.

        A year nobody has entered reads as empty rather than missing: the page
        asks for a year before it knows whether anything is in it, and the
        warning about an unentered year comes from :meth:`list_years`.

        Args:
            session: Active async session.
            year: The year to read.

        Returns:
            Its segments and its day total.
        """
        holidays = await self.leave_holiday_repository.list_by_year(session, year)
        return LeaveCalendarYearDto(
            year=year,
            segments=group_into_segments(holidays),
            total_days=len(holidays),
        )

    async def list_years(self, session: AsyncSession) -> LeaveHolidayYearsDto:
        """Which years hold rows, plus this year and next.

        This year comes from the Beijing calendar day, not from the browser and
        not from the pod's UTC date. It is the only place in this slice that
        touches a clock.

        Args:
            session: Active async session.

        Returns:
            The entered years and the two the page must always offer.
        """
        years = await self.leave_holiday_repository.list_years(session)
        this_year = business_today().year
        return LeaveHolidayYearsDto(
            years=years, current_year=this_year, next_year=this_year + 1
        )

    async def replace_year(
        self,
        session: AsyncSession,
        year: int,
        segments: list[LeaveHolidaySegmentInputDto],
    ) -> LeaveCalendarYearDto:
        """Replaces one year's holidays with the segments given.

        Validation happens first, so a rejected payload deletes nothing -- the
        write path removes the year before inserting it again. The commit is
        explicit because the session does not commit on its own; without it the
        request answers 200 with nothing stored and raises nothing.

        What comes back is read from storage rather than echoed from the
        request, so a mistyped date shows up as a segment that split.

        Args:
            session: Active async session.
            year: The year being replaced.
            segments: Its complete segment list.

        Returns:
            The year as stored.

        Raises:
            ValueError: The payload is empty or malformed. See
                :func:`backend.leave.leave_calendar_segments.expand_segments`.
        """
        holidays = expand_segments(year, segments)
        await self.leave_holiday_repository.replace_year(session, year, holidays)
        await session.commit()
        return await self.get_year(session, year)

    def get_policy(self) -> LeavePolicyDto:
        """The read-only policy constants the page displays.

        Returns:
            The weekend, the working day length, the level hours and the two
            ceilings.
        """
        return current_policy()
