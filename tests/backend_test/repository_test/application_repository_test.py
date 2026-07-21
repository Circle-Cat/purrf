import unittest
from datetime import date, datetime, timezone

from sqlalchemy.exc import IntegrityError

from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
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
    async def _seed_job_and_user(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        user = _make_user("A", "B", "a@b.com")
        await self.insert_entities([job, user])
        await self.session.flush()
        return job, user

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


if __name__ == "__main__":
    unittest.main()
