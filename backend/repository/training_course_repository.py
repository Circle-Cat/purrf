from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_entity import TrainingEntity


class TrainingCourseRepository:
    """Reads and writes for the course catalogue."""

    async def list_courses(
        self, session: AsyncSession, include_inactive: bool = True
    ) -> list[tuple[TrainingCourseEntity, int]]:
        """Every course with the number of people assigned to it.

        An outer-joined aggregate rather than a query per row: the admin page
        shows the count on every line.

        Args:
            session (AsyncSession): The active async database session.
            include_inactive (bool): Whether deactivated courses are returned.
                They are by default.

        Returns:
            list[tuple[TrainingCourseEntity, int]]: Courses paired with their
            assignment counts, oldest first.
        """
        statement = (
            select(TrainingCourseEntity, func.count(TrainingEntity.training_id))
            .outerjoin(
                TrainingEntity,
                TrainingEntity.course_id == TrainingCourseEntity.course_id,
            )
            .group_by(TrainingCourseEntity.course_id)
            .order_by(TrainingCourseEntity.course_id)
        )
        if not include_inactive:
            statement = statement.where(TrainingCourseEntity.is_active.is_(True))

        result = await session.execute(statement)
        return [(course, count) for course, count in result.all()]

    async def get_course_by_id(
        self, session: AsyncSession, course_id: int
    ) -> TrainingCourseEntity | None:
        """Fetch one course, or None if there is no such row."""
        result = await session.execute(
            select(TrainingCourseEntity).where(
                TrainingCourseEntity.course_id == course_id
            )
        )
        return result.scalars().one_or_none()

    async def count_assignments(self, session: AsyncSession, course_id: int) -> int:
        """How many people hold an assignment to this course."""
        result = await session.execute(
            select(func.count(TrainingEntity.training_id)).where(
                TrainingEntity.course_id == course_id
            )
        )
        return result.scalar_one()

    async def add_course(
        self, session: AsyncSession, course: TrainingCourseEntity
    ) -> TrainingCourseEntity:
        """Insert a course and flush so the caller gets its generated id.

        Flush, not commit: the surrounding request owns the transaction.
        """
        session.add(course)
        await session.flush()
        return course
