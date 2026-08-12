from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ApplicationSubmissionRepository:
    """Database operations for append-only application submission versions."""

    async def get_current(
        self, session: AsyncSession, application_id: int
    ) -> ApplicationSubmissionEntity | None:
        """Return the highest-version submission for an application, or None."""
        result = await session.execute(
            select(ApplicationSubmissionEntity)
            .where(ApplicationSubmissionEntity.application_id == application_id)
            .order_by(ApplicationSubmissionEntity.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_by_user(
        self, session: AsyncSession, user_id: int
    ) -> ApplicationSubmissionEntity | None:
        """Return a candidate's most recent submission across every job.

        The application form uses it to fall back on when a candidate has
        applied before but never saved anything to their profile: rather than
        make them retype what they already sent once, it starts them from it.

        Ordered by ``submitted_at``, nulls last so a row that somehow lacks one
        can never outrank a real submission, and broken by ``submission_id``
        so two submissions in the same instant still order the same way twice.

        Args:
            session (AsyncSession): The active DB session.
            user_id (int): The candidate whose submissions to search.

        Returns:
            ApplicationSubmissionEntity | None: None when they have never
                submitted anything.
        """
        result = await session.execute(
            select(ApplicationSubmissionEntity)
            .join(
                ApplicationEntity,
                ApplicationSubmissionEntity.application_id
                == ApplicationEntity.application_id,
            )
            .where(ApplicationEntity.user_id == user_id)
            .order_by(
                ApplicationSubmissionEntity.submitted_at.desc().nullslast(),
                ApplicationSubmissionEntity.submission_id.desc(),
            )
            .limit(1)
        )
        return result.scalars().first()

    async def list_by_application(
        self, session: AsyncSession, application_id: int
    ) -> list[ApplicationSubmissionEntity]:
        """Return all submission versions for an application, ascending by version."""
        result = await session.execute(
            select(ApplicationSubmissionEntity)
            .where(ApplicationSubmissionEntity.application_id == application_id)
            .order_by(ApplicationSubmissionEntity.version.asc())
        )
        return list(result.scalars().all())

    async def create(
        self, session: AsyncSession, entity: ApplicationSubmissionEntity
    ) -> ApplicationSubmissionEntity:
        """Insert a submission version and flush so its submission_id is populated."""
        session.add(entity)
        await session.flush()
        return entity

    async def update(
        self, session: AsyncSession, entity: ApplicationSubmissionEntity
    ) -> ApplicationSubmissionEntity:
        """Persist mutations to a submission version."""
        merged = await session.merge(entity)
        await session.flush()
        return merged
