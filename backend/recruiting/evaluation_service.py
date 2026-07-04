from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.dto.evaluation_dto import (
    EvaluationDto,
    EvaluationSubmitDto,
    MyEvaluationDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.recruiting import evaluation_rubric
from backend.recruiting.pipeline_owners import normalized_owner_ids


class EvaluationService:
    """Assignee-facing writes for interview evaluation scorecards (sub-project #3 slice 1).

    Authorization is row-level against application_assignment (is the
    caller the current stage's assignee), not an enum permission — mirrors
    BoardService's owner-gating philosophy but on the other side of the
    same application record.
    """

    def __init__(
        self,
        application_repository,
        application_assignment_repository,
        evaluation_repository,
        job_repository,
        users_repository,
    ):
        """
        Args:
            application_repository (ApplicationRepository): Application data access.
            application_assignment_repository (ApplicationAssignmentRepository):
                Assignment data access.
            evaluation_repository (EvaluationRepository): Scorecard data access.
            job_repository (JobRepository): Posting data access, for job titles
                in "My Evaluations".
            users_repository (UsersRepository): Applicant lookups, for
                applicant names in "My Evaluations".
        """
        self.application_repository = application_repository
        self.application_assignment_repository = application_assignment_repository
        self.evaluation_repository = evaluation_repository
        self.job_repository = job_repository
        self.users_repository = users_repository

    async def submit(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        dto: EvaluationSubmitDto,
    ) -> EvaluationDto:
        """Save a draft, or confirm (permanently lock) an evaluation.

        Confirming also flips the application's sub_status to "evaluated"
        so the owner knows to come review it.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application being evaluated.
            dto (EvaluationSubmitDto): The rubric answers and confirm flag.

        Returns:
            EvaluationDto: The saved (or now-confirmed) row.

        Raises:
            ValueError: If the application is missing, the caller is not the
                current stage's assignee, the responses fail rubric
                validation (incomplete on confirm, or malformed), or the
                row is already confirmed.
        """
        application = await self.application_repository.get_by_id(
            session, application_id, for_update=True
        )
        if application is None:
            raise ValueError(f"application {application_id} not found")
        assignment = await self.application_assignment_repository.get(
            session, application_id, application.stage
        )
        if assignment is None or assignment.assignee_id != current_user.user_id:
            raise ValueError(
                "you are not the assignee for this application's current stage"
            )
        evaluation_rubric.validate_responses(
            application.stage, dto.responses, require_complete=dto.confirm
        )
        row = await self.evaluation_repository.upsert_draft(
            session,
            application_id,
            application.stage,
            current_user.user_id,
            dto.responses,
        )
        if dto.confirm:
            row = await self.evaluation_repository.confirm(
                session, row, datetime.now(timezone.utc)
            )
            application.sub_status = "evaluated"
            await self.application_repository.update(session, application)
        await session.commit()
        return EvaluationDto(
            id=row.evaluation_id,
            application_id=row.application_id,
            stage=row.stage,
            evaluator_id=row.evaluator_id,
            responses=row.responses,
            is_confirmed=row.is_confirmed,
            confirmed_at=row.confirmed_at,
        )

    async def get_mine(
        self, session: AsyncSession, current_user: UserContextDto
    ) -> list[MyEvaluationDto]:
        """List every application currently assigned to the caller.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.

        Returns:
            list[MyEvaluationDto]: One entry per assignment, with
                is_confirmed reflecting whether that stage's evaluation
                (if any has been started at all) is locked.
        """
        assignments = await self.application_assignment_repository.list_by_assignee(
            session, current_user.user_id
        )
        result = []
        for assignment in assignments:
            application = await self.application_repository.get_by_id(
                session, assignment.application_id
            )
            if application is None:
                continue
            job = await self.job_repository.get_by_job_id(session, application.job_id)
            user = await self.users_repository.get_user_by_user_id(
                session, application.user_id
            )
            evaluation = await self.evaluation_repository.get(
                session,
                assignment.application_id,
                assignment.stage,
                current_user.user_id,
            )
            result.append(
                MyEvaluationDto(
                    application_id=assignment.application_id,
                    job_title=job.title if job is not None else "",
                    applicant_name=(
                        f"{user.first_name} {user.last_name}".strip()
                        if user is not None
                        else ""
                    ),
                    stage=assignment.stage,
                    is_confirmed=bool(
                        evaluation is not None and evaluation.is_confirmed
                    ),
                )
            )
        return result

    async def get_for_application(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
    ) -> list[EvaluationDto]:
        """Return every evaluation row for an application, across all stages.

        Authorization mirrors ``BoardService.get_application_detail``: the
        caller must be either a configured owner of the application's job
        (``pipeline_owners.normalized_owner_ids``) or the assignee for the
        application's *current* stage. This is intentionally a duplicated
        inline check rather than a shared helper with ``board_service`` —
        the two services don't share enough constructor shape to make a
        lift clean, and it's a few lines (see task-18 brief / YAGNI).

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application whose evaluation rows to list.

        Returns:
            list[EvaluationDto]: Every evaluator's row for this application,
                across every stage it has visited (draft and confirmed). The
                owner's summary shows the full history; a single stage's
                rubric form filters this list client-side by ``stage``.

        Raises:
            ValueError: If the application is missing, or the caller is
                neither an owner of the application's job nor its
                current-stage assignee. Both cases raise the same generic
                message so response bodies don't leak which application ids
                exist to unauthorized callers.
        """
        application = await self.application_repository.get_by_id(
            session, application_id
        )
        if application is None:
            raise ValueError(f"application {application_id} not found")
        job = await self.job_repository.get_by_job_id(session, application.job_id)
        is_owner = job is not None and current_user.user_id in normalized_owner_ids(
            job.pipeline_config
        )
        is_assignee = False
        if not is_owner:
            assignment = await self.application_assignment_repository.get(
                session, application_id, application.stage
            )
            is_assignee = (
                assignment is not None
                and assignment.assignee_id == current_user.user_id
            )
        if job is None or not (is_owner or is_assignee):
            raise ValueError(f"application {application_id} not found")
        rows = await self.evaluation_repository.list_by_application(
            session, application_id
        )
        return [
            EvaluationDto(
                id=row.evaluation_id,
                application_id=row.application_id,
                stage=row.stage,
                evaluator_id=row.evaluator_id,
                responses=row.responses,
                is_confirmed=row.is_confirmed,
                confirmed_at=row.confirmed_at,
            )
            for row in rows
        ]
