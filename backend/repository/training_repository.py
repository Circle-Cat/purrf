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
    ) -> list[tuple[TrainingEntity, str | None, bool, bool]]:
        """Fetch a user's training records, each with its course name,
        whether that course has a live package, and whether it is still
        active.

        Outer joined: course_id is nullable, and a row without one is still
        the user's assignment and still has to be shown.

        The first boolean is what tells the caller a course we serve apart
        from one nobody has uploaded to, or has only a package still pending
        verification. Resolving an actual object key is the content route's
        job, per request.

        The second is whether the course is still open. A deactivated course
        is closed to the people already assigned it, not only to new
        assignments, so the row has to carry the reason it can no longer be
        started. A row with no course reads as active: there is no course to
        have closed, and the legacy link rows are all of them.
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
                TrainingCourseEntity.is_active,
            )
            .outerjoin(
                TrainingCourseEntity,
                TrainingEntity.course_id == TrainingCourseEntity.course_id,
            )
            .where(TrainingEntity.user_id == user_id)
        )
        return [(row[0], row[1], row[2], row[3] is not False) for row in result.all()]

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

    async def get_training_by_user_ids_and_course_id(
        self,
        session: AsyncSession,
        user_ids: list[int],
        course_id: int,
    ) -> dict[int, TrainingEntity]:
        """
        Batch-fetch the rows several people hold for one course.

        One query for a whole cohort: a bulk assignment has to know who
        already holds the course, and asking per person would be a thousand
        sequential round trips inside one open write transaction.

        Args:
            session (AsyncSession): The active async database session.
            user_ids (list[int]): The people to look up.
            course_id (int): The course they may hold.

        Returns:
            dict[int, TrainingEntity]: {user_id: row} for the people who hold
            it. Anybody without a row is simply absent. Empty for no users.
        """
        if not user_ids:
            return {}
        result = await session.execute(
            select(TrainingEntity).where(
                TrainingEntity.user_id.in_(user_ids),
                TrainingEntity.course_id == course_id,
            )
        )
        return {row.user_id: row for row in result.scalars().all()}

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

    async def add_trainings(
        self, session: AsyncSession, entities: list[TrainingEntity]
    ) -> None:
        """Appends training rows, giving each its training_id.

        For rows that are new: an insert, not the SELECT-then-merge
        ``upsert_training`` does. Passing an empty list is meaningful, not a
        no-op -- the flush still writes whatever else the caller has made
        dirty in this session, which is how a bulk assign that only adopts
        existing rows gets those adoptions written.

        Args:
            session (AsyncSession): Active async session. Not committed.
            entities (list[TrainingEntity]): Rows to append, possibly empty.
        """
        session.add_all(entities)
        await session.flush()

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
