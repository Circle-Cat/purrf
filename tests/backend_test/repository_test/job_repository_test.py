import unittest

from datetime import datetime, timezone

from backend.repository.job_repository import JobRepository
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestJobRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = JobRepository()

    async def test_persists_pipeline_config_and_pending(self):
        """create_job round-trips pipeline_config; pending fields default to None."""
        job = JobEntity(
            kind=JobKind.EMPLOYMENT,
            title="SWE Intern",
            status=JobStatus.DRAFT,
            pipeline_config=[{"stage": "recruiter_screening", "rounds": 1}],
        )
        saved = await self.repo.create_job(self.session, job)

        self.assertEqual(saved.pipeline_config[0]["stage"], "recruiter_screening")
        self.assertIsNone(saved.pending_payload)

    async def test_list_all_returns_every_status(self):
        """list_all returns jobs regardless of status."""
        await self.repo.create_job(
            self.session,
            JobEntity(kind=JobKind.ACTIVITY, title="A", status=JobStatus.DRAFT),
        )
        await self.repo.create_job(
            self.session,
            JobEntity(kind=JobKind.ACTIVITY, title="B", status=JobStatus.CLOSED),
        )
        rows = await self.repo.list_all(self.session)

        titles = {r.title for r in rows}
        self.assertIn("A", titles)
        self.assertIn("B", titles)

    async def test_list_publicly_visible_includes_pending_revision_and_close(self):
        """Postings mid revision-review or close-review are still candidate-visible.

        Both keep serving their last approved version while the review is
        open, so the browse list must keep them. The statuses with no
        approved version on offer (draft, pending_review, closed,
        pending_reopen) must stay out.
        """
        visible = {
            "visible-published": JobStatus.PUBLISHED,
            "visible-revising": JobStatus.PUBLISHED_PENDING_REVISION,
            "visible-closing": JobStatus.PENDING_CLOSE,
        }
        hidden = {
            "hidden-draft": JobStatus.DRAFT,
            "hidden-review": JobStatus.PENDING_REVIEW,
            "hidden-closed": JobStatus.CLOSED,
            "hidden-reopening": JobStatus.PENDING_REOPEN,
        }
        for title, status in {**visible, **hidden}.items():
            await self.repo.create_job(
                self.session,
                JobEntity(kind=JobKind.ACTIVITY, title=title, status=status),
            )

        rows = await self.repo.list_publicly_visible(self.session)

        titles = {r.title for r in rows}
        for title in visible:
            self.assertIn(title, titles)
        for title in hidden:
            self.assertNotIn(title, titles)

    async def test_list_published_stays_strict(self):
        """list_published serves the backfill's exact-PUBLISHED question."""
        for title, status in (
            ("strict-published", JobStatus.PUBLISHED),
            ("strict-closing", JobStatus.PENDING_CLOSE),
        ):
            await self.repo.create_job(
                self.session,
                JobEntity(kind=JobKind.ACTIVITY, title=title, status=status),
            )

        titles = {r.title for r in await self.repo.list_published(self.session)}

        self.assertIn("strict-published", titles)
        self.assertNotIn("strict-closing", titles)

    async def test_delete_job_removes_entity(self):
        """delete_job removes the posting so get_by_job_id returns None afterward."""
        job = await self.repo.create_job(
            self.session,
            JobEntity(
                kind=JobKind.ACTIVITY, title="To Delete", status=JobStatus.CLOSED
            ),
        )
        job_id = job.job_id
        self.assertIsNotNone(job_id)

        await self.repo.delete_job(self.session, job)

        fetched = await self.repo.get_by_job_id(self.session, job_id)
        self.assertIsNone(fetched)

    async def test_config_columns_round_trip(self):
        """create_job round-trips screen_rules/profile_config/pipeline_config."""
        repo = JobRepository()
        job = JobEntity(
            kind=JobKind.ACTIVITY,
            status=JobStatus.DRAFT,
            title="Config columns",
            screen_rules={"rules": []},
            profile_config={
                "education": "required",
                "workExperience": "optional",
                "resume": "off",
            },
            pipeline_config={
                "stages": [
                    {
                        "stage": "recruiter_screening",
                        "rounds": 1,
                    }
                ]
            },
        )
        created = await repo.create_job(self.session, job)
        fetched = await repo.get_by_job_id(self.session, created.job_id)
        self.assertEqual(fetched.screen_rules, {"rules": []})
        self.assertEqual(fetched.profile_config["education"], "required")
        self.assertEqual(
            fetched.pipeline_config["stages"][0]["stage"], "recruiter_screening"
        )

    async def _application_for(self, job: JobEntity) -> ApplicationEntity:
        """One application against ``job``, with the applicant it needs."""
        applicant = UsersEntity(
            first_name="U",
            last_name="Ser",
            timezone="UTC",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )
        await self.insert_entities([applicant])
        application = ApplicationEntity(
            job_id=job.job_id,
            user_id=applicant.user_id,
            stage=ApplicationStage.APPLIED,
        )
        await self.insert_entities([application])
        return application

    async def test_get_by_application_id_returns_the_job_applied_to(self):
        """Recipient resolution holds an application id and wants the owners,
        which live in the job's pipeline_config."""
        job = await self.repo.create_job(
            self.session,
            JobEntity(
                kind=JobKind.ACTIVITY,
                title="A",
                status=JobStatus.PUBLISHED,
                pipeline_config={"ownerIds": [1, 2]},
            ),
        )
        application = await self._application_for(job)

        found = await self.repo.get_by_application_id(
            self.session, application.application_id
        )

        self.assertIsNotNone(found)
        self.assertEqual(found.job_id, job.job_id)
        self.assertEqual(found.pipeline_config, {"ownerIds": [1, 2]})

    async def test_get_by_application_id_returns_none_for_no_such_application(self):
        self.assertIsNone(await self.repo.get_by_application_id(self.session, 999_999))


if __name__ == "__main__":
    unittest.main()
