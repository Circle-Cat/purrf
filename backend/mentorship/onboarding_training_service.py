from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.training_links import external_link_for
from backend.common.mentorship_enums import (
    ParticipantRole,
    TrainingCategory,
    TrainingPackageState,
    TrainingStatus,
)
from backend.common.recruiting_enums import JobKind
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_entity import TrainingEntity

_ROLE_TO_CATEGORY = {
    ParticipantRole.MENTOR: TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
    ParticipantRole.MENTEE: TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
}


class OnboardingTrainingService:
    """Creates a participant's mentorship onboarding training task.

    The task is assigned at admission rather than at round registration, so
    someone admitted to a mentor/mentee activity posting can start the
    training straight away instead of waiting for a registration window. The
    row is therefore created with no deadline; RegistrationService stamps one
    the first time the user registers for a round.
    """

    def __init__(
        self,
        logger,
        training_repository,
        training_course_repository,
        training_course_package_repository,
    ):
        """
        Args:
            logger: Application logger.
            training_repository (TrainingRepository): Training data access.
            training_course_repository (TrainingCourseRepository): Resolves the
                category into the course the row must point at.
            training_course_package_repository (TrainingCoursePackageRepository):
                Reads whether the course has a live package.
        """
        self.logger = logger
        self.training_repo = training_repository
        self.training_course_repo = training_course_repository
        self.training_course_package_repo = training_course_package_repository

    async def ensure_for_admitted(
        self, session: AsyncSession, user_id: int, job
    ) -> None:
        """Assign the onboarding training a newly admitted participant owes.

        A no-op unless `job` is an ACTIVITY posting with a mentor/mentee
        `mentorship_role` — employment postings and non-mentorship activities
        carry no onboarding training.

        Admission does not know a deadline: the task is assigned so it can be
        started right away, and only the participant's first round
        registration fixes a due date. Idempotent, so being admitted twice
        into the same role neither duplicates nor resets the task.

        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The admitted user.
            job (JobEntity): The posting they were admitted to.
        """
        if job.kind != JobKind.ACTIVITY or job.mentorship_role is None:
            return

        category = _ROLE_TO_CATEGORY.get(job.mentorship_role)
        if category is None:
            return

        await self.ensure_onboarding_training(
            session=session, user_id=user_id, category=category
        )

    async def ensure_onboarding_training(
        self,
        session: AsyncSession,
        user_id: int,
        category: TrainingCategory,
        deadline: datetime | None = None,
    ) -> TrainingEntity:
        """Make sure a user holds an onboarding task, recording a known deadline.

        One rule shared by both moments that can produce the task:

        - No row yet: create it, carrying `deadline` (null at admission, set
          when a user admitted before this flow existed registers directly).
        - Row exists with no deadline: this is the first time a deadline is
          known, so stamp it. Done regardless of completion status — the
          deadline records the row's due date rather than gating anything.
        - Row exists with a deadline: left alone. Later registrations never
          recompute it.

        Either way the row ends up carrying the course its category stands
        for: that is what the learner opens, what the admin page counts, and
        what an overwrite clears resume state by.

        Does not commit. The caller owns the transaction, so the training row
        and the decision that caused it stand or fall together.

        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The user who owes the training.
            category (TrainingCategory): Which onboarding training.
            deadline (datetime | None): The due date, when one is known yet.

        Returns:
            TrainingEntity: The existing or newly created row.
        """
        existing = await self.training_repo.get_training_by_user_id_and_category(
            session=session, user_id=user_id, category=category
        )
        course = await self._course_for(session=session, category=category)
        course_id = course.course_id if course is not None else None
        has_live_package = course is not None and (
            await self.training_course_package_repo.get_by_state(
                session, course.course_id, TrainingPackageState.LIVE
            )
            is not None
        )
        # Nothing once we serve the package ourselves. The profile page prefers
        # a stored link over the in-app course, so a link written here after an
        # upload is what the learner follows -- and nothing out there is ever
        # recorded against this row.
        link = None if has_live_package else (external_link_for(category))

        if existing is None:
            created = await self.training_repo.upsert_training(
                session=session,
                entity=TrainingEntity(
                    user_id=user_id,
                    category=category,
                    course_id=course_id,
                    status=TrainingStatus.TO_DO,
                    completed_timestamp=None,
                    deadline=deadline,
                    link=link,
                ),
            )
            self.logger.info(
                "[OnboardingTrainingService] assigned %s to user %s.",
                category.value,
                user_id,
            )
            return created

        changed = False

        # A row from before this path attached a course carries none, and
        # without one its owner cannot open the course at all. Attaching it on
        # the next touch heals those rows in place.
        if existing.course_id is None and course_id is not None:
            existing.course_id = course_id
            changed = True

        if deadline is not None and existing.deadline is None:
            existing.deadline = deadline
            changed = True

        if changed:
            return await self.training_repo.upsert_training(
                session=session, entity=existing
            )

        return existing

    async def _course_for(
        self, session: AsyncSession, category: TrainingCategory
    ) -> TrainingCourseEntity | None:
        """The seed course this category stands for, if the catalogue holds it.

        None rather than an error when it does not: the training task itself
        is what admission owes the participant, and refusing to record it
        because the catalogue is short a row would cost more than the course
        being unopenable until somebody seeds it.
        """
        course = await self.training_course_repo.get_course_by_category(
            session=session, category=category
        )
        if course is None:
            self.logger.warning(
                "[OnboardingTrainingService] no course carries category %s; "
                "the row for this user will not be openable.",
                category.value,
            )
            return None
        return course
