from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.common.recruiting_enums import ApplicationStage
from backend.entity.evaluation_entity import EvaluationEntity


class EvaluationRepository:
    """Database operations for EvaluationEntity (one row per app+stage+round+evaluator)."""

    async def get(
        self,
        session: AsyncSession,
        application_id: int,
        stage: ApplicationStage,
        round: int,
        evaluator_id: int,
    ) -> EvaluationEntity | None:
        """Return one evaluator's row for an application's stage+round, or None.

        Args:
            session (AsyncSession): The active DB session.
            application_id (int): The application being evaluated.
            stage (ApplicationStage): The stage being evaluated.
            round (int): The round within that stage being evaluated.
            evaluator_id (int): The evaluator whose row to look up.

        Returns:
            EvaluationEntity | None: The evaluator's row, if it exists.
        """
        result = await session.execute(
            select(EvaluationEntity).where(
                EvaluationEntity.application_id == application_id,
                EvaluationEntity.stage == stage,
                EvaluationEntity.round == round,
                EvaluationEntity.evaluator_id == evaluator_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_draft(
        self,
        session: AsyncSession,
        application_id: int,
        stage: ApplicationStage,
        round: int,
        evaluator_id: int,
        responses: dict,
    ) -> EvaluationEntity:
        """Create or update an unconfirmed evaluation draft.

        Args:
            session (AsyncSession): The active DB session.
            application_id (int): The application being evaluated.
            stage (ApplicationStage): The stage being evaluated.
            round (int): The round within that stage being evaluated.
            evaluator_id (int): The evaluator writing this draft.
            responses (dict): The rubric answers so far.

        Returns:
            EvaluationEntity: The created or updated (still unconfirmed) row.

        Raises:
            ValueError: If a row already exists for this key and is
                confirmed (immutable).
        """
        existing = await self.get(session, application_id, stage, round, evaluator_id)
        if existing is not None:
            if existing.is_confirmed:
                raise ValueError(
                    "this evaluation is already confirmed and cannot be edited"
                )
            existing.responses = responses
            session.add(existing)
            await session.flush()
            return existing
        entity = EvaluationEntity(
            application_id=application_id,
            stage=stage,
            round=round,
            evaluator_id=evaluator_id,
            responses=responses,
        )
        session.add(entity)
        await session.flush()
        return entity

    async def confirm(
        self,
        session: AsyncSession,
        evaluation: EvaluationEntity,
        confirmed_at: datetime,
    ) -> EvaluationEntity:
        """Lock an evaluation row permanently.

        Args:
            session (AsyncSession): The active DB session.
            evaluation (EvaluationEntity): The row to confirm (already loaded).
            confirmed_at (datetime): The confirmation timestamp.

        Returns:
            EvaluationEntity: The now-confirmed row.
        """
        evaluation.is_confirmed = True
        evaluation.confirmed_at = confirmed_at
        session.add(evaluation)
        await session.flush()
        return evaluation

    async def list_by_application(
        self, session: AsyncSession, application_id: int
    ) -> list[EvaluationEntity]:
        """Every evaluation row for an application, across all stages it has visited.

        Args:
            session (AsyncSession): The active DB session.
            application_id (int): The application whose rows to list.

        Returns:
            list[EvaluationEntity]: Unordered; one row per (stage, evaluator)
                pair that has ever submitted a draft or confirmation for
                this application. Used by the owner's history summary and,
                filtered client-side by stage, by the current-stage
                assignee's rubric pre-fill.
        """
        result = await session.execute(
            select(EvaluationEntity).where(
                EvaluationEntity.application_id == application_id
            )
        )
        return list(result.scalars().all())

    async def list_by_assignee(
        self, session: AsyncSession, assignee_id: int
    ) -> list[EvaluationEntity]:
        """Every evaluation row (draft or confirmed) written by one evaluator.

        Args:
            session (AsyncSession): The active DB session.
            assignee_id (int): The evaluator whose rows to list.

        Returns:
            list[EvaluationEntity]: Unordered; the service layer joins these
                against application_assignment/application/job for display.
        """
        result = await session.execute(
            select(EvaluationEntity).where(EvaluationEntity.evaluator_id == assignee_id)
        )
        return list(result.scalars().all())
