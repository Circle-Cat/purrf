import logging
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend.common.mentorship_enums import (
    CommunicationMethod,
    ParticipantRole,
    TrainingCategory,
)
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.application_entity import ApplicationEntity
from backend.entity.event_entity import EventEntity
from backend.entity.job_entity import JobEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.notification_entity import NotificationEntity
from backend.entity.training_entity import TrainingEntity

from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_progress_entity import TrainingProgressEntity
from backend.entity.users_entity import UsersEntity
from backend.mentorship import recipient_resolvers  # noqa: F401 (registers)
from backend.mentorship.mentorship_admission_service import (
    MentorshipAdmissionService,
)
from backend.mentorship.onboarding_training_service import OnboardingTrainingService
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
from backend.repository.training_course_repository import TrainingCourseRepository
from backend.repository.training_progress_repository import TrainingProgressRepository
from backend.repository.training_repository import TrainingRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

# Offsets from now, not fixed dates: `get_open_mentor_registration_round`
# compares these against the real wall clock, so a hard-coded deadline stops
# being open the moment it passes and takes this file red with it.
_NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _at(days: int) -> str:
    """A round timestamp `days` from now, in the shape the admin API writes
    into the round's JSONB description -- stored and asserted verbatim."""
    return (_NOW + timedelta(days=days)).isoformat()


_PROMOTION = _at(-20)
_DEADLINE = _at(40)
_MATCHING = _at(55)
# Open too, but closing before `_DEADLINE`, so it is the one to register for.
_SOONER_DEADLINE = _at(5)


class MentorshipAdmissionServiceTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.course_repository = TrainingCourseRepository()
        self.progress_repository = TrainingProgressRepository()
        self.service = MentorshipAdmissionService(
            logger=logging.getLogger(__name__),
            onboarding_training_service=OnboardingTrainingService(
                logger=logging.getLogger(__name__),
                training_repository=TrainingRepository(),
                training_course_repository=self.course_repository,
            ),
            mentorship_round_repository=MentorshipRoundRepository(),
        )

    async def _admit(self, kind=JobKind.ACTIVITY, role=ParticipantRole.MENTOR):
        user = UsersEntity(
            first_name="Ada",
            last_name="Lovelace",
            timezone="Asia/Shanghai",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )
        await self.insert_entities([user])
        job = JobEntity(
            kind=kind, mentorship_role=role, title="Mentor", status=JobStatus.PUBLISHED
        )
        await self.insert_entities([job])
        application = ApplicationEntity(
            job_id=job.job_id, user_id=user.user_id, stage=ApplicationStage.HIRED
        )
        await self.insert_entities([application])

        await self.service.on_admitted(
            session=self.session, application=application, job=job
        )
        return user, application

    async def _open_round(self, name="2026 Fall"):
        round_entity = MentorshipRoundEntity(
            name=name,
            required_meetings=5,
            description={
                "promotion_start_at": _PROMOTION,
                "mentor_application_deadline_at": _DEADLINE,
                "match_notification_at": _MATCHING,
            },
        )
        await self.insert_entities([round_entity])
        return round_entity

    async def _events(self) -> list[EventEntity]:
        result = await self.session.execute(
            select(EventEntity).where(
                EventEntity.event_type == "mentorship.mentor_admitted"
            )
        )
        return list(result.scalars())

    async def _notified_user_ids(self) -> set[int]:
        result = await self.session.execute(select(NotificationEntity.user_id))
        return set(result.scalars())

    async def _training_categories(self, user_id: int) -> set[TrainingCategory]:
        result = await self.session.execute(
            select(TrainingEntity.category).where(TrainingEntity.user_id == user_id)
        )
        return set(result.scalars())

    async def _training(self, user_id: int) -> TrainingEntity:
        result = await self.session.execute(
            select(TrainingEntity).where(TrainingEntity.user_id == user_id)
        )
        return result.scalars().one()

    async def _seed_course(self, category: TrainingCategory) -> TrainingCourseEntity:
        """The catalogue row the migration seeds for a category."""
        result = await self.session.execute(
            select(TrainingCourseEntity).where(
                TrainingCourseEntity.category == category
            )
        )
        return result.scalars().one()

    async def _assigned_count(self, course_id: int) -> int:
        counts = {
            course.course_id: count
            for course, count in await self.course_repository.list_courses(self.session)
        }
        return counts[course_id]

    async def test_an_admitted_mentor_is_notified(self):
        """The regression ``actor_id=None`` exists to prevent: on the
        auto-hire paths the acting user is the applicant, and an event that
        recorded them as the actor would discard the only recipient."""
        await self._open_round()

        user, _ = await self._admit()

        self.assertEqual(await self._notified_user_ids(), {user.user_id})

    async def test_the_event_names_no_actor(self):
        await self._open_round()

        await self._admit()

        (event,) = await self._events()
        self.assertIsNone(event.actor_id)

    async def test_the_open_round_is_snapshotted_verbatim(self):
        """Stored as found, not parsed and re-serialised: the renderer owns
        the one tolerant parse, and a redelivery must render what admission
        saw rather than whichever round is open by then."""
        round_entity = await self._open_round()

        await self._admit()

        (event,) = await self._events()
        self.assertEqual(
            event.details,
            {
                "mentorshipRole": "mentor",
                "roundId": round_entity.round_id,
                "roundName": "2026 Fall",
                "registrationDeadlineAt": _DEADLINE,
                "matchNotificationAt": _MATCHING,
            },
        )

    async def test_the_round_closing_soonest_wins(self):
        await self._open_round(name="2027 Spring")
        soonest = MentorshipRoundEntity(
            name="2026 Fall",
            required_meetings=5,
            description={
                "promotion_start_at": _PROMOTION,
                "mentor_application_deadline_at": _SOONER_DEADLINE,
                "match_notification_at": _MATCHING,
            },
        )
        await self.insert_entities([soonest])

        await self._admit()

        (event,) = await self._events()
        self.assertEqual(event.details["roundName"], "2026 Fall")

    async def test_no_open_round_records_the_event_with_nulls(self):
        """Still an event -- the person is still admitted and still hears
        about it; the copy just cannot promise dates."""
        await self._admit()

        (event,) = await self._events()
        self.assertEqual(
            event.details,
            {
                "mentorshipRole": "mentor",
                "roundId": None,
                "roundName": None,
                "registrationDeadlineAt": None,
                "matchNotificationAt": None,
            },
        )

    async def test_an_admitted_mentee_is_not_notified(self):
        await self._open_round()

        await self._admit(role=ParticipantRole.MENTEE)

        self.assertEqual(await self._events(), [])
        self.assertEqual(await self._notified_user_ids(), set())

    async def test_a_non_mentorship_activity_records_nothing(self):
        await self._open_round()

        await self._admit(role=None)

        self.assertEqual(await self._events(), [])

    async def test_an_employment_posting_records_nothing(self):
        await self._open_round()

        await self._admit(kind=JobKind.EMPLOYMENT, role=None)

        self.assertEqual(await self._events(), [])

    async def test_a_mentor_still_gets_the_onboarding_training(self):
        user, _ = await self._admit()

        self.assertEqual(
            await self._training_categories(user.user_id),
            {TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING},
        )

    async def test_a_mentee_still_gets_the_onboarding_training(self):
        """Admission assigns training to both roles; only the email is
        mentor-only."""
        user, _ = await self._admit(role=ParticipantRole.MENTEE)

        self.assertEqual(
            await self._training_categories(user.user_id),
            {TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING},
        )

    async def test_an_employment_posting_assigns_no_training(self):
        user, _ = await self._admit(kind=JobKind.EMPLOYMENT, role=None)

        self.assertEqual(await self._training_categories(user.user_id), set())

    async def test_the_training_it_creates_points_at_the_seed_course(self):
        """Without the course id the learner cannot open the course at all."""
        user, _ = await self._admit()

        course = await self._seed_course(TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING)
        training = await self._training(user.user_id)
        self.assertEqual(training.course_id, course.course_id)

    async def test_the_seed_course_counts_the_people_admission_assigned_it_to(self):
        """The number the admin page shows before deactivating or overwriting
        a course -- it has to include the automatic dispatch."""
        course = await self._seed_course(TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING)
        before = await self._assigned_count(course.course_id)

        await self._admit()

        self.assertEqual(await self._assigned_count(course.course_id), before + 1)

    async def test_clearing_resume_state_reaches_an_admission_created_row(self):
        """An overwrite promises to drop stale suspend_data for everyone on
        the course."""
        user, _ = await self._admit()
        training = await self._training(user.user_id)
        progress = TrainingProgressEntity(
            training_id=training.training_id,
            lesson_status="incomplete",
            lesson_location="Summary",
            suspend_data="stale",
        )
        await self.insert_entities([progress])
        course = await self._seed_course(TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING)

        cleared = await self.progress_repository.clear_resume_state(
            self.session, course.course_id
        )

        self.assertEqual(cleared, 1)
        await self.session.refresh(progress)
        self.assertIsNone(progress.suspend_data)


if __name__ == "__main__":
    unittest.main()
