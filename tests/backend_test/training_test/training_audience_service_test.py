import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.common.constants import MicrosoftAccountStatus, MicrosoftGroups
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import TrainingCategory, TrainingStatus
from backend.dto.training_audience_dto import TrainingAudienceFilterDto
from backend.training.training_audience_service import TrainingAudienceService


def _row(user_id, **overrides):
    """One audience row as the repository hands it over."""
    row = {
        "user_id": user_id,
        "first_name": "Ada",
        "last_name": "Internal",
        "preferred_name": None,
        "is_internal": True,
        "course_status": None,
        "assigned_course_count": 0,
        "done_course_count": 0,
    }
    row.update(overrides)
    return SimpleNamespace(**row)


class TestTrainingAudienceService(unittest.IsolatedAsyncioTestCase):
    """The search behind the bulk assignment card, above the SQL."""

    def setUp(self):
        self.session = AsyncMock()

        self.audience_repository = MagicMock()
        self.audience_repository.search_audience = AsyncMock(return_value=([], 0))
        self.audience_repository.count_audience = AsyncMock(return_value=0)
        self.audience_repository.list_audience_ids = AsyncMock(return_value=[])

        self.user_emails_repository = MagicMock()
        self.user_emails_repository.list_by_emails = AsyncMock(return_value=[])
        self.user_emails_repository.get_contact_emails_by_user_ids = AsyncMock(
            return_value={}
        )

        self.ldap_service = MagicMock()
        self.ldap_service.get_ldaps_by_status_and_group = MagicMock(return_value={})

        self.training_repository = MagicMock()
        self.training_repository.get_training_with_course_by_user_id = AsyncMock(
            return_value=[]
        )
        self.progress_repository = MagicMock()
        self.progress_repository.get_by_training_ids = AsyncMock(return_value={})

        self.service = TrainingAudienceService(
            logger=MagicMock(),
            training_audience_repository=self.audience_repository,
            user_emails_repository=self.user_emails_repository,
            ldap_service=self.ldap_service,
            training_repository=self.training_repository,
            training_progress_repository=self.progress_repository,
        )

    def _restriction_passed(self):
        return self.audience_repository.search_audience.await_args.kwargs[
            "restrict_user_ids"
        ]

    async def test_no_group_leaves_the_search_unrestricted(self):
        await self.service.search_audience(self.session, TrainingAudienceFilterDto())

        self.assertIsNone(self._restriction_passed())
        self.ldap_service.get_ldaps_by_status_and_group.assert_not_called()

    async def test_a_group_restricts_the_search_to_its_members(self):
        self.ldap_service.get_ldaps_by_status_and_group.return_value = {
            "interns": {"active": {"ada": "Ada Internal", "bo": "Bo External"}}
        }
        self.user_emails_repository.list_by_emails.return_value = [
            SimpleNamespace(email="ada@circlecat.org", user_id=7),
            SimpleNamespace(email="bo@circlecat.org", user_id=9),
        ]

        await self.service.search_audience(
            self.session,
            TrainingAudienceFilterDto(user_type="internal"),
            group=MicrosoftGroups.INTERNS,
        )

        self.assertEqual(sorted(self._restriction_passed()), [7, 9])
        self.assertEqual(
            sorted(self.user_emails_repository.list_by_emails.await_args.args[1]),
            ["ada@circlecat.org", "bo@circlecat.org"],
        )

    async def test_only_the_active_side_of_a_group_is_read(self):
        await self.service.search_audience(
            self.session,
            TrainingAudienceFilterDto(user_type="internal"),
            group=MicrosoftGroups.EMPLOYEES,
        )

        self.ldap_service.get_ldaps_by_status_and_group.assert_called_once_with(
            MicrosoftAccountStatus.ACTIVE, [MicrosoftGroups.EMPLOYEES]
        )

    async def test_a_group_needs_the_internal_type_to_mean_anything(self):
        with self.assertRaises(ValueError):
            await self.service.search_audience(
                self.session,
                TrainingAudienceFilterDto(user_type="external"),
                group=MicrosoftGroups.INTERNS,
            )

        self.ldap_service.get_ldaps_by_status_and_group.assert_not_called()
        self.audience_repository.search_audience.assert_not_awaited()

    async def test_a_group_without_a_type_at_all_is_refused(self):
        with self.assertRaises(ValueError):
            await self.service.search_audience(
                self.session,
                TrainingAudienceFilterDto(),
                group=MicrosoftGroups.INTERNS,
            )

    async def test_a_failing_directory_read_is_not_an_empty_group(self):
        self.ldap_service.get_ldaps_by_status_and_group.side_effect = RuntimeError(
            "redis is down"
        )

        with self.assertRaises(RuntimeError):
            await self.service.search_audience(
                self.session,
                TrainingAudienceFilterDto(user_type="internal"),
                group=MicrosoftGroups.INTERNS,
            )

        self.audience_repository.search_audience.assert_not_awaited()

    async def test_a_group_holding_no_purrf_account_matches_nobody(self):
        self.ldap_service.get_ldaps_by_status_and_group.return_value = {
            "interns": {"active": {"ada": "Ada Internal"}}
        }
        self.user_emails_repository.list_by_emails.return_value = []

        await self.service.search_audience(
            self.session,
            TrainingAudienceFilterDto(user_type="internal"),
            group=MicrosoftGroups.INTERNS,
        )

        self.assertEqual(self._restriction_passed(), [])

    async def test_rows_carry_the_contact_address(self):
        self.audience_repository.search_audience.return_value = (
            [_row(7), _row(9)],
            2,
        )
        self.user_emails_repository.get_contact_emails_by_user_ids.return_value = {
            7: "ada@circlecat.org"
        }

        result = await self.service.search_audience(
            self.session, TrainingAudienceFilterDto()
        )

        self.assertEqual(result.total, 2)
        self.assertEqual(result.rows[0].contact_email, "ada@circlecat.org")
        self.assertIsNone(result.rows[1].contact_email)

    async def test_rows_carry_the_course_status_and_the_counts(self):
        self.audience_repository.search_audience.return_value = (
            [
                _row(
                    7,
                    course_status=TrainingStatus.DONE,
                    assigned_course_count=4,
                    done_course_count=2,
                )
            ],
            1,
        )

        result = await self.service.search_audience(
            self.session, TrainingAudienceFilterDto()
        )

        self.assertEqual(result.rows[0].course_status, TrainingStatus.DONE)
        self.assertEqual(result.rows[0].assigned_course_count, 4)
        self.assertEqual(result.rows[0].done_course_count, 2)

    async def test_selecting_everyone_returns_the_ids(self):
        self.audience_repository.count_audience.return_value = 2
        self.audience_repository.list_audience_ids.return_value = [7, 9]

        result = await self.service.list_audience_ids(
            self.session, TrainingAudienceFilterDto()
        )

        self.assertEqual(result.user_ids, [7, 9])
        self.assertEqual(result.total, 2)

    async def test_a_selection_at_the_cap_is_allowed(self):
        self.audience_repository.count_audience.return_value = (
            TrainingAudienceService.ID_SELECTION_CAP
        )
        self.audience_repository.list_audience_ids.return_value = list(
            range(TrainingAudienceService.ID_SELECTION_CAP)
        )

        result = await self.service.list_audience_ids(
            self.session, TrainingAudienceFilterDto()
        )

        self.assertEqual(len(result.user_ids), TrainingAudienceService.ID_SELECTION_CAP)

    async def test_a_selection_over_the_cap_is_refused_rather_than_trimmed(self):
        self.audience_repository.count_audience.return_value = (
            TrainingAudienceService.ID_SELECTION_CAP + 1
        )

        with self.assertRaises(ConflictError):
            await self.service.list_audience_ids(
                self.session, TrainingAudienceFilterDto()
            )

        self.audience_repository.list_audience_ids.assert_not_awaited()


