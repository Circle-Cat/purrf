from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.common.recruiting_enums import ApplicationStage
from backend.entity.application_assignment_entity import ApplicationAssignmentEntity
from backend.entity.application_entity import ApplicationEntity
from backend.entity.users_entity import UsersEntity


class ApplicationAssignmentRepository:
    """Database operations for ApplicationAssignmentEntity (one row per app+stage+round)."""

    async def get(
        self,
        session: AsyncSession,
        application_id: int,
        stage: ApplicationStage,
        round: int,
    ) -> ApplicationAssignmentEntity | None:
        """Return the current assignment for an application's stage+round, or None.

        Args:
            session (AsyncSession): The active DB session.
            application_id (int): The application to look up.
            stage (ApplicationStage): The stage to look up.
            round (int): The round within that stage to look up.

        Returns:
            ApplicationAssignmentEntity | None: The active assignment row.
        """
        result = await session.execute(
            select(ApplicationAssignmentEntity).where(
                ApplicationAssignmentEntity.application_id == application_id,
                ApplicationAssignmentEntity.stage == stage,
                ApplicationAssignmentEntity.round == round,
            )
        )
        return result.scalar_one_or_none()

    async def get_current_assignee_ids(
        self, session: AsyncSession, application_id: int
    ) -> set[int]:
        """Who is responsible for an application right now, and can still act.

        Scoped to the application's own stage and round. This table keeps one
        row per (application, stage, round) and reassignment only overwrites
        within that key, so the rows accumulate as an application walks the
        pipeline -- unscoped, a round-one screener stays an assignee for every
        later event.

        Narrowed again to accounts that are active and not blocked. The two
        flags are read separately because blocking deliberately leaves
        is_active alone, so activity does not cover it.

        Args:
            session (AsyncSession): The active async database session.
            application_id (int): The application whose assignees are wanted.

        Returns:
            set[int]: Assignee user ids. Empty when nobody who can act holds
                the current stage and round.
        """
        result = await session.execute(
            select(func.array_agg(ApplicationAssignmentEntity.assignee_id))
            .select_from(ApplicationAssignmentEntity)
            .join(
                ApplicationEntity,
                ApplicationEntity.application_id
                == ApplicationAssignmentEntity.application_id,
            )
            .join(
                UsersEntity,
                UsersEntity.user_id == ApplicationAssignmentEntity.assignee_id,
            )
            .where(
                ApplicationAssignmentEntity.application_id == application_id,
                ApplicationAssignmentEntity.stage == ApplicationEntity.stage,
                ApplicationAssignmentEntity.round == ApplicationEntity.current_round,
                UsersEntity.is_active,
                UsersEntity.is_blocked.is_(False),
            )
        )
        return set(result.scalar_one_or_none() or ())

    async def upsert(
        self,
        session: AsyncSession,
        application_id: int,
        stage: ApplicationStage,
        round: int,
        assignee_id: int,
        assigned_by: int,
    ) -> ApplicationAssignmentEntity:
        """Create or overwrite the assignment for an application's stage+round.

        One active assignee at a time per (application_id, stage, round): a
        second call on the same triple updates the existing row rather than
        creating a duplicate.

        Args:
            session (AsyncSession): The active DB session.
            application_id (int): The application being assigned.
            stage (ApplicationStage): The stage being assigned.
            round (int): The round within that stage being assigned.
            assignee_id (int): The user now responsible for this stage+round.
            assigned_by (int): The owner who made this assignment.

        Returns:
            ApplicationAssignmentEntity: The created or updated row.
        """
        existing = await self.get(session, application_id, stage, round)
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
            round=round,
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

    async def list_by_application_ids(
        self, session: AsyncSession, application_ids: list[int]
    ) -> list[ApplicationAssignmentEntity]:
        """Every assignment row for a batch of applications, for board reads.

        Args:
            session (AsyncSession): The active DB session.
            application_ids (list[int]): The applications to fetch
                assignments for.

        Returns:
            list[ApplicationAssignmentEntity]: Unordered; ``[]`` immediately
                for an empty input (skips the query).
        """
        if not application_ids:
            return []
        result = await session.execute(
            select(ApplicationAssignmentEntity).where(
                ApplicationAssignmentEntity.application_id.in_(application_ids)
            )
        )
        return list(result.scalars().all())
