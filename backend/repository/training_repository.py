from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.entity.training_entity import TrainingEntity
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_course_package_entity import (
    TrainingCoursePackageEntity,
)
from backend.common.mentorship_enums import TrainingCategory, TrainingPackageState


class TrainingRepository:
    async def get_training_with_course_by_user_id(
        self, session: AsyncSession, user_id: int
    ) -> list[tuple[TrainingEntity, str | None, bool]]:
        """Fetch a user's training records, each with its course name and
        whether that course has a live package.

        Outer joined: course_id is nullable, and a row without one is still
        the user's assignment and still has to be shown.

        The boolean is what tells the caller a course we serve apart from one
        nobody has uploaded to, or has only a package still pending
        verification. Resolving an actual object key is the content route's
        job, per request.
        """
        has_live_package = (
            select(TrainingCoursePackageEntity.package_id)
            .where(
                TrainingCoursePackageEntity.course_id == TrainingCourseEntity.course_id,
                TrainingCoursePackageEntity.state == TrainingPackageState.LIVE,
            )
            .exists()
        )
        result = await session.execute(
            select(
                TrainingEntity,
                TrainingCourseEntity.name,
                has_live_package,
            )
            .outerjoin(
                TrainingCourseEntity,
                TrainingEntity.course_id == TrainingCourseEntity.course_id,
            )
            .where(TrainingEntity.user_id == user_id)
        )
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def get_training_by_user_id_and_category(
        self, session: AsyncSession, user_id: int, category: TrainingCategory
    ) -> TrainingEntity | None:
        """
        Fetch a training record for a given user_id and category.
        """
        result = await session.execute(
            select(TrainingEntity).where(
                TrainingEntity.user_id == user_id,
                TrainingEntity.category == category,
            )
        )
        return result.scalars().one_or_none()

    async def get_training_by_user_ids_and_categories(
        self,
        session: AsyncSession,
        user_ids: list[int],
        categories: list[TrainingCategory],
    ) -> list[TrainingEntity]:
        """
        Batch-fetch training records for a list of user IDs and categories.

        Args:
            session (AsyncSession): The active async database session.
            user_ids (list[int]): A list of user IDs to retrieve training records for.
            categories (list[TrainingCategory]): Training categories to filter by.

        Returns:
            list[TrainingEntity]: Matching training records. Returns an empty list if
            user_ids is empty or no records match.
        """
        if not user_ids:
            return []
        result = await session.execute(
            select(TrainingEntity).where(
                TrainingEntity.user_id.in_(user_ids),
                TrainingEntity.category.in_(categories),
            )
        )
        return result.scalars().all()

    async def upsert_training(
        self, session: AsyncSession, entity: TrainingEntity
    ) -> TrainingEntity:
        """
        Inserts or updates a TrainingEntity object in the database.
        """
        merged_entity = await session.merge(entity)
        await session.flush()
        return merged_entity

    async def get_training_by_user_id_and_course_id(
        self, session: AsyncSession, user_id: int, course_id: int
    ) -> TrainingEntity | None:
        """
        Fetch the assignment a user holds for one course, if any.

        The read behind idempotent assignment.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The user the assignment belongs to.
            course_id (int): The course being assigned.

        Returns:
            TrainingEntity | None: The existing assignment, or None.
        """
        result = await session.execute(
            select(TrainingEntity).where(
                TrainingEntity.user_id == user_id,
                TrainingEntity.course_id == course_id,
            )
        )
        return result.scalars().one_or_none()

    async def get_training_by_id(
        self, session: AsyncSession, training_id: int, for_update: bool = False
    ) -> TrainingEntity | None:
        """
        Fetch one assignment by its primary key.

        Args:
            session (AsyncSession): The active async database session.
            training_id (int): The assignment to fetch.
            for_update (bool): Take a row lock, held until this transaction
                commits. Anyone else reading the same row this way waits, and
                then reads the status this transaction wrote rather than the
                one they would otherwise still see. Required of anything that
                decides the assignment's next status from its current one; a
                plain read must not ask for it.

        Returns:
            TrainingEntity | None: The assignment, or None.
        """
        stmt = select(TrainingEntity).where(TrainingEntity.training_id == training_id)
        if for_update:
            # populate_existing so the row the lock re-read wins over anything
            # this session already had in memory for it -- the point of the
            # lock is to read what the other transaction just committed.
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        result = await session.execute(stmt)
        return result.scalars().one_or_none()
