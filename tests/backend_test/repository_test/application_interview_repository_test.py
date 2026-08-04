import unittest
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError
from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.application_interview_repository import (
    ApplicationInterviewRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    """Build a UsersEntity satisfying every NOT NULL column, unique email."""
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestApplicationInterviewRepository(BaseRepositoryTestLib):
    async def _seed_application(self):
        """Create a job, an applicant, a recruiter, and one application.

        Returns:
            tuple[ApplicationEntity, UsersEntity, UsersEntity]: The seeded
                application, the applicant, and a recruiter user (usable as
                ``scheduled_by``).
        """
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        applicant = _make_user()
        recruiter = _make_user()
        await self.insert_entities([job, applicant, recruiter])
        app = ApplicationEntity(
            job_id=job.job_id,
            user_id=applicant.user_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        await self.insert_entities([app])
        return app, applicant, recruiter

    def _schedule_kwargs(self, app, recruiter, round=1, **overrides):
        kwargs = dict(
            application_id=app.application_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
            round=round,
            google_event_id="event-1",
            meet_link="https://meet.google.com/abc-defg-hij",
            start_at=datetime(2026, 8, 1, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 8, 1, 14, 45, tzinfo=timezone.utc),
            scheduled_by=recruiter.user_id,
        )
        kwargs.update(overrides)
        return kwargs

    async def test_get_returns_none_when_no_row(self):
        app, _applicant, _recruiter = await self._seed_application()
        repo = ApplicationInterviewRepository()

        result = await repo.get(
            self.session, app.application_id, ApplicationStage.RECRUITER_SCREENING, 1
        )

        self.assertIsNone(result)

    async def test_create_then_get_round_trips_every_column(self):
        app, _applicant, recruiter = await self._seed_application()
        repo = ApplicationInterviewRepository()

        created = await repo.create(
            self.session, **self._schedule_kwargs(app, recruiter)
        )
        fetched = await repo.get(
            self.session, app.application_id, ApplicationStage.RECRUITER_SCREENING, 1
        )

        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.interview_id, created.interview_id)
        self.assertEqual(fetched.application_id, app.application_id)
        self.assertEqual(fetched.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(fetched.round, 1)
        self.assertEqual(fetched.google_event_id, "event-1")
        self.assertEqual(fetched.meet_link, "https://meet.google.com/abc-defg-hij")
        self.assertEqual(
            fetched.start_at, datetime(2026, 8, 1, 14, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(
            fetched.end_at, datetime(2026, 8, 1, 14, 45, tzinfo=timezone.utc)
        )
        self.assertEqual(fetched.scheduled_by, recruiter.user_id)
        self.assertIsNotNone(fetched.created_at)
        self.assertIsNotNone(fetched.updated_at)

    async def test_create_twice_for_the_same_stage_and_round_violates_uniqueness(self):
        app, _applicant, recruiter = await self._seed_application()
        repo = ApplicationInterviewRepository()

        await repo.create(self.session, **self._schedule_kwargs(app, recruiter))

        with self.assertRaises(IntegrityError):
            await repo.create(
                self.session,
                **self._schedule_kwargs(app, recruiter, google_event_id="event-2"),
            )

    async def test_create_is_allowed_for_a_second_round(self):
        app, _applicant, recruiter = await self._seed_application()
        repo = ApplicationInterviewRepository()

        first = await repo.create(self.session, **self._schedule_kwargs(app, recruiter))
        second = await repo.create(
            self.session, **self._schedule_kwargs(app, recruiter, round=2)
        )

        self.assertNotEqual(first.interview_id, second.interview_id)
        fetched_round_two = await repo.get(
            self.session, app.application_id, ApplicationStage.RECRUITER_SCREENING, 2
        )
        self.assertEqual(fetched_round_two.interview_id, second.interview_id)

    async def test_update_schedule_changes_times_and_zone_but_not_scheduled_by(self):
        app, _applicant, recruiter = await self._seed_application()
        repo = ApplicationInterviewRepository()
        entity = await repo.create(
            self.session, **self._schedule_kwargs(app, recruiter)
        )
        new_start = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)
        new_end = new_start + timedelta(minutes=45)

        updated = await repo.update_schedule(
            self.session,
            entity,
            start_at=new_start,
            end_at=new_end,
            meet_link="https://meet.google.com/xyz-wxyz-xyz",
        )

        self.assertEqual(updated.start_at, new_start)
        self.assertEqual(updated.end_at, new_end)
        self.assertEqual(updated.meet_link, "https://meet.google.com/xyz-wxyz-xyz")
        self.assertEqual(updated.scheduled_by, recruiter.user_id)
        self.assertEqual(updated.google_event_id, "event-1")

    async def test_delete_removes_the_row(self):
        app, _applicant, recruiter = await self._seed_application()
        repo = ApplicationInterviewRepository()
        entity = await repo.create(
            self.session, **self._schedule_kwargs(app, recruiter)
        )

        await repo.delete(self.session, entity)

        fetched = await repo.get(
            self.session, app.application_id, ApplicationStage.RECRUITER_SCREENING, 1
        )
        self.assertIsNone(fetched)

    async def test_list_by_application_ids_returns_rows_for_a_batch(self):
        app1, applicant1, recruiter = await self._seed_application()
        job2 = JobEntity(kind=JobKind.ACTIVITY, title="T2", status=JobStatus.PUBLISHED)
        applicant2 = _make_user()
        await self.insert_entities([job2, applicant2])
        app2 = ApplicationEntity(
            job_id=job2.job_id,
            user_id=applicant2.user_id,
            stage=ApplicationStage.TECH,
        )
        app3 = ApplicationEntity(
            job_id=job2.job_id,
            user_id=applicant1.user_id,
            stage=ApplicationStage.TECH,
        )
        await self.insert_entities([app2, app3])
        repo = ApplicationInterviewRepository()

        await repo.create(self.session, **self._schedule_kwargs(app1, recruiter))
        await repo.create(
            self.session,
            **self._schedule_kwargs(
                app2, recruiter, round=1, stage=ApplicationStage.TECH
            ),
        )
        await repo.create(
            self.session,
            **self._schedule_kwargs(
                app3, recruiter, round=1, stage=ApplicationStage.TECH
            ),
        )

        results = await repo.list_by_application_ids(
            self.session, [app1.application_id, app2.application_id]
        )

        self.assertEqual(
            {r.application_id for r in results},
            {app1.application_id, app2.application_id},
        )

    async def test_list_by_application_ids_short_circuits_on_an_empty_input(self):
        repo = ApplicationInterviewRepository()
        original_execute = self.session.execute
        calls = []

        async def spy_execute(*args, **kwargs):
            calls.append((args, kwargs))
            return await original_execute(*args, **kwargs)

        self.session.execute = spy_execute

        results = await repo.list_by_application_ids(self.session, [])

        self.assertEqual(results, [])
        self.assertEqual(
            calls, [], "expected no query for an empty application_ids input"
        )


if __name__ == "__main__":
    unittest.main()
