from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.dto.evaluation_dto import EvaluationDto, EvaluationSubmitDto, MyEvaluationDto
from backend.dto.user_context_dto import UserContextDto
from backend.recruiting import evaluation_rubric


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
        recruiting_mapper,
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
            recruiting_mapper (RecruitingMapper): Entity->DTO conversion.
        """
        self.application_repository = application_repository
        self.application_assignment_repository = application_assignment_repository
        self.evaluation_repository = evaluation_repository
        self.job_repository = job_repository
        self.users_repository = users_repository
        self.recruiting_mapper = recruiting_mapper

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
            session, application_id, application.stage, current_user.user_id, dto.responses
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
                session, assignment.application_id, assignment.stage, current_user.user_id
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
                    is_confirmed=bool(evaluation is not None and evaluation.is_confirmed),
                )
            )
        return result
