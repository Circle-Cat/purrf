from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def upsert(
        self, session: AsyncSession, training_id: int, **columns
    ) -> TrainingProgressEntity:
        """Create or update the progress row for one assignment.

        One statement, not a read followed by an insert: two overlapping first
        commits on the same assignment both read no row, and the second insert
        would violate the unique constraint on ``training_id`` and 500 the
        request -- taking that learner's completion down with it. ON CONFLICT
        turns the loser of that race into an update instead.

        Args:
            session (AsyncSession): The active async database session.
            training_id (int): The assignment the row belongs to.
            **columns: Column values to write.

        Returns:
            TrainingProgressEntity: The stored row.
        """
        values = {
            "training_id": training_id,
            **columns,
            "last_accessed_at": datetime.now(timezone.utc),
        }
        statement = (
            insert(TrainingProgressEntity)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[TrainingProgressEntity.training_id],
                set_={
                    name: value
                    for name, value in values.items()
                    if name != "training_id"
                },
            )
            .returning(TrainingProgressEntity)
        )
        # populate_existing: the caller has usually already loaded this row, and
        # the object it holds must end up carrying what was just written.
        result = await session.execute(
            statement, execution_options={"populate_existing": True}
        )
        return result.scalars().one()

    async def clear_resume_state(self, session: AsyncSession, course_id: int) -> int:
        """Wipe the replaced package's state for everyone on this course.

        A previous package's suspend_data means nothing to a new one and can
        hang it, so an overwrite drops it. Rows already DONE included: the
        person who verified the replaced package is one of them, and they are
        the likeliest to open the replacement.

        lesson_status goes with it. It is seeded back into the CMI model when
        the course opens, and the player re-sends the whole model on every
        commit, so a status left over from the replaced package returns
        looking like the new one reporting itself finished -- enough to mark
        the replacement verified with nobody having run it.

        The record of having finished lives on the assignment's own status,
        which nothing here touches.

        Args:
            session (AsyncSession): The active async database session.
            course_id (int): The course whose package was replaced.

        Returns:
            int: How many learners were reset.
        """
        on_this_course = select(TrainingEntity.training_id).where(
            TrainingEntity.course_id == course_id
        )
        result = await session.execute(
            update(TrainingProgressEntity)
            .where(TrainingProgressEntity.training_id.in_(on_this_course))
            .values(suspend_data=None, lesson_location=None, lesson_status=None)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount or 0
