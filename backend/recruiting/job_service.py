from backend.entity.job_entity import JobEntity
from backend.repository.job_repository import JobRepository
from backend.repository.user_permissions_repository import UserPermissionsRepository
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.dto.job_dto import JobCreateDto, JobDto
from backend.dto.job_review_dto import ApproverDto
from backend.common.permissions import Permission
from backend.common.recruiting_enums import JobStatus
from sqlalchemy.ext.asyncio import AsyncSession


class JobService:
    """Manages recruiting postings (create/edit/publish/close)."""

    def __init__(
        self,
        job_repository: JobRepository,
        recruiting_mapper: RecruitingMapper,
        user_permissions_repository: UserPermissionsRepository,
    ):
        """
        Initialise the service with its repositories and mapper.

        Args:
            job_repository (JobRepository): Data-access layer for JobEntity.
            recruiting_mapper (RecruitingMapper): Entity-to-DTO converter.
            user_permissions_repository (UserPermissionsRepository): Used to
                resolve who may approve postings.
        """
        self.job_repository = job_repository
        self.recruiting_mapper = recruiting_mapper
        self.user_permissions_repository = user_permissions_repository

    async def list_active_approvers(
        self, session: AsyncSession
    ) -> list[ApproverDto]:
        """List active users who may approve postings (hold job.approve).

        Args:
            session (AsyncSession): Active database async session.

        Returns:
            list[ApproverDto]: One entry per active approver.
        """
        users = await self.user_permissions_repository.get_active_users_with_permission(
            session, Permission.RECRUITING_JOB_APPROVE.value
        )
        return [self.recruiting_mapper.to_approver_dto(u) for u in users]

    async def create_job(self, session: AsyncSession, dto: JobCreateDto) -> JobDto:
        """Create a DRAFT posting from a JobCreateDto.

        Args:
            session (AsyncSession): Active database async session.
            dto (JobCreateDto): Payload with posting fields.

        Returns:
            JobDto: The newly created posting, including its assigned id.
        """
        job = JobEntity(
            kind=dto.kind,
            mentorship_role=dto.mentorship_role,
            status=JobStatus.DRAFT,
            title=dto.title,
            description=dto.description,
            form_schema=dto.form_schema,
            pipeline_config=dto.pipeline_config,
        )
        job = await self.job_repository.create_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def update_job(
        self, session: AsyncSession, job_id: int, dto: JobCreateDto
    ) -> JobDto:
        """Update a posting's editable fields.

        A DRAFT posting is edited in place. Editing the form schema or pipeline
        of a PUBLISHED posting does not touch the live version: the change is
        parked in pending_form_schema/pending_pipeline_config and the status
        flips to PUBLISHED_PENDING_REVISION until a reviewer approves it.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the posting to update.
            dto (JobCreateDto): New values for editable fields.

        Returns:
            JobDto: The updated posting.

        Raises:
            ValueError: If no posting with the given id exists.
        """
        job = await self._require_job(session, job_id)
        if job.status == JobStatus.PUBLISHED and (
            dto.form_schema != job.form_schema
            or dto.pipeline_config != job.pipeline_config
        ):
            job.pending_form_schema = dto.form_schema
            job.pending_pipeline_config = dto.pipeline_config
            job.status = JobStatus.PUBLISHED_PENDING_REVISION
        else:
            job.title = dto.title
            job.description = dto.description
            job.kind = dto.kind
            job.mentorship_role = dto.mentorship_role
            job.form_schema = dto.form_schema
            job.pipeline_config = dto.pipeline_config
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def publish_job(self, session: AsyncSession, job_id: int) -> JobDto:
        """Transition a posting to PUBLISHED.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the posting to publish.

        Returns:
            JobDto: The posting with status PUBLISHED.

        Raises:
            ValueError: If no posting with the given id exists.
        """
        job = await self._require_job(session, job_id)
        job.status = JobStatus.PUBLISHED
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def close_job(self, session: AsyncSession, job_id: int) -> JobDto:
        """Transition a posting to CLOSED.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the posting to close.

        Returns:
            JobDto: The posting with status CLOSED.

        Raises:
            ValueError: If no posting with the given id exists.
        """
        job = await self._require_job(session, job_id)
        job.status = JobStatus.CLOSED
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def reopen_job(self, session: AsyncSession, job_id: int) -> JobDto:
        """Reopen a CLOSED posting, returning it to PUBLISHED.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the posting to reopen.

        Returns:
            JobDto: The posting with status PUBLISHED.

        Raises:
            ValueError: If the posting does not exist or is not CLOSED.
        """
        job = await self._require_job(session, job_id)
        if job.status != JobStatus.CLOSED:
            raise ValueError(f"Job {job_id} is not closed; cannot reopen")
        job.status = JobStatus.PUBLISHED
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def list_published(self, session: AsyncSession) -> list[JobDto]:
        """List all PUBLISHED postings.

        Args:
            session (AsyncSession): Active database async session.

        Returns:
            list[JobDto]: All currently published postings.
        """
        jobs = await self.job_repository.list_published(session)
        return [self.recruiting_mapper.to_job_dto(j) for j in jobs]

    async def get_job(self, session: AsyncSession, job_id: int) -> JobDto:
        """Fetch one posting by id.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the posting to retrieve.

        Returns:
            JobDto: The requested posting.

        Raises:
            ValueError: If no posting with the given id exists.
        """
        job = await self._require_job(session, job_id)
        return self.recruiting_mapper.to_job_dto(job)

    async def _require_job(self, session: AsyncSession, job_id: int) -> JobEntity:
        """Return the JobEntity for job_id, or raise ValueError if absent.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier to look up.

        Returns:
            JobEntity: The found entity.

        Raises:
            ValueError: If the job does not exist.
        """
        job = await self.job_repository.get_by_job_id(session, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        return job
