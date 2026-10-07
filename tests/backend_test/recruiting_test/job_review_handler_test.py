"""What a job posting review does to the posting, by kind."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.common.recruiting_enums import JobStatus
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.recruiting.job_review_handler import (
    JobReviewHandler,
    apply_pending_payload,
)

JOB_ID = 41
RAISER = 7
REVIEWER = 8
REQUEST_ID = 903

_STAGED = {
    "title": "Staged title",
    "description": "Staged description",
    "cooldownDays": 30,
    "screenRules": {"r": 1},
    "formSchema": {"f": 1},
    "pipelineConfig": {
        "stages": [{"key": "screening", "defaultAssigneeId": None}],
        "ownerIds": [21],
    },
    "profileConfig": {"p": 1},
}


def _job(status, *, pending_payload=None, was_published=False):
    return SimpleNamespace(
        job_id=JOB_ID,
        status=status,
        pending_payload=pending_payload,
        was_published=was_published,
        title="Live title",
        description="Live description",
        cooldown_days=10,
        screen_rules=None,
        form_schema=None,
        pipeline_config={
            "stages": [{"key": "screening", "defaultAssigneeId": None}],
            "ownerIds": [21],
        },
        profile_config=None,
    )


def _request(kind, reason="Ready to go live"):
    row = ApprovalRequestEntity(
        action="job_review",
        target_type="job",
        target_id=str(JOB_ID),
        payload={"kind": kind},
        reason=reason,
        raised_by=RAISER,
        reviewer_id=REVIEWER,
    )
    row.request_id = REQUEST_ID
    return row


class JobReviewHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.job = _job(JobStatus.DRAFT)
        self.jobs = MagicMock()
        self.jobs.get_by_job_id = AsyncMock(side_effect=lambda s, job_id: self.job)
        self.jobs.update_job = AsyncMock(side_effect=lambda s, job: job)
        self.perms = MagicMock()
        # Owner 21 can advance applications; nobody else is asked about.
        self.perms.get_active_users_with_permission = AsyncMock(
            return_value=[SimpleNamespace(user_id=21)]
        )
        self.session = AsyncMock()
        self.handler = JobReviewHandler(
            job_repository=self.jobs, user_permissions_repository=self.perms
        )

    async def _check(self, kind):
        await self.handler.check_raise(
            self.session,
            raised_by=RAISER,
            target_id=str(JOB_ID),
            payload={"kind": kind},
        )

    def test_events_are_recorded_against_the_posting(self):
        self.assertEqual(self.handler.subject_id(_request("initial")), JOB_ID)

    async def test_events_carry_what_the_timeline_and_bell_read(self):
        details = await self.handler.event_details(self.session, _request("close"))

        self.assertEqual(
            details,
            {"kind": "close", "reviewId": REQUEST_ID, "message": "Ready to go live"},
        )

    async def test_each_kind_opens_only_from_its_status(self):
        allowed = {
            "initial": _job(JobStatus.DRAFT),
            "revision": _job(JobStatus.PUBLISHED, pending_payload=_STAGED),
            "close": _job(JobStatus.PUBLISHED),
            "reopen": _job(JobStatus.CLOSED, was_published=True),
        }
        for kind, job in allowed.items():
            with self.subTest(kind=kind):
                self.job = job
                await self._check(kind)

        refused = {
            "initial": _job(JobStatus.PUBLISHED),
            "revision": _job(JobStatus.PUBLISHED),  # nothing staged
            "close": _job(JobStatus.DRAFT),
            "reopen": _job(JobStatus.PUBLISHED),
        }
        for kind, job in refused.items():
            with self.subTest(kind=kind):
                self.job = job
                with self.assertRaises(ValueError):
                    await self._check(kind)

    async def test_an_unknown_kind_or_missing_posting_is_refused(self):
        with self.assertRaises(ValueError):
            await self._check("delete")
        self.job = None
        with self.assertRaises(ValueError):
            await self._check("initial")

    async def test_raising_moves_the_posting_to_its_waiting_status(self):
        waiting = {
            "initial": (JobStatus.DRAFT, JobStatus.PENDING_REVIEW),
            "revision": (JobStatus.PUBLISHED, JobStatus.PUBLISHED_PENDING_REVISION),
            "close": (JobStatus.PUBLISHED, JobStatus.PENDING_CLOSE),
            "reopen": (JobStatus.CLOSED, JobStatus.PENDING_REOPEN),
        }
        for kind, (before, after) in waiting.items():
            with self.subTest(kind=kind):
                self.job = _job(before)
                await self.handler.on_raised(self.session, _request(kind))
                self.assertEqual(self.job.status, after)
                self.jobs.update_job.assert_awaited_with(self.session, self.job)

    async def test_approving_moves_the_posting_on(self):
        self.job = _job(JobStatus.PENDING_REVIEW)
        await self.handler.execute(self.session, _request("initial"), actor_id=REVIEWER)
        self.assertEqual(
            (self.job.status, self.job.was_published), (JobStatus.PUBLISHED, True)
        )

        self.job = _job(JobStatus.PENDING_CLOSE, was_published=True)
        await self.handler.execute(self.session, _request("close"), actor_id=REVIEWER)
        self.assertEqual(self.job.status, JobStatus.CLOSED)

    async def test_approving_a_revision_applies_the_staged_edit(self):
        self.job = _job(
            JobStatus.PUBLISHED_PENDING_REVISION,
            pending_payload=dict(_STAGED),
            was_published=True,
        )

        await self.handler.execute(
            self.session, _request("revision"), actor_id=REVIEWER
        )

        self.assertEqual(self.job.status, JobStatus.PUBLISHED)
        self.assertEqual(self.job.title, "Staged title")
        self.assertIsNone(self.job.pending_payload)

    async def test_approving_a_reopen_applies_a_staged_edit_if_there_is_one(self):
        self.job = _job(
            JobStatus.PENDING_REOPEN, pending_payload=dict(_STAGED), was_published=True
        )
        await self.handler.execute(self.session, _request("reopen"), actor_id=REVIEWER)
        self.assertEqual(
            (self.job.status, self.job.title), (JobStatus.PUBLISHED, "Staged title")
        )

        self.job = _job(JobStatus.PENDING_REOPEN, was_published=True)
        await self.handler.execute(self.session, _request("reopen"), actor_id=REVIEWER)
        self.assertEqual(
            (self.job.status, self.job.title), (JobStatus.PUBLISHED, "Live title")
        )

    async def test_rejecting_or_withdrawing_puts_the_posting_back(self):
        back = {
            "initial": (JobStatus.PENDING_REVIEW, JobStatus.DRAFT),
            "revision": (JobStatus.PUBLISHED_PENDING_REVISION, JobStatus.PUBLISHED),
            "close": (JobStatus.PENDING_CLOSE, JobStatus.PUBLISHED),
            "reopen": (JobStatus.PENDING_REOPEN, JobStatus.CLOSED),
        }
        for kind, (before, after) in back.items():
            with self.subTest(kind=kind):
                self.job = _job(before, pending_payload=dict(_STAGED))
                await self.handler.revert(self.session, _request(kind))
                self.assertEqual(self.job.status, after)
                # A sent-back revision keeps its edit so it can be fixed and
                # sent again.
                self.assertEqual(self.job.pending_payload, _STAGED)

    async def test_approval_rechecks_the_config_except_for_a_close(self):
        self.job = _job(JobStatus.PENDING_REVIEW)
        self.assertEqual(
            await self.handler.problems_at_approval(self.session, _request("initial")),
            [],
        )

        # Owner 21 can no longer advance applications.
        self.perms.get_active_users_with_permission.return_value = []
        problems = await self.handler.problems_at_approval(
            self.session, _request("initial")
        )
        self.assertEqual(problems, ["owners [21] no longer qualify"])

        # A close publishes nothing, so a blocked owner cannot trap it open.
        self.assertEqual(
            await self.handler.problems_at_approval(self.session, _request("close")),
            [],
        )


class ApplyPendingPayloadTest(unittest.TestCase):
    def test_a_missing_key_clears_its_field(self):
        job = _job(JobStatus.PUBLISHED, pending_payload={"title": "Only a title"})

        apply_pending_payload(job)

        self.assertEqual(job.title, "Only a title")
        self.assertIsNone(job.description)
        self.assertIsNone(job.pending_payload)


if __name__ == "__main__":
    unittest.main()