def _assignment(training_id, **overrides):
    """One training row as the repository hands it over, with its course."""
    fields = {
        "training_id": training_id,
        "course_id": 5,
        "category": TrainingCategory.CORPORATE_CULTURE_COURSE,
        "status": TrainingStatus.TO_DO,
        "deadline": None,
        "completed_timestamp": None,
    }
    fields.update(overrides)
    return (SimpleNamespace(**fields), "Corporate Culture", True, True)


def _progress(training_id, **overrides):
    fields = {
        "training_id": training_id,
        "lesson_status": "incomplete",
        "score_raw": None,
        "score_max": None,
        "session_time_seconds": 940,
        "last_accessed_at": "2026-09-01T10:00:00+00:00",
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


class TestOnePersonsAssignments(unittest.IsolatedAsyncioTestCase):
    """The read behind expanding a row: what one person holds.

    The only place in the repo an administrator can see somebody else's whole
    training list, so it is read-only and independent of the target course.
    """

    def setUp(self):
        self.session = AsyncMock()
        self.training_repository = MagicMock()
        self.training_repository.get_training_with_course_by_user_id = AsyncMock(
            return_value=[]
        )
        self.progress_repository = MagicMock()
        self.progress_repository.get_by_training_ids = AsyncMock(return_value={})
        self.service = TrainingAudienceService(
            logger=MagicMock(),
            training_audience_repository=MagicMock(),
            user_emails_repository=MagicMock(),
            ldap_service=MagicMock(),
            training_repository=self.training_repository,
            training_progress_repository=self.progress_repository,
        )

    async def test_somebody_holding_nothing_has_an_empty_list(self):
        result = await self.service.list_user_assignments(self.session, 11)

        self.assertEqual(result.rows, [])
        self.progress_repository.get_by_training_ids.assert_not_awaited()

    async def test_a_row_carries_the_course_name_and_the_status(self):
        self.training_repository.get_training_with_course_by_user_id.return_value = [
            _assignment(42, status=TrainingStatus.DONE)
        ]

        result = await self.service.list_user_assignments(self.session, 11)

        self.assertEqual(result.rows[0].training_id, 42)
        self.assertEqual(result.rows[0].course_name, "Corporate Culture")
        self.assertEqual(result.rows[0].status, TrainingStatus.DONE)

    async def test_runtime_state_comes_from_the_progress_row(self):
        self.training_repository.get_training_with_course_by_user_id.return_value = [
            _assignment(42)
        ]
        self.progress_repository.get_by_training_ids.return_value = {
            42: _progress(42, score_raw=Decimal("82.50"))
        }

        result = await self.service.list_user_assignments(self.session, 11)

        row = result.rows[0]
        self.assertEqual(row.score_raw, "82.50")
        self.assertEqual(row.session_time_seconds, 940)
        self.assertEqual(row.lesson_status, "incomplete")

    async def test_an_assignment_nobody_opened_reports_no_runtime_state(self):
        self.training_repository.get_training_with_course_by_user_id.return_value = [
            _assignment(42)
        ]

        result = await self.service.list_user_assignments(self.session, 11)

        row = result.rows[0]
        self.assertIsNone(row.score_raw)
        self.assertIsNone(row.session_time_seconds)
        self.assertIsNone(row.last_accessed_at)
        self.assertIsNone(row.lesson_status)

    async def test_every_progress_row_is_read_in_one_go(self):
        self.training_repository.get_training_with_course_by_user_id.return_value = [
            _assignment(42),
            _assignment(43, course_id=6),
        ]

        await self.service.list_user_assignments(self.session, 11)

        self.progress_repository.get_by_training_ids.assert_awaited_once_with(
            self.session, [42, 43]
        )

    async def test_a_row_whose_course_the_catalogue_lost_still_appears(self):
        training = SimpleNamespace(
            training_id=42,
            course_id=None,
            category=TrainingCategory.CORPORATE_CULTURE_COURSE,
            status=TrainingStatus.TO_DO,
            deadline=None,
            completed_timestamp=None,
        )
        self.training_repository.get_training_with_course_by_user_id.return_value = [
            (training, None, False, True)
        ]

        result = await self.service.list_user_assignments(self.session, 11)

        self.assertIsNone(result.rows[0].course_name)
        self.assertIsNone(result.rows[0].course_id)


if __name__ == "__main__":
    unittest.main()
