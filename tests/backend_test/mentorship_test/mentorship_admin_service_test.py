import unittest
from unittest.mock import MagicMock, AsyncMock
from backend.mentorship.mentorship_admin_service import MentorshipAdminService
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from backend.dto.participant_search_row_dto import ParticipantSearchRow
from backend.dto.admin_meeting_log_dto import AdminMeetingDto
from backend.common.mentorship_enums import (
    ApprovalStatus,
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
        meeting_log=None,
    )
    row_fields.update(kwargs)
    return ParticipantSearchRow(**row_fields)


async def _collect_csv(agen) -> str:
    """Decodes with utf-8-sig to strip the leading UTF-8 BOM the export writes."""
    chunks = [chunk async for chunk in agen]
    return b"".join(chunks).decode("utf-8-sig")


class TestMentorshipAdminService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_users_repo = MagicMock()
        self.mock_users_repo.get_users_and_emails_by_ids = AsyncMock()

        self.mock_participants_repo = MagicMock()
        self.mock_participants_repo.search_participants_for_admin = AsyncMock()
        self.mock_participants_repo.iter_search_participants_for_admin = AsyncMock()

        self.mock_rounds_repo = MagicMock()
        self.mock_rounds_repo.get_all_rounds = AsyncMock(return_value=[])

        self.mock_training_repo = MagicMock()
        self.mock_training_repo.get_training_by_user_ids_and_categories = AsyncMock(
            return_value=[]
        )

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
        self.mock_database = MagicMock()
        self.mock_database.session.return_value.__aenter__.return_value = (
            self.mock_session
        )
        self.mock_database.session.return_value.__aexit__.return_value = None

        self.mock_date_time_util = MagicMock()
        self.mock_date_time_util.format_iso_utc_to_pt.side_effect = (
            lambda iso, fmt="%Y-%m-%d %H:%M %Z": f"PT({iso})"
        )
        self.mock_logger = MagicMock()

        self.service = MentorshipAdminService(
            users_repository=self.mock_users_repo,
            participants_repository=self.mock_participants_repo,
            rounds_repository=self.mock_rounds_repo,
            training_repository=self.mock_training_repo,
            pairs_repository=self.mock_pairs_repo,
            mentorship_mapper=self.mock_mapper,
            date_time_util=self.mock_date_time_util,
            database=self.mock_database,
            logger=self.mock_logger,
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
                    "late_user_id": [],
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
                    "late_user_id": [2],
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
                    "late_user_id": [],
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
                    "late_user_id": [],
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
                    "late_user_id": [1],
                },
            ]
        }
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertIn(MeetingNoteTag.MENTEE_ABSENT, result.meetings[0].note)
        self.assertIn(MeetingNoteTag.MENTOR_LATE, result.meetings[0].note)

    def test_build_common_export_columns_sanitizes_formula_injection(self):
        """Free-text fields starting with =, +, -, or @ get a leading single-quote
        so spreadsheet software treats them as literal text, not formulas."""
        row = _make_row(user_id=1)
        users_map = {
            1: MagicMock(
                user_id=1,
                first_name="=cmd|calc",
                last_name="+SUM(A1)",
                preferred_name="-1+1",
            ),
        }
        emails_map = {
            1: [
                MagicMock(is_primary=True, email="@evil.com"),
                MagicMock(is_primary=False, email="+alt@evil.com"),
            ]
        }

        common = self.service._build_common_export_columns(row, users_map, emails_map)

        self.assertEqual(common[1], "'=cmd|calc")  # first_name
        self.assertEqual(common[2], "'+SUM(A1)")  # last_name
        self.assertEqual(common[3], "'-1+1")  # preferred_name
        self.assertEqual(common[4], "'@evil.com")  # primary_email
        self.assertEqual(common[5], "'+alt@evil.com")  # alternative_emails joined

    def test_build_common_export_columns_sanitizes_leading_whitespace(self):
        """A formula-trigger character preceded by leading whitespace is still
        sanitized, since some spreadsheet apps strip it before checking the
        prefix; the original (unstripped) value is what gets quoted."""
        row = _make_row(user_id=1)
        users_map = {
            1: MagicMock(
                user_id=1, first_name=" =cmd|calc", last_name="Doe", preferred_name=None
            )
        }
        emails_map = {1: []}

        common = self.service._build_common_export_columns(row, users_map, emails_map)

        self.assertEqual(common[1], "' =cmd|calc")

    def test_build_common_export_columns_normal_and_none_values_unaffected(self):
        """Values that don't start with a formula-trigger character (including
        None) pass through unchanged."""
        row = _make_row(user_id=1)
        users_map = {
            1: MagicMock(
                user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
            )
        }
        emails_map = {1: [MagicMock(is_primary=True, email="alice@example.com")]}

        common = self.service._build_common_export_columns(row, users_map, emails_map)

        self.assertEqual(common, [1, "Alice", "Doe", None, "alice@example.com", ""])

    def test_build_participant_export_columns_approval_status_raw_enum(self):
        """Approval Status column is the raw enum value, not a display string."""
        row = _make_row(user_id=1, approval_status=ApprovalStatus.UN_MATCHED)

        participant = self.service._build_participant_export_columns(
            row, users_map={}, trainings_map={}, rounds_map={}
        )

        self.assertEqual(participant[2], "un_matched")

    def test_build_participant_export_columns_no_pair_leaves_matched_user_blank(self):
        """A row with no pair_id has blank Matched User columns."""
        row = _make_row(user_id=1)

        participant = self.service._build_participant_export_columns(
            row, users_map={}, trainings_map={}, rounds_map={}
        )

        self.assertEqual(participant, ["", "", "", "", "", ""])

    def test_build_participant_export_columns_matched_name_formula_injection(self):
        """The matched user's name is sanitized the same as any other free-text field."""
        row = _make_row(
            user_id=1,
            pair_id=10,
            mentor_id=1,
            mentee_id=2,
            participant_role=ParticipantRole.MENTOR,
        )
        users_map = {
            2: MagicMock(
                user_id=2,
                first_name="=Mentee",
                last_name="Smith",
                preferred_name="@pref",
            ),
        }

        participant = self.service._build_participant_export_columns(
            row, users_map, trainings_map={}, rounds_map={}
        )

        # partner's preferred_name ("@pref") wins per partner_display_name and
        # gets sanitized after combining.
        self.assertEqual(participant[5], "'@pref")  # matched_user_name

    def test_build_participant_export_columns_matched_name_fallback(self):
        """Matched User Name falls back to "first last" when the partner has no
        preferred_name, and the combined result is still sanitized."""
        row = _make_row(
            user_id=1,
            pair_id=10,
            mentor_id=1,
            mentee_id=2,
            participant_role=ParticipantRole.MENTOR,
        )
        users_map = {
            2: MagicMock(
                user_id=2, first_name="=Mentee", last_name="Smith", preferred_name=None
            ),
        }

        participant = self.service._build_participant_export_columns(
            row, users_map, trainings_map={}, rounds_map={}
        )

        self.assertEqual(participant[4], 2)  # matched_user_id
        self.assertEqual(
            participant[5], "'=Mentee Smith"
        )  # matched_user_name, sanitized

    def test_build_participant_export_columns_onboarding_status_mentee_role(self):
        """A mentee-role row's Onboarding Status is the mentee onboarding status,
        not the mentor one, even if both are set."""
        row = _make_row(user_id=1, participant_role=ParticipantRole.MENTEE)
        trainings_map = {
            1: {
                TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING: TrainingStatus.DONE,
                TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING: TrainingStatus.TO_DO,
            }
        }

        participant = self.service._build_participant_export_columns(
            row, users_map={}, trainings_map=trainings_map, rounds_map={}
        )

        self.assertEqual(participant[3], "to_do")

    def test_build_participant_export_columns_onboarding_status_mentor_role(self):
        """A mentor-role row's Onboarding Status is the mentor onboarding status."""
        row = _make_row(user_id=1, participant_role=ParticipantRole.MENTOR)
        trainings_map = {
            1: {
                TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING: TrainingStatus.DONE,
                TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING: TrainingStatus.TO_DO,
            }
        }

        participant = self.service._build_participant_export_columns(
            row, users_map={}, trainings_map=trainings_map, rounds_map={}
        )

        self.assertEqual(participant[3], "done")

    def test_build_non_participant_export_columns_returns_both_statuses(self):
        """A non-participant row exposes both mentor and mentee onboarding
        status, since it has no participant_role to disambiguate by."""
        row = _make_row(user_id=1)
        trainings_map = {
            1: {
                TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING: TrainingStatus.DONE,
                TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING: TrainingStatus.TO_DO,
            }
        }

        non_participant = self.service._build_non_participant_export_columns(
            row, trainings_map
        )

        self.assertEqual(non_participant, ["done", "to_do"])

    def test_build_non_participant_export_columns_blank_when_no_training(self):
        """A user with no training record has blank onboarding status columns."""
        row = _make_row(user_id=1)

        non_participant = self.service._build_non_participant_export_columns(
            row, trainings_map={}
        )

        self.assertEqual(non_participant, ["", ""])

    def test_extract_meetings_for_row_empty_meeting_log_returns_empty_list(self):
        """A row with no meeting_log (e.g. non-participant) yields no meetings."""
        row = _make_row(user_id=1, meeting_log=None)
        self.assertEqual(self.service._extract_meetings_for_row(row), [])

    def test_extract_meetings_for_row_v2_resolves_notes(self):
        """A v2 meeting_log maps through the same AdminMeetingDto/note logic as get_meeting_log."""
        row = _make_row(
            user_id=1,
            mentor_id=10,
            mentee_id=20,
            meeting_log={
                "google_meetings": [
                    {
                        "meeting_id": "m1",
                        "start_datetime": "2024-07-15T22:00:00Z",
                        "end_datetime": "2024-07-15T23:00:00Z",
                        "created_datetime": "2024-07-01T00:00:00Z",
                        "is_completed": False,
                        "absent_user_id": 10,
                    }
                ]
            },
        )

        meetings = self.service._extract_meetings_for_row(row)

        self.assertEqual(len(meetings), 1)
        self.assertEqual(meetings[0].meeting_id, "m1")
        self.assertEqual(meetings[0].note, [MeetingNoteTag.MENTOR_ABSENT])

    def test_extract_meetings_for_row_v2_malformed_datetime_raises(self):
        """A meeting with start_datetime=None now surfaces as a DTO
        validation error instead of being defaulted — the caller
        (stream_export_csv) is responsible for catching and skipping."""
        row = _make_row(
            user_id=1,
            mentor_id=10,
            mentee_id=20,
            meeting_log={
                "google_meetings": [
                    {
                        "meeting_id": "m1",
                        "start_datetime": None,
                        "end_datetime": "2024-07-15T23:00:00Z",
                        "created_datetime": "2024-07-01T00:00:00Z",
                        "is_completed": True,
                    }
                ]
            },
        )
        with self.assertRaises(Exception):
            self.service._extract_meetings_for_row(row)

    async def test_missing_participation_status_raises_value_error(self):
        """participation_status decides which column set to use, so it must
        be set — an unfiltered ("both") export isn't a supported mode."""
        with self.assertRaises(ValueError):
            await self.service.stream_export_csv(
                ParticipantSearchFilterDto(), "summary"
            ).__anext__()

    async def test_participant_export_missing_mode_raises_value_error(self):
        """mode decides which meeting column set to use for a participant
        export, so it must be set there — unlike a non-participant export,
        which has no meeting data and can safely ignore mode."""
        with self.assertRaises(ValueError):
            await self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                None,
            ).__anext__()

    async def test_summary_mode_emits_header_and_one_row_per_person(self):
        """Summary mode: header + one CSV row per participant row, no meeting query."""
        row = _make_row(user_id=1, round_id=None, pair_id=None)
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                )
            },
            {1: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                "summary",
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(
            lines[0].split(","),
            [
                "User ID",
                "First Name",
                "Last Name",
                "Preferred Name",
                "Primary Email",
                "Alternative Emails",
                "Round",
                "Participant Role",
                "Approval Status",
                "Onboarding Status",
                "Matched User ID",
                "Matched User Name",
                "Completed Meetings",
                "Required Meetings",
            ],
        )
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].startswith("1,Alice,Doe,,,,"))

        # need_meeting_log must be False for summary mode.
        first_call = self.mock_participants_repo.iter_search_participants_for_admin.call_args_list[
            0
        ]
        self.assertFalse(first_call.kwargs["need_meeting_log"])

    async def test_summary_mode_skips_row_on_build_failure_and_logs(self):
        """A row whose common-column build fails (e.g. missing from
        users_map) is logged and skipped in summary mode too — this
        protection isn't limited to detailed mode's meeting handling."""
        bad_row = _make_row(user_id=1, round_id=10, pair_id=100)
        good_row = _make_row(user_id=2, round_id=20, pair_id=200)
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [bad_row, good_row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                2: MagicMock(
                    user_id=2, first_name="Bob", last_name="Lee", preferred_name=None
                )
            },
            {2: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                "summary",
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(len(lines), 2)  # header + only the good row
        self.assertTrue(lines[1].startswith("2,Bob,Lee"))

        self.mock_logger.exception.assert_called_once()
        _, user_id_arg, pair_id_arg, round_id_arg = (
            self.mock_logger.exception.call_args.args
        )
        self.assertEqual((user_id_arg, pair_id_arg, round_id_arg), (1, 100, 10))

    async def test_summary_mode_first_chunk_starts_with_utf8_bom(self):
        """The raw byte stream is prefixed with a UTF-8 BOM so Excel on
        Windows doesn't mojibake non-ASCII names."""
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            []
        ]

        chunks = [
            chunk
            async for chunk in self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                "summary",
            )
        ]

        self.assertTrue(chunks[0].startswith(b"\xef\xbb\xbf"))

    async def test_detailed_mode_emits_one_row_per_meeting_and_pt_formats_time(self):
        """Detailed mode: one CSV row per meeting, using the PT formatter."""
        row = _make_row(
            user_id=1,
            mentor_id=1,
            mentee_id=2,
            meeting_log={
                "google_meetings": [
                    {
                        "meeting_id": "m1",
                        "start_datetime": "2024-07-15T22:00:00Z",
                        "end_datetime": "2024-07-15T23:00:00Z",
                        "created_datetime": "2024-07-01T00:00:00Z",
                        "is_completed": True,
                    }
                ]
            },
        )
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                )
            },
            {1: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                "detailed",
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(
            lines[0].split(",")[-4:],
            [
                "Complete Status",
                "Start Datetime (PT)",
                "End Datetime (PT)",
                "Note",
            ],
        )
        self.assertIn("PT(2024-07-15T22:00:00Z)", lines[1])
        self.assertIn("Completed", lines[1])

        second_call = self.mock_participants_repo.iter_search_participants_for_admin.call_args_list[
            0
        ]
        self.assertTrue(second_call.kwargs["need_meeting_log"])

    async def test_detailed_mode_skips_row_on_processing_failure_and_logs(self):
        """A row whose meeting data fails to process (e.g. malformed datetime)
        is logged with its identifying info and skipped — the stream
        continues with the next row instead of aborting."""
        bad_row = _make_row(
            user_id=1,
            round_id=10,
            pair_id=100,
            mentor_id=1,
            mentee_id=2,
            meeting_log={
                "google_meetings": [
                    {
                        "meeting_id": "m-bad",
                        "start_datetime": None,
                        "end_datetime": "2024-07-15T23:00:00Z",
                        "created_datetime": "2024-07-01T00:00:00Z",
                        "is_completed": True,
                    }
                ]
            },
        )
        good_row = _make_row(
            user_id=2,
            round_id=20,
            pair_id=200,
            mentor_id=2,
            mentee_id=3,
            meeting_log={
                "google_meetings": [
                    {
                        "meeting_id": "m-good",
                        "start_datetime": "2024-07-15T22:00:00Z",
                        "end_datetime": "2024-07-15T23:00:00Z",
                        "created_datetime": "2024-07-01T00:00:00Z",
                        "is_completed": True,
                    }
                ]
            },
        )
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [bad_row, good_row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                ),
                2: MagicMock(
                    user_id=2, first_name="Bob", last_name="Lee", preferred_name=None
                ),
            },
            {1: [], 2: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                "detailed",
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(len(lines), 2)  # header + only the good row's meeting
        self.assertTrue(lines[1].startswith("2,Bob,Lee"))

        self.mock_logger.exception.assert_called_once()
        _, user_id_arg, pair_id_arg, round_id_arg = (
            self.mock_logger.exception.call_args.args
        )
        self.assertEqual((user_id_arg, pair_id_arg, round_id_arg), (1, 100, 10))

    async def test_detailed_mode_skips_whole_row_not_partial_meetings(self):
        """A pair with two meetings where both DTOs construct fine but only
        the second fails to *format* emits neither meeting — a partial
        failure must not leave the first, already-formatted meeting written
        to the buffer before the second one blows up."""

        def _format_or_raise(iso, fmt="%Y-%m-%d %H:%M %Z"):
            if iso == "bad-datetime":
                raise ValueError(f"Invalid ISO datetime string: {iso}")
            return f"PT({iso})"

        self.mock_date_time_util.format_iso_utc_to_pt.side_effect = _format_or_raise

        row = _make_row(
            user_id=1,
            round_id=10,
            pair_id=100,
            mentor_id=1,
            mentee_id=2,
            meeting_log={
                "google_meetings": [
                    {
                        "meeting_id": "m-good",
                        "start_datetime": "2024-07-15T22:00:00Z",
                        "end_datetime": "2024-07-15T23:00:00Z",
                        "created_datetime": "2024-07-01T00:00:00Z",
                        "is_completed": True,
                    },
                    {
                        "meeting_id": "m-bad",
                        "start_datetime": "2024-07-16T22:00:00Z",
                        "end_datetime": "bad-datetime",
                        "created_datetime": "2024-07-02T00:00:00Z",
                        "is_completed": True,
                    },
                ]
            },
        )
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                )
            },
            {1: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                "detailed",
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(len(lines), 1)  # header only — neither meeting written
        self.mock_logger.exception.assert_called_once()

    async def test_detailed_mode_keeps_row_with_no_meetings_blank(self):
        """A row with pair_id but empty meeting_log still gets one CSV row,
        with the meeting columns left blank — it isn't dropped just because
        it has no meetings yet."""
        row = _make_row(user_id=1, pair_id=5, meeting_log={})
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                )
            },
            {1: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                "detailed",
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(len(lines), 2)  # header + one blank-meeting row
        self.assertEqual(lines[1].split(",")[-4:], ["", "", "", ""])

    async def test_non_participant_export_ignores_mode_value(self):
        """A non-participant export accepts any mode value but ignores it
        entirely: header/columns still use the common + non-participant
        set, and meeting logs are never queried, even when mode="detailed"."""
        row = _make_row(user_id=1, participant_role=None, pair_id=None)
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                )
            },
            {1: []},
        )
        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = [
            MagicMock(
                user_id=1,
                category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
                status=TrainingStatus.DONE,
            )
        ]

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="non_participant"),
                "detailed",
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(
            lines[0].split(","),
            [
                "User ID",
                "First Name",
                "Last Name",
                "Preferred Name",
                "Primary Email",
                "Alternative Emails",
                "Mentor Onboarding Status",
                "Mentee Onboarding Status",
            ],
        )
        self.assertEqual(lines[1], "1,Alice,Doe,,,,done,")

        # need_meeting_log must stay False for a non-participant export even
        # when mode="detailed", since non-participants have no meetings.
        first_call = self.mock_participants_repo.iter_search_participants_for_admin.call_args_list[
            0
        ]
        self.assertFalse(first_call.kwargs["need_meeting_log"])

    async def test_non_participant_export_with_no_mode_succeeds(self):
        """mode is optional for a non-participant export because it has no
        meeting data."""
        row = _make_row(user_id=1, participant_role=None, pair_id=None)
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                )
            },
            {1: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="non_participant")
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(len(lines), 2)  # header + the one row

    async def test_non_participant_mode_skips_row_on_build_failure_and_logs(self):
        """A non-participant row whose common-column build fails is logged
        and skipped, same protection as the participant path."""
        bad_row = _make_row(user_id=1, round_id=None, pair_id=None)
        good_row = _make_row(user_id=2, round_id=None, pair_id=None)
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [bad_row, good_row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                2: MagicMock(
                    user_id=2, first_name="Bob", last_name="Lee", preferred_name=None
                )
            },
            {2: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="non_participant"),
                "summary",
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(len(lines), 2)  # header + only the good row
        self.assertTrue(lines[1].startswith("2,Bob,Lee"))
        self.mock_logger.exception.assert_called_once()

    async def test_stops_paginating_on_empty_page(self):
        """The batch loop stops as soon as a page comes back empty."""
        row = _make_row(user_id=1)
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                )
            },
            {1: []},
        )

        await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                "summary",
            )
        )

        self.assertEqual(
            self.mock_participants_repo.iter_search_participants_for_admin.await_count,
            2,
        )

    async def test_multiple_batches_paginate_with_incrementing_offset_and_bom_once(
        self,
    ):
        """Two non-empty pages: offset increments by the batch size on each
        call, every row from both pages is emitted, and the BOM appears only
        in the first chunk, not re-prepended to later batches."""
        row1 = _make_row(user_id=1)
        row2 = _make_row(user_id=2)
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row1],
            [row2],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                ),
                2: MagicMock(
                    user_id=2, first_name="Bob", last_name="Lee", preferred_name=None
                ),
            },
            {1: [], 2: []},
        )

        chunks = [
            chunk
            async for chunk in self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                "summary",
            )
        ]

        self.assertTrue(chunks[0].startswith(b"\xef\xbb\xbf"))
        for later_chunk in chunks[1:]:
            self.assertFalse(later_chunk.startswith(b"\xef\xbb\xbf"))

        call_offsets = [
            call.kwargs["offset"]
            for call in self.mock_participants_repo.iter_search_participants_for_admin.call_args_list
        ]
        self.assertEqual(call_offsets, [0, 500, 1000])

        csv_text = b"".join(chunks).decode("utf-8-sig")
        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(len(lines), 3)  # header + one row per batch
        self.assertTrue(lines[1].startswith("1,Alice,Doe"))
        self.assertTrue(lines[2].startswith("2,Bob,Lee"))


if __name__ == "__main__":
    unittest.main()
