import unittest
from unittest.mock import MagicMock, AsyncMock
from backend.mentorship.mentorship_admin_service import MentorshipAdminService
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from backend.dto.participant_search_row_dto import ParticipantSearchRow
from backend.common.mentorship_enums import (
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)


def _make_row(**kwargs):
    row_fields = dict(
        user_id=1,
        round_id=None,
        pair_id=None,
        participant_role=None,
        approval_status=None,
        completed_count=None,
        mentor_id=None,
        mentee_id=None,
    )
    row_fields.update(kwargs)
    return ParticipantSearchRow(**row_fields)


class TestMentorshipAdminService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_users_repo = MagicMock()
        self.mock_users_repo.get_users_and_emails_by_ids = AsyncMock()

        self.mock_participants_repo = MagicMock()
        self.mock_participants_repo.search_participants_for_admin = AsyncMock()

        self.mock_rounds_repo = MagicMock()
        self.mock_rounds_repo.get_all_rounds = AsyncMock()

        self.mock_training_repo = MagicMock()
        self.mock_training_repo.get_training_by_user_ids = AsyncMock()

        self.mock_session = AsyncMock()

        self.service = MentorshipAdminService(
            users_repository=self.mock_users_repo,
            participants_repository=self.mock_participants_repo,
            rounds_repository=self.mock_rounds_repo,
            training_repository=self.mock_training_repo,
        )

    async def test_empty_rows_returns_immediately(self):
        """Returns empty result without calling other repos when no rows found."""
        self.mock_participants_repo.search_participants_for_admin.return_value = ([], 0)

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        self.assertEqual(result.participant_rows, [])
        self.assertEqual(result.total, 0)
        self.mock_users_repo.get_users_and_emails_by_ids.assert_not_awaited()
        self.mock_rounds_repo.get_all_rounds.assert_not_awaited()
        self.mock_training_repo.get_training_by_user_ids.assert_not_awaited()

    async def test_partner_ids_included_in_user_fetch(self):
        """users repo receives both the participant's and the partner's user_id."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [_make_row(user_id=1, pair_id=5, mentor_id=1, mentee_id=2)],
            1,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1,
                    first_name="Alice",
                    last_name="Doe",
                    preferred_name="Alice Doe",
                ),
                2: MagicMock(
                    user_id=2,
                    first_name="Bob",
                    last_name="Smith",
                    preferred_name="Bob Smith",
                ),
            },
            {},
        )
        self.mock_rounds_repo.get_all_rounds.return_value = []
        self.mock_training_repo.get_training_by_user_ids.return_value = {}

        await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        _, called_ids = self.mock_users_repo.get_users_and_emails_by_ids.call_args[0]
        self.assertEqual(set(called_ids), {1, 2})

    async def test_matched_user_resolves_partner_correctly(self):
        """matched_user always refers to the other participant in the pair."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [
                _make_row(
                    user_id=1,
                    pair_id=99,
                    mentor_id=1,
                    mentee_id=2,
                    participant_role=ParticipantRole.MENTOR,
                ),
                _make_row(
                    user_id=2,
                    pair_id=99,
                    mentor_id=1,
                    mentee_id=2,
                    participant_role=ParticipantRole.MENTEE,
                ),
            ],
            2,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1,
                    first_name="Alice",
                    last_name="Doe",
                    preferred_name="Alice Doe",
                ),
                2: MagicMock(
                    user_id=2,
                    first_name="Bob",
                    last_name="Smith",
                    preferred_name="Bob Smith",
                ),
            },
            {},
        )
        self.mock_rounds_repo.get_all_rounds.return_value = []
        self.mock_training_repo.get_training_by_user_ids.return_value = {}

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        rows = {r.user_id: r for r in result.participant_rows}
        self.assertEqual(rows[1].matched_user.id, 2)
        self.assertEqual(rows[2].matched_user.id, 1)

    async def test_onboarding_status_requires_done_training(self):
        """onboarding_status is 'completed' only when training status is DONE; otherwise 'incomplete'."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [
                _make_row(user_id=1, participant_role=ParticipantRole.MENTEE),
                _make_row(user_id=2, participant_role=ParticipantRole.MENTEE),
                _make_row(user_id=3, participant_role=ParticipantRole.MENTOR),
            ],
            3,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1,
                    first_name="Alice",
                    last_name="Doe",
                    preferred_name="Alice Doe",
                ),
                2: MagicMock(
                    user_id=2,
                    first_name="Bob",
                    last_name="Smith",
                    preferred_name="Bob Smith",
                ),
                3: MagicMock(
                    user_id=3,
                    first_name="Carol",
                    last_name="Jones",
                    preferred_name="Carol Jones",
                ),
            },
            {},
        )
        self.mock_rounds_repo.get_all_rounds.return_value = []
        self.mock_training_repo.get_training_by_user_ids.return_value = {
            1: [
                MagicMock(
                    category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                    status=TrainingStatus.DONE,
                )
            ],
            2: [
                MagicMock(
                    category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                    status=TrainingStatus.IN_PROGRESS,
                )
            ],
            3: [
                MagicMock(
                    category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
                    status=TrainingStatus.TO_DO,
                )
            ],
        }

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        rows = {r.user_id: r for r in result.participant_rows}
        self.assertEqual(rows[1].onboarding_status, "completed")
        self.assertEqual(rows[2].onboarding_status, "incomplete")
        self.assertEqual(rows[3].onboarding_status, "incomplete")

    async def test_post_filter_onboarding_status(self):
        """Rows not matching filters.onboarding_status are excluded; total reflects the repo count."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [
                _make_row(user_id=1, participant_role=ParticipantRole.MENTEE),
                _make_row(user_id=2, participant_role=ParticipantRole.MENTEE),
            ],
            2,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1,
                    first_name="Alice",
                    last_name="Doe",
                    preferred_name="Alice Doe",
                ),
                2: MagicMock(
                    user_id=2,
                    first_name="Bob",
                    last_name="Smith",
                    preferred_name="Bob Smith",
                ),
            },
            {},
        )
        self.mock_rounds_repo.get_all_rounds.return_value = []
        self.mock_training_repo.get_training_by_user_ids.return_value = {
            1: [
                MagicMock(
                    category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                    status=TrainingStatus.DONE,
                )
            ],
            2: [
                MagicMock(
                    category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                    status=TrainingStatus.IN_PROGRESS,
                )
            ],
        }

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto(onboarding_status="completed")
        )

        self.assertEqual(len(result.participant_rows), 1)
        self.assertEqual(result.participant_rows[0].user_id, 1)
        self.assertEqual(result.total, 2)


if __name__ == "__main__":
    unittest.main()
