import unittest
from unittest.mock import AsyncMock, MagicMock, create_autospec

from backend.recruiting.job_service import JobService
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.dto.job_dto import JobCreateDto
from backend.entity.job_entity import JobEntity
from backend.entity.job_review_entity import JobReviewEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.notification_repository import NotificationRepository
from backend.common.permissions import Permission
from backend.common.recruiting_enums import (
    JobKind,
    JobReviewKind,
    JobReviewStatus,
    JobStatus,
    NotificationType,
)
from backend.common.mentorship_enums import ParticipantRole


class TestJobService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        def _create(session, entity):
            entity.job_id = 1
            return entity

        self.repo = MagicMock()
        self.repo.get_by_job_id = AsyncMock()
        self.repo.create_job = AsyncMock(side_effect=_create)
        self.repo.update_job = AsyncMock(side_effect=lambda session, entity: entity)
        self.repo.list_all = AsyncMock(return_value=[])
        self.repo.delete_job = AsyncMock()
        self.perms = MagicMock()
        self.perms.get_active_users_with_permission = AsyncMock(return_value=[])
        self.review_repo = MagicMock()
        self.review_repo.create = AsyncMock(side_effect=lambda session, entity: entity)
        self.review_repo.get = AsyncMock()
        self.review_repo.get_open_for_job = AsyncMock(return_value=None)
        self.review_repo.list_by_reviewer = AsyncMock(return_value=[])
        self.review_repo.get_latest_reviews = AsyncMock(return_value={})
        self.session = AsyncMock()
        self.notification_repo = create_autospec(NotificationRepository, instance=True)
        self.users_repo = MagicMock()
        self.users_repo.get_all_by_ids = AsyncMock(return_value=[])
        self.job_activity_repo = MagicMock()
        self.job_activity_repo.create = AsyncMock()
        self.job_activity_repo.list_by_job = AsyncMock(return_value=[])
        self.service = JobService(
            self.repo,
            RecruitingMapper(),
            self.perms,
            self.review_repo,
            self.notification_repo,
            self.users_repo,
            self.job_activity_repo,
        )

    def _job(self, **kw):
        defaults = {"kind": JobKind.ACTIVITY, "title": "T", "status": JobStatus.DRAFT}
        defaults.update(kw)
        job = JobEntity(**defaults)
        job.job_id = 1
        return job

    def _approver(self, uid):
        u = UsersEntity(
            first_name=f"A{uid}", last_name="X", primary_email=f"a{uid}@x.com"
        )
        u.user_id = uid
        return u

    def _two_approvers(self):
        """Make reviewer id 2 a valid approver alongside id 3."""
        self.perms.get_active_users_with_permission.return_value = [
            self._approver(2),
            self._approver(3),
        ]

    def _make_users(self, *ids):
        """Build lightweight user mocks exposing only ``user_id``."""
        users = []
        for uid in ids:
            u = MagicMock()
            u.user_id = uid
            users.append(u)
        return users

    async def test_create_stores_pipeline_config(self):
        """create_job persists pipeline_config and starts in DRAFT."""
        dto = JobCreateDto(
            title="SWE",
            kind=JobKind.EMPLOYMENT,
            pipelineConfig={"stages": [{"stage": "tech", "rounds": 1}]},
        )
        result = await self.service.create_job(self.session, dto, created_by=1)

        self.assertEqual(result.pipeline_config["stages"][0]["stage"], "tech")
        self.assertEqual(result.status, JobStatus.DRAFT)

    async def test_create_logs_job_created_activity(self):
        """create_job writes a job_created activity entry attributed to the creator."""
        dto = JobCreateDto(title="T", kind=JobKind.ACTIVITY)

        await self.service.create_job(self.session, dto, created_by=7)

        self.job_activity_repo.create.assert_awaited_once_with(
            self.session, 1, 7, "job_created"
        )

    async def test_get_job_exposes_pending_payload(self):
        """get_job surfaces pending_payload straight through from the entity."""
        job = self._job(status=JobStatus.PUBLISHED_PENDING_REVISION)
        job.pending_payload = {"title": "New title"}
        self.repo.get_by_job_id.return_value = job

        result = await self.service.get_job(self.session, job.job_id)

        self.assertEqual(result.pending_payload, {"title": "New title"})

    async def test_get_job_includes_reviewer_id_from_open_review(self):
        """get_job surfaces reviewer_id from the job's open PENDING review."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        open_review = JobReviewEntity(
            review_id=5,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=4,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.get_open_for_job = AsyncMock(return_value=open_review)

        result = await self.service.get_job(self.session, job.job_id)

        self.assertEqual(result.reviewer_id, 4)

    async def test_get_job_reviewer_id_none_without_open_review(self):
        """get_job leaves reviewer_id None when there is no open review."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job

        result = await self.service.get_job(self.session, job.job_id)

        self.assertIsNone(result.reviewer_id)

    async def test_update_published_any_field_parks_pending_payload(self):
        """Editing a PUBLISHED posting — any field — parks a full draft, live fields untouched."""
        job = self._job(
            status=JobStatus.PUBLISHED,
            title="old title",
            description="old desc",
            form_schema={"questions": []},
            cooldown_days=30,
        )
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(
            title="new title", kind=job.kind, description="old desc", cooldownDays=90
        )

        result = await self.service.update_job(self.session, job.job_id, dto)

        self.assertEqual(result.status, JobStatus.PUBLISHED_PENDING_REVISION)
        self.assertEqual(result.title, "old title")  # live field untouched
        self.assertEqual(result.pending_payload["title"], "new title")
        self.assertEqual(result.pending_payload["formSchema"], {"questions": []})
        self.assertEqual(result.pending_payload["cooldownDays"], 90)

    async def test_update_published_omitted_optional_field_falls_back_to_live(self):
        """A dto with screen_rules/form_schema/pipeline_config/profile_config left
        unset must not blank those fields out in the resulting pending_payload."""
        job = self._job(
            status=JobStatus.PUBLISHED,
            screen_rules={"rules": [{"id": "r1"}]},
            form_schema={"questions": [{"id": "q1"}]},
            pipeline_config={"ownerId": 1, "stages": []},
            profile_config={"education": "required"},
        )
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(title=job.title, kind=job.kind)  # no config fields set

        result = await self.service.update_job(self.session, job.job_id, dto)

        self.assertEqual(
            result.pending_payload["screenRules"], {"rules": [{"id": "r1"}]}
        )
        self.assertEqual(
            result.pending_payload["formSchema"], {"questions": [{"id": "q1"}]}
        )
        self.assertEqual(
            result.pending_payload["pipelineConfig"], {"ownerId": 1, "stages": []}
        )
        self.assertEqual(
            result.pending_payload["profileConfig"], {"education": "required"}
        )

    async def test_update_published_explicit_cooldown_clear_is_not_a_fallback(self):
        """Sending cooldown_days=None on a PUBLISHED edit is an explicit clear,
        not 'leave unchanged' — unlike the four optional config fields."""
        job = self._job(status=JobStatus.PUBLISHED, cooldown_days=30)
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(title=job.title, kind=job.kind, cooldownDays=None)

        result = await self.service.update_job(self.session, job.job_id, dto)

        self.assertIsNone(result.pending_payload["cooldownDays"])

    async def test_create_job_stores_config_as_camelcase(self):
        """create_job serialises typed config to camelCase JSONB dicts."""
        dto = JobCreateDto(
            title="T",
            formSchema={
                "questions": [
                    {"id": "q1", "type": "long_text", "label": "Why", "maxWords": 300}
                ]
            },
            profileConfig={
                "education": "required",
                "workExperience": "optional",
                "resume": "off",
            },
        )
        await self.service.create_job(self.session, dto, created_by=1)
        entity = self.repo.create_job.call_args.args[1]
        self.assertEqual(entity.form_schema["questions"][0]["maxWords"], 300)
        self.assertEqual(entity.profile_config["education"], "required")

    async def test_create_job_rejects_unqualified_assignee(self):
        """A pre-set assignee who is not an interview evaluator is rejected."""
        self.perms.get_active_users_with_permission = AsyncMock(return_value=[])
        dto = JobCreateDto(
            title="T",
            pipelineConfig={
                "stages": [
                    {
                        "stage": "recruiter_screening",
                        "rounds": 1,
                        "defaultAssigneeId": 7,
                    }
                ]
            },
        )
        with self.assertRaises(ValueError):
            await self.service.create_job(self.session, dto, created_by=1)

    async def test_create_job_accepts_qualified_assignee_and_owner(self):
        """create_job succeeds when assignee/owner hold the right permissions."""

        async def pool(session, perm):
            if perm == Permission.RECRUITING_INTERVIEW_EVALUATE.value:
                return self._make_users(7)
            if perm == Permission.RECRUITING_APPLICATION_ADVANCE.value:
                return self._make_users(42)
            return []

        self.perms.get_active_users_with_permission = AsyncMock(side_effect=pool)
        dto = JobCreateDto(
            title="T",
            pipelineConfig={
                "ownerId": 42,
                "stages": [
                    {
                        "stage": "recruiter_screening",
                        "rounds": 1,
                        "defaultAssigneeId": 7,
                    }
                ],
            },
        )
        result = await self.service.create_job(self.session, dto, created_by=1)
        self.assertEqual(result.title, "T")

    async def test_create_job_rejects_unqualified_owner(self):
        """An owner who cannot advance applications is rejected."""

        async def pool(session, perm):
            if perm == Permission.RECRUITING_INTERVIEW_EVALUATE.value:
                return self._make_users(7)
            return []  # no advancers

        self.perms.get_active_users_with_permission = AsyncMock(side_effect=pool)
        dto = JobCreateDto(title="T", pipelineConfig={"ownerId": 99, "stages": []})
        with self.assertRaises(ValueError):
            await self.service.create_job(self.session, dto, created_by=1)

    async def test_create_job_accepts_multiple_qualified_owners(self):
        """create_job succeeds when every listed owner can advance applications."""

        async def pool(session, perm):
            if perm == Permission.RECRUITING_APPLICATION_ADVANCE.value:
                return self._make_users(42, 43)
            return []

        self.perms.get_active_users_with_permission = AsyncMock(side_effect=pool)
        dto = JobCreateDto(
            title="T", pipelineConfig={"ownerIds": [42, 43], "stages": []}
        )
        result = await self.service.create_job(self.session, dto, created_by=1)
        self.assertEqual(result.title, "T")

    async def test_create_job_rejects_any_unqualified_owner_names_offenders(self):
        """When one of several owners cannot advance applications, name it."""

        async def pool(session, perm):
            if perm == Permission.RECRUITING_APPLICATION_ADVANCE.value:
                return self._make_users(42)
            return []

        self.perms.get_active_users_with_permission = AsyncMock(side_effect=pool)
        dto = JobCreateDto(
            title="T", pipelineConfig={"ownerIds": [42, 99], "stages": []}
        )
        with self.assertRaisesRegex(ValueError, "99"):
            await self.service.create_job(self.session, dto, created_by=1)

    async def test_update_draft_changes_live_directly(self):
        """Editing a DRAFT posting mutates the live fields with no review gate."""
        job = self._job(status=JobStatus.DRAFT, title="old")
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(title="new", kind=job.kind)

        result = await self.service.update_job(self.session, job.job_id, dto)

        self.assertEqual(result.title, "new")
        self.assertEqual(result.status, JobStatus.DRAFT)

    async def test_list_active_approvers_maps_users(self):
        """list_active_approvers maps active job.approve holders to ApproverDto."""
        u1 = UsersEntity(first_name="Ann", last_name="Lee", primary_email="ann@x.com")
        u1.user_id = 7
        u2 = UsersEntity(first_name="Bo", last_name="Ng", primary_email="bo@x.com")
        u2.user_id = 8
        self.perms.get_active_users_with_permission.return_value = [u1, u2]

        result = await self.service.list_active_approvers(self.session)

        self.assertEqual([a.user_id for a in result], [7, 8])
        self.assertEqual(result[0].name, "Ann Lee")
        self.assertEqual(result[0].email, "ann@x.com")

    async def test_submit_rejects_self_review(self):
        """A submitter cannot pick themselves as the reviewer."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, "self"):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=1, submitted_by=1, message=None
            )

    async def test_submit_requires_two_approvers(self):
        """Submission needs an approver pool of at least two."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job
        self.perms.get_active_users_with_permission.return_value = [self._approver(2)]

        with self.assertRaisesRegex(ValueError, "pool"):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )

    async def test_submit_rejects_reviewer_outside_pool(self):
        """The chosen reviewer must hold the approve permission."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()  # ids 2 and 3

        with self.assertRaisesRegex(ValueError, "approver"):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=9, submitted_by=1, message=None
            )

    async def test_submit_rejects_when_review_already_open(self):
        """A posting with a pending review cannot open a second one."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()
        self.review_repo.get_open_for_job.return_value = JobReviewEntity(
            review_id=99,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )

        with self.assertRaisesRegex(ValueError, "already has an open review"):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )
        self.review_repo.create.assert_not_awaited()

    async def test_decision_locks_the_review_row(self):
        """approve fetches the review FOR UPDATE so deciders serialise."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=50,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.get.return_value = review

        await self.service.approve(self.session, review.review_id, acting_user_id=2)

        self.review_repo.get.assert_awaited_once_with(
            self.session, review.review_id, for_update=True
        )

    async def test_submit_draft_creates_initial_review_and_flips_status(self):
        """Submitting a DRAFT opens an INITIAL review and moves to PENDING_REVIEW."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        result = await self.service.submit_for_review(
            self.session, job.job_id, reviewer_id=2, submitted_by=1, message="hi"
        )

        self.assertEqual(result.status, JobStatus.PENDING_REVIEW)
        self.review_repo.create.assert_awaited_once()
        created = self.review_repo.create.await_args.args[1]
        self.assertEqual(created.kind, JobReviewKind.INITIAL)
        self.assertEqual(created.status, JobReviewStatus.PENDING)
        self.assertEqual(created.reviewer_id, 2)
        self.assertEqual(result.reviewer_id, 2)

    async def test_submit_for_review_notifies_the_reviewer(self):
        """submit_for_review inserts a JOB_REVIEW_REQUESTED notification for the reviewer."""
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.DRAFT)
        job.job_id = 1
        job.pipeline_config = {}
        self.repo.get_by_job_id = AsyncMock(return_value=job)
        self.review_repo.get_open_for_job = AsyncMock(return_value=None)
        approver1 = UsersEntity(first_name="A", last_name="B", primary_email="a@b.com")
        approver1.user_id = 6
        approver2 = UsersEntity(first_name="C", last_name="D", primary_email="c@d.com")
        approver2.user_id = 7
        self.perms.get_active_users_with_permission = AsyncMock(
            return_value=[approver1, approver2]
        )

        await self.service.submit_for_review(self.session, 1, 6, 9, "please review")

        self.notification_repo.create.assert_awaited_once()
        (_session_arg, entity_arg), _ = self.notification_repo.create.call_args
        self.assertEqual(entity_arg.user_id, 6)
        self.assertEqual(entity_arg.type, NotificationType.JOB_REVIEW_REQUESTED)
        self.assertEqual(entity_arg.job_id, 1)
        self.assertEqual(entity_arg.actor_user_id, 9)

    async def test_submit_for_review_logs_review_opened_activity(self):
        """submit_for_review logs a review_opened activity entry."""
        self._two_approvers()
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job

        await self.service.submit_for_review(self.session, job.job_id, 2, 5, "please")

        self.job_activity_repo.create.assert_awaited_once_with(
            self.session,
            job.job_id,
            5,
            "review_opened",
            {"kind": "initial", "reviewerId": 2, "message": "please"},
        )

    async def test_submit_revision_keeps_published_pending(self):
        """Submitting a parked revision opens a REVISION review, status unchanged."""
        job = self._job(status=JobStatus.PUBLISHED_PENDING_REVISION)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        result = await self.service.submit_for_review(
            self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED_PENDING_REVISION)
        created = self.review_repo.create.await_args.args[1]
        self.assertEqual(created.kind, JobReviewKind.REVISION)

    async def test_approve_revision_applies_pending_payload(self):
        """Approving a REVISION applies the full pending_payload and clears it."""
        job = self._job(
            status=JobStatus.PUBLISHED_PENDING_REVISION,
            form_schema={"a": 1},
            title="old",
        )
        job.pending_payload = {
            "title": "new",
            "description": None,
            "cooldownDays": None,
            "screenRules": None,
            "formSchema": {"a": 2},
            "pipelineConfig": None,
            "profileConfig": None,
        }
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=5,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.REVISION,
        )
        self.review_repo.get.return_value = review

        result = await self.service.approve(
            self.session, review.review_id, acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)
        self.assertEqual(result.title, "new")
        self.assertEqual(result.form_schema, {"a": 2})
        self.assertIsNone(result.pending_payload)
        self.assertEqual(review.status, JobReviewStatus.APPROVED)
        self.assertIsNotNone(review.decided_at)

    async def test_approve_revision_tolerates_partial_pending_payload(self):
        """A partial pending_payload degrades missing keys to None instead of
        raising, even though _build_pending_payload never produces one today."""
        job = self._job(
            status=JobStatus.PUBLISHED_PENDING_REVISION,
            form_schema={"a": 1},
            title="old",
        )
        job.pending_payload = {"title": "x"}
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=42,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.REVISION,
        )
        self.review_repo.get.return_value = review

        result = await self.service.approve(
            self.session, review.review_id, acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)
        self.assertEqual(result.title, "x")
        self.assertIsNone(result.description)
        self.assertIsNone(result.form_schema)
        self.assertIsNone(result.pending_payload)

    async def test_approve_initial_publishes(self):
        """Approving an INITIAL review publishes the draft."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=6,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.get.return_value = review

        result = await self.service.approve(
            self.session, review.review_id, acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)

    async def test_approve_logs_review_decided_activity(self):
        """approve logs a review_decided activity entry."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            job_id=job.job_id,
            submitted_by=5,
            reviewer_id=9,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        review.review_id = 3
        self.review_repo.get.return_value = review

        await self.service.approve(self.session, 3, 9)

        self.job_activity_repo.create.assert_awaited_once_with(
            self.session,
            job.job_id,
            9,
            "review_decided",
            {"kind": "initial", "decision": "approved", "comment": None},
        )

    async def test_approve_requires_pending_review(self):
        """An already-decided review cannot be approved again."""
        review = JobReviewEntity(
            review_id=7,
            job_id=1,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.APPROVED,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.get.return_value = review

        with self.assertRaises(ValueError):
            await self.service.approve(self.session, review.review_id, acting_user_id=2)

    async def test_approve_rejects_non_assigned_reviewer(self):
        """Only the assigned reviewer may approve; others are rejected."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=40,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.get.return_value = review

        with self.assertRaisesRegex(ValueError, "assigned reviewer"):
            await self.service.approve(self.session, review.review_id, acting_user_id=3)
        # The posting must not have advanced.
        self.assertEqual(review.status, JobReviewStatus.PENDING)

    async def test_approve_rejects_submitter_self_decision(self):
        """The submitter cannot approve their own posting even if they act."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=41,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.get.return_value = review

        with self.assertRaisesRegex(ValueError, "assigned reviewer"):
            await self.service.approve(self.session, review.review_id, acting_user_id=1)

    async def test_reject_rejects_non_assigned_reviewer(self):
        """Only the assigned reviewer may reject; others are rejected."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=42,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.get.return_value = review

        with self.assertRaisesRegex(ValueError, "assigned reviewer"):
            await self.service.reject(
                self.session, review.review_id, comment="no", acting_user_id=3
            )
        self.assertEqual(review.status, JobReviewStatus.PENDING)

    async def test_reject_requires_comment(self):
        """Rejection requires a non-empty comment."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=8,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.get.return_value = review

        with self.assertRaisesRegex(ValueError, "comment"):
            await self.service.reject(
                self.session, review.review_id, comment="", acting_user_id=2
            )

    async def test_reject_initial_returns_to_draft(self):
        """Rejecting an INITIAL review sends the posting back to DRAFT."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=9,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.get.return_value = review

        result = await self.service.reject(
            self.session, review.review_id, comment="fix the form", acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.DRAFT)
        self.assertEqual(review.status, JobReviewStatus.REJECTED)
        self.assertEqual(review.reject_comment, "fix the form")

    async def test_reject_logs_review_decided_activity(self):
        """reject logs a review_decided activity entry with the comment."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            job_id=job.job_id,
            submitted_by=5,
            reviewer_id=9,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        review.review_id = 3
        self.review_repo.get.return_value = review

        await self.service.reject(self.session, 3, "not ready", 9)

        self.job_activity_repo.create.assert_awaited_once_with(
            self.session,
            job.job_id,
            9,
            "review_decided",
            {"kind": "initial", "decision": "rejected", "comment": "not ready"},
        )

    async def test_reject_revision_keeps_published_and_discards_pending(self):
        """Rejecting a REVISION discards the parked draft and stays PUBLISHED."""
        job = self._job(
            status=JobStatus.PUBLISHED_PENDING_REVISION,
            form_schema={"a": 1},
            title="old",
        )
        job.pending_payload = {"title": "new", "formSchema": {"a": 2}}
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=10,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.REVISION,
        )
        self.review_repo.get.return_value = review

        result = await self.service.reject(
            self.session, review.review_id, comment="no", acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)
        self.assertEqual(result.title, "old")
        self.assertEqual(result.form_schema, {"a": 1})
        self.assertIsNone(result.pending_payload)

    async def test_publish_job_is_removed(self):
        """Direct publish is gone; publishing only happens through approval."""
        self.assertFalse(hasattr(self.service, "publish_job"))

    async def test_list_all_jobs_returns_every_status(self):
        """list_all_jobs maps every posting the repository returns."""
        self.repo.list_all.return_value = [
            self._job(status=JobStatus.DRAFT),
            self._job(status=JobStatus.CLOSED),
        ]

        result = await self.service.list_all_jobs(self.session)

        self.assertEqual(len(result), 2)
        self.assertEqual(
            {r.status for r in result}, {JobStatus.DRAFT, JobStatus.CLOSED}
        )

    async def test_list_all_jobs_surfaces_latest_rejection_comment(self):
        """list_all_jobs populates last_reject_comment for jobs whose latest review is REJECTED."""
        job_with_reject = self._job(status=JobStatus.DRAFT)
        job_with_reject.job_id = 1
        job_no_reject = self._job(status=JobStatus.PUBLISHED)
        job_no_reject.job_id = 2
        self.repo.list_all.return_value = [job_with_reject, job_no_reject]

        rejected_review = JobReviewEntity(
            review_id=99,
            job_id=1,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.REJECTED,
            kind=JobReviewKind.INITIAL,
            reject_comment="fix the form",
        )
        self.review_repo.get_latest_reviews = AsyncMock(
            return_value={1: rejected_review}
        )

        result = await self.service.list_all_jobs(self.session)

        dto_1 = next(r for r in result if r.id == 1)
        dto_2 = next(r for r in result if r.id == 2)
        self.assertEqual(dto_1.last_reject_comment, "fix the form")
        self.assertIsNone(dto_2.last_reject_comment)

    async def test_list_all_jobs_no_comment_when_latest_is_approved(self):
        """last_reject_comment is None when the latest review was approved."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.job_id = 1
        self.repo.list_all.return_value = [job]

        approved_review = JobReviewEntity(
            review_id=100,
            job_id=1,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.APPROVED,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.get_latest_reviews = AsyncMock(
            return_value={1: approved_review}
        )

        result = await self.service.list_all_jobs(self.session)

        self.assertIsNone(result[0].last_reject_comment)

    async def test_list_all_jobs_includes_reviewer_id_for_open_review(self):
        """list_all_jobs surfaces reviewer_id when the latest review is still PENDING."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        job.job_id = 1
        self.repo.list_all.return_value = [job]

        pending_review = JobReviewEntity(
            review_id=101,
            job_id=1,
            submitted_by=1,
            reviewer_id=6,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.get_latest_reviews = AsyncMock(
            return_value={1: pending_review}
        )

        result = await self.service.list_all_jobs(self.session)

        self.assertEqual(result[0].reviewer_id, 6)

    async def test_list_all_jobs_reviewer_id_none_when_latest_is_decided(self):
        """reviewer_id is None once the latest review has been approved or rejected."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.job_id = 1
        self.repo.list_all.return_value = [job]

        approved_review = JobReviewEntity(
            review_id=102,
            job_id=1,
            submitted_by=1,
            reviewer_id=6,
            status=JobReviewStatus.APPROVED,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.get_latest_reviews = AsyncMock(
            return_value={1: approved_review}
        )

        result = await self.service.list_all_jobs(self.session)

        self.assertIsNone(result[0].reviewer_id)

    async def test_list_reviews_for_reviewer_returns_pending(self):
        """list_reviews_for_reviewer maps the reviewer's pending reviews with job title."""
        review = JobReviewEntity(
            review_id=11,
            job_id=1,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.list_by_reviewer.return_value = [review]
        job = self._job(title="Senior Engineer")
        self.repo.get_by_job_id.return_value = job

        result = await self.service.list_reviews_for_reviewer(self.session, 2)

        self.assertEqual([r.review_id for r in result], [11])
        self.assertEqual(result[0].job_title, "Senior Engineer")
        self.review_repo.list_by_reviewer.assert_awaited_once_with(
            self.session, 2, [JobReviewStatus.PENDING]
        )

    # ---------------------------------------------------------------------------
    # close_job
    # ---------------------------------------------------------------------------

    async def test_close_job_draft_succeeds(self):
        """close_job transitions a DRAFT posting to CLOSED."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job

        result = await self.service.close_job(self.session, job.job_id)

        self.assertEqual(result.status, JobStatus.CLOSED)

    async def test_close_job_published_raises(self):
        """close_job rejects a PUBLISHED posting; must use request_close instead."""
        job = self._job(status=JobStatus.PUBLISHED)
        self.repo.get_by_job_id.return_value = job

        with self.assertRaisesRegex(ValueError, "request_close"):
            await self.service.close_job(self.session, job.job_id)

    # ---------------------------------------------------------------------------
    # reopen_job removed
    # ---------------------------------------------------------------------------

    async def test_reopen_job_removed(self):
        """reopen_job no longer exists; callers must use request_reopen."""
        self.assertFalse(hasattr(self.service, "reopen_job"))

    # ---------------------------------------------------------------------------
    # request_close
    # ---------------------------------------------------------------------------

    async def test_request_close_published_creates_review(self):
        """request_close from PUBLISHED creates a CLOSE review and sets PENDING_CLOSE."""
        job = self._job(status=JobStatus.PUBLISHED)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        result = await self.service.request_close(
            self.session, job.job_id, reviewer_id=2, submitted_by=1, message="closing"
        )

        self.assertEqual(result.status, JobStatus.PENDING_CLOSE)
        self.review_repo.create.assert_awaited_once()
        created = self.review_repo.create.await_args.args[1]
        self.assertEqual(created.kind, JobReviewKind.CLOSE)
        self.assertEqual(created.status, JobReviewStatus.PENDING)
        self.assertEqual(created.reviewer_id, 2)
        self.assertEqual(created.submit_message, "closing")

    async def test_request_close_non_published_raises(self):
        """request_close from a non-PUBLISHED status raises ValueError."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaises(ValueError):
            await self.service.request_close(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )

    async def test_request_close_self_review_raises(self):
        """request_close blocks self-review."""
        job = self._job(status=JobStatus.PUBLISHED)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, "self"):
            await self.service.request_close(
                self.session, job.job_id, reviewer_id=1, submitted_by=1, message=None
            )

    async def test_request_close_pool_too_small_raises(self):
        """request_close blocks when the approver pool is fewer than two."""
        job = self._job(status=JobStatus.PUBLISHED)
        self.repo.get_by_job_id.return_value = job
        self.perms.get_active_users_with_permission.return_value = [self._approver(2)]

        with self.assertRaisesRegex(ValueError, "pool"):
            await self.service.request_close(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )

    async def test_request_close_reviewer_not_in_pool_raises(self):
        """request_close blocks a reviewer outside the active approver pool."""
        job = self._job(status=JobStatus.PUBLISHED)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, "approver"):
            await self.service.request_close(
                self.session, job.job_id, reviewer_id=9, submitted_by=1, message=None
            )

    # ---------------------------------------------------------------------------
    # request_reopen
    # ---------------------------------------------------------------------------

    async def test_request_reopen_closed_creates_review(self):
        """request_reopen from CLOSED creates a REOPEN review and sets PENDING_REOPEN."""
        job = self._job(status=JobStatus.CLOSED, was_published=True)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        result = await self.service.request_reopen(
            self.session, job.job_id, reviewer_id=2, submitted_by=1, message="reopening"
        )

        self.assertEqual(result.status, JobStatus.PENDING_REOPEN)
        self.review_repo.create.assert_awaited_once()
        created = self.review_repo.create.await_args.args[1]
        self.assertEqual(created.kind, JobReviewKind.REOPEN)
        self.assertEqual(created.status, JobReviewStatus.PENDING)

    async def test_request_reopen_non_closed_raises(self):
        """request_reopen from a non-CLOSED status raises ValueError."""
        job = self._job(status=JobStatus.PUBLISHED)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaises(ValueError):
            await self.service.request_reopen(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )

    async def test_request_reopen_never_published_raises(self):
        """A CLOSED posting that was never published cannot be reopened."""
        job = self._job(status=JobStatus.CLOSED, was_published=False)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, "never published"):
            await self.service.request_reopen(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )

    # ---------------------------------------------------------------------------
    # approve — CLOSE and REOPEN kinds
    # ---------------------------------------------------------------------------

    async def test_approve_close_review_closes_job(self):
        """Approving a CLOSE review transitions the posting to CLOSED."""
        job = self._job(status=JobStatus.PENDING_CLOSE)
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=20,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.CLOSE,
        )
        self.review_repo.get.return_value = review

        result = await self.service.approve(
            self.session, review.review_id, acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.CLOSED)
        self.assertEqual(review.status, JobReviewStatus.APPROVED)
        self.assertIsNotNone(review.decided_at)

    async def test_approve_reopen_with_pending_payload_applies_it(self):
        """Approving a REOPEN with a staged edit applies it and republishes."""
        job = self._job(
            status=JobStatus.PENDING_REOPEN, was_published=True, title="old"
        )
        job.pending_payload = {
            "title": "new",
            "description": None,
            "cooldownDays": None,
            "screenRules": None,
            "formSchema": None,
            "pipelineConfig": None,
            "profileConfig": None,
        }
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=11,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.REOPEN,
        )
        self.review_repo.get.return_value = review

        result = await self.service.approve(
            self.session, review.review_id, acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)
        self.assertEqual(result.title, "new")
        self.assertIsNone(result.pending_payload)
        self.assertTrue(result.was_published)

    async def test_approve_reopen_without_edit_just_publishes(self):
        """Approving a REOPEN with no staged edit only flips status."""
        job = self._job(
            status=JobStatus.PENDING_REOPEN, was_published=True, title="old"
        )
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=12,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.REOPEN,
        )
        self.review_repo.get.return_value = review

        result = await self.service.approve(
            self.session, review.review_id, acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)
        self.assertEqual(result.title, "old")

    # ---------------------------------------------------------------------------
    # reject — CLOSE and REOPEN kinds
    # ---------------------------------------------------------------------------

    async def test_reject_close_review_restores_published(self):
        """Rejecting a CLOSE review aborts the close and returns the posting to PUBLISHED."""
        job = self._job(status=JobStatus.PENDING_CLOSE)
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=22,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.CLOSE,
        )
        self.review_repo.get.return_value = review

        result = await self.service.reject(
            self.session, review.review_id, comment="keep it open", acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)
        self.assertEqual(review.status, JobReviewStatus.REJECTED)
        self.assertEqual(review.reject_comment, "keep it open")

    async def test_reject_reopen_review_keeps_pending_payload(self):
        """Rejecting a REOPEN reverts to CLOSED but keeps the staged draft."""
        job = self._job(status=JobStatus.PENDING_REOPEN, was_published=True)
        job.pending_payload = {"title": "draft title"}
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=13,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.REOPEN,
        )
        self.review_repo.get.return_value = review

        result = await self.service.reject(
            self.session, review.review_id, comment="not yet", acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.CLOSED)
        self.assertEqual(result.pending_payload, {"title": "draft title"})

    # ---------------------------------------------------------------------------
    # approve — was_published flag
    # ---------------------------------------------------------------------------

    async def test_approve_initial_sets_was_published(self):
        """Approving an INITIAL review marks the posting as was_published=True."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=30,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        self.review_repo.get.return_value = review

        await self.service.approve(self.session, review.review_id, acting_user_id=2)

        self.assertTrue(job.was_published)

    async def test_approve_close_does_not_change_was_published(self):
        """Approving a CLOSE review does not set was_published (it was already True)."""
        job = self._job(status=JobStatus.PENDING_CLOSE)
        job.was_published = True
        self.repo.get_by_job_id.return_value = job
        review = JobReviewEntity(
            review_id=31,
            job_id=job.job_id,
            submitted_by=1,
            reviewer_id=2,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.CLOSE,
        )
        self.review_repo.get.return_value = review

        await self.service.approve(self.session, review.review_id, acting_user_id=2)

        # Posting is now CLOSED; was_published must remain True.
        self.assertTrue(job.was_published)
        self.assertEqual(job.status, JobStatus.CLOSED)

    # ---------------------------------------------------------------------------
    # delete_job
    # ---------------------------------------------------------------------------

    async def test_delete_job_closed_never_published_calls_repo(self):
        """delete_job on a CLOSED, never-published posting calls repo.delete_job."""
        job = self._job(status=JobStatus.CLOSED)
        job.was_published = False
        self.repo.get_by_job_id.return_value = job

        await self.service.delete_job(self.session, job.job_id)

        self.repo.delete_job.assert_awaited_once_with(self.session, job)

    async def test_delete_job_ever_published_raises(self):
        """delete_job on a CLOSED posting that was_published raises ValueError."""
        job = self._job(status=JobStatus.CLOSED)
        job.was_published = True
        self.repo.get_by_job_id.return_value = job

        with self.assertRaises(ValueError):
            await self.service.delete_job(self.session, job.job_id)

    async def test_delete_job_non_closed_raises(self):
        """delete_job on a non-CLOSED posting raises ValueError."""
        job = self._job(status=JobStatus.DRAFT)
        job.was_published = False
        self.repo.get_by_job_id.return_value = job

        with self.assertRaises(ValueError):
            await self.service.delete_job(self.session, job.job_id)

    async def test_delete_job_published_raises(self):
        """delete_job on a PUBLISHED posting raises ValueError."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.was_published = True
        self.repo.get_by_job_id.return_value = job

        with self.assertRaises(ValueError):
            await self.service.delete_job(self.session, job.job_id)

    # ---------------------------------------------------------------------------
    # update_job — non-editable status guard
    # ---------------------------------------------------------------------------

    async def test_update_published_pending_revision_raises(self):
        """update_job raises ValueError and does not call repo when status is PUBLISHED_PENDING_REVISION."""
        job = self._job(status=JobStatus.PUBLISHED_PENDING_REVISION)
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(title="new title", kind=job.kind)

        with self.assertRaisesRegex(ValueError, "cannot be edited"):
            await self.service.update_job(self.session, job.job_id, dto)

        self.repo.update_job.assert_not_awaited()

    async def test_update_pending_review_raises(self):
        """update_job raises ValueError and does not call repo when status is PENDING_REVIEW."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(title="new title", kind=job.kind)

        with self.assertRaisesRegex(ValueError, "cannot be edited"):
            await self.service.update_job(self.session, job.job_id, dto)

        self.repo.update_job.assert_not_awaited()

    async def test_update_closed_never_published_raises(self):
        """A CLOSED posting that was never published cannot be edited."""
        job = self._job(status=JobStatus.CLOSED, was_published=False)
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(title="new title", kind=job.kind)

        with self.assertRaisesRegex(ValueError, "never published"):
            await self.service.update_job(self.session, job.job_id, dto)

        self.repo.update_job.assert_not_awaited()

    async def test_update_closed_parks_pending_payload_without_status_change(self):
        """Editing a CLOSED posting stages a draft but leaves status/live fields alone."""
        job = self._job(
            status=JobStatus.CLOSED,
            title="old title",
            was_published=True,
        )
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(title="new title", kind=job.kind)

        result = await self.service.update_job(self.session, job.job_id, dto)

        self.assertEqual(result.status, JobStatus.CLOSED)
        self.assertEqual(result.title, "old title")
        self.assertEqual(result.pending_payload["title"], "new title")

    async def test_update_published_changing_kind_raises(self):
        """kind is locked once published -- a differing value raises instead
        of being silently dropped."""
        job = self._job(status=JobStatus.PUBLISHED, kind=JobKind.ACTIVITY)
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(title=job.title, kind=JobKind.EMPLOYMENT)

        with self.assertRaises(ValueError):
            await self.service.update_job(self.session, job.job_id, dto)
        self.repo.update_job.assert_not_awaited()

    async def test_update_published_changing_mentorship_role_raises(self):
        """mentorship_role is locked once published, same as kind."""
        job = self._job(
            status=JobStatus.PUBLISHED,
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTOR,
        )
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(
            title=job.title, kind=job.kind, mentorship_role=ParticipantRole.MENTEE
        )

        with self.assertRaises(ValueError):
            await self.service.update_job(self.session, job.job_id, dto)
        self.repo.update_job.assert_not_awaited()

    async def test_update_published_same_kind_and_mentorship_role_succeeds(self):
        """Sending back the same kind/mentorship_role is not a change -- must
        not false-positive as a lock violation."""
        job = self._job(
            status=JobStatus.PUBLISHED,
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTOR,
        )
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(
            title="new title", kind=job.kind, mentorship_role=job.mentorship_role
        )

        result = await self.service.update_job(self.session, job.job_id, dto)

        self.assertEqual(result.status, JobStatus.PUBLISHED_PENDING_REVISION)

    async def test_update_closed_changing_kind_raises(self):
        """kind/mentorship_role stay locked for a CLOSED posting, same as PUBLISHED."""
        job = self._job(
            status=JobStatus.CLOSED,
            kind=JobKind.ACTIVITY,
            was_published=True,
        )
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(title=job.title, kind=JobKind.EMPLOYMENT)

        with self.assertRaises(ValueError):
            await self.service.update_job(self.session, job.job_id, dto)
        self.repo.update_job.assert_not_awaited()

    async def test_list_interview_pool(self):
        users = self._make_users(7, 8)
        for u in users:
            u.first_name, u.last_name, u.primary_email = "A", "B", "a@b.com"

        async def pool(session, perm):
            if perm == Permission.RECRUITING_INTERVIEW_EVALUATE.value:
                return users
            return []

        self.perms.get_active_users_with_permission = AsyncMock(side_effect=pool)
        result = await self.service.list_interview_pool(self.session)
        self.assertEqual({a.user_id for a in result}, {7, 8})

    async def test_list_job_owners(self):
        users = self._make_users(42)
        for u in users:
            u.first_name, u.last_name, u.primary_email = "O", "W", "o@w.com"
        self.perms.get_active_users_with_permission = AsyncMock(return_value=users)
        result = await self.service.list_job_owners(self.session)
        self.assertEqual(result[0].user_id, 42)

    # ---------------------------------------------------------------------------
    # cooldown_days plumbing + get_published_job
    # ---------------------------------------------------------------------------

    async def test_create_job_persists_cooldown_days(self):
        dto = JobCreateDto.model_validate({
            "title": "T",
            "kind": "employment",
            "cooldownDays": 90,
        })
        result = await self.service.create_job(self.session, dto, created_by=1)
        self.assertEqual(result.cooldown_days, 90)

    async def test_get_published_job_rejects_unpublished(self):
        self.repo.get_by_job_id = AsyncMock(
            return_value=self._job(status=JobStatus.DRAFT)
        )
        with self.assertRaises(ValueError):
            await self.service.get_published_job(self.session, 1)

    async def test_get_published_job_returns_published(self):
        self.repo.get_by_job_id = AsyncMock(
            return_value=self._job(status=JobStatus.PUBLISHED)
        )
        result = await self.service.get_published_job(self.session, 1)
        self.assertEqual(result.status, JobStatus.PUBLISHED)

    async def test_get_published_job_public_excludes_internal_config(self):
        """The candidate-facing projection must never leak internal config."""
        job = self._job(
            status=JobStatus.PUBLISHED,
            form_schema={"questions": []},
            profile_config={"resume": "required"},
        )
        job.screen_rules = {"rules": [{"id": "r1"}]}
        job.pipeline_config = {"stages": [{"stage": "tech", "ownerId": 9}]}
        job.pending_payload = {"formSchema": {"questions": [{"id": "leak"}]}}
        self.repo.get_by_job_id = AsyncMock(return_value=job)

        dto = await self.service.get_published_job_public(self.session, 1)

        self.assertEqual(dto.title, "T")
        self.assertEqual(dto.form_schema, {"questions": []})
        self.assertEqual(dto.profile_config, {"resume": "required"})
        self.assertFalse(hasattr(dto, "screen_rules"))
        self.assertFalse(hasattr(dto, "pipeline_config"))
        self.assertFalse(hasattr(dto, "pending_payload"))
        self.assertFalse(hasattr(dto, "last_reject_comment"))

        dumped = dto.model_dump()
        for leaked_field in (
            "screen_rules",
            "pipeline_config",
            "pending_payload",
            "last_reject_comment",
        ):
            self.assertNotIn(leaked_field, dumped)

    async def test_get_published_job_public_rejects_unpublished(self):
        self.repo.get_by_job_id = AsyncMock(
            return_value=self._job(status=JobStatus.DRAFT)
        )
        with self.assertRaises(ValueError):
            await self.service.get_published_job_public(self.session, 1)

    async def test_approve_notifies_the_submitter(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.DRAFT)
        job.job_id = 1
        review = JobReviewEntity(
            job_id=1,
            submitted_by=9,
            reviewer_id=6,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        review.review_id = 100
        self.review_repo.get = AsyncMock(return_value=review)
        self.repo.get_by_job_id = AsyncMock(return_value=job)

        await self.service.approve(self.session, 100, acting_user_id=6)

        self.notification_repo.create.assert_awaited_once()
        (_session_arg, entity_arg), _ = self.notification_repo.create.call_args
        self.assertEqual(entity_arg.user_id, 9)
        self.assertEqual(entity_arg.type, NotificationType.JOB_REVIEW_APPROVED)
        self.assertEqual(entity_arg.job_id, 1)
        self.assertEqual(entity_arg.job_review_id, 100)
        self.assertEqual(entity_arg.actor_user_id, 6)

    async def test_reject_notifies_the_submitter(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.DRAFT)
        job.job_id = 1
        review = JobReviewEntity(
            job_id=1,
            submitted_by=9,
            reviewer_id=6,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
        )
        review.review_id = 100
        self.review_repo.get = AsyncMock(return_value=review)
        self.repo.get_by_job_id = AsyncMock(return_value=job)

        await self.service.reject(
            self.session, 100, "needs more detail", acting_user_id=6
        )

        self.notification_repo.create.assert_awaited_once()
        (_session_arg, entity_arg), _ = self.notification_repo.create.call_args
        self.assertEqual(entity_arg.user_id, 9)
        self.assertEqual(entity_arg.type, NotificationType.JOB_REVIEW_REJECTED)
        self.assertEqual(entity_arg.job_id, 1)
        self.assertEqual(entity_arg.job_review_id, 100)
        self.assertEqual(entity_arg.actor_user_id, 6)

    async def test_list_published_returns_public_summaries(self):
        job1 = self._job(status=JobStatus.PUBLISHED)
        job2 = self._job(status=JobStatus.PUBLISHED)
        job2.job_id = 2
        self.repo.list_published = AsyncMock(return_value=[job1, job2])

        result = await self.service.list_published(self.session)

        self.assertEqual([d.id for d in result], [1, 2])
        for d in result:
            self.assertEqual(
                set(type(d).model_fields.keys()),
                {"id", "title", "kind", "description"},
            )


if __name__ == "__main__":
    unittest.main()
