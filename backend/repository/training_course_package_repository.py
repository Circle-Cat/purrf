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

    async def live_packages_for(
        self, session: AsyncSession, course_ids: list[int]
    ) -> dict[int, TrainingCoursePackageEntity]:
        """Every one of these courses' live packages, keyed by course_id.

        For a caller that renders package fields -- not just whether one
        exists -- so one batched query serves the whole page instead of a
        lookup per row.
        """
        if not course_ids:
            return {}
        result = await session.execute(
            select(TrainingCoursePackageEntity).where(
                TrainingCoursePackageEntity.course_id.in_(course_ids),
                TrainingCoursePackageEntity.state == TrainingPackageState.LIVE,
            )
        )
        return {package.course_id: package for package in result.scalars().all()}
