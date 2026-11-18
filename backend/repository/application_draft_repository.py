from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.application_draft_entity import ApplicationDraftEntity
from backend.entity.job_entity import JobEntity


class ApplicationDraftRepository:
    """Database operations for ApplicationDraftEntity: at most one draft per
    (user, job)."""

    async def get(
        self, session: AsyncSession, user_id: int, job_id: int
    ) -> ApplicationDraftEntity | None:
        """Return the user's draft for a job, or None.

        Args:
            session (AsyncSession): The active DB session.
            user_id (int): The draft's owner.
            job_id (int): The posting the draft is for.

        Returns:
            ApplicationDraftEntity | None: The draft, or None if there is none.
        """
        result = await session.execute(
            select(ApplicationDraftEntity).where(
                ApplicationDraftEntity.user_id == user_id,
                ApplicationDraftEntity.job_id == job_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self, session: AsyncSession, user_id: int, job_id: int, content: dict
    ) -> ApplicationDraftEntity:
        """Create the user's draft for a job, or overwrite its content.

        One statement rather than a read and an insert, so two first saves
        that overlap end as one row instead of a unique violation.
        ``created_datetime`` keeps the time of the first save;
        ``updated_timestamp`` moves on every save.

        Args:
            session (AsyncSession): The active DB session.
            user_id (int): The draft's owner.
            job_id (int): The posting the draft is for.
            content (dict): The form state to store, replacing any before it.

        Returns:
            ApplicationDraftEntity: The stored row.
        """
        statement = (
            insert(ApplicationDraftEntity)
            .values(user_id=user_id, job_id=job_id, content=content)
            .on_conflict_do_update(
                index_elements=[
                    ApplicationDraftEntity.user_id,
                    ApplicationDraftEntity.job_id,
                ],
                set_={"content": content, "updated_timestamp": func.now()},
            )
            .returning(ApplicationDraftEntity)
        )
        result = await session.execute(
            statement, execution_options={"populate_existing": True}
        )
        return result.scalars().one()

    async def delete(self, session: AsyncSession, user_id: int, job_id: int) -> None:
        """Remove the user's draft for a job, if there is one.

        Args:
            session (AsyncSession): The active DB session.
            user_id (int): The draft's owner.
            job_id (int): The posting the draft is for.
        """
        await session.execute(
            delete(ApplicationDraftEntity).where(
                ApplicationDraftEntity.user_id == user_id,
                ApplicationDraftEntity.job_id == job_id,
            )
        )

    async def list_by_user_with_job(
        self, session: AsyncSession, user_id: int
    ) -> list[tuple[ApplicationDraftEntity, JobEntity]]:
        """Return every draft the user holds, joined with its job.

        Args:
            session (AsyncSession): The active DB session.
            user_id (int): The drafts' owner.

        Returns:
            list[tuple[ApplicationDraftEntity, JobEntity]]: (draft, job) pairs,
                most recently saved first, newest id breaking ties.
        """
        result = await session.execute(
            select(ApplicationDraftEntity, JobEntity)
            .join(JobEntity, ApplicationDraftEntity.job_id == JobEntity.job_id)
            .where(ApplicationDraftEntity.user_id == user_id)
            .order_by(
                ApplicationDraftEntity.updated_timestamp.desc(),
                ApplicationDraftEntity.application_draft_id.desc(),
            )
        )
        return [tuple(row) for row in result.all()]
