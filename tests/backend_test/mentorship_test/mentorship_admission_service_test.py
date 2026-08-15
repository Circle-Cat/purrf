import logging
import unittest
from datetime import datetime, timezone

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
from backend.entity.users_entity import UsersEntity
from backend.mentorship import recipient_resolvers  # noqa: F401 (registers)
from backend.mentorship.mentorship_admission_service import (
    MentorshipAdmissionService,
)
from backend.mentorship.onboarding_training_service import OnboardingTrainingService
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
from backend.repository.training_repository import TrainingRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

# Verbatim as the admin API writes them into the round's JSONB description.
_PROMOTION = "2026-08-01T07:00:00+00:00"
_DEADLINE = "2026-09-30T15:59:00+00:00"
_MATCHING = "2026-10-15T00:00:00+00:00"


class MentorshipAdmissionServiceTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.service = MentorshipAdmissionService(
            logger=logging.getLogger(__name__),
            onboarding_training_service=OnboardingTrainingService(
                logger=logging.getLogger(__name__),
                training_repository=TrainingRepository(),
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
                "mentor_application_deadline_at": "2026-08-20T15:59:00+00:00",
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


if __name__ == "__main__":
    unittest.main()
