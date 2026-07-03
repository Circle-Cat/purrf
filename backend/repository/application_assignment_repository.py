from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.common.recruiting_enums import ApplicationStage
from backend.entity.application_assignment_entity import ApplicationAssignmentEntity


class ApplicationAssignmentRepository:
    """Database operations for ApplicationAssignmentEntity (one row per app+stage)."""

    async def get(
        self, session: AsyncSession, application_id: int, stage: ApplicationStage
    ) -> ApplicationAssignmentEntity | None:
        """Return the current assignment for an application's stage, or None.

        Args:
            session (AsyncSession): The active DB session.
            application_id (int): The application to look up.
            stage (ApplicationStage): The stage to look up.

        Returns:
            ApplicationAssignmentEntity | None: The active assignment row.
        """
        result = await session.execute(
            select(ApplicationAssignmentEntity).where(
                ApplicationAssignmentEntity.application_id == application_id,
                ApplicationAssignmentEntity.stage == stage,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        session: AsyncSession,
        application_id: int,
        stage: ApplicationStage,
        assignee_id: int,
        assigned_by: int,
    ) -> ApplicationAssignmentEntity:
        """Create or overwrite the assignment for an application's stage.

        One active assignee at a time per (application_id, stage): a second
        call on the same pair updates the existing row rather than creating
        a duplicate.

        Args:
            session (AsyncSession): The active DB session.
            application_id (int): The application being assigned.
            stage (ApplicationStage): The stage being assigned.
            assignee_id (int): The user now responsible for this stage.
            assigned_by (int): The owner who made this assignment.

        Returns:
            ApplicationAssignmentEntity: The created or updated row.
        """
        existing = await self.get(session, application_id, stage)
        if existing is not None:
            existing.assignee_id = assignee_id
            existing.assigned_by = assigned_by
            existing.assigned_at = datetime.now(timezone.utc)
            session.add(existing)
            await session.flush()
            return existing
        entity = ApplicationAssignmentEntity(
            application_id=application_id,
            stage=stage,
            assignee_id=assignee_id,
            assigned_by=assigned_by,
        )
        session.add(entity)
        await session.flush()
        return entity

    async def list_by_assignee(
        self, session: AsyncSession, assignee_id: int
    ) -> list[ApplicationAssignmentEntity]:
        """Every active assignment currently held by one user.

        Args:
            session (AsyncSession): The active DB session.
            assignee_id (int): The user whose assignments to list.

        Returns:
            list[ApplicationAssignmentEntity]: Unordered.
        """
        result = await session.execute(
            select(ApplicationAssignmentEntity).where(
                ApplicationAssignmentEntity.assignee_id == assignee_id
            )
        )
        return list(result.scalars().all())
