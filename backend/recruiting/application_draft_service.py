from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.recruiting_enums import (
    ApplicationStage,
    PUBLICLY_VISIBLE_JOB_STATUSES,
)
from backend.dto.application_dto import ApplicationDraftDto, ApplicationDraftSaveDto
from backend.dto.user_context_dto import UserContextDto


class ApplicationDraftService:
    """A candidate's private, unsubmitted application drafts.

    A draft is not an application: nothing here touches the ``application``
    table, and staff never read drafts. Submitting goes through
    ``ApplicationService.submit``, which deletes the draft it replaces.
    """

    def __init__(
        self,
        application_draft_repository,
        application_repository,
        job_repository,
        recruiting_mapper,
    ):
        """
        Args:
            application_draft_repository (ApplicationDraftRepository): Draft
                data access.
            application_repository (ApplicationRepository): Reads the caller's
                latest application, to refuse a draft beside a live one.
            job_repository (JobRepository): Posting data access.
            recruiting_mapper (RecruitingMapper): Entity to DTO conversion.
        """
        self.application_draft_repository = application_draft_repository
        self.application_repository = application_repository
        self.job_repository = job_repository
        self.recruiting_mapper = recruiting_mapper

    async def get_mine(
        self, session: AsyncSession, current_user: UserContextDto, job_id: int
    ) -> ApplicationDraftDto | None:
        """Return the caller's draft for a job, or None.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated candidate.
            job_id (int): The posting to look up.

        Returns:
            ApplicationDraftDto | None: The saved draft, or None if absent.
        """
        draft = await self.application_draft_repository.get(
            session, current_user.user_id, job_id
        )
        if draft is None:
            return None
        return self.recruiting_mapper.to_application_draft_dto(draft)

    async def save(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        dto: ApplicationDraftSaveDto,
    ) -> ApplicationDraftDto:
        """Create or overwrite the caller's draft for a job.

        Refused where ``ApplicationService.submit`` would refuse the
        submission it leads to for reasons the candidate cannot fix by editing
        the form: the posting is missing or not live, or the caller already
        has an application for it that is not REJECTED. A rejected candidate
        may draft a reapplication.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated candidate.
            dto (ApplicationDraftSaveDto): The form state to store.

        Returns:
            ApplicationDraftDto: The stored draft.

        Raises:
            ValueError: If the posting is missing or not live, or the caller
                already has an active application for it.
        """
        job = await self.job_repository.get_by_job_id(session, dto.job_id)
        if job is None or job.status not in PUBLICLY_VISIBLE_JOB_STATUSES:
            raise ValueError(f"Published job {dto.job_id} not found")
        existing = await self.application_repository.get_latest_by_job_and_user(
            session, dto.job_id, current_user.user_id
        )
        if existing is not None and existing.stage != ApplicationStage.REJECTED:
            raise ValueError("you already have an application for this job")
        draft = await self.application_draft_repository.upsert(
            session,
            current_user.user_id,
            dto.job_id,
            {
                "personal": dto.personal,
                "education": dto.education,
                "experience": dto.experience,
                "answers": dto.answers,
                "resumeSha256": dto.resume_sha256,
                "resumeObjectKey": dto.resume_object_key,
            },
        )
        await session.commit()
        return self.recruiting_mapper.to_application_draft_dto(draft)
