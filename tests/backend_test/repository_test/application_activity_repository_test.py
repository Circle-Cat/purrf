import unittest
from datetime import datetime, timezone
from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.application_activity_repository import (
    ApplicationActivityRepository,
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


class TestApplicationActivityRepository(BaseRepositoryTestLib):
    async def _seed_application(self):
        """Create a job, an actor user, and one application for it.

        Returns:
            tuple[ApplicationEntity, UsersEntity]: The seeded application and
                an actor usable for logged events.
        """
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        actor = _make_user()
        await self.insert_entities([job, actor])
        app = ApplicationEntity(
            job_id=job.job_id,
            user_id=actor.user_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        await self.insert_entities([app])
        return app, actor

    async def test_list_by_application_returns_empty_before_any_activity(self):
        app, _actor = await self._seed_application()
        repo = ApplicationActivityRepository()

        result = await repo.list_by_application(self.session, app.application_id)

        self.assertEqual(result, [])

    async def test_create_persists_event_type_and_details(self):
        app, actor = await self._seed_application()
        repo = ApplicationActivityRepository()

        created = await repo.create(
            self.session,
            app.application_id,
            actor.user_id,
            "application_submitted",
            details={"stage": "recruiter_screening"},
        )

        self.assertEqual(created.application_id, app.application_id)
        self.assertEqual(created.actor_id, actor.user_id)
        self.assertEqual(created.event_type, "application_submitted")
        self.assertEqual(created.details, {"stage": "recruiter_screening"})

    async def test_create_defaults_details_to_empty_dict_when_omitted(self):
        app, actor = await self._seed_application()
        repo = ApplicationActivityRepository()

        created = await repo.create(
            self.session, app.application_id, actor.user_id, "application_submitted"
        )

        self.assertEqual(created.details, {})

    async def test_list_by_application_returns_newest_first(self):
        app, actor = await self._seed_application()
        repo = ApplicationActivityRepository()

        first = await repo.create(
            self.session, app.application_id, actor.user_id, "application_submitted"
        )
        second = await repo.create(
            self.session, app.application_id, actor.user_id, "stage_changed"
        )

        result = await repo.list_by_application(self.session, app.application_id)

        self.assertEqual(
            [row.activity_id for row in result], [second.activity_id, first.activity_id]
        )

    async def test_list_by_application_only_returns_rows_for_that_application(self):
        app1, actor = await self._seed_application()
        job2 = JobEntity(kind=JobKind.ACTIVITY, title="T2", status=JobStatus.PUBLISHED)
        await self.insert_entities([job2])
        app2 = ApplicationEntity(
            job_id=job2.job_id,
            user_id=actor.user_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        await self.insert_entities([app2])
        repo = ApplicationActivityRepository()

        await repo.create(
            self.session, app1.application_id, actor.user_id, "application_submitted"
        )
        await repo.create(
            self.session, app2.application_id, actor.user_id, "application_submitted"
        )

        result = await repo.list_by_application(self.session, app1.application_id)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].application_id, app1.application_id)

    async def test_create_honors_explicit_created_at(self):
        app, actor = await self._seed_application()
        repo = ApplicationActivityRepository()
        backdated = datetime(2023, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

        created = await repo.create(
            self.session,
            app.application_id,
            actor.user_id,
            "email_received",
            details={"subject": "Hi"},
            created_at=backdated,
        )

        self.assertEqual(created.created_at, backdated)

    async def test_create_defaults_created_at_when_omitted(self):
        app, actor = await self._seed_application()
        repo = ApplicationActivityRepository()

        created = await repo.create(
            self.session, app.application_id, actor.user_id, "stage_changed"
        )

        self.assertIsNotNone(created.created_at)


if __name__ == "__main__":
    unittest.main()
