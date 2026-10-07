import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from sqlalchemy.exc import IntegrityError

from backend.approval.approval_service import APPROVAL_CHECKS_FAILED, ApprovalService
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.exceptions import ConflictError
from backend.recruiting.job_review_handler import JOB_REVIEW, JobReviewHandler
from backend.recruiting.job_service import JobService
import backend.recruiting.recipient_resolvers  # noqa: F401 -- registers resolvers
from backend.repository.notification_repository import NotificationRepository
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.dto.job_dto import JobCreateDto
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.permissions import Permission
from backend.common.recruiting_enums import (
    JobKind,
    JobReviewKind,
    JobStatus,
    RecruitingEvent,
)
from backend.common.mentorship_enums import ParticipantRole

# Kept apart from the user ids the tests use (submitter 1, approvers 2 and
# 3) and from the request ids the fake repository hands out (301 up), so a
# read of the wrong one shows.
JOB_ID = 41


class _FakeApprovalRequestRepository:
    """In-memory ApprovalRequestRepository with the real one's semantics.

    Closing and reassigning only touch a pending row and say whether they
    did; "latest" is the request raised last; a second pending request on a
    target is refused the way the partial unique index refuses it.
    """

    def __init__(self):
        self.rows: list[ApprovalRequestEntity] = []
        self.created: list[ApprovalRequestEntity] = []
        self.get_calls: list[tuple[int, bool]] = []
        self._next_id = 301

    def add(self, **fields) -> ApprovalRequestEntity:
        row = ApprovalRequestEntity(**fields)
        row.request_id = self._next_id
        self._next_id += 1
        self.rows.append(row)
        return row

    def _matching(self, action, target_type, target_id=None):
        return [
            r
            for r in self.rows
            if r.action == action
            and r.target_type == target_type
            and (target_id is None or r.target_id == target_id)
        ]

    async def create(
        self,
        session,
        *,
        action,
        target_type,
        target_id,
        payload,
        reason,
        raised_by,
        reviewer_id,
    ):
        if await self.get_pending_for_target(session, action, target_type, target_id):
            raise IntegrityError("INSERT", {}, Exception("pending target"))
        row = self.add(
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
            reason=reason,
            raised_by=raised_by,
            reviewer_id=reviewer_id,
            status=ApprovalRequestStatus.PENDING,
        )
        self.created.append(row)
        return row

    async def get(self, session, request_id, *, for_update=False):
        self.get_calls.append((request_id, for_update))
        return next((r for r in self.rows if r.request_id == request_id), None)

    async def get_pending_for_target(self, session, action, target_type, target_id):
        return next(
            (
                r
                for r in self._matching(action, target_type, target_id)
                if r.status == ApprovalRequestStatus.PENDING
            ),
            None,
        )

    async def list_latest_for_targets(self, session, action, target_type, target_ids):
        latest = {}
        for r in self._matching(action, target_type):
            if r.target_id in target_ids:
                latest[r.target_id] = r
        return list(latest.values())

    async def get_latest_closed_for_target(
        self, session, action, target_type, target_id
    ):
        closed = [
            r
            for r in self._matching(action, target_type, target_id)
            if r.status != ApprovalRequestStatus.PENDING
        ]
        return closed[-1] if closed else None

    async def list_pending_for_reviewer(self, session, reviewer_id, actions):
        return [
            r
            for r in self.rows
            if r.reviewer_id == reviewer_id
            and r.status == ApprovalRequestStatus.PENDING
            and r.action in actions
        ]

    async def list_pending_raised_by(self, session, raised_by, actions):
        return [
            r
            for r in self.rows
            if r.raised_by == raised_by
            and r.status == ApprovalRequestStatus.PENDING
            and r.action in actions
        ]

    async def set_reviewer(self, session, request_id, reviewer_id):
        row = await self.get(session, request_id)
        if row is None or row.status != ApprovalRequestStatus.PENDING:
            return False
        row.reviewer_id = reviewer_id
        return True

    async def close(self, session, request_id, *, status, decided_by, decision_comment):
        row = await self.get(session, request_id)
        if row is None or row.status != ApprovalRequestStatus.PENDING:
            return False
        row.status = status
        row.decided_by = decided_by
        row.decided_at = datetime.now(timezone.utc)
        row.decision_comment = decision_comment
        return True


