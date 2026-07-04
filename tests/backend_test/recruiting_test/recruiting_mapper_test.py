import unittest
from datetime import datetime, timezone

from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus


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
        user = UsersEntity(
            first_name="Ada", last_name="Lovelace", primary_email="ada@b.com"
        )
        user.user_id = 2

        dto = self.mapper.to_board_card_dto(application, user)

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
        user = UsersEntity(first_name="Cher", last_name="", primary_email="c@b.com")
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
        user = UsersEntity(first_name="A", last_name="B", primary_email="a@b.com")
        user.user_id = 2

        dto = self.mapper.to_board_card_dto(application, user)

        self.assertEqual(dto.round, 2)

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
        user = UsersEntity(first_name="A", last_name="B", primary_email="a@b.com")
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
        user = UsersEntity(first_name="A", last_name="B", primary_email="a@b.com")
        user.user_id = 2
        user.is_blocked = False

        dto = self.mapper.to_board_card_dto(application, user)

        self.assertFalse(dto.is_blocked)

    def test_to_board_card_dto_is_blocked_defaults_false_when_unset(self):
        application = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.APPLIED, current_round=1
        )
        application.application_id = 1
        user = UsersEntity(first_name="A", last_name="B", primary_email="a@b.com")
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


if __name__ == "__main__":
    unittest.main()
