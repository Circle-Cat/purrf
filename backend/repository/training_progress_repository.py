from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_enums import TrainingStatus
from backend.entity.training_entity import TrainingEntity
from backend.entity.training_progress_entity import TrainingProgressEntity


class TrainingProgressRepository:
    """The SCORM runtime state behind assignments."""

    async def get_by_training_id(
        self, session: AsyncSession, training_id: int
    ) -> TrainingProgressEntity | None:
        """Fetch the progress row for one assignment, if it has one."""
        result = await session.execute(
            select(TrainingProgressEntity).where(
                TrainingProgressEntity.training_id == training_id
            )
        )
        return result.scalars().one_or_none()

    async def clear_resume_state(self, session: AsyncSession, course_id: int) -> int:
        """Wipe resume data for everyone on this course who has not finished.

        A previous package's suspend_data means nothing to a new one and can
        hang it, so an overwrite drops it. Rows already DONE are untouched:
        their record stands and they have no reason to open the course again.

        Args:
            session (AsyncSession): The active async database session.
            course_id (int): The course whose package was replaced.

        Returns:
            int: How many learners were reset.
        """
        unfinished = select(TrainingEntity.training_id).where(
            TrainingEntity.course_id == course_id,
            TrainingEntity.status != TrainingStatus.DONE,
        )
        result = await session.execute(
            update(TrainingProgressEntity)
            .where(TrainingProgressEntity.training_id.in_(unfinished))
            .values(suspend_data=None, lesson_location=None)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount or 0
