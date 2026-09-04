from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_enums import TrainingPackageState
from backend.entity.training_course_package_entity import (
    TrainingCoursePackageEntity,
)


class TrainingCoursePackageRepository:
    """Reads and writes for the packages behind a course."""

    async def get_by_state(
        self,
        session: AsyncSession,
        course_id: int,
        state: TrainingPackageState,
    ) -> TrainingCoursePackageEntity | None:
        """The package filling one of a course's two slots, or None."""
        result = await session.execute(
            select(TrainingCoursePackageEntity).where(
                TrainingCoursePackageEntity.course_id == course_id,
                TrainingCoursePackageEntity.state == state,
            )
        )
        return result.scalars().one_or_none()

    async def get_by_id(
        self, session: AsyncSession, package_id: int
    ) -> TrainingCoursePackageEntity | None:
        """Fetch one package, or None if there is no such row."""
        result = await session.execute(
            select(TrainingCoursePackageEntity).where(
                TrainingCoursePackageEntity.package_id == package_id
            )
        )
        return result.scalars().one_or_none()

    async def add(
        self, session: AsyncSession, package: TrainingCoursePackageEntity
    ) -> TrainingCoursePackageEntity:
        """Insert a package and flush so the caller gets its generated id.

        Flush, not commit: the surrounding request owns the transaction.
        """
        session.add(package)
        await session.flush()
        return package

    async def delete(
        self, session: AsyncSession, package: TrainingCoursePackageEntity
    ) -> None:
        """Drop a package row, freeing its slot within this transaction."""
        await session.delete(package)
        await session.flush()

    async def live_course_ids(
        self, session: AsyncSession, course_ids: list[int]
    ) -> set[int]:
        """Which of these courses have something live.

        A batch answer rather than a lookup per course: the callers asking it
        -- the course list, a person's profile -- are already holding a page
        of rows when they ask.
        """
        if not course_ids:
            return set()
        result = await session.execute(
            select(TrainingCoursePackageEntity.course_id).where(
                TrainingCoursePackageEntity.course_id.in_(course_ids),
                TrainingCoursePackageEntity.state == TrainingPackageState.LIVE,
            )
        )
        return set(result.scalars().all())
