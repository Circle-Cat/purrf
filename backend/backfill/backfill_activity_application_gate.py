import asyncio
import sys
import traceback
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.database import Database
from backend.common.logger import get_logger
from backend.common.mentorship_enums import ParticipantRole
from backend.common.recruiting_enums import ApplicationStage, JobKind
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.repository.application_repository import ApplicationRepository
from backend.repository.job_repository import JobRepository
from backend.repository.mentorship_round_participants_repository import (
    MentorshipRoundParticipantsRepository,
)

logger = get_logger()


class ActivityApplicationGateBackfillService:
    """One-time backfill: grandfathers in every legacy mentorship round
    participant so RegistrationService.update_registration_info's new
    approved-application gate doesn't lock them out.

    For every distinct (user_id, participant_role) that has ever registered
    for a mentorship round, ensures a HIRED application exists against the
    currently published ACTIVITY posting for that role - creating one if
    none exists, or promoting an existing non-HIRED application to HIRED.
    """

    def __init__(self, application_repo, job_repo, participants_repo):
        self.application_repo = application_repo
        self.job_repo = job_repo
        self.participants_repo = participants_repo

    async def backfill(self, session: AsyncSession) -> None:
        jobs = await self.job_repo.list_published(session)
        job_by_role: dict[ParticipantRole, JobEntity] = {
            job.mentorship_role: job
            for job in jobs
            if job.kind == JobKind.ACTIVITY and job.mentorship_role is not None
        }

        user_roles = await self.participants_repo.list_distinct_user_roles(session)
        for user_id, role in user_roles:
            job = job_by_role.get(role)
            if not job:
                logger.warning(
                    "No published ACTIVITY posting for role %s; skipping user %s.",
                    role,
                    user_id,
                )
                continue

            existing_hired = await self.application_repo.get_hired_activity_application(
                session=session, user_id=user_id, mentorship_role=role
            )
            if existing_hired:
                continue

            existing_application = (
                await self.application_repo.get_latest_by_job_and_user(
                    session=session, job_id=job.job_id, user_id=user_id
                )
            )
            if existing_application:
                existing_application.stage = ApplicationStage.HIRED
                existing_application.stage_entered_at = datetime.now(timezone.utc)
                await self.application_repo.update(
                    session=session, entity=existing_application
                )
                logger.info(
                    "Promoted existing application to HIRED for user %s, job %s.",
                    user_id,
                    job.job_id,
                )
                continue

            await self.application_repo.create(
                session=session,
                entity=ApplicationEntity(
                    job_id=job.job_id,
                    user_id=user_id,
                    stage=ApplicationStage.HIRED,
                    stage_entered_at=datetime.now(timezone.utc),
                ),
            )
            logger.info(
                "Created backfilled HIRED application for user %s, job %s.",
                user_id,
                job.job_id,
            )


async def main():
    logger.info("Script started...")
    db = Database(echo=True)
    service = ActivityApplicationGateBackfillService(
        application_repo=ApplicationRepository(),
        job_repo=JobRepository(),
        participants_repo=MentorshipRoundParticipantsRepository(),
    )
    async with db.session() as session:
        try:
            await service.backfill(session)
            await session.commit()
            logger.info("Backfill successful!")
        except Exception as e:
            await session.rollback()
            logger.error(f"Global backfill failure: {e}")
            raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
        logger.info("--- SCRIPT FINISHED SUCCESSFULLY ---")
    except Exception as e:
        logger.info(f"\nCRITICAL ERROR DURING EXECUTION: {e}")
        traceback.print_exc()
        sys.exit(1)
