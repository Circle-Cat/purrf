import unittest
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from backend.entity.email_thread_entity import EmailThreadEntity
from backend.entity.job_entity import JobEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.users_entity import UsersEntity
from backend.common.communication_enums import ContextType
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.common.mentorship_enums import CommunicationMethod, ParticipantRole
from backend.repository.application_repository import ApplicationRepository
from backend.repository.application_submission_repository import (
    ApplicationSubmissionRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user(first_name: str, last_name: str, primary_email: str) -> UsersEntity:
    """Build a UsersEntity satisfying every NOT NULL column."""
    return UsersEntity(
        first_name=first_name,
        last_name=last_name,
        timezone="UTC",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestApplicationRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = ApplicationRepository()

    async def _seed_job_and_user(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        user = _make_user("A", "B", "a@b.com")
        await self.insert_entities([job, user])
        await self.session.flush()
        return job, user

    async def _make_application(
        self,
        stage: ApplicationStage = ApplicationStage.APPLIED,
        stage_entered_at: datetime | None = None,
    ) -> ApplicationEntity:
        """Create a job + user + application in one call, for tests that only
        care about the application's stage. ``stage_entered_at=None`` leaves
        the column's server default in place."""
        job, user = await self._seed_job_and_user()
        entity = ApplicationEntity(job_id=job.job_id, user_id=user.user_id, stage=stage)
        if stage_entered_at is not None:
            entity.stage_entered_at = stage_entered_at
        return await self.repo.create(self.session, entity)

    async def test_create_and_get_latest_by_job_and_user(self):
        job, user = await self._seed_job_and_user()
        repo = ApplicationRepository()
        created = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id, user_id=user.user_id, stage=ApplicationStage.APPLIED
            ),
        )
        self.assertIsNotNone(created.application_id)
        found = await repo.get_latest_by_job_and_user(
            self.session, job.job_id, user.user_id
        )
        self.assertEqual(found.application_id, created.application_id)
        self.assertIsNone(
            await repo.get_latest_by_job_and_user(self.session, job.job_id, 999999)
        )

    async def test_get_latest_by_job_and_user_returns_newest_attempt(self):
        job, user = await self._seed_job_and_user()
        repo = ApplicationRepository()
        old = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.REJECTED,
            ),
        )
        new = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id, user_id=user.user_id, stage=ApplicationStage.APPLIED
            ),
        )
        got = await repo.get_latest_by_job_and_user(
            self.session, job.job_id, user.user_id
        )
        self.assertEqual(got.application_id, new.application_id)
        self.assertNotEqual(got.application_id, old.application_id)

    async def test_list_by_job_returns_only_latest_attempt_per_user(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        user_a = _make_user("A", "One", "a1@b.com")
        user_b = _make_user("B", "Two", "b2@b.com")
        await self.insert_entities([job, user_a, user_b])
        await self.session.flush()

        repo = ApplicationRepository()
        old_a = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_a.user_id,
                stage=ApplicationStage.REJECTED,
            ),
        )
        new_a = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_a.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )
        only_b = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_b.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )

        rows = await repo.list_by_job(self.session, job.job_id)

        listed_ids = {app.application_id for app, _ in rows}
        self.assertEqual(listed_ids, {new_a.application_id, only_b.application_id})
        self.assertNotIn(old_a.application_id, listed_ids)

    async def test_two_rejected_rows_coexist_for_same_job_and_user(self):
        job, user = await self._seed_job_and_user()
        repo = ApplicationRepository()
        first = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.REJECTED,
            ),
        )
        second = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.REJECTED,
            ),
        )
        self.assertNotEqual(first.application_id, second.application_id)

    async def test_submission_get_current_returns_highest_version(self):
        job, user = await self._seed_job_and_user()
        app = await ApplicationRepository().create(
            self.session,
            ApplicationEntity(job_id=job.job_id, user_id=user.user_id),
        )
        sub_repo = ApplicationSubmissionRepository()
        await sub_repo.create(
            self.session,
            ApplicationSubmissionEntity(
                application_id=app.application_id, version=1, submission={"a": 1}
            ),
        )
        await sub_repo.create(
            self.session,
            ApplicationSubmissionEntity(
                application_id=app.application_id, version=2, submission={"a": 2}
            ),
        )
        current = await sub_repo.get_current(self.session, app.application_id)
        self.assertEqual(current.version, 2)
        versions = await sub_repo.list_by_application(self.session, app.application_id)
        self.assertEqual([v.version for v in versions], [1, 2])

    async def test_list_by_job_returns_joined_rows_ordered_excluding_other_jobs(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        other_job = JobEntity(
            kind=JobKind.ACTIVITY, title="Other", status=JobStatus.PUBLISHED
        )
        user_a = _make_user("A", "One", "a1@b.com")
        user_b = _make_user("B", "Two", "b2@b.com")
        await self.insert_entities([job, other_job, user_a, user_b])
        await self.session.flush()

        repo = ApplicationRepository()
        app_a = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_a.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )
        app_b = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_b.user_id,
                stage=ApplicationStage.RECRUITER_SCREENING,
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(job_id=other_job.job_id, user_id=user_a.user_id),
        )

        rows = await repo.list_by_job(self.session, job.job_id)

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [app.application_id for app, _ in rows],
            [app_a.application_id, app_b.application_id],
        )
        self.assertEqual(
            [user.user_id for _, user in rows], [user_a.user_id, user_b.user_id]
        )
        self.assertTrue(all(app.job_id == job.job_id for app, _ in rows))

    async def test_list_by_user_returns_joined_rows_across_jobs(self):
        job_a = JobEntity(
            kind=JobKind.ACTIVITY, title="Job A", status=JobStatus.PUBLISHED
        )
        job_b = JobEntity(
            kind=JobKind.ACTIVITY, title="Job B", status=JobStatus.PUBLISHED
        )
        user_a = _make_user("A", "One", "a1@b.com")
        user_b = _make_user("B", "Two", "b2@b.com")
        await self.insert_entities([job_a, job_b, user_a, user_b])
        await self.session.flush()

        repo = ApplicationRepository()
        app_a1 = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_a.job_id,
                user_id=user_a.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_a.job_id,
                user_id=user_b.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )
        app_a2 = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_b.job_id,
                user_id=user_a.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )

        result = await repo.list_by_user(self.session, user_a.user_id)

        self.assertEqual(
            {(app.application_id, job.job_id) for app, job in result},
            {
                (app_a1.application_id, job_a.job_id),
                (app_a2.application_id, job_b.job_id),
            },
        )

    async def test_count_by_job_and_stage_groups_across_jobs(self):
        job_a = JobEntity(
            kind=JobKind.ACTIVITY, title="Job A", status=JobStatus.PUBLISHED
        )
        job_b = JobEntity(
            kind=JobKind.ACTIVITY, title="Job B", status=JobStatus.PUBLISHED
        )
        user_1 = _make_user("A", "One", "a1@b.com")
        user_2 = _make_user("B", "Two", "b2@b.com")
        user_3 = _make_user("C", "Three", "c3@b.com")
        await self.insert_entities([job_a, job_b, user_1, user_2, user_3])
        await self.session.flush()

        repo = ApplicationRepository()
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_a.job_id,
                user_id=user_1.user_id,
                stage=ApplicationStage.RECRUITER_SCREENING,
                created_datetime=datetime(2026, 6, 1, tzinfo=timezone.utc),
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_a.job_id,
                user_id=user_2.user_id,
                stage=ApplicationStage.TECH,
                created_datetime=datetime(2026, 6, 2, tzinfo=timezone.utc),
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_b.job_id,
                user_id=user_1.user_id,
                stage=ApplicationStage.RECRUITER_SCREENING,
                created_datetime=datetime(2026, 6, 3, tzinfo=timezone.utc),
            ),
        )
        # Outside the date range — must not be counted.
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_a.job_id,
                user_id=user_3.user_id,
                stage=ApplicationStage.HIRED,
                created_datetime=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ),
        )

        result = await repo.count_by_job_and_stage(
            self.session, date(2026, 6, 1), date(2026, 6, 30), None
        )

        self.assertEqual(
            {(job_id, stage, count) for job_id, stage, count in result},
            {
                (job_a.job_id, ApplicationStage.RECRUITER_SCREENING, 1),
                (job_a.job_id, ApplicationStage.TECH, 1),
                (job_b.job_id, ApplicationStage.RECRUITER_SCREENING, 1),
            },
        )

    async def test_count_by_job_and_stage_filters_by_job_ids(self):
        job_a = JobEntity(
            kind=JobKind.ACTIVITY, title="Job A", status=JobStatus.PUBLISHED
        )
        job_b = JobEntity(
            kind=JobKind.ACTIVITY, title="Job B", status=JobStatus.PUBLISHED
        )
        user = _make_user("A", "One", "a1@b.com")
        await self.insert_entities([job_a, job_b, user])
        await self.session.flush()

        repo = ApplicationRepository()
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_a.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.RECRUITER_SCREENING,
                created_datetime=datetime(2026, 6, 1, tzinfo=timezone.utc),
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_b.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.RECRUITER_SCREENING,
                created_datetime=datetime(2026, 6, 1, tzinfo=timezone.utc),
            ),
        )

        result = await repo.count_by_job_and_stage(
            self.session, date(2026, 6, 1), date(2026, 6, 30), [job_a.job_id]
        )

        self.assertEqual(
            [(job_id, stage, count) for job_id, stage, count in result],
            [(job_a.job_id, ApplicationStage.RECRUITER_SCREENING, 1)],
        )

    async def test_count_by_job_and_day_groups_by_calendar_day(self):
        job = JobEntity(
            kind=JobKind.ACTIVITY, title="Job A", status=JobStatus.PUBLISHED
        )
        user_1 = _make_user("A", "One", "a1@b.com")
        user_2 = _make_user("B", "Two", "b2@b.com")
        user_3 = _make_user("C", "Three", "c3@b.com")
        await self.insert_entities([job, user_1, user_2, user_3])
        await self.session.flush()

        repo = ApplicationRepository()
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_1.user_id,
                created_datetime=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_2.user_id,
                created_datetime=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_3.user_id,
                created_datetime=datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc),
            ),
        )

        result = await repo.count_by_job_and_day(
            self.session, date(2026, 6, 1), date(2026, 6, 30), None
        )

        self.assertEqual(
            {(job_id, day, count) for job_id, day, count in result},
            {
                (job.job_id, date(2026, 6, 1), 2),
                (job.job_id, date(2026, 6, 2), 1),
            },
        )

    async def test_count_methods_return_empty_for_no_matches(self):
        repo = ApplicationRepository()
        stage_result = await repo.count_by_job_and_stage(
            self.session, date(2026, 1, 1), date(2026, 1, 31), None
        )
        day_result = await repo.count_by_job_and_day(
            self.session, date(2026, 1, 1), date(2026, 1, 31), None
        )
        self.assertEqual(stage_result, [])
        self.assertEqual(day_result, [])

    async def test_get_hired_activity_application_finds_matching_role_and_stage(self):
        job = JobEntity(
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTEE,
            title="Mentee Activity",
            status=JobStatus.PUBLISHED,
        )
        other_role_job = JobEntity(
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTOR,
            title="Mentor Activity",
            status=JobStatus.PUBLISHED,
        )
        user = _make_user("A", "B", "a@b.com")
        await self.insert_entities([job, other_role_job, user])
        await self.session.flush()

        repo = ApplicationRepository()
        hired_mentee = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id, user_id=user.user_id, stage=ApplicationStage.HIRED
            ),
        )
        # Same user, HIRED for a different role. Querying both roles below
        # and asserting each returns its own application (not the other
        # one) makes this test fail if the mentorship_role filter is ever
        # dropped, regardless of row insertion order.
        hired_mentor = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=other_role_job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.HIRED,
            ),
        )

        found_mentee = await repo.get_hired_activity_application(
            self.session, user_id=user.user_id, mentorship_role=ParticipantRole.MENTEE
        )
        self.assertEqual(found_mentee.application_id, hired_mentee.application_id)

        found_mentor = await repo.get_hired_activity_application(
            self.session, user_id=user.user_id, mentorship_role=ParticipantRole.MENTOR
        )
        self.assertEqual(found_mentor.application_id, hired_mentor.application_id)

    async def test_get_recent_hired_activity_role_returns_most_recent_role(self):
        """When a user was hired into more than one activity posting, the
        role of the most recent application (highest application_id) wins."""
        mentee_job = JobEntity(
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTEE,
            title="Mentee Activity",
            status=JobStatus.PUBLISHED,
        )
        mentor_job = JobEntity(
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTOR,
            title="Mentor Activity",
            status=JobStatus.PUBLISHED,
        )
        user = _make_user("A", "B", "recent-role@b.com")
        await self.insert_entities([mentee_job, mentor_job, user])
        await self.session.flush()

        repo = ApplicationRepository()
        # Hired as mentee first, then as mentor. The later (mentor) row has
        # the higher application_id, so the most recent role is MENTOR.
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=mentee_job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.HIRED,
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=mentor_job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.HIRED,
            ),
        )

        role = await repo.get_recent_hired_activity_role(
            self.session, user_id=user.user_id
        )
        self.assertEqual(role, ParticipantRole.MENTOR)

    async def test_get_recent_hired_activity_role_ignores_non_hired_and_non_activity(
        self,
    ):
        """Only HIRED applications on ACTIVITY postings count; a non-HIRED
        activity application and a HIRED non-activity application are both
        ignored, yielding None."""
        activity_job = JobEntity(
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTOR,
            title="Mentor Activity",
            status=JobStatus.PUBLISHED,
        )
        employment_job = JobEntity(
            kind=JobKind.EMPLOYMENT,
            title="Some Job",
            status=JobStatus.PUBLISHED,
        )
        user = _make_user("A", "B", "no-role@b.com")
        await self.insert_entities([activity_job, employment_job, user])
        await self.session.flush()

        repo = ApplicationRepository()
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=activity_job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.RECRUITER_SCREENING,
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=employment_job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.HIRED,
            ),
        )

        role = await repo.get_recent_hired_activity_role(
            self.session, user_id=user.user_id
        )
        self.assertIsNone(role)

    async def test_get_hired_activity_application_returns_none_when_not_hired(self):
        job = JobEntity(
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTOR,
            title="Mentor Activity",
            status=JobStatus.PUBLISHED,
        )
        user = _make_user("A", "B", "a2@b.com")
        await self.insert_entities([job, user])
        await self.session.flush()

        repo = ApplicationRepository()
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.RECRUITER_SCREENING,
            ),
        )

        found = await repo.get_hired_activity_application(
            self.session, user_id=user.user_id, mentorship_role=ParticipantRole.MENTOR
        )
        self.assertIsNone(found)

    async def test_allows_second_application_after_rejection(self):
        job, user = await self._seed_job_and_user()
        repo = ApplicationRepository()
        first = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.REJECTED,
            ),
        )
        second = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id, user_id=user.user_id, stage=ApplicationStage.APPLIED
            ),
        )
        self.assertNotEqual(first.application_id, second.application_id)

    async def test_rejects_two_active_applications_for_same_job_and_user(self):
        job, user = await self._seed_job_and_user()
        repo = ApplicationRepository()
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id, user_id=user.user_id, stage=ApplicationStage.APPLIED
            ),
        )
        with self.assertRaises(IntegrityError):
            await repo.create(
                self.session,
                ApplicationEntity(
                    job_id=job.job_id, user_id=user.user_id, stage=ApplicationStage.TECH
                ),
            )

    async def test_list_by_job_and_stage_orders_by_entry_desc_and_pages(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        user_1 = _make_user("A", "One", "page1@b.com")
        user_2 = _make_user("B", "Two", "page2@b.com")
        user_3 = _make_user("C", "Three", "page3@b.com")
        await self.insert_entities([job, user_1, user_2, user_3])
        await self.session.flush()

        repo = ApplicationRepository()
        t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
        t3 = datetime(2026, 1, 3, tzinfo=timezone.utc)
        app_t1 = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_1.user_id,
                stage=ApplicationStage.REJECTED,
                stage_entered_at=t1,
            ),
        )
        app_t2 = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_2.user_id,
                stage=ApplicationStage.REJECTED,
                stage_entered_at=t2,
            ),
        )
        app_t3 = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_3.user_id,
                stage=ApplicationStage.REJECTED,
                stage_entered_at=t3,
            ),
        )

        page = await repo.list_by_job_and_stage(
            self.session, job.job_id, ApplicationStage.REJECTED, limit=2, offset=0
        )
        self.assertEqual(
            [a.application_id for a, _ in page],
            [app_t3.application_id, app_t2.application_id],
        )

        page2 = await repo.list_by_job_and_stage(
            self.session, job.job_id, ApplicationStage.REJECTED, limit=2, offset=2
        )
        self.assertEqual([a.application_id for a, _ in page2], [app_t1.application_id])

    async def test_list_by_job_and_stage_excludes_reapplied_users_old_rejected_row(
        self,
    ):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        reapplied_user = _make_user("A", "One", "reapplied@b.com")
        still_rejected_user = _make_user("B", "Two", "stillrejected@b.com")
        await self.insert_entities([job, reapplied_user, still_rejected_user])
        await self.session.flush()

        repo = ApplicationRepository()
        old_rejected = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=reapplied_user.user_id,
                stage=ApplicationStage.REJECTED,
                stage_entered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        )
        # Newer, active (non-rejected) row for the same user — this is their
        # latest attempt and must be what "counts" for this user.
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=reapplied_user.user_id,
                stage=ApplicationStage.APPLIED,
                stage_entered_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            ),
        )
        currently_rejected = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=still_rejected_user.user_id,
                stage=ApplicationStage.REJECTED,
                stage_entered_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
        )

        page = await repo.list_by_job_and_stage(
            self.session, job.job_id, ApplicationStage.REJECTED, limit=50, offset=0
        )

        page_ids = [a.application_id for a, _ in page]
        self.assertNotIn(old_rejected.application_id, page_ids)
        self.assertIn(currently_rejected.application_id, page_ids)

    async def test_count_latest_by_job_and_stage_matches_items(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        reapplied_user = _make_user("A", "One", "count-reapplied@b.com")
        rejected_user_1 = _make_user("B", "Two", "count-rej1@b.com")
        rejected_user_2 = _make_user("C", "Three", "count-rej2@b.com")
        await self.insert_entities([
            job,
            reapplied_user,
            rejected_user_1,
            rejected_user_2,
        ])
        await self.session.flush()

        repo = ApplicationRepository()
        # Old rejected row superseded by a newer active row — must not count.
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=reapplied_user.user_id,
                stage=ApplicationStage.REJECTED,
                stage_entered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=reapplied_user.user_id,
                stage=ApplicationStage.APPLIED,
                stage_entered_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=rejected_user_1.user_id,
                stage=ApplicationStage.REJECTED,
                stage_entered_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=rejected_user_2.user_id,
                stage=ApplicationStage.REJECTED,
                stage_entered_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
            ),
        )

        total = await repo.count_latest_by_job_and_stage(
            self.session, job.job_id, ApplicationStage.REJECTED
        )
        page = await repo.list_by_job_and_stage(
            self.session, job.job_id, ApplicationStage.REJECTED, limit=1000, offset=0
        )
        self.assertEqual(total, len(page))
        self.assertEqual(total, 2)

    async def test_list_by_job_exclude_stages_drops_terminal(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        applied_user = _make_user("A", "One", "exclude-applied@b.com")
        tech_user = _make_user("B", "Two", "exclude-tech@b.com")
        rejected_user = _make_user("C", "Three", "exclude-rejected@b.com")
        hired_user = _make_user("D", "Four", "exclude-hired@b.com")
        await self.insert_entities([
            job,
            applied_user,
            tech_user,
            rejected_user,
            hired_user,
        ])
        await self.session.flush()

        repo = ApplicationRepository()
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=applied_user.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=tech_user.user_id,
                stage=ApplicationStage.TECH,
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=rejected_user.user_id,
                stage=ApplicationStage.REJECTED,
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=hired_user.user_id,
                stage=ApplicationStage.HIRED,
            ),
        )

        rows = await repo.list_by_job(
            self.session,
            job.job_id,
            exclude_stages={ApplicationStage.REJECTED, ApplicationStage.HIRED},
        )

        stages = {a.stage for a, _ in rows}
        self.assertNotIn(ApplicationStage.REJECTED, stages)
        self.assertNotIn(ApplicationStage.HIRED, stages)
        self.assertEqual(stages, {ApplicationStage.APPLIED, ApplicationStage.TECH})

    # ---- list_due_email_sync_applications -----------------------------

    async def _thread_for(self, application, gmail_thread_id):
        """Give an application one email thread, so the sweep can see it."""
        await self.insert_entities([
            EmailThreadEntity(
                user_id=application.user_id,
                gmail_thread_id=gmail_thread_id,
                subject="Hi",
                context_type=ContextType.APPLICATION,
                context_id=application.application_id,
            )
        ])

    async def test_due_sync_includes_non_terminal_with_a_thread(self):
        app = await self._make_application(stage=ApplicationStage.TECH)
        await self._thread_for(app, "gt-active")
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        due = await self.repo.list_due_email_sync_applications(self.session, cutoff)

        self.assertIn(app.application_id, [a.application_id for a in due])

    async def test_due_sync_excludes_application_without_threads(self):
        # The sweep must never walk applications that have never had an email.
        app = await self._make_application(stage=ApplicationStage.TECH)
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        due = await self.repo.list_due_email_sync_applications(self.session, cutoff)

        self.assertNotIn(app.application_id, [a.application_id for a in due])

    async def test_due_sync_includes_recently_terminal(self):
        app = await self._make_application(
            stage=ApplicationStage.REJECTED,
            stage_entered_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        await self._thread_for(app, "gt-recent-reject")
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        due = await self.repo.list_due_email_sync_applications(self.session, cutoff)

        self.assertIn(app.application_id, [a.application_id for a in due])

    async def test_due_sync_excludes_long_terminal(self):
        app = await self._make_application(
            stage=ApplicationStage.HIRED,
            stage_entered_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        await self._thread_for(app, "gt-old-hire")
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        due = await self.repo.list_due_email_sync_applications(self.session, cutoff)

        self.assertNotIn(app.application_id, [a.application_id for a in due])

    async def test_due_sync_returns_each_application_once(self):
        # Two threads on one application must not yield two rows, or the sweep
        # would sync it twice and double-count the summary.
        app = await self._make_application(stage=ApplicationStage.TECH)
        await self._thread_for(app, "gt-one")
        await self._thread_for(app, "gt-two")
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        due = await self.repo.list_due_email_sync_applications(self.session, cutoff)

        matching = [a for a in due if a.application_id == app.application_id]
        self.assertEqual(len(matching), 1)

    # ---- list_due_email_sync_applications: thread filter ---------------

    async def test_thread_filter_narrows_to_the_given_threads(self):
        wanted = await self._make_application(stage=ApplicationStage.TECH)
        other = await self._make_application(stage=ApplicationStage.TECH)
        await self._thread_for(wanted, "gt-wanted")
        await self._thread_for(other, "gt-other")
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        due = await self.repo.list_due_email_sync_applications(
            self.session, cutoff, gmail_thread_ids={"gt-wanted"}
        )

        ids = [a.application_id for a in due]
        self.assertIn(wanted.application_id, ids)
        self.assertNotIn(other.application_id, ids)

    async def test_thread_filter_still_applies_the_terminal_window(self):
        # A flagged thread does not override eligibility: an application that
        # went terminal long ago stays out even when new mail arrives.
        app = await self._make_application(
            stage=ApplicationStage.REJECTED,
            stage_entered_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        await self._thread_for(app, "gt-old-reject")
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        due = await self.repo.list_due_email_sync_applications(
            self.session, cutoff, gmail_thread_ids={"gt-old-reject"}
        )

        self.assertNotIn(app.application_id, [a.application_id for a in due])

    async def test_thread_filter_unknown_thread_matches_nothing(self):
        app = await self._make_application(stage=ApplicationStage.TECH)
        await self._thread_for(app, "gt-known")
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        due = await self.repo.list_due_email_sync_applications(
            self.session, cutoff, gmail_thread_ids={"gt-never-seen"}
        )

        self.assertEqual(due, [])

    async def test_omitting_the_thread_filter_is_unchanged_behaviour(self):
        # Regression guard: the weekly reconcile passes no filter and must keep
        # seeing exactly what it saw before this parameter existed. If the two
        # call shapes ever diverge, the two jobs disagree about eligibility.
        app = await self._make_application(stage=ApplicationStage.TECH)
        await self._thread_for(app, "gt-unfiltered")
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        with_default = await self.repo.list_due_email_sync_applications(
            self.session, cutoff
        )
        with_explicit_none = await self.repo.list_due_email_sync_applications(
            self.session, cutoff, gmail_thread_ids=None
        )

        self.assertIn(app.application_id, [a.application_id for a in with_default])
        self.assertEqual(
            [a.application_id for a in with_default],
            [a.application_id for a in with_explicit_none],
        )

    # ---- search_latest_by_jobs -----------------------------------------

    async def _seed_applicant(self, job, first_name, last_name, emails=()):
        """Create a user with the given email rows and one application to
        `job`. `emails` is a tuple of (address, is_primary, otp_confirmed)."""
        user = _make_user(first_name, last_name, "unused@example.com")
        await self.insert_entities([user])
        await self.session.flush()
        for address, is_primary, confirmed in emails:
            await self.insert_entities([
                UserEmailsEntity(
                    user_id=user.user_id,
                    email=address,
                    is_primary=is_primary,
                    otp_confirmed=confirmed,
                )
            ])
        await self.session.flush()
        application = await self.repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )
        return user, application

    async def _seed_job(self, title="T"):
        job = JobEntity(kind=JobKind.ACTIVITY, title=title, status=JobStatus.PUBLISHED)
        await self.insert_entities([job])
        await self.session.flush()
        return job

    async def test_search_matches_across_first_and_last_name(self):
        job = await self._seed_job()
        _, wanted = await self._seed_applicant(job, "Zhang", "Wei")
        await self._seed_applicant(job, "Li", "Ming")

        rows = await self.repo.search_latest_by_jobs(
            self.session, [job.job_id], "zhang w", limit=20
        )

        self.assertEqual([a.application_id for a, _ in rows], [wanted.application_id])

    async def test_search_matches_any_email_row_not_just_the_contact_one(self):
        job = await self._seed_job()
        _, wanted = await self._seed_applicant(
            job,
            "Zhang",
            "Wei",
            emails=(
                ("primary@example.com", True, True),
                ("side@example.com", False, False),
            ),
        )

        rows = await self.repo.search_latest_by_jobs(
            self.session, [job.job_id], "side@", limit=20
        )

        self.assertEqual([a.application_id for a, _ in rows], [wanted.application_id])

    async def test_search_returns_one_row_per_application_despite_many_emails(self):
        job = await self._seed_job()
        _, wanted = await self._seed_applicant(
            job,
            "Zhang",
            "Wei",
            emails=(
                ("a@example.com", True, True),
                ("b@example.com", False, True),
                ("c@example.com", False, True),
            ),
        )

        rows = await self.repo.search_latest_by_jobs(
            self.session, [job.job_id], "example.com", limit=20
        )

        self.assertEqual([a.application_id for a, _ in rows], [wanted.application_id])

    async def test_search_escapes_underscore_wildcard_in_the_term(self):
        # Unescaped, "_" is a single-character SQL wildcard, so "AXB Wildcard"
        # would match "%a_b%" too (a, any one char, b). Only the literal
        # "A_B Underscore" applicant must come back for the term "a_b".
        job = await self._seed_job()
        _, decoy = await self._seed_applicant(job, "AXB", "Wildcard")
        _, literal = await self._seed_applicant(job, "A_B", "Underscore")

        rows = await self.repo.search_latest_by_jobs(
            self.session, [job.job_id], "a_b", limit=20
        )

        ids = [a.application_id for a, _ in rows]
        self.assertEqual(ids, [literal.application_id])
        self.assertNotIn(decoy.application_id, ids)

    async def test_search_escapes_percent_wildcard_in_the_term(self):
        # Unescaped, "%" matches any run of characters (including none), so
        # "AZZZB Wildcard" would match "%a%b%" too (a, anything, b). Only the
        # literal "A%B Percent" applicant must come back for the term "a%b".
        job = await self._seed_job()
        _, decoy = await self._seed_applicant(job, "AZZZB", "Wildcard")
        _, literal = await self._seed_applicant(job, "A%B", "Percent")

        rows = await self.repo.search_latest_by_jobs(
            self.session, [job.job_id], "a%b", limit=20
        )

        ids = [a.application_id for a, _ in rows]
        self.assertEqual(ids, [literal.application_id])
        self.assertNotIn(decoy.application_id, ids)

    async def test_search_finds_applicant_with_no_email_rows_by_name(self):
        job = await self._seed_job()
        _, wanted = await self._seed_applicant(job, "Zhang", "Wei")

        rows = await self.repo.search_latest_by_jobs(
            self.session, [job.job_id], "zhang", limit=20
        )

        self.assertEqual([a.application_id for a, _ in rows], [wanted.application_id])

    async def test_search_returns_only_the_latest_attempt_per_job_and_user(self):
        job = await self._seed_job()
        user, older = await self._seed_applicant(job, "Zhang", "Wei")
        older.stage = ApplicationStage.REJECTED
        await self.session.flush()
        newer = await self.repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )

        rows = await self.repo.search_latest_by_jobs(
            self.session, [job.job_id], "zhang", limit=20
        )

        self.assertEqual([a.application_id for a, _ in rows], [newer.application_id])

    async def test_search_spans_several_jobs_and_ignores_jobs_not_listed(self):
        job_a = await self._seed_job("A")
        job_b = await self._seed_job("B")
        job_c = await self._seed_job("C")
        _, in_a = await self._seed_applicant(job_a, "Zhang", "Wei")
        _, in_b = await self._seed_applicant(job_b, "Zhang", "Min")
        await self._seed_applicant(job_c, "Zhang", "Hidden")

        rows = await self.repo.search_latest_by_jobs(
            self.session, [job_a.job_id, job_b.job_id], "zhang", limit=20
        )

        self.assertEqual(
            {a.application_id for a, _ in rows},
            {in_a.application_id, in_b.application_id},
        )

    async def test_search_groups_by_job_and_user_so_every_job_survives(self):
        # A user with applications to two searched jobs must surface BOTH.
        # Grouping the "latest per user" subquery by user_id alone (as
        # list_by_job does, but with job_id fixed there) would collapse this
        # to a single MAX(application_id) across both jobs and silently drop
        # whichever application has the lower id.
        job_a = await self._seed_job("A")
        job_b = await self._seed_job("B")
        user = _make_user("Multi", "Job", "unused@example.com")
        await self.insert_entities([user])
        await self.session.flush()
        app_a = await self.repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_a.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )
        app_b = await self.repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_b.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )

        rows = await self.repo.search_latest_by_jobs(
            self.session, [job_a.job_id, job_b.job_id], "multi", limit=20
        )

        self.assertEqual(
            {a.application_id for a, _ in rows},
            {app_a.application_id, app_b.application_id},
        )

    async def test_search_returns_nothing_for_empty_job_ids(self):
        rows = await self.repo.search_latest_by_jobs(
            self.session, [], "zhang", limit=20
        )

        self.assertEqual(rows, [])

    async def test_search_matches_email_case_insensitively(self):
        job = await self._seed_job()
        _, wanted = await self._seed_applicant(
            job,
            "Zhang",
            "Wei",
            emails=(("MixedCase@Example.com", True, True),),
        )

        rows = await self.repo.search_latest_by_jobs(
            self.session, [job.job_id], "MIXEDCASE@example.COM", limit=20
        )

        self.assertEqual([a.application_id for a, _ in rows], [wanted.application_id])

    async def test_search_orders_by_created_datetime_desc_then_id_desc(self):
        job = await self._seed_job()
        user_1 = _make_user("Zhang", "One", "unused@example.com")
        user_2 = _make_user("Zhang", "Two", "unused@example.com")
        user_3 = _make_user("Zhang", "Three", "unused@example.com")
        await self.insert_entities([user_1, user_2, user_3])
        await self.session.flush()

        # Inserted oldest-first (so ascending application_id) but with
        # explicit created_datetime values in the OPPOSITE order, so a test
        # that passed by accident under "order by application_id" would
        # fail here.
        app_1 = await self.repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_1.user_id,
                stage=ApplicationStage.APPLIED,
                created_datetime=datetime(2026, 1, 3, tzinfo=timezone.utc),
            ),
        )
        app_2 = await self.repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_2.user_id,
                stage=ApplicationStage.APPLIED,
                created_datetime=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
        )
        app_3 = await self.repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_3.user_id,
                stage=ApplicationStage.APPLIED,
                created_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        )

        rows = await self.repo.search_latest_by_jobs(
            self.session, [job.job_id], "zhang", limit=20
        )

        self.assertEqual(
            [a.application_id for a, _ in rows],
            [app_1.application_id, app_2.application_id, app_3.application_id],
        )

    async def test_search_honours_the_limit(self):
        job = await self._seed_job()
        for i in range(3):
            await self._seed_applicant(job, "Zhang", f"N{i}")

        rows = await self.repo.search_latest_by_jobs(
            self.session, [job.job_id], "zhang", limit=2
        )

        self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