class TestJobService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        def _create(session, entity):
            entity.job_id = 1
            return entity

        self.repo = MagicMock()
        self.repo.get_by_job_id = AsyncMock()
        self.repo.get_by_job_ids = AsyncMock(return_value=[])
        self.repo.create_job = AsyncMock(side_effect=_create)
        self.repo.update_job = AsyncMock(side_effect=lambda session, entity: entity)
        self.repo.list_all = AsyncMock(return_value=[])
        self.repo.delete_job = AsyncMock()
        self.perms = MagicMock()
        self.perms.get_active_users_with_permission = AsyncMock(return_value=[])
        # The old review table; only delete_job still clears it.
        self.review_repo = MagicMock()
        self.review_repo.delete_by_job = AsyncMock()
        self.requests = _FakeApprovalRequestRepository()
        self.session = AsyncMock()
        self.event_repo = MagicMock()
        self.event_repo.list_by_subject = AsyncMock(return_value=[])

        async def _record(session, **kwargs):
            self.call_order.append("record")
            return None

        # One recorder for both modules: review events are written by the
        # approval service, the rest by the job service.
        self.record_event = AsyncMock(side_effect=_record)
        for target in (
            "backend.recruiting.job_service.record_event",
            "backend.approval.approval_service.record_event",
        ):
            recorder = patch(target, new=self.record_event)
            recorder.start()
            self.addCleanup(recorder.stop)
        self.notification_repo = self._notification_repository_double()
        self.users_repo = MagicMock()
        self.users_repo.get_all_by_ids = AsyncMock(return_value=[])
        self.user_emails_repo = MagicMock()
        self.user_emails_repo.get_contact_emails_by_user_ids = AsyncMock(
            return_value={}
        )
        self.approval_service = ApprovalService(
            self.requests,
            self.perms,
            self.users_repo,
            MagicMock(),
            handlers=[JobReviewHandler(self.repo, self.perms)],
        )
        self.service = JobService(
            self.repo,
            RecruitingMapper(),
            self.perms,
            self.review_repo,
            self.notification_repo,
            self.users_repo,
            self.user_emails_repo,
            self.event_repo,
            approval_service=self.approval_service,
        )

    def _seed_review(
        self,
        kind=JobReviewKind.INITIAL,
        *,
        status=ApprovalRequestStatus.PENDING,
        raised_by=1,
        reviewer_id=2,
        reason=None,
        decision_comment=None,
        job_id=JOB_ID,
    ) -> ApprovalRequestEntity:
        """Put a job review request in the fake repository and return it."""
        return self.requests.add(
            action=JOB_REVIEW,
            target_type="job",
            target_id=str(job_id),
            payload={"kind": kind.value},
            reason=reason,
            raised_by=raised_by,
            reviewer_id=reviewer_id,
            status=status,
            decision_comment=decision_comment,
        )

    def _notification_repository_double(self):
        """A notification repository stand-in, plus the ordering harness.

        `self.call_order` records the event write and the commit so a test can
        assert the rows land *inside* the transaction. Asserting only "it was
        awaited" would pass even if they were written after the commit, which
        would let a rollback drop the notifications while the change they
        announce survived.
        """
        self.call_order = []
        repository = create_autospec(NotificationRepository, instance=True)
        self.session.commit = AsyncMock(
            side_effect=lambda: self.call_order.append("commit")
        )
        return repository

    def _job(self, **kw):
        defaults = {"kind": JobKind.ACTIVITY, "title": "T", "status": JobStatus.DRAFT}
        defaults.update(kw)
        job = JobEntity(**defaults)
        job.job_id = JOB_ID
        return job

    def _approver(self, uid):
        u = UsersEntity(first_name=f"A{uid}", last_name="X")
        u.user_id = uid
        return u

    def _two_approvers(self):
        """Make reviewer id 2 a valid approver alongside id 3."""
        self.perms.get_active_users_with_permission.return_value = [
            self._approver(2),
            self._approver(3),
        ]

    def _make_users(self, *ids):
        """Build lightweight user mocks exposing ``user_id`` and the name columns.

        The three name attributes are explicit because a bare ``MagicMock``
        auto-creates them as mocks, which reads as "this person has a preferred
        name" and lets a display-name assertion pass on a mock repr.
        """
        users = []
        for uid in ids:
            u = MagicMock()
            u.user_id = uid
            u.first_name = None
            u.last_name = None
            u.preferred_name = None
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

        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="job",
            subject_id=1,
            actor_id=7,
            event_type=RecruitingEvent.JOB_CREATED,
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
        self._seed_review(raised_by=1, reviewer_id=4)

        result = await self.service.get_job(self.session, job.job_id)

        self.assertEqual(result.reviewer_id, 4)

    async def test_get_job_includes_submitted_by_from_open_review(self):
        """Who sent it up, so the page can tell whether the viewer may reassign.

        Reassignment is the submitter's alone, and nothing else on the posting
        says who that is -- the review id itself stays scoped to the assigned
        reviewer, who is the one person this action routes around.
        """
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        self._seed_review(raised_by=1, reviewer_id=4)

        result = await self.service.get_job(self.session, job.job_id)

        self.assertEqual(result.submitted_by, 1)

    async def test_get_job_submitted_by_none_without_open_review(self):
        """Nothing is waiting, so there is nobody whose request it is."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job

        result = await self.service.get_job(self.session, job.job_id)

        self.assertIsNone(result.submitted_by)

    async def test_get_job_reviewer_id_none_without_open_review(self):
        """get_job leaves reviewer_id None when there is no open review."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job

        result = await self.service.get_job(self.session, job.job_id)

        self.assertIsNone(result.reviewer_id)

    async def test_get_job_includes_submit_message_from_open_review(self):
        """get_job surfaces the requester's note from the job's open review."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        self._seed_review(
            raised_by=1, reviewer_id=4, reason="Please check the pipeline stages."
        )

        result = await self.service.get_job(self.session, job.job_id)

        self.assertEqual(result.submit_message, "Please check the pipeline stages.")

    async def test_get_job_submit_message_none_without_open_review(self):
        """get_job leaves submit_message None when no review is open."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job

        result = await self.service.get_job(self.session, job.job_id)

        self.assertIsNone(result.submit_message)

    async def test_get_job_surfaces_last_reject_kind(self):
        """get_job populates last_reject_comment/last_reject_kind from the job's most-recent rejected review, mirroring list_all_jobs."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job
        self._seed_review(
            JobReviewKind.REVISION,
            status=ApprovalRequestStatus.REJECTED,
            decision_comment="fix the title",
        )

        result = await self.service.get_job(self.session, job.job_id)

        self.assertEqual(result.last_reject_comment, "fix the title")
        self.assertEqual(result.last_reject_kind, "revision")

    async def test_get_job_no_reject_info_without_rejected_review(self):
        """get_job leaves last_reject_comment/last_reject_kind None when there's no rejected review."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job

        result = await self.service.get_job(self.session, job.job_id)

        self.assertIsNone(result.last_reject_comment)
        self.assertIsNone(result.last_reject_kind)

    async def test_update_published_any_field_parks_pending_payload(self):
        """Editing a PUBLISHED posting — any field — parks a full draft, live
        fields and status untouched (status stays PUBLISHED, mirroring CLOSED;
        the flip to PUBLISHED_PENDING_REVISION now happens at submit time)."""
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

        self.assertEqual(result.status, JobStatus.PUBLISHED)
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
                    {"id": "q1", "type": "long_text", "label": "Why", "maxLength": 300}
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
        self.assertEqual(entity.form_schema["questions"][0]["maxLength"], 300)
        self.assertEqual(entity.profile_config["education"], "required")

    def _form_dto(self, *, next_seq=None, ids=("q1",)):
        """A minimal formSchema payload for a JobCreateDto.

        Args:
            next_seq (int | None): ``nextSeq`` to send, or None to omit it the
                way a pre-counter client bundle would.
            ids (tuple[str, ...]): Question ids the form carries.

        Returns:
            dict: A camelCase formSchema dict.
        """
        form = {
            "questions": [
                {"id": qid, "type": "short_text", "label": qid.upper()} for qid in ids
            ]
        }
        if next_seq is not None:
            form["nextSeq"] = next_seq
        return form

    async def test_create_job_derives_next_seq_from_the_ids_present(self):
        """A create with no counter still persists one, past every live id."""
        dto = JobCreateDto(title="T", formSchema=self._form_dto(ids=("q1", "q2")))

        await self.service.create_job(self.session, dto, created_by=1)

        entity = self.repo.create_job.call_args.args[1]
        self.assertEqual(entity.form_schema["nextSeq"], 3)

    async def test_create_job_keeps_a_higher_incoming_next_seq(self):
        """A counter already past the floor (ids were deleted) is kept."""
        dto = JobCreateDto(title="T", formSchema=self._form_dto(next_seq=9))

        await self.service.create_job(self.session, dto, created_by=1)

        entity = self.repo.create_job.call_args.args[1]
        self.assertEqual(entity.form_schema["nextSeq"], 9)

    async def test_update_draft_keeps_the_stored_next_seq_when_absent(self):
        """A payload without a counter must not erase the stored one.

        A browser on a pre-counter bundle rebuilds formSchema as {questions}
        alone; letting that through would restart id recycling on the next
        delete-then-add.
        """
        job = self._job(
            status=JobStatus.DRAFT,
            form_schema={"questions": [{"id": "q1"}], "nextSeq": 12},
        )
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(title="T", kind=job.kind, formSchema=self._form_dto())

        result = await self.service.update_job(self.session, job.job_id, dto)

        self.assertEqual(result.form_schema["nextSeq"], 12)

    async def test_update_draft_keeps_the_stored_next_seq_over_a_lower_one(self):
        """The DTO's floor check only sees the live ids, not the stored counter.

        nextSeq=3 clears the floor for a form holding q1, so validation lets
        it through; only the comparison against the stored value stops it from
        rewinding the counter.
        """
        job = self._job(
            status=JobStatus.DRAFT,
            form_schema={"questions": [{"id": "q1"}], "nextSeq": 12},
        )
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(
            title="T", kind=job.kind, formSchema=self._form_dto(next_seq=3)
        )

        result = await self.service.update_job(self.session, job.job_id, dto)

        self.assertEqual(result.form_schema["nextSeq"], 12)

    async def test_update_draft_takes_a_higher_incoming_next_seq(self):
        """A client that has advanced the counter wins over the stored value."""
        job = self._job(
            status=JobStatus.DRAFT,
            form_schema={"questions": [{"id": "q1"}], "nextSeq": 12},
        )
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(
            title="T", kind=job.kind, formSchema=self._form_dto(next_seq=20)
        )

        result = await self.service.update_job(self.session, job.job_id, dto)

        self.assertEqual(result.form_schema["nextSeq"], 20)

    async def test_update_published_pending_payload_keeps_the_stored_next_seq(self):
        """The staged-edit path carries the counter forward too."""
        job = self._job(
            status=JobStatus.PUBLISHED,
            form_schema={"questions": [{"id": "q1"}], "nextSeq": 12},
        )
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(title="T", kind=job.kind, formSchema=self._form_dto())

        result = await self.service.update_job(self.session, job.job_id, dto)

        self.assertEqual(result.pending_payload["formSchema"]["nextSeq"], 12)

    async def test_update_published_pending_payload_takes_a_higher_next_seq(self):
        """A higher incoming counter reaches the staged payload."""
        job = self._job(
            status=JobStatus.PUBLISHED,
            form_schema={"questions": [{"id": "q1"}], "nextSeq": 12},
        )
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(
            title="T", kind=job.kind, formSchema=self._form_dto(next_seq=20)
        )

        result = await self.service.update_job(self.session, job.job_id, dto)

        self.assertEqual(result.pending_payload["formSchema"]["nextSeq"], 20)

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
        u1 = UsersEntity(first_name="Ann", last_name="Lee")
        u1.user_id = 7
        u2 = UsersEntity(first_name="Bo", last_name="Ng")
        u2.user_id = 8
        self.perms.get_active_users_with_permission.return_value = [u1, u2]
        # Approver emails come from user_emails, not the legacy column.
        self.user_emails_repo.get_contact_emails_by_user_ids.return_value = {
            7: "ann@x.com"
        }

        result = await self.service.list_active_approvers(self.session)

        self.assertEqual([a.user_id for a in result], [7, 8])
        self.assertEqual(result[0].name, "Ann Lee")
        self.assertEqual(result[0].email, "ann@x.com")
        # A user with no user_emails rows falls back to an empty address.
        self.assertEqual(result[1].email, "")

    def _valid_pipeline(self, owner_id=2):
        """A minimal submittable pipeline config: one stage + one owner."""
        return {
            "stages": [{"stage": "recruiter_screening", "rounds": 1}],
            "ownerIds": [owner_id],
        }

    def _qualify(self, job):
        """Give the job a valid live pipeline whose owner is in the pool."""
        job.pipeline_config = self._valid_pipeline(owner_id=2)
        self._two_approvers()

    async def test_submit_draft_without_pipeline_stages_raises(self):
        """A posting whose pipeline has no stages cannot be submitted — every
        posting needs at least one human stage as a screening fallback."""
        job = self._job(status=JobStatus.DRAFT)
        job.pipeline_config = {"stages": [], "ownerIds": [2]}
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, "pipeline stage"):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )
        self.assertEqual(self.requests.created, [])

    async def test_submit_draft_without_pipeline_config_raises(self):
        """A posting with no pipeline config at all is equally unsubmittable."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, "pipeline stage"):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )

    async def test_submit_draft_without_owner_raises(self):
        """A posting with no Recruiter owner cannot be submitted — applications
        would be visible to no one."""
        job = self._job(status=JobStatus.DRAFT)
        job.pipeline_config = {
            "stages": [{"stage": "recruiter_screening", "rounds": 1}],
            "ownerIds": [],
        }
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, "recruiter"):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )
        self.assertEqual(self.requests.created, [])

    async def test_submit_draft_with_legacy_single_owner_passes(self):
        """The legacy single-``ownerId`` shape satisfies the owner requirement."""
        job = self._job(status=JobStatus.DRAFT)
        job.pipeline_config = {
            "stages": [{"stage": "recruiter_screening", "rounds": 1}],
            "ownerId": 2,
        }
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        result = await self.service.submit_for_review(
            self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
        )

        self.assertEqual(result.status, JobStatus.PENDING_REVIEW)

    async def test_submit_for_review_names_the_submitter_and_their_note(self):
        """The response describes the review it just opened, so it names it.

        ``get_job`` reads both fields off the open review and returns them.
        Leaving them out here has the two endpoints disagree about whether
        anyone submitted this posting at all.
        """
        job = self._job(status=JobStatus.DRAFT)
        job.pipeline_config = self._valid_pipeline()
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        result = await self.service.submit_for_review(
            self.session,
            job.job_id,
            reviewer_id=2,
            submitted_by=1,
            message="Ready for you",
        )

        self.assertEqual(result.submitted_by, 1)
        self.assertEqual(result.submit_message, "Ready for you")

    async def test_submit_revision_validates_staged_pipeline_not_live(self):
        """A staged edit that empties the pipeline is caught at submit time,
        even when the live config is still valid."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.pipeline_config = self._valid_pipeline()
        job.pending_payload = {
            "title": "new",
            "pipelineConfig": {"stages": [], "ownerIds": [2]},
        }
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, "pipeline stage"):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )

    async def test_submit_revision_rechecks_staged_assignee_permission(self):
        """The assignee/owner permission re-check runs against the staged
        config (what would go live), not the current live config."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.pipeline_config = self._valid_pipeline()
        job.pending_payload = {
            "title": "new",
            "pipelineConfig": {
                "stages": [
                    {
                        "stage": "recruiter_screening",
                        "rounds": 1,
                        "defaultAssigneeId": 8,
                    }
                ],
                "ownerIds": [2],
            },
        }
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()  # pool is ids 2 and 3 — 8 no longer qualifies

        with self.assertRaisesRegex(ValueError, "no longer qualify"):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )

    async def test_submit_rejects_self_review(self):
        """A submitter cannot pick themselves as the reviewer."""
        job = self._job(status=JobStatus.DRAFT)
        job.pipeline_config = self._valid_pipeline(owner_id=2)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, "your own request"):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=1, submitted_by=1, message=None
            )

    async def test_submit_allows_single_approver_pool(self):
        """Submission has no minimum pool size — one eligible approver suffices."""
        job = self._job(status=JobStatus.DRAFT)
        job.pipeline_config = self._valid_pipeline(owner_id=2)
        self.repo.get_by_job_id.return_value = job
        self.perms.get_active_users_with_permission.return_value = [self._approver(2)]

        result = await self.service.submit_for_review(
            self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
        )

        self.assertEqual(result.reviewer_id, 2)

    async def test_submit_rejects_reviewer_outside_pool(self):
        """The chosen reviewer must hold the approve permission."""
        job = self._job(status=JobStatus.DRAFT)
        job.pipeline_config = self._valid_pipeline(owner_id=2)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()  # ids 2 and 3

        with self.assertRaisesRegex(ValueError, "cannot review this request"):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=9, submitted_by=1, message=None
            )

    async def test_submit_rejects_when_review_already_open(self):
        """A posting waiting on a review is in its pending status, which is
        what refuses a second submission."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        job.pipeline_config = self._valid_pipeline(owner_id=2)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()
        self._seed_review(JobReviewKind.INITIAL)

        with self.assertRaisesRegex(ValueError, "cannot be submitted"):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )
        self.assertEqual(self.requests.created, [])

    async def test_submit_refuses_a_second_pending_review_even_from_draft(self):
        """Should the status ever disagree with the open review, the one
        pending request per posting still holds, as a conflict."""
        job = self._job(status=JobStatus.DRAFT)
        job.pipeline_config = self._valid_pipeline(owner_id=2)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()
        self._seed_review(JobReviewKind.INITIAL)

        with self.assertRaises(ConflictError):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )
        self.assertEqual(self.requests.created, [])
        self.assertEqual(job.status, JobStatus.DRAFT)

    async def test_decision_locks_the_review_row(self):
        """approve fetches the review FOR UPDATE so deciders serialise."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        self._qualify(job)
        review = self._seed_review(JobReviewKind.INITIAL)

        await self.service.approve(self.session, review.request_id, acting_user_id=2)

        self.assertIn((review.request_id, True), self.requests.get_calls)

    async def test_submit_draft_creates_initial_review_and_flips_status(self):
        """Submitting a DRAFT opens an INITIAL review and moves to PENDING_REVIEW."""
        job = self._job(status=JobStatus.DRAFT)
        job.pipeline_config = self._valid_pipeline(owner_id=2)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        result = await self.service.submit_for_review(
            self.session, job.job_id, reviewer_id=2, submitted_by=1, message="hi"
        )

        self.assertEqual(result.status, JobStatus.PENDING_REVIEW)
        (created,) = self.requests.created
        self.assertEqual(created.payload["kind"], JobReviewKind.INITIAL)
        self.assertEqual(created.status, ApprovalRequestStatus.PENDING)
        self.assertEqual(created.reviewer_id, 2)
        self.assertEqual(result.reviewer_id, 2)

    async def test_submit_for_review_records_the_notification_inside_the_transaction(
        self,
    ):
        # Same setup as test_submit_for_review_notifies_the_reviewer.
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.DRAFT)
        job.job_id = JOB_ID
        job.pipeline_config = self._valid_pipeline(owner_id=6)
        self.repo.get_by_job_id = AsyncMock(return_value=job)
        approver1 = UsersEntity(first_name="A", last_name="B")
        approver1.user_id = 6
        approver2 = UsersEntity(first_name="C", last_name="D")
        approver2.user_id = 7
        self.perms.get_active_users_with_permission = AsyncMock(
            return_value=[approver1, approver2]
        )

        await self.service.submit_for_review(
            self.session, JOB_ID, 6, 9, "please review"
        )

        self.record_event.assert_awaited_once()
        self.assertEqual(self.call_order, ["record", "commit"])

    async def test_submit_for_review_records_review_opened(self):
        """submit_for_review records a review_opened event."""
        self._two_approvers()
        job = self._job(status=JobStatus.DRAFT)
        job.pipeline_config = self._valid_pipeline(owner_id=2)
        self.repo.get_by_job_id.return_value = job

        await self.service.submit_for_review(self.session, job.job_id, 2, 5, "please")

        (created,) = self.requests.created
        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="job",
            subject_id=job.job_id,
            actor_id=5,
            event_type=RecruitingEvent.REVIEW_OPENED,
            details={
                "kind": "initial",
                "reviewId": created.request_id,
                "message": "please",
                "requestId": created.request_id,
                "action": JOB_REVIEW,
            },
        )

    async def test_submit_for_review_stores_a_blank_message_as_none(self):
        """The note is optional; whitespace is no note at all."""
        self._two_approvers()
        job = self._job(status=JobStatus.DRAFT)
        job.pipeline_config = self._valid_pipeline(owner_id=2)
        self.repo.get_by_job_id.return_value = job

        result = await self.service.submit_for_review(
            self.session, job.job_id, reviewer_id=2, submitted_by=1, message="   "
        )

        (created,) = self.requests.created
        self.assertIsNone(created.reason)
        self.assertIsNone(result.submit_message)
        self.assertIsNone(self.record_event.await_args.kwargs["details"]["message"])

    async def test_review_opened_names_the_review_it_just_opened(self):
        """The id on the event has to be the review this call created.

        The resolver reads the reviewer off that row, so emitting the wrong
        id -- or spelling the key differently -- resolves to nobody, or to
        somebody else's reviewer, without erroring. What the resolver does
        with the id once it has it is covered against a real database in
        recipient_resolvers_test.
        """
        self._two_approvers()
        job = self._job(status=JobStatus.DRAFT)
        job.pipeline_config = self._valid_pipeline(owner_id=2)
        self.repo.get_by_job_id.return_value = job

        # An earlier, closed review of the same posting holds an id the event
        # must not pick up.
        self._seed_review(status=ApprovalRequestStatus.REJECTED, decision_comment="no")

        await self.service.submit_for_review(self.session, job.job_id, 2, 5, "please")

        (created,) = self.requests.created
        self.assertEqual(
            self.record_event.await_args.kwargs["details"]["reviewId"],
            created.request_id,
        )

    async def test_submit_published_with_staged_edit_opens_revision_review(self):
        """Submitting a PUBLISHED posting with a staged edit opens a REVISION
        review and flips status to PUBLISHED_PENDING_REVISION — the flip now
        happens at submit time, not at edit time."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.pending_payload = {
            "title": "new",
            "pipelineConfig": self._valid_pipeline(),
        }
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        result = await self.service.submit_for_review(
            self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED_PENDING_REVISION)
        (created,) = self.requests.created
        self.assertEqual(created.payload["kind"], JobReviewKind.REVISION)

    async def test_submit_published_without_staged_edit_raises(self):
        """Submitting a PUBLISHED posting with nothing staged is rejected —
        there is no draft to send for review."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.pipeline_config = self._valid_pipeline()
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, "nothing staged"):
            await self.service.submit_for_review(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )

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
            "pipelineConfig": self._valid_pipeline(),
            "profileConfig": None,
        }
        self.repo.get_by_job_id.return_value = job
        self._qualify(job)
        review = self._seed_review(JobReviewKind.REVISION)

        result = await self.service.approve(
            self.session, review.request_id, acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)
        self.assertEqual(result.title, "new")
        self.assertEqual(result.form_schema, {"a": 2})
        self.assertIsNone(result.pending_payload)
        self.assertEqual(review.status, ApprovalRequestStatus.APPROVED)
        self.assertIsNotNone(review.decided_at)

    async def test_approve_revision_tolerates_partial_pending_payload(self):
        """A partial pending_payload degrades missing keys to None instead of
        raising, even though _build_pending_payload never produces one today."""
        job = self._job(
            status=JobStatus.PUBLISHED_PENDING_REVISION,
            form_schema={"a": 1},
            title="old",
        )
        job.pending_payload = {"title": "x", "pipelineConfig": self._valid_pipeline()}
        self.repo.get_by_job_id.return_value = job
        self._qualify(job)
        review = self._seed_review(JobReviewKind.REVISION)

        result = await self.service.approve(
            self.session, review.request_id, acting_user_id=2
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
        self._qualify(job)
        review = self._seed_review(JobReviewKind.INITIAL)

        result = await self.service.approve(
            self.session, review.request_id, acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)

    async def test_approve_logs_review_decided_activity(self):
        """approve logs a review_decided activity entry."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        self._qualify(job)
        review = self._seed_review(JobReviewKind.INITIAL, raised_by=5, reviewer_id=9)

        await self.service.approve(self.session, review.request_id, 9)

        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="job",
            subject_id=job.job_id,
            actor_id=9,
            event_type=RecruitingEvent.REVIEW_DECIDED,
            details={
                "kind": "initial",
                "reviewId": review.request_id,
                "message": None,
                "requestId": review.request_id,
                "action": JOB_REVIEW,
                "decision": "approved",
                "comment": None,
            },
        )

    async def test_approve_requires_pending_review(self):
        """An already-decided review cannot be approved again."""
        job = self._job(status=JobStatus.PUBLISHED)
        self.repo.get_by_job_id.return_value = job
        self._qualify(job)
        review = self._seed_review(
            JobReviewKind.INITIAL, status=ApprovalRequestStatus.APPROVED
        )

        with self.assertRaises(ConflictError):
            await self.service.approve(
                self.session, review.request_id, acting_user_id=2
            )
        self.repo.update_job.assert_not_awaited()

    async def test_reject_requires_pending_review(self):
        """A withdrawn review is closed; rejecting it is a conflict too."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(
            JobReviewKind.INITIAL, status=ApprovalRequestStatus.WITHDRAWN
        )

        with self.assertRaises(ConflictError):
            await self.service.reject(
                self.session, review.request_id, comment="no", acting_user_id=2
            )
        self.assertEqual(review.status, ApprovalRequestStatus.WITHDRAWN)

    async def test_approve_refuses_a_request_that_is_not_a_job_review(self):
        """The review endpoints decide job reviews only, whoever the reviewer."""
        other = self.requests.add(
            action="user_block",
            target_type="user",
            target_id="77",
            payload={},
            reason=None,
            raised_by=1,
            reviewer_id=2,
            status=ApprovalRequestStatus.PENDING,
        )

        with self.assertRaisesRegex(ValueError, f"Review {other.request_id} not found"):
            await self.service.approve(self.session, other.request_id, acting_user_id=2)
        self.assertEqual(other.status, ApprovalRequestStatus.PENDING)

    async def test_reject_refuses_a_request_that_is_not_a_job_review(self):
        other = self.requests.add(
            action="user_block",
            target_type="user",
            target_id="77",
            payload={},
            reason=None,
            raised_by=1,
            reviewer_id=2,
            status=ApprovalRequestStatus.PENDING,
        )

        with self.assertRaisesRegex(ValueError, f"Review {other.request_id} not found"):
            await self.service.reject(
                self.session, other.request_id, comment="no", acting_user_id=2
            )
        self.assertEqual(other.status, ApprovalRequestStatus.PENDING)

    async def test_approve_refuses_an_unknown_review(self):
        with self.assertRaises(ValueError):
            await self.service.approve(self.session, 999, acting_user_id=2)

    async def test_approve_rejects_non_assigned_reviewer(self):
        """Only the assigned reviewer may approve; others are rejected."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(JobReviewKind.INITIAL)

        with self.assertRaises(PermissionError):
            await self.service.approve(
                self.session, review.request_id, acting_user_id=3
            )
        # The posting must not have advanced.
        self.assertEqual(review.status, ApprovalRequestStatus.PENDING)
        self.assertEqual(job.status, JobStatus.PENDING_REVIEW)

    def _pending_review(self, *, submit_message=None):
        """A PENDING review of the default job, for the reassign tests. The
        posting waits in PENDING_REVIEW with a config that still holds, unless
        a test has already put another posting in the repository."""
        if not isinstance(self.repo.get_by_job_id.return_value, JobEntity):
            job = self._job(status=JobStatus.PENDING_REVIEW)
            job.pipeline_config = self._valid_pipeline(owner_id=2)
            self.repo.get_by_job_id.return_value = job
        return self._seed_review(
            JobReviewKind.INITIAL, raised_by=1, reviewer_id=2, reason=submit_message
        )

    async def test_reassign_review_moves_it_to_the_new_reviewer(self):
        """The submitter redirects a review nobody can decide any more.

        The posting's own status is untouched: it is still in the same gate,
        waiting on a different person.
        """
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        self._qualify(job)
        review = self._pending_review()
        self._two_approvers()

        await self.service.reassign_review(
            self.session, JOB_ID, acting_user_id=1, reviewer_id=3
        )

        self.assertEqual(review.reviewer_id, 3)
        self.assertEqual(review.status, ApprovalRequestStatus.PENDING)
        self.assertEqual(job.status, JobStatus.PENDING_REVIEW)

    async def test_reassign_review_still_names_who_submitted_it(self):
        """A redirected review is still open, so the response still names it.

        The reassign affordance is keyed on this field alone, so answering
        with None tells the caller the posting may no longer be reassigned.
        """
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        self._qualify(job)
        self._pending_review(submit_message="Please take a look")
        self._two_approvers()

        result = await self.service.reassign_review(
            self.session, JOB_ID, acting_user_id=1, reviewer_id=3
        )

        self.assertEqual(result.submitted_by, 1)
        self.assertEqual(result.submit_message, "Please take a look")

    async def test_reassign_review_records_who_it_came_from(self):
        """The event carries the previous reviewer, which the row no longer does.

        Without it the timeline can say a reassignment happened but not what
        it undid, and the row has already been overwritten by then.
        """
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        self._qualify(job)
        review = self._pending_review()
        self._two_approvers()

        await self.service.reassign_review(
            self.session, JOB_ID, acting_user_id=1, reviewer_id=3
        )

        self.record_event.assert_awaited_once()
        kwargs = self.record_event.await_args.kwargs
        self.assertEqual(kwargs["subject_type"], "job")
        self.assertEqual(kwargs["subject_id"], JOB_ID)
        self.assertEqual(kwargs["actor_id"], 1)
        self.assertEqual(kwargs["event_type"], RecruitingEvent.REVIEW_REASSIGNED)
        self.assertEqual(kwargs["details"]["reviewId"], review.request_id)
        self.assertEqual(kwargs["details"]["previousReviewerId"], 2)
        # The event must be written before the commit, or a rollback would
        # drop the notification while the reassignment survived.
        self.assertEqual(self.call_order, ["record", "commit"])

    async def test_reassign_review_rejects_a_caller_who_is_not_the_submitter(self):
        """Redirecting a question you asked, not taking over someone's duty.

        Nobody may pull a review off its reviewer -- not the current reviewer,
        not another approver. Same rule block requests already use.
        """
        review = self._pending_review()
        self._two_approvers()

        with self.assertRaises(PermissionError):
            await self.service.reassign_review(
                self.session, JOB_ID, acting_user_id=2, reviewer_id=3
            )
        self.assertEqual(review.reviewer_id, 2)

    async def test_reassign_review_rejects_a_job_with_no_open_review(self):
        """A decided review is not open, so there is nothing to redirect."""
        self._two_approvers()
        self._seed_review(status=ApprovalRequestStatus.APPROVED)

        with self.assertRaisesRegex(ValueError, "no open review"):
            await self.service.reassign_review(
                self.session, JOB_ID, acting_user_id=1, reviewer_id=3
            )

    async def test_reassign_review_locks_the_review_row(self):
        """Serialised against a decision landing on the reviewer being replaced.

        Without the lock an approve could commit between the read here and
        the write below, leaving a decided review whose reviewer_id names
        somebody who never saw it.
        """
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        self._qualify(job)
        review = self._pending_review()
        self._two_approvers()

        await self.service.reassign_review(
            self.session, JOB_ID, acting_user_id=1, reviewer_id=3
        )

        self.assertIn((review.request_id, True), self.requests.get_calls)

    async def test_reassign_review_rejects_the_reviewer_it_already_has(self):
        review = self._pending_review()
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, "already the reviewer"):
            await self.service.reassign_review(
                self.session, JOB_ID, acting_user_id=1, reviewer_id=2
            )
        self.record_event.assert_not_awaited()
        self.assertEqual(review.reviewer_id, 2)

    async def test_reassign_review_rejects_the_submitter_as_the_new_reviewer(self):
        """Reassignment must not become a way round the no-self-review rule.

        ``_open_review`` refuses a submitter who picks themselves; without the
        same check here they could pick anyone, then reassign to themselves.
        """
        review = self._pending_review()
        self.perms.get_active_users_with_permission.return_value = [
            self._approver(1),
            self._approver(2),
        ]

        with self.assertRaisesRegex(ValueError, "your own request"):
            await self.service.reassign_review(
                self.session, JOB_ID, acting_user_id=1, reviewer_id=1
            )
        self.assertEqual(review.reviewer_id, 2)

    async def test_reassign_review_rejects_someone_who_is_not_an_active_approver(self):
        """The pool already excludes deactivated and blocked accounts.

        ``get_active_users_with_permission`` filters both flags, so a
        reassignment cannot hand the review to another account that cannot
        sign in -- which is the whole point of the action.
        """
        review = self._pending_review()
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, "cannot review this request"):
            await self.service.reassign_review(
                self.session, JOB_ID, acting_user_id=1, reviewer_id=9
            )
        self.assertEqual(review.reviewer_id, 2)

    async def test_approve_rejects_submitter_self_decision(self):
        """The submitter cannot approve their own posting even if they act."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(JobReviewKind.INITIAL)

        with self.assertRaises(PermissionError):
            await self.service.approve(
                self.session, review.request_id, acting_user_id=1
            )
        self.assertEqual(job.status, JobStatus.PENDING_REVIEW)

    async def test_reject_rejects_non_assigned_reviewer(self):
        """Only the assigned reviewer may reject; others are rejected."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(JobReviewKind.INITIAL)

        with self.assertRaises(PermissionError):
            await self.service.reject(
                self.session, review.request_id, comment="no", acting_user_id=3
            )
        self.assertEqual(review.status, ApprovalRequestStatus.PENDING)

    async def test_reject_requires_comment(self):
        """Rejection requires a non-empty comment."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(JobReviewKind.INITIAL)

        with self.assertRaisesRegex(ValueError, "Give a reason"):
            await self.service.reject(
                self.session, review.request_id, comment="  ", acting_user_id=2
            )
        self.assertEqual(review.status, ApprovalRequestStatus.PENDING)
        self.assertEqual(job.status, JobStatus.PENDING_REVIEW)

    async def test_reject_initial_returns_to_draft(self):
        """Rejecting an INITIAL review sends the posting back to DRAFT."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(JobReviewKind.INITIAL)

        result = await self.service.reject(
            self.session, review.request_id, comment="fix the form", acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.DRAFT)
        self.assertEqual(review.status, ApprovalRequestStatus.REJECTED)
        self.assertEqual(review.decision_comment, "fix the form")

    async def test_reject_logs_review_decided_activity(self):
        """reject logs a review_decided activity entry with the comment."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(
            JobReviewKind.INITIAL, raised_by=5, reviewer_id=9, reason="please"
        )

        await self.service.reject(self.session, review.request_id, "not ready", 9)

        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="job",
            subject_id=job.job_id,
            actor_id=9,
            event_type=RecruitingEvent.REVIEW_DECIDED,
            details={
                "kind": "initial",
                "reviewId": review.request_id,
                "message": "please",
                "requestId": review.request_id,
                "action": JOB_REVIEW,
                "decision": "rejected",
                "comment": "not ready",
            },
        )

    async def test_reject_revision_keeps_published_and_keeps_pending(self):
        """Rejecting a REVISION reverts to PUBLISHED but keeps the staged
        draft — matching how rejecting a REOPEN keeps it too — so the
        submitter can address feedback and resubmit without redoing the edit."""
        job = self._job(
            status=JobStatus.PUBLISHED_PENDING_REVISION,
            form_schema={"a": 1},
            title="old",
        )
        job.pending_payload = {"title": "new", "formSchema": {"a": 2}}
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(JobReviewKind.REVISION)

        result = await self.service.reject(
            self.session, review.request_id, comment="no", acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)
        self.assertEqual(result.title, "old")
        self.assertEqual(result.form_schema, {"a": 1})
        self.assertEqual(
            result.pending_payload, {"title": "new", "formSchema": {"a": 2}}
        )

    # ---------------------------------------------------------------------------
    # withdraw_review
    # ---------------------------------------------------------------------------

    async def _withdraw(self, kind, waiting, **job_fields):
        job = self._job(status=waiting, **job_fields)
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(kind, raised_by=1, reviewer_id=2)
        result = await self.service.withdraw_review(
            self.session, JOB_ID, acting_user_id=1
        )
        self.assertEqual(review.status, ApprovalRequestStatus.WITHDRAWN)
        self.assertEqual(review.decided_by, 1)
        return job, result

    async def test_withdraw_initial_returns_the_posting_to_draft(self):
        _, result = await self._withdraw(
            JobReviewKind.INITIAL, JobStatus.PENDING_REVIEW
        )

        self.assertEqual(result.status, JobStatus.DRAFT)

    async def test_withdraw_revision_returns_to_published_and_keeps_the_edit(self):
        """The staged edit stays, so it can be fixed and sent again."""
        _, result = await self._withdraw(
            JobReviewKind.REVISION,
            JobStatus.PUBLISHED_PENDING_REVISION,
            title="live",
            pending_payload={"title": "staged"},
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)
        self.assertEqual(result.title, "live")
        self.assertEqual(result.pending_payload, {"title": "staged"})

    async def test_withdraw_close_returns_the_posting_to_published(self):
        _, result = await self._withdraw(
            JobReviewKind.CLOSE, JobStatus.PENDING_CLOSE, was_published=True
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)

    async def test_withdraw_reopen_returns_the_posting_to_closed(self):
        _, result = await self._withdraw(
            JobReviewKind.REOPEN, JobStatus.PENDING_REOPEN, was_published=True
        )

        self.assertEqual(result.status, JobStatus.CLOSED)

    async def test_withdraw_records_a_withdrawn_decision_inside_the_transaction(
        self,
    ):
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(raised_by=1, reviewer_id=2, reason="please")

        await self.service.withdraw_review(self.session, JOB_ID, acting_user_id=1)

        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="job",
            subject_id=JOB_ID,
            actor_id=1,
            event_type=RecruitingEvent.REVIEW_DECIDED,
            details={
                "kind": "initial",
                "reviewId": review.request_id,
                "message": "please",
                "requestId": review.request_id,
                "action": JOB_REVIEW,
                "decision": "withdrawn",
                "comment": None,
            },
        )
        self.assertEqual(self.call_order, ["record", "commit"])

    async def test_withdraw_is_the_submitters_alone(self):
        """Not even the reviewer may take back somebody else's request."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(raised_by=1, reviewer_id=2)

        with self.assertRaises(PermissionError):
            await self.service.withdraw_review(self.session, JOB_ID, acting_user_id=2)

        self.assertEqual(review.status, ApprovalRequestStatus.PENDING)
        self.assertEqual(job.status, JobStatus.PENDING_REVIEW)
        self.record_event.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_withdraw_without_an_open_review_raises(self):
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job
        self._seed_review(status=ApprovalRequestStatus.REJECTED, decision_comment="no")

        with self.assertRaisesRegex(ValueError, "no open review"):
            await self.service.withdraw_review(self.session, JOB_ID, acting_user_id=1)
        self.repo.update_job.assert_not_awaited()

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
        job_with_reject.job_id = 41
        job_no_reject = self._job(status=JobStatus.PUBLISHED)
        job_no_reject.job_id = 42
        self.repo.list_all.return_value = [job_with_reject, job_no_reject]
        self._seed_review(
            JobReviewKind.REVISION,
            status=ApprovalRequestStatus.REJECTED,
            decision_comment="fix the form",
            job_id=41,
        )

        result = await self.service.list_all_jobs(self.session)

        dto_1 = next(r for r in result if r.id == 41)
        dto_2 = next(r for r in result if r.id == 42)
        self.assertEqual(dto_1.last_reject_comment, "fix the form")
        self.assertEqual(dto_1.last_reject_kind, "revision")
        self.assertIsNone(dto_2.last_reject_comment)

    async def test_list_all_jobs_reads_only_the_latest_review(self):
        """An old rejection stops showing once a newer review is the latest."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.list_all.return_value = [job]
        self._seed_review(status=ApprovalRequestStatus.REJECTED, decision_comment="no")
        self._seed_review(reviewer_id=6)

        result = await self.service.list_all_jobs(self.session)

        self.assertIsNone(result[0].last_reject_comment)
        self.assertEqual(result[0].reviewer_id, 6)

    async def test_list_all_jobs_no_comment_when_latest_is_approved(self):
        """last_reject_comment is None when the latest review was approved."""
        job = self._job(status=JobStatus.PUBLISHED)
        self.repo.list_all.return_value = [job]
        self._seed_review(status=ApprovalRequestStatus.APPROVED)

        result = await self.service.list_all_jobs(self.session)

        self.assertIsNone(result[0].last_reject_comment)

    async def test_list_all_jobs_no_comment_when_latest_was_withdrawn(self):
        """A withdrawal is not a rejection: nobody sent the posting back."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.list_all.return_value = [job]
        self._seed_review(status=ApprovalRequestStatus.WITHDRAWN)

        result = await self.service.list_all_jobs(self.session)

        self.assertIsNone(result[0].last_reject_comment)
        self.assertIsNone(result[0].last_reject_kind)
        self.assertIsNone(result[0].reviewer_id)

    async def test_list_all_jobs_includes_reviewer_id_for_open_review(self):
        """list_all_jobs surfaces reviewer_id when the latest review is still PENDING."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        self.repo.list_all.return_value = [job]
        self._seed_review(reviewer_id=6)

        result = await self.service.list_all_jobs(self.session)

        self.assertEqual(result[0].reviewer_id, 6)

    async def test_list_all_jobs_reviewer_id_none_when_latest_is_decided(self):
        """reviewer_id is None once the latest review has been approved or rejected."""
        job = self._job(status=JobStatus.PUBLISHED)
        self.repo.list_all.return_value = [job]
        self._seed_review(reviewer_id=6, status=ApprovalRequestStatus.APPROVED)

        result = await self.service.list_all_jobs(self.session)

        self.assertIsNone(result[0].reviewer_id)

    async def test_list_reviews_for_reviewer_returns_pending(self):
        """list_reviews_for_reviewer maps the reviewer's pending reviews with job title."""
        review = self._seed_review(raised_by=1, reviewer_id=2, reason="Have a look")
        # Neither someone else's review nor a decided one of theirs is listed.
        self._seed_review(reviewer_id=3, job_id=42)
        self._seed_review(status=ApprovalRequestStatus.APPROVED, job_id=43)
        job = self._job(title="Senior Engineer")
        self.repo.get_by_job_ids.return_value = [job]

        result = await self.service.list_reviews_for_reviewer(self.session, 2)

        self.assertEqual([r.review_id for r in result], [review.request_id])
        self.assertEqual(result[0].job_id, JOB_ID)
        self.assertEqual(result[0].submitted_by, 1)
        self.assertEqual(result[0].reviewer_id, 2)
        self.assertEqual(result[0].kind, JobReviewKind.INITIAL)
        self.assertEqual(result[0].status, "pending")
        self.assertEqual(result[0].submit_message, "Have a look")
        self.assertEqual(result[0].job_title, "Senior Engineer")
        self.repo.get_by_job_ids.assert_awaited_once_with(self.session, [JOB_ID])

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
        (created,) = self.requests.created
        self.assertEqual(created.payload["kind"], JobReviewKind.CLOSE)
        self.assertEqual(created.status, ApprovalRequestStatus.PENDING)
        self.assertEqual(created.reviewer_id, 2)
        self.assertEqual(created.reason, "closing")

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

        with self.assertRaisesRegex(ValueError, "your own request"):
            await self.service.request_close(
                self.session, job.job_id, reviewer_id=1, submitted_by=1, message=None
            )

    async def test_request_close_reviewer_not_in_pool_raises(self):
        """request_close blocks a reviewer outside the active approver pool."""
        job = self._job(status=JobStatus.PUBLISHED)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, "cannot review this request"):
            await self.service.request_close(
                self.session, job.job_id, reviewer_id=9, submitted_by=1, message=None
            )

    # ---------------------------------------------------------------------------
    # request_reopen
    # ---------------------------------------------------------------------------

    async def test_request_reopen_closed_creates_review(self):
        """request_reopen from CLOSED creates a REOPEN review and sets PENDING_REOPEN."""
        job = self._job(status=JobStatus.CLOSED, was_published=True)
        job.pipeline_config = self._valid_pipeline()
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        result = await self.service.request_reopen(
            self.session, job.job_id, reviewer_id=2, submitted_by=1, message="reopening"
        )

        self.assertEqual(result.status, JobStatus.PENDING_REOPEN)
        (created,) = self.requests.created
        self.assertEqual(created.payload["kind"], JobReviewKind.REOPEN)
        self.assertEqual(created.status, ApprovalRequestStatus.PENDING)

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
    # Owner re-check: every review kind but CLOSE
    # ---------------------------------------------------------------------------

    def _assert_nothing_written(self):
        self.assertEqual(self.requests.created, [])
        self.repo.update_job.assert_not_awaited()
        self.record_event.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    def _review_of(self, kind):
        return self._seed_review(kind, raised_by=1, reviewer_id=2)

    async def test_request_close_allows_blocked_live_owner(self):
        """A close publishes nothing, so an owner who dropped out of the
        holder pool must not trap the posting open."""
        job = self._job(status=JobStatus.PUBLISHED, was_published=True)
        job.pipeline_config = self._valid_pipeline(owner_id=8)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()  # pool is ids 2 and 3 — owner 8 no longer qualifies

        result = await self.service.request_close(
            self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
        )

        self.assertEqual(result.status, JobStatus.PENDING_CLOSE)

    async def test_request_reopen_refuses_blocked_live_owner(self):
        """A reopen republishes the live config, so a live owner who dropped
        out of the holder pool stops the request."""
        job = self._job(status=JobStatus.CLOSED, was_published=True)
        job.pipeline_config = self._valid_pipeline(owner_id=8)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, r"owners \[8\] no longer qualify"):
            await self.service.request_reopen(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )
        self.assertEqual(job.status, JobStatus.CLOSED)
        self._assert_nothing_written()

    async def test_request_reopen_refuses_blocked_staged_owner(self):
        """Approving a reopen applies the staged edit, so a blocked owner in
        the staged edit stops the request even when the live config is fine."""
        job = self._job(status=JobStatus.CLOSED, was_published=True)
        job.pipeline_config = self._valid_pipeline(owner_id=2)
        job.pending_payload = {
            "title": "new",
            "pipelineConfig": self._valid_pipeline(8),
        }
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()

        with self.assertRaisesRegex(ValueError, r"owners \[8\] no longer qualify"):
            await self.service.request_reopen(
                self.session, job.job_id, reviewer_id=2, submitted_by=1, message=None
            )
        self.assertEqual(job.status, JobStatus.CLOSED)
        self._assert_nothing_written()

    async def _assert_approve_refused(self, job, kind):
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()
        review = self._review_of(kind)
        status_before = job.status

        with self.assertRaisesRegex(
            ConflictError, r"owners \[8\] no longer qualify"
        ) as caught:
            await self.service.approve(
                self.session, review.request_id, acting_user_id=2
            )

        self.assertEqual(caught.exception.code, APPROVAL_CHECKS_FAILED)

        self.assertEqual(review.status, ApprovalRequestStatus.PENDING)
        self.assertIsNone(review.decided_at)
        self.assertEqual(job.status, status_before)
        self._assert_nothing_written()

    async def test_approve_initial_refuses_blocked_owner(self):
        job = self._job(status=JobStatus.PENDING_REVIEW)
        job.pipeline_config = self._valid_pipeline(owner_id=8)
        await self._assert_approve_refused(job, JobReviewKind.INITIAL)

    async def test_approve_revision_refuses_blocked_staged_owner(self):
        """Judged on the staged edit, which is what approval publishes."""
        job = self._job(status=JobStatus.PUBLISHED_PENDING_REVISION)
        job.pipeline_config = self._valid_pipeline(owner_id=2)
        job.pending_payload = {
            "title": "new",
            "pipelineConfig": self._valid_pipeline(8),
        }
        await self._assert_approve_refused(job, JobReviewKind.REVISION)
        self.assertIsNotNone(job.pending_payload)

    async def test_approve_reopen_refuses_blocked_owner(self):
        job = self._job(status=JobStatus.PENDING_REOPEN, was_published=True)
        job.pipeline_config = self._valid_pipeline(owner_id=8)
        await self._assert_approve_refused(job, JobReviewKind.REOPEN)

    async def test_approve_close_allows_blocked_owner(self):
        job = self._job(status=JobStatus.PENDING_CLOSE, was_published=True)
        job.pipeline_config = self._valid_pipeline(owner_id=8)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()
        review = self._review_of(JobReviewKind.CLOSE)

        result = await self.service.approve(
            self.session, review.request_id, acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.CLOSED)
        self.assertEqual(review.status, ApprovalRequestStatus.APPROVED)

    async def test_reassign_review_refuses_blocked_owner(self):
        """Moving a review that could never be approved would only park it
        on someone else."""
        job = self._job(status=JobStatus.PENDING_REVIEW)
        job.pipeline_config = self._valid_pipeline(owner_id=8)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()
        review = self._review_of(JobReviewKind.INITIAL)

        with self.assertRaisesRegex(ValueError, r"owners \[8\] no longer qualify"):
            await self.service.reassign_review(
                self.session, job.job_id, acting_user_id=1, reviewer_id=3
            )

        self.assertEqual(review.reviewer_id, 2)
        self._assert_nothing_written()

    async def test_reassign_review_close_allows_blocked_owner(self):
        job = self._job(status=JobStatus.PENDING_CLOSE, was_published=True)
        job.pipeline_config = self._valid_pipeline(owner_id=8)
        self.repo.get_by_job_id.return_value = job
        self._two_approvers()
        review = self._review_of(JobReviewKind.CLOSE)

        await self.service.reassign_review(
            self.session, job.job_id, acting_user_id=1, reviewer_id=3
        )

        self.assertEqual(review.reviewer_id, 3)

    # ---------------------------------------------------------------------------
    # approve — CLOSE and REOPEN kinds
    # ---------------------------------------------------------------------------

    async def test_approve_close_review_closes_job(self):
        """Approving a CLOSE review transitions the posting to CLOSED."""
        job = self._job(status=JobStatus.PENDING_CLOSE)
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(JobReviewKind.CLOSE)

        result = await self.service.approve(
            self.session, review.request_id, acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.CLOSED)
        self.assertEqual(review.status, ApprovalRequestStatus.APPROVED)
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
            "pipelineConfig": self._valid_pipeline(),
            "profileConfig": None,
        }
        self.repo.get_by_job_id.return_value = job
        self._qualify(job)
        review = self._seed_review(JobReviewKind.REOPEN)

        result = await self.service.approve(
            self.session, review.request_id, acting_user_id=2
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
        self._qualify(job)
        review = self._seed_review(JobReviewKind.REOPEN)

        result = await self.service.approve(
            self.session, review.request_id, acting_user_id=2
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
        review = self._seed_review(JobReviewKind.CLOSE)

        result = await self.service.reject(
            self.session, review.request_id, comment="keep it open", acting_user_id=2
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)
        self.assertEqual(review.status, ApprovalRequestStatus.REJECTED)
        self.assertEqual(review.decision_comment, "keep it open")

    async def test_reject_reopen_review_keeps_pending_payload(self):
        """Rejecting a REOPEN reverts to CLOSED but keeps the staged draft."""
        job = self._job(status=JobStatus.PENDING_REOPEN, was_published=True)
        job.pending_payload = {"title": "draft title"}
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(JobReviewKind.REOPEN)

        result = await self.service.reject(
            self.session, review.request_id, comment="not yet", acting_user_id=2
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
        self._qualify(job)
        review = self._seed_review(JobReviewKind.INITIAL)

        await self.service.approve(self.session, review.request_id, acting_user_id=2)

        self.assertTrue(job.was_published)

    async def test_approve_close_does_not_change_was_published(self):
        """Approving a CLOSE review does not set was_published (it was already True)."""
        job = self._job(status=JobStatus.PENDING_CLOSE)
        job.was_published = True
        self.repo.get_by_job_id.return_value = job
        review = self._seed_review(JobReviewKind.CLOSE)

        await self.service.approve(self.session, review.request_id, acting_user_id=2)

        # Posting is now CLOSED; was_published must remain True.
        self.assertTrue(job.was_published)
        self.assertEqual(job.status, JobStatus.CLOSED)

    # ---------------------------------------------------------------------------
    # delete_job
    # ---------------------------------------------------------------------------

    async def test_delete_job_removes_review_history_before_deleting_the_job(self):
        """delete_job deletes the job's job_review rows before deleting the job
        itself, so a Draft posting that was previously submitted and rejected
        (and so still has a job_review row pointing at it) can be deleted
        without an FK-violation 500."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job

        await self.service.delete_job(self.session, job.job_id)

        self.review_repo.delete_by_job.assert_awaited_once_with(
            self.session, job.job_id
        )
        self.repo.delete_job.assert_awaited_once_with(self.session, job)

    async def test_delete_job_draft_succeeds(self):
        """delete_job now also allows deleting a DRAFT posting."""
        job = self._job(status=JobStatus.DRAFT)
        self.repo.get_by_job_id.return_value = job

        await self.service.delete_job(self.session, job.job_id)

        self.repo.delete_job.assert_awaited_once_with(self.session, job)

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

        self.assertEqual(result.status, JobStatus.PUBLISHED)

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

    # ---------------------------------------------------------------------------
    # discard_pending_edit
    # ---------------------------------------------------------------------------

    async def test_discard_pending_edit_from_published_clears_it(self):
        """Discarding a staged edit on a PUBLISHED posting clears
        pending_payload; status and live fields are untouched."""
        job = self._job(status=JobStatus.PUBLISHED, title="live title")
        job.pending_payload = {"title": "staged title"}
        self.repo.get_by_job_id.return_value = job

        result = await self.service.discard_pending_edit(
            self.session, job.job_id, acting_user_id=1
        )

        self.assertEqual(result.status, JobStatus.PUBLISHED)
        self.assertEqual(result.title, "live title")
        self.assertIsNone(result.pending_payload)
        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="job",
            subject_id=job.job_id,
            actor_id=1,
            event_type=RecruitingEvent.PENDING_EDIT_DISCARDED,
        )

    async def test_discard_pending_edit_from_closed_clears_it(self):
        """Discarding a staged edit on a CLOSED posting clears
        pending_payload; status stays CLOSED."""
        job = self._job(status=JobStatus.CLOSED, was_published=True)
        job.pending_payload = {"title": "staged title"}
        self.repo.get_by_job_id.return_value = job

        result = await self.service.discard_pending_edit(
            self.session, job.job_id, acting_user_id=1
        )

        self.assertEqual(result.status, JobStatus.CLOSED)
        self.assertIsNone(result.pending_payload)

    async def test_discard_pending_edit_raises_when_nothing_staged(self):
        """Nothing to discard when pending_payload is already None."""
        job = self._job(status=JobStatus.PUBLISHED)
        self.repo.get_by_job_id.return_value = job

        with self.assertRaisesRegex(ValueError, "nothing staged"):
            await self.service.discard_pending_edit(
                self.session, job.job_id, acting_user_id=1
            )

    async def test_discard_pending_edit_raises_from_other_status(self):
        """Only PUBLISHED/CLOSED postings can have a staged edit to discard."""
        job = self._job(status=JobStatus.DRAFT)
        job.pending_payload = {"title": "staged title"}
        self.repo.get_by_job_id.return_value = job

        with self.assertRaisesRegex(ValueError, "cannot discard"):
            await self.service.discard_pending_edit(
                self.session, job.job_id, acting_user_id=1
            )

    async def test_list_interview_pool(self):
        users = self._make_users(7, 8)
        for u in users:
            u.first_name, u.last_name = "A", "B"

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
            u.first_name, u.last_name = "O", "W"
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

    async def test_get_published_job_serves_posting_pending_close(self):
        self.repo.get_by_job_id = AsyncMock(
            return_value=self._job(status=JobStatus.PENDING_CLOSE)
        )

        result = await self.service.get_published_job(self.session, 1)

        self.assertEqual(result.status, JobStatus.PENDING_CLOSE)

    async def test_approve_records_the_notification_inside_the_transaction(self):
        # Same setup as test_approve_notifies_the_submitter.
        job = JobEntity(
            kind=JobKind.ACTIVITY, title="T", status=JobStatus.PENDING_REVIEW
        )
        job.job_id = JOB_ID
        review = self._seed_review(JobReviewKind.INITIAL, raised_by=9, reviewer_id=6)
        self.repo.get_by_job_id = AsyncMock(return_value=job)
        self._qualify(job)

        await self.service.approve(
            self.session, review_id=review.request_id, acting_user_id=6
        )

        self.record_event.assert_awaited_once()
        self.assertEqual(self.call_order, ["record", "commit"])

    async def test_reject_records_the_notification_inside_the_transaction(self):
        # Same setup as test_reject_notifies_the_submitter.
        job = JobEntity(
            kind=JobKind.ACTIVITY, title="T", status=JobStatus.PENDING_REVIEW
        )
        job.job_id = JOB_ID
        review = self._seed_review(JobReviewKind.INITIAL, raised_by=9, reviewer_id=6)
        self.repo.get_by_job_id = AsyncMock(return_value=job)

        await self.service.reject(
            self.session, review.request_id, "needs more detail", acting_user_id=6
        )

        self.record_event.assert_awaited_once()
        self.assertEqual(self.call_order, ["record", "commit"])

    async def test_get_job_activity_resolves_actor_names(self):
        """get_job_activity returns rows newest-first with actor names resolved."""
        row = MagicMock()
        row.event_id = 1
        row.subject_type = "job"
        row.subject_id = 9
        row.actor_id = 7
        row.event_type = "recruiting.job_created"
        row.details = {}
        row.created_at = datetime(2026, 7, 4, 12, 0, 0)
        self.event_repo.list_by_subject.return_value = [row]
        actor = UsersEntity(first_name="Ada", last_name="Lovelace")
        actor.user_id = 7
        self.users_repo.get_all_by_ids.return_value = [actor]

        result = await self.service.get_job_activity(self.session, 9)

        self.event_repo.list_by_subject.assert_awaited_once_with(self.session, "job", 9)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].actor_name, "Ada Lovelace")
        self.assertEqual(result[0].event_type, "recruiting.job_created")

    async def test_get_job_activity_names_the_actor_by_their_preferred_name(self):
        """A job's activity log names internal colleagues by the shared rule."""
        row = MagicMock()
        row.event_id = 1
        row.subject_type = "job"
        row.subject_id = 9
        row.actor_id = 7
        row.event_type = "recruiting.job_created"
        row.details = {}
        row.created_at = datetime(2026, 7, 4, 12, 0, 0)
        self.event_repo.list_by_subject.return_value = [row]
        actor = UsersEntity(
            first_name="Ada", last_name="Lovelace", preferred_name="Addy"
        )
        actor.user_id = 7
        self.users_repo.get_all_by_ids.return_value = [actor]

        result = await self.service.get_job_activity(self.session, 9)

        self.assertEqual(result[0].actor_name, "Addy")

    async def test_get_job_activity_falls_back_for_unresolved_actor(self):
        """A since-removed actor resolves to a 'User {id}' fallback."""
        row = MagicMock()
        row.event_id = 1
        row.subject_type = "job"
        row.subject_id = 9
        row.actor_id = 7
        row.event_type = "recruiting.job_created"
        row.details = {}
        row.created_at = datetime(2026, 7, 4, 12, 0, 0)
        self.event_repo.list_by_subject.return_value = [row]
        self.users_repo.get_all_by_ids.return_value = []

        result = await self.service.get_job_activity(self.session, 9)

        self.assertEqual(result[0].actor_name, "User 7")

    async def test_list_publicly_visible_returns_public_summaries(self):
        job1 = self._job(status=JobStatus.PUBLISHED)
        job2 = self._job(status=JobStatus.PENDING_CLOSE)
        job2.job_id = 2
        self.repo.list_publicly_visible = AsyncMock(return_value=[job1, job2])

        result = await self.service.list_publicly_visible(self.session)

        self.assertEqual([d.id for d in result], [JOB_ID, 2])
        for d in result:
            self.assertEqual(
                set(type(d).model_fields.keys()),
                {"id", "title", "kind", "description"},
            )


if __name__ == "__main__":
    unittest.main()
