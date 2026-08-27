import unittest
from datetime import datetime, timezone

from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.common.mentorship_enums import ParticipantRole


class TestRecruitingMapper(unittest.TestCase):
    def setUp(self):
        """Instantiate the mapper under test."""
        self.mapper = RecruitingMapper()

    def _make_job_entity(self, **kw):
        """Build a JobEntity fixture with sensible defaults for mapper tests."""
        defaults = {
            "kind": JobKind.ACTIVITY,
            "title": "T",
            "status": JobStatus.PUBLISHED,
            "description": "d",
        }
        defaults.update(kw)
        job = JobEntity(**defaults)
        job.job_id = 1
        return job

    def test_to_public_job_summary_dto_exposes_only_card_fields(self):
        job = self._make_job_entity()
        dto = self.mapper.to_public_job_summary_dto(job)
        self.assertEqual(dto.id, job.job_id)
        self.assertEqual(dto.title, job.title)
        self.assertEqual(dto.kind, job.kind)
        self.assertEqual(dto.description, job.description)
        self.assertEqual(
            set(type(dto).model_fields.keys()), {"id", "title", "kind", "description"}
        )

    def test_to_public_job_dto_reports_whether_the_posting_still_takes_applications(
        self,
    ):
        """The one status fact a candidate is allowed to see.

        An applicant can now open a posting that has stopped being live, so
        the projection has to say so -- otherwise the page offers actions
        (edit, reapply) the backend will refuse.
        """
        live = {
            JobStatus.PUBLISHED,
            JobStatus.PUBLISHED_PENDING_REVISION,
            JobStatus.PENDING_CLOSE,
        }
        for status in JobStatus:
            with self.subTest(status=status):
                dto = self.mapper.to_public_job_dto(
                    self._make_job_entity(status=status)
                )
                self.assertEqual(dto.accepting_applications, status in live)

    def test_to_public_job_dto_does_not_expose_the_raw_status(self):
        """`accepting_applications` is the whole answer: the status string
        names internal review states (pending_close, pending_reopen) that are
        nobody's business outside recruiting."""
        dto = self.mapper.to_public_job_dto(self._make_job_entity())
        self.assertNotIn("status", dto.model_dump())

    def test_to_approver_dto_prefers_the_preferred_name(self):
        """An approver is an internal colleague, so the shared rule applies."""
        user = UsersEntity(first_name="Robert", last_name="Smith", preferred_name="Bob")
        user.user_id = 7

        dto = self.mapper.to_approver_dto(user, "bob@example.com")

        self.assertEqual(dto.name, "Bob")

    def test_to_approver_dto_falls_back_to_the_full_name(self):
        """With no preferred name the approver keeps their full name."""
        user = UsersEntity(first_name="Robert", last_name="Smith")
        user.user_id = 7

        dto = self.mapper.to_approver_dto(user, "bob@example.com")

        self.assertEqual(dto.name, "Robert Smith")

    def test_to_board_card_dto_names_the_applicant_by_their_legal_name(self):
        """A candidate's preferred name never replaces their legal name.

        The board is a record of who applied, so it names them the way their
        application does even when they have a preferred name on file.
        """
        application = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.APPLIED, current_round=1
        )
        application.application_id = 1
        user = UsersEntity(
            first_name="Ada", last_name="Lovelace", preferred_name="Addy"
        )
        user.user_id = 2

        dto = self.mapper.to_board_card_dto(application, user)

        self.assertEqual(dto.applicant_name, "Ada Lovelace")

    def test_to_board_applicant_hit_dto_names_the_applicant_by_their_legal_name(self):
        """A search hit names the candidate the same way its card does."""
        application = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.APPLIED, current_round=1
        )
        application.application_id = 1
        application.created_datetime = datetime(2026, 6, 1, tzinfo=timezone.utc)
        user = UsersEntity(
            first_name="Ada", last_name="Lovelace", preferred_name="Addy"
        )
        user.user_id = 2

        dto = self.mapper.to_board_applicant_hit_dto(
            application, user, self._make_job_entity()
        )

        self.assertEqual(dto.applicant_name, "Ada Lovelace")

    def test_to_board_card_dto_maps_fields_and_joins_applicant_name(self):
        applied_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
        application = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.RECRUITER_SCREENING,
            sub_status="pending",
            tags={"cold_freeze": {"thaw_date": "2026-04-01"}},
            current_round=1,
        )
        application.application_id = 42
        application.created_datetime = applied_at
        user = UsersEntity(first_name="Ada", last_name="Lovelace")
        user.user_id = 2

        dto = self.mapper.to_board_card_dto(
            application, user, applicant_email="ada@b.com"
        )

        self.assertEqual(dto.id, 42)
        self.assertEqual(dto.applicant_name, "Ada Lovelace")
        self.assertEqual(dto.applicant_email, "ada@b.com")
        self.assertEqual(dto.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(dto.sub_status, "pending")
        self.assertEqual(dto.tags, {"cold_freeze": {"thaw_date": "2026-04-01"}})
        self.assertEqual(dto.applied_at, applied_at)

    def test_to_board_card_dto_strips_trailing_space_for_empty_last_name(self):
        application = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.APPLIED, current_round=1
        )
        application.application_id = 1
        user = UsersEntity(first_name="Cher", last_name="")
        user.user_id = 2

        dto = self.mapper.to_board_card_dto(application, user)

        self.assertEqual(dto.applicant_name, "Cher")

    def test_to_board_card_dto_includes_round(self):
        application = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.TECH,
            current_round=2,
        )
        application.application_id = 1
        user = UsersEntity(first_name="A", last_name="B")
        user.user_id = 2

        dto = self.mapper.to_board_card_dto(application, user)

        self.assertEqual(dto.round, 2)

    def test_to_board_card_dto_passes_through_reviewer_name(self):
        application = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.TECH,
            current_round=1,
        )
        application.application_id = 1
        user = UsersEntity(first_name="A", last_name="B")
        user.user_id = 2

        dto = self.mapper.to_board_card_dto(
            application, user, reviewer_name="Ivan Interviewer"
        )

        self.assertEqual(dto.reviewer_name, "Ivan Interviewer")

    def test_to_board_card_dto_reviewer_name_defaults_to_none(self):
        application = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.TECH, current_round=1
        )
        application.application_id = 1
        user = UsersEntity(first_name="A", last_name="B")
        user.user_id = 2

        dto = self.mapper.to_board_card_dto(application, user)

        self.assertIsNone(dto.reviewer_name)

    def test_to_application_dto_includes_current_round(self):
        application = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.TECH,
            current_round=2,
        )
        application.application_id = 1

        dto = self.mapper.to_application_dto(application)

        self.assertEqual(dto.current_round, 2)

    def test_to_board_card_dto_is_blocked_true_for_currently_blocked_user(self):
        application = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.REJECTED,
            tags={"blacklisted": True},
            current_round=1,
        )
        application.application_id = 1
        user = UsersEntity(first_name="A", last_name="B")
        user.user_id = 2
        user.is_blocked = True

        dto = self.mapper.to_board_card_dto(application, user)

        self.assertTrue(dto.is_blocked)

    def test_to_board_card_dto_is_blocked_false_once_unblocked(self):
        application = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.REJECTED,
            tags={"blacklisted": True},
            current_round=1,
        )
        application.application_id = 1
        user = UsersEntity(first_name="A", last_name="B")
        user.user_id = 2
        user.is_blocked = False

        dto = self.mapper.to_board_card_dto(application, user)

        self.assertFalse(dto.is_blocked)

    def test_to_board_card_dto_is_blocked_defaults_false_when_unset(self):
        application = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.APPLIED, current_round=1
        )
        application.application_id = 1
        user = UsersEntity(first_name="A", last_name="B")
        user.user_id = 2

        dto = self.mapper.to_board_card_dto(application, user)

        self.assertFalse(dto.is_blocked)

    def test_to_job_dto_includes_reviewer_id_when_provided(self):
        job = self._make_job_entity(status=JobStatus.PENDING_REVIEW)
        dto = self.mapper.to_job_dto(job, reviewer_id=7)
        self.assertEqual(dto.reviewer_id, 7)

    def test_to_job_dto_reviewer_id_defaults_to_none(self):
        job = self._make_job_entity()
        dto = self.mapper.to_job_dto(job)
        self.assertIsNone(dto.reviewer_id)

    def test_to_job_dto_carries_submit_blockers(self):
        job = self._make_job_entity()
        dto = self.mapper.to_job_dto(job, submit_blockers=["needs a stage"])
        self.assertEqual(dto.submit_blockers, ["needs a stage"])

    def test_to_job_dto_defaults_submit_blockers_to_empty(self):
        job = self._make_job_entity()
        dto = self.mapper.to_job_dto(job)
        self.assertEqual(dto.submit_blockers, [])

    def test_to_my_application_summary_dto_maps_fields(self):
        application = ApplicationEntity(
            job_id=5, user_id=2, stage=ApplicationStage.HIRED
        )
        application.application_id = 10
        job = self._make_job_entity(
            title="CircleCat Mentor", mentorship_role=ParticipantRole.MENTOR
        )
        job.job_id = 5

        dto = self.mapper.to_my_application_summary_dto(application, job)

        self.assertEqual(dto.application_id, 10)
        self.assertEqual(dto.job_id, 5)
        self.assertEqual(dto.job_title, "CircleCat Mentor")
        self.assertEqual(dto.job_kind, JobKind.ACTIVITY)
        self.assertEqual(dto.mentorship_role, ParticipantRole.MENTOR)
        self.assertEqual(dto.stage, ApplicationStage.HIRED)


if __name__ == "__main__":
    unittest.main()
