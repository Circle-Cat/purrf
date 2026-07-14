import unittest
from unittest.mock import MagicMock, AsyncMock
from backend.mentorship.mentorship_admin_service import MentorshipAdminService
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from backend.dto.participant_search_row_dto import ParticipantSearchRow
from backend.dto.admin_meeting_log_dto import AdminMeetingDto
from backend.common.mentorship_enums import (
    MeetingNoteTag,
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
        self.mock_training_repo.get_training_by_user_ids_and_categories = AsyncMock()

        self.mock_pairs_repo = MagicMock()
        self.mock_pairs_repo.get_pair_by_id = AsyncMock()

        self.mock_mapper = MagicMock()
        self.mock_mapper.map_to_admin_meeting_dto.side_effect = (
            lambda meeting, *, is_completed, note_tags: AdminMeetingDto(
                meeting_id=meeting["meeting_id"],
                start_datetime=meeting["start_datetime"],
                end_datetime=meeting["end_datetime"],
                is_completed=is_completed,
                note=note_tags,
                create_datetime=meeting["created_datetime"],
            )
        )

        self.mock_session = AsyncMock()

        self.service = MentorshipAdminService(
            users_repository=self.mock_users_repo,
            participants_repository=self.mock_participants_repo,
            rounds_repository=self.mock_rounds_repo,
            training_repository=self.mock_training_repo,
            pairs_repository=self.mock_pairs_repo,
            mentorship_mapper=self.mock_mapper,
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
        self.mock_training_repo.get_training_by_user_ids_and_categories.assert_not_awaited()

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
        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = []

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
        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = []

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        rows = {r.user_id: r for r in result.participant_rows}
        self.assertEqual(rows[1].matched_user.id, 2)
        self.assertEqual(rows[2].matched_user.id, 1)

    async def test_onboarding_status_requires_done_training(self):
        """mentor/mentee_onboarding_status returns the raw TrainingStatus from the training record."""
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
        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = [
            MagicMock(
                user_id=1,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                status=TrainingStatus.DONE,
            ),
            MagicMock(
                user_id=2,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                status=TrainingStatus.IN_PROGRESS,
            ),
            MagicMock(
                user_id=3,
                category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
                status=TrainingStatus.TO_DO,
            ),
        ]

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        rows = {r.user_id: r for r in result.participant_rows}
        self.assertEqual(rows[1].mentee_onboarding_status, TrainingStatus.DONE)
        self.assertIsNone(rows[1].mentor_onboarding_status)
        self.assertEqual(rows[2].mentee_onboarding_status, TrainingStatus.IN_PROGRESS)
        self.assertIsNone(rows[2].mentor_onboarding_status)
        self.assertEqual(rows[3].mentor_onboarding_status, TrainingStatus.TO_DO)
        self.assertIsNone(rows[3].mentee_onboarding_status)

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
        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = [
            MagicMock(
                user_id=1,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                status=TrainingStatus.DONE,
            ),
            MagicMock(
                user_id=2,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                status=TrainingStatus.IN_PROGRESS,
            ),
        ]

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto(onboarding_status="completed")
        )

        self.assertEqual(len(result.participant_rows), 1)
        self.assertEqual(result.participant_rows[0].user_id, 1)
        self.assertEqual(result.total, 2)

    async def test_get_meeting_log_pair_not_found(self):
        """Returns None when pair_id does not exist."""
        self.mock_pairs_repo.get_pair_by_id.return_value = None

        result = await self.service.get_meeting_log(self.mock_session, pair_id=999)

        self.assertIsNone(result)

    async def test_get_meeting_log_v2_notes_and_sort(self):
        """v2 pair has round_version v2, notes derived from meeting fields, sorted by create_datetime."""
        pair = MagicMock()
        pair.mentor_id = 1
        pair.mentee_id = 2
        pair.meeting_log = {
            "google_meetings": [
                {
                    "meeting_id": "m2",
                    "start_datetime": "2024-02-01T10:00:00",
                    "end_datetime": "2024-02-01T11:00:00",
                    "is_completed": True,
                    "created_datetime": "2024-02-01T09:00:00",
                    "has_insufficient_duration": False,
                    "has_unknown_absent": None,
                    "absent_user_id": None,
                    "has_unknown_late": False,
                    "late_user_ids": [],
                },
                {
                    "meeting_id": "m1",
                    "start_datetime": "2024-01-01T10:00:00",
                    "end_datetime": "2024-01-01T11:00:00",
                    "is_completed": False,
                    "created_datetime": "2024-01-01T09:00:00",
                    "has_insufficient_duration": False,
                    "has_unknown_absent": None,
                    "absent_user_id": 1,
                    "has_unknown_late": False,
                    "late_user_ids": [2],
                },
            ]
        }
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(result.round_version, "v2")
        self.assertEqual([m.meeting_id for m in result.meetings], ["m1", "m2"])
        self.assertIn(MeetingNoteTag.MENTOR_ABSENT, result.meetings[0].note)
        self.assertIn(MeetingNoteTag.MENTEE_LATE, result.meetings[0].note)
        self.assertEqual(result.meetings[1].note, [])

    async def test_get_meeting_log_v1(self):
        """v1 pair has round_version v1, is_completed always True, note always empty."""
        pair = MagicMock()
        pair.mentor_id = 1
        pair.mentee_id = 2
        pair.meeting_log = {
            "meeting_time_list": [
                {
                    "meeting_id": "v1-m1",
                    "start_datetime": "2024-01-01T10:00:00",
                    "end_datetime": "2024-01-01T11:00:00",
                    "created_datetime": "2024-01-01T09:00:00",
                }
            ]
        }
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(result.round_version, "v1")
        self.assertEqual(result.meetings[0].is_completed, True)
        self.assertEqual(result.meetings[0].note, [])

    async def test_get_meeting_log_both_empty_defaults_to_v2(self):
        """Pair with neither google_meetings nor meeting_time_list defaults to v2 with no meetings."""
        pair = MagicMock()
        pair.mentor_id = 1
        pair.mentee_id = 2
        pair.meeting_log = {}
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(result.round_version, "v2")
        self.assertEqual(result.meetings, [])

    async def test_get_meeting_log_v2_unknown_absent_and_unknown_late(self):
        """Unknown absent/late flags produce UNKNOWN_ABSENT/UNKNOWN_LATE tags."""
        pair = MagicMock()
        pair.mentor_id = 1
        pair.mentee_id = 2
        pair.meeting_log = {
            "google_meetings": [
                {
                    "meeting_id": "m1",
                    "start_datetime": "2024-01-01T10:00:00",
                    "end_datetime": "2024-01-01T11:00:00",
                    "is_completed": False,
                    "created_datetime": "2024-01-01T09:00:00",
                    "has_insufficient_duration": False,
                    "has_unknown_absent": True,
                    "absent_user_id": None,
                    "has_unknown_late": True,
                    "late_user_ids": [],
                },
            ]
        }
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(
            result.meetings[0].note,
            [MeetingNoteTag.UNKNOWN_ABSENT, MeetingNoteTag.UNKNOWN_LATE],
        )

    async def test_get_meeting_log_v2_insufficient_duration(self):
        """has_insufficient_duration produces the INSUFFICIENT_DURATION tag."""
        pair = MagicMock()
        pair.mentor_id = 1
        pair.mentee_id = 2
        pair.meeting_log = {
            "google_meetings": [
                {
                    "meeting_id": "m1",
                    "start_datetime": "2024-01-01T10:00:00",
                    "end_datetime": "2024-01-01T11:00:00",
                    "is_completed": False,
                    "created_datetime": "2024-01-01T09:00:00",
                    "has_insufficient_duration": True,
                    "has_unknown_absent": False,
                    "absent_user_id": None,
                    "has_unknown_late": False,
                    "late_user_ids": [],
                },
            ]
        }
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(
            result.meetings[0].note, [MeetingNoteTag.INSUFFICIENT_DURATION]
        )

    async def test_get_meeting_log_v2_mentee_absent_and_mentor_late(self):
        """Mentee absence and mentor lateness are tagged from the opposite-role fields."""
        pair = MagicMock()
        pair.mentor_id = 1
        pair.mentee_id = 2
        pair.meeting_log = {
            "google_meetings": [
                {
                    "meeting_id": "m1",
                    "start_datetime": "2024-01-01T10:00:00",
                    "end_datetime": "2024-01-01T11:00:00",
                    "is_completed": False,
                    "created_datetime": "2024-01-01T09:00:00",
                    "has_insufficient_duration": False,
                    "has_unknown_absent": False,
                    "absent_user_id": 2,
                    "has_unknown_late": False,
                    "late_user_ids": [1],
                },
            ]
        }
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertIn(MeetingNoteTag.MENTEE_ABSENT, result.meetings[0].note)
        self.assertIn(MeetingNoteTag.MENTOR_LATE, result.meetings[0].note)


if __name__ == "__main__":
    unittest.main()
