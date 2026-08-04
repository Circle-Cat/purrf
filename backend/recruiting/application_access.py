from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.permissions import Permission
from backend.dto.user_context_dto import UserContextDto
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.recruiting.pipeline_owners import normalized_owner_ids


class ApplicationAccess:
    """Shared application-access gating, used by ``BoardService`` and
    ``InterviewSchedulingService``.

    Extracted verbatim from ``BoardService._load_owned_application`` /
    ``._validate_interview_assignee`` (same behaviour, same error messages)
    so both services share one implementation instead of one copying the
    other's private methods. ``BoardService`` keeps its own
    ``_load_owned_application``/``_validate_interview_assignee`` as one-line
    delegations to this class, so its existing call sites and tests are
    untouched.
    """

    def __init__(
        self,
        application_repository,
        job_repository,
        application_assignment_repository,
        user_permissions_repository,
    ):
        """
        Args:
            application_repository (ApplicationRepository): Application data access.
            job_repository (JobRepository): Posting data access.
            application_assignment_repository (ApplicationAssignmentRepository):
                Per-(application, stage, round) interviewer assignment data
                access, used to check assignee standing.
            user_permissions_repository (UserPermissionsRepository): Used to
                verify a proposed assignee actively holds
                ``Permission.RECRUITING_INTERVIEW_EVALUATE``.
        """
        self.application_repository = application_repository
        self.job_repository = job_repository
        self.application_assignment_repository = application_assignment_repository
        self.user_permissions_repository = user_permissions_repository

    async def load_owned_application(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        *,
        for_update: bool = False,
        allow_assignee: bool = False,
        allow_self: bool = False,
        allow_read_all: bool = False,
    ) -> tuple[ApplicationEntity, JobEntity]:
        """Load an application and assert the caller may read/write it.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application to load.
            for_update (bool): When True, row-locks the application (``SELECT
                ... FOR UPDATE``) so a concurrent decision on the same
                application serialises behind this transaction.
            allow_assignee (bool): When True, a caller who is the
                application's current-stage assignee (but not an owner)
                also passes — used by the read path (``get_application_detail``)
                now that owners and assignees share one detail page.
                Mutation paths (``change_stage``,
                ``set_sub_status``, ``reassign``, ``blacklist``) leave this
                False and stay owner-only.
            allow_self (bool): When True, a caller who is the application's
                own submitter also passes, regardless of job ownership or
                assignment — used by ``get_resume`` so a candidate can read
                her own application's résumé bytes. Every other caller
                leaves this False and stays owner/assignee-only.
            allow_read_all (bool): When True, a caller who holds
                ``Permission.RECRUITING_APPLICATION_READ_ALL`` also passes,
                regardless of ownership/assignment. Read-only call sites opt
                in explicitly; every mutation path leaves this False, so
                ``read.all`` never grants a write.

        Returns:
            tuple[ApplicationEntity, JobEntity]: The application and its job.

        Raises:
            ValueError: If the application is missing, or the caller is
                none of: an owner of the application's job, (when
                ``allow_assignee`` is True) the application's current-stage
                assignee, (when ``allow_self`` is True) the application's
                own submitter, or (when ``allow_read_all`` is True) a holder
                of ``RECRUITING_APPLICATION_READ_ALL``. All cases raise the
                same generic message (mirroring
                ``ApplicationService._load_owned``) so response bodies
                don't leak which application ids exist to unauthorized
                callers.
        """
        application = await self.application_repository.get_by_id(
            session, application_id, for_update=for_update
        )
        # Missing and not-owned/not-assignee must be indistinguishable: a
        # distinct message would let any authenticated caller probe which
        # application ids exist.
        if application is None:
            raise ValueError(f"application {application_id} not found")
        job = await self.job_repository.get_by_job_id(session, application.job_id)
        is_owner = job is not None and current_user.user_id in normalized_owner_ids(
            job.pipeline_config
        )
        is_assignee = False
        if not is_owner and allow_assignee:
            assignment = await self.application_assignment_repository.get(
                session, application_id, application.stage, application.current_round
            )
            is_assignee = (
                assignment is not None
                and assignment.assignee_id == current_user.user_id
            )
        is_self = allow_self and application.user_id == current_user.user_id
        is_read_all = allow_read_all and current_user.has_permission(
            Permission.RECRUITING_APPLICATION_READ_ALL
        )
        if job is None or not (is_owner or is_assignee or is_self or is_read_all):
            raise ValueError(f"application {application_id} not found")
        return application, job

    async def validate_interview_assignee(
        self, session: AsyncSession, assignee_id: int
    ) -> None:
        """Assert an assignee is an active RECRUITING_INTERVIEW_EVALUATE holder.

        Args:
            session (AsyncSession): Active database async session.
            assignee_id (int): The proposed assignee's user id.

        Raises:
            ValueError: If ``assignee_id`` is not an active holder of
                ``Permission.RECRUITING_INTERVIEW_EVALUATE``.
        """
        pool = await self.user_permissions_repository.get_active_users_with_permission(
            session, Permission.RECRUITING_INTERVIEW_EVALUATE.value
        )
        if assignee_id not in {u.user_id for u in pool}:
            raise ValueError(
                f"assignee {assignee_id} is not an active interview evaluator"
            )
