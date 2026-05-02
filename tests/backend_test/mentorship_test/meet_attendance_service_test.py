import unittest
from unittest.mock import MagicMock, AsyncMock

from backend.mentorship.meet_attendance_service import MeetAttendanceService


def _make_gm(
    conference_id="abc-xxxx-xyz",
    start_datetime="2026-04-07T10:00:00+00:00",
    end_datetime="2026-04-07T11:00:00+00:00",
    is_completed=False,
    created_datetime="2026-04-01T10:00:00+00:00",
):
    return {
        "meeting_id": "meeting-1",
        "meet_link": "https://meet.google.com/abc-xxxx-xyz",
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "created_datetime": created_datetime,
        "is_completed": is_completed,
        "entry_points": [],
        "conference_id": conference_id,
    }


def _make_pair(pair_id, mentor_id, mentee_id, google_meetings):
    pair = MagicMock()
    pair.pair_id = pair_id
    pair.mentor_id = mentor_id
    pair.mentee_id = mentee_id
    pair.completed_count = 0
    pair.meeting_log = {"google_meetings": google_meetings}
    return pair


def _make_user(user_id, primary_email, alternative_emails=None):
    user = MagicMock()
    user.user_id = user_id
    user.primary_email = primary_email
    user.alternative_emails = alternative_emails or []
    return user


def _make_service(**overrides):
    defaults = dict(
        logger=MagicMock(),
        google_service=MagicMock(),
        mentorship_pairs_repository=MagicMock(),
        mentorship_round_repository=MagicMock(),
        users_repository=MagicMock(),
    )
    return MeetAttendanceService(**{**defaults, **overrides})


class TestSyncAttendance(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_google_service = MagicMock()
        self.mock_google_service.list_ended_conferences = AsyncMock()
        self.mock_google_service.get_meeting_code_for_space = AsyncMock()
        self.mock_google_service.fetch_participants_for_record = AsyncMock()
        self.mock_google_service.get_email_by_google_user_id = MagicMock()

        self.mock_pairs_repo = MagicMock()
        self.mock_pairs_repo.get_active_pairs_by_round = AsyncMock()
        self.mock_pairs_repo.upsert_pairs_batch = AsyncMock()

        self.mock_round_repo = MagicMock()
        self.mock_round_repo.get_running_round_id = AsyncMock()

        self.mock_users_repo = MagicMock()
        self.mock_users_repo.get_all_by_ids = AsyncMock()

        self.mock_session = AsyncMock()

        self.service = _make_service(
            google_service=self.mock_google_service,
            mentorship_pairs_repository=self.mock_pairs_repo,
            mentorship_round_repository=self.mock_round_repo,
            users_repository=self.mock_users_repo,
        )

        self.round_id = 1
        self.mentor = _make_user(user_id=10, primary_email="mentor@example.com")
        self.mentee = _make_user(user_id=20, primary_email="mentee@example.com")

    def _make_conference(
        self,
        space="spaces/ABC",
        name="conferenceRecords/REC1",
        start="2026-04-07T10:10:00+00:00",
        end="2026-04-07T11:00:00+00:00",
    ):
        return {"space": space, "name": name, "start_time": start, "end_time": end}

    def _make_active_pair(
        self,
        conf_id="abc-xxxx-xyz",
        start="2026-04-07T10:00:00+00:00",
        end="2026-04-07T11:00:00+00:00",
    ):
        return _make_pair(
            pair_id=101,
            mentor_id=self.mentor.user_id,
            mentee_id=self.mentee.user_id,
            google_meetings=[
                _make_gm(conference_id=conf_id, start_datetime=start, end_datetime=end)
            ],
        )

    async def test_no_active_round_returns_empty(self):
        self.mock_round_repo.get_running_round_id.return_value = None
        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )
        self.assertEqual(result, {})
        self.mock_google_service.list_ended_conferences.assert_not_called()

    async def test_no_conferences_returns_empty(self):
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = []
        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )
        self.assertEqual(result, {})
        self.mock_google_service.list_ended_conferences.assert_called_once()
        self.mock_pairs_repo.get_active_pairs_by_round.assert_not_called()

    async def test_no_pairs_returns_zero_summary(self):
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference()
        ]
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = []
        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )
        self.assertEqual(result["pairs_updated"], 0)
        self.mock_pairs_repo.upsert_pairs_batch.assert_not_called()

    async def test_unknown_meeting_code_is_skipped(self):
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(space="spaces/UNKNOWN")
        ]
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [
            self._make_active_pair(conf_id="abc-xxxx-xyz")
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = "zzz-zzz-zzz"

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )
        self.assertEqual(result["meetings_skipped"], 1)
        self.assertEqual(result["pairs_updated"], 0)

    async def test_two_signed_in_meeting_completed(self):
        """Both mentor and mentee signed in, meeting duration >= 80% → is_completed=True."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:05:00+00:00",
                end="2026-04-07T11:00:00+00:00",  # 55 min of 60 min
            )
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "signedin_user_id": "uid-mentor",
                "start_time": "2026-04-07T10:05:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
            {
                "signedin_user_id": "uid-mentee",
                "start_time": "2026-04-07T10:06:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
        ]
        self.mock_google_service.get_email_by_google_user_id.side_effect = lambda uid: (
            "mentor@example.com" if uid == "uid-mentor" else "mentee@example.com"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["meetings_completed"], 1)
        self.assertEqual(result["meetings_absent"], 0)
        gm = pair.meeting_log["google_meetings"][0]
        self.assertTrue(gm["is_completed"])
        self.assertIsNone(gm["absent_user_id"])
        self.assertIsNone(gm["has_unknown_absent"])

    async def test_two_signed_in_meeting_not_completed(self):
        """Both attended but duration < 80% → is_completed=False, no absence flag."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T10:05:00+00:00",  # 5 min of 60 min
            )
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "signedin_user_id": "uid-mentor",
                "start_time": "2026-04-07T10:00:00+00:00",
                "end_time": "2026-04-07T10:05:00+00:00",
            },
            {
                "signedin_user_id": "uid-mentee",
                "start_time": "2026-04-07T10:01:00+00:00",
                "end_time": "2026-04-07T10:05:00+00:00",
            },
        ]
        self.mock_google_service.get_email_by_google_user_id.side_effect = lambda uid: (
            "mentor@example.com" if uid == "uid-mentor" else "mentee@example.com"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["meetings_completed"], 0)
        gm = pair.meeting_log["google_meetings"][0]
        self.assertFalse(gm["is_completed"])
        self.assertIsNone(gm["has_unknown_absent"])
        self.assertTrue(gm["has_insufficient_duration"])

    async def test_one_signed_in_one_anonymous_completed_no_unknown_absent(self):
        """1 signed-in + 1 anon, meeting complete → anon assumed to be other party, no flag."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:05:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "signedin_user_id": "uid-mentee",
                "start_time": "2026-04-07T10:05:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
            {
                "display_name": "Anonymous Mentor",
                "start_time": "2026-04-07T10:05:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
        ]
        self.mock_google_service.get_email_by_google_user_id.return_value = (
            "mentee@example.com"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["meetings_completed"], 1)
        gm = pair.meeting_log["google_meetings"][0]
        self.assertTrue(gm["is_completed"])
        self.assertIsNone(gm["has_unknown_absent"])

    async def test_one_signed_in_one_anonymous_not_completed_sets_unknown_absent_and_insufficient_duration(
        self,
    ):
        """1 signed-in + 1 anon, meeting NOT complete → can't confirm anon was other party,
        and duration flag is set."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T10:02:00+00:00",  # 2 min of 60
            )
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "signedin_user_id": "uid-mentee",
                "start_time": "2026-04-07T10:00:00+00:00",
                "end_time": "2026-04-07T10:02:00+00:00",
            },
            {
                "display_name": "Anonymous Mentor",
                "start_time": "2026-04-07T10:00:00+00:00",
                "end_time": "2026-04-07T10:02:00+00:00",
            },
        ]
        self.mock_google_service.get_email_by_google_user_id.return_value = (
            "mentee@example.com"
        )

        await self.service.sync_attendance(session=self.mock_session, lookback_hours=2)

        gm = pair.meeting_log["google_meetings"][0]
        self.assertFalse(gm["is_completed"])
        self.assertIsNone(
            gm["has_unknown_absent"]
        )  # 1 known + 1 anon → anon inferred as other party
        self.assertTrue(gm["has_insufficient_duration"])

    async def test_fewer_than_two_participants_marks_absent(self):
        """Only 1 participant → absent path, mentor flagged absent."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:05:00+00:00",
                end="2026-04-07T10:10:00+00:00",
            )
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "signedin_user_id": "uid-mentee",
                "start_time": "2026-04-07T10:05:00+00:00",
                "end_time": "2026-04-07T10:10:00+00:00",
            },
        ]
        self.mock_google_service.get_email_by_google_user_id.return_value = (
            "mentee@example.com"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["meetings_absent"], 1)
        gm = pair.meeting_log["google_meetings"][0]
        self.assertFalse(gm["is_completed"])
        self.assertEqual(gm["absent_user_id"], self.mentor.user_id)

    async def test_stale_gm_fields_are_reset_on_each_run(self):
        """Fields from a prior run (e.g. absent_user_id) must not persist when no longer applicable."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:05:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        stale_gm = _make_gm(conference_id="abc-xxxx-xyz")
        stale_gm["absent_user_id"] = 999
        stale_gm["has_unknown_absent"] = True
        pair = _make_pair(
            pair_id=101,
            mentor_id=self.mentor.user_id,
            mentee_id=self.mentee.user_id,
            google_meetings=[stale_gm],
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "signedin_user_id": "uid-mentor",
                "start_time": "2026-04-07T10:05:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
            {
                "signedin_user_id": "uid-mentee",
                "start_time": "2026-04-07T10:06:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
        ]
        self.mock_google_service.get_email_by_google_user_id.side_effect = lambda uid: (
            "mentor@example.com" if uid == "uid-mentor" else "mentee@example.com"
        )

        await self.service.sync_attendance(session=self.mock_session, lookback_hours=2)

        gm = pair.meeting_log["google_meetings"][0]
        self.assertIsNone(gm["absent_user_id"])
        self.assertIsNone(gm["has_unknown_absent"])

    async def test_completed_meeting_is_not_reprocessed(self):
        """A gm already marked is_completed=True is excluded from the lookup; fields stay unchanged."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference()
        ]
        completed_gm = _make_gm(conference_id="abc-xxxx-xyz", is_completed=True)
        completed_gm["absent_user_id"] = None
        pair = _make_pair(
            pair_id=101,
            mentor_id=self.mentor.user_id,
            mentee_id=self.mentee.user_id,
            google_meetings=[completed_gm],
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.mock_pairs_repo.upsert_pairs_batch.assert_not_called()
        self.assertEqual(result["pairs_updated"], 0)
        # gm fields must be untouched
        self.assertTrue(pair.meeting_log["google_meetings"][0]["is_completed"])

    async def test_mentee_arrives_late_sets_late_user_id(self):
        """Mentee joins >5 min after mentor → late_user_id = mentee."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "signedin_user_id": "uid-mentor",
                "start_time": "2026-04-07T10:00:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
            {
                "signedin_user_id": "uid-mentee",
                "start_time": "2026-04-07T10:08:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },  # 8 min late
        ]
        self.mock_google_service.get_email_by_google_user_id.side_effect = lambda uid: (
            "mentor@example.com" if uid == "uid-mentor" else "mentee@example.com"
        )

        await self.service.sync_attendance(session=self.mock_session, lookback_hours=2)

        gm = pair.meeting_log["google_meetings"][0]
        self.assertEqual(gm["late_user_id"], [self.mentee.user_id])
        self.assertFalse(gm["has_unknown_late"])

    async def test_both_arrive_late_sets_both_late_user_ids(self):
        """Both mentor and mentee join >5 min after scheduled start → late_user_id contains both."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "signedin_user_id": "uid-mentor",
                "start_time": "2026-04-07T10:10:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },  # 10 min late
            {
                "signedin_user_id": "uid-mentee",
                "start_time": "2026-04-07T10:08:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },  # 8 min late
        ]
        self.mock_google_service.get_email_by_google_user_id.side_effect = lambda uid: (
            "mentor@example.com" if uid == "uid-mentor" else "mentee@example.com"
        )

        await self.service.sync_attendance(session=self.mock_session, lookback_hours=2)

        gm = pair.meeting_log["google_meetings"][0]
        self.assertIsNotNone(gm["late_user_id"])
        self.assertCountEqual(
            gm["late_user_id"], [self.mentor.user_id, self.mentee.user_id]
        )
        self.assertFalse(gm["has_unknown_late"])

    async def test_multiple_conference_records_accumulates_reconnect_sessions(self):
        """Two conference records for the same space (disconnect + rejoin) are merged.
        Each session alone is < 80%; combined they exceed the threshold → is_completed=True."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        # Two separate call records for the same Meet room
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                space="spaces/ABC",
                name="conferenceRecords/REC1",
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T10:25:00+00:00",  # 25 min
            ),
            self._make_conference(
                space="spaces/ABC",
                name="conferenceRecords/REC2",
                start="2026-04-07T10:30:00+00:00",
                end="2026-04-07T10:55:00+00:00",  # 25 min
            ),
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",  # 60 min scheduled
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.side_effect = [
            [  # REC1: both join at 10:00, end at conf end 10:25
                {
                    "signedin_user_id": "uid-mentor",
                    "start_time": "2026-04-07T10:00:00+00:00",
                    "end_time": "2026-04-07T10:25:00+00:00",
                },
                {
                    "signedin_user_id": "uid-mentee",
                    "start_time": "2026-04-07T10:00:00+00:00",
                    "end_time": "2026-04-07T10:25:00+00:00",
                },
            ],
            [  # REC2: both rejoin at 10:30, end at conf end 10:55
                {
                    "signedin_user_id": "uid-mentor",
                    "start_time": "2026-04-07T10:30:00+00:00",
                    "end_time": "2026-04-07T10:55:00+00:00",
                },
                {
                    "signedin_user_id": "uid-mentee",
                    "start_time": "2026-04-07T10:30:00+00:00",
                    "end_time": "2026-04-07T10:55:00+00:00",
                },
            ],
        ]
        self.mock_google_service.get_email_by_google_user_id.side_effect = lambda uid: (
            "mentor@example.com" if uid == "uid-mentor" else "mentee@example.com"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        # 25 + 25 = 50 min = 83% of 60 min → complete
        self.assertEqual(result["meetings_completed"], 1)
        gm = pair.meeting_log["google_meetings"][0]
        self.assertTrue(gm["is_completed"])
        self.assertCountEqual(gm["late_user_id"], [])
        self.assertFalse(gm["has_unknown_late"])

    async def test_only_anonymous_participant_sets_unknown_absent(self):
        """Single anonymous attendee with no sign-in → neither party identified → has_unknown_absent=True."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {"display_name": "anonymous", "end_time": "2026-04-07T11:00:00+00:00"},
        ]

        await self.service.sync_attendance(session=self.mock_session, lookback_hours=2)

        gm = pair.meeting_log["google_meetings"][0]
        self.assertFalse(gm["is_completed"])
        self.assertTrue(gm["has_unknown_absent"])

    async def test_both_anonymous_sets_unknown_absent_and_unknown_late(self):
        """Two anonymous attendees arrive late → neither identified → has_unknown_absent=True, has_unknown_late=True."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        # Conference runs 10:10–10:40 (30 min); both guests join at 10:10 (> legal_wait_end 10:05)
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:10:00+00:00",
                end="2026-04-07T10:40:00+00:00",  # 30 min of 60
            )
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        # Distinct display names so they are tracked as two separate anon trees
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "display_name": "Guest A",
                "start_time": "2026-04-07T10:10:00+00:00",
                "end_time": "2026-04-07T10:40:00+00:00",
            },
            {
                "display_name": "Guest B",
                "start_time": "2026-04-07T10:10:00+00:00",
                "end_time": "2026-04-07T10:40:00+00:00",
            },
        ]

        await self.service.sync_attendance(session=self.mock_session, lookback_hours=2)

        gm = pair.meeting_log["google_meetings"][0]
        self.assertFalse(gm["is_completed"])
        self.assertFalse(gm["has_unknown_absent"])
        self.assertTrue(gm["has_unknown_late"])

    async def test_alternative_email_matching(self):
        """Mentor signs into Meet with an alternative email → still matched to the correct user."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:05:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        mentor_with_alt = _make_user(
            user_id=self.mentor.user_id,
            primary_email="mentor@example.com",
            alternative_emails=["mentor-alt@example.com"],
        )
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [
            mentor_with_alt,
            self.mentee,
        ]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "signedin_user_id": "uid-mentor",
                "start_time": "2026-04-07T10:05:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
            {
                "signedin_user_id": "uid-mentee",
                "start_time": "2026-04-07T10:05:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
        ]
        # Mentor is identified by alternative email, not primary
        self.mock_google_service.get_email_by_google_user_id.side_effect = lambda uid: (
            "mentor-alt@example.com" if uid == "uid-mentor" else "mentee@example.com"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["meetings_completed"], 1)
        gm = pair.meeting_log["google_meetings"][0]
        self.assertTrue(gm["is_completed"])
        self.assertIsNone(gm["absent_user_id"])

    async def test_identity_overlap_same_user_two_devices(self):
        """Same signedin_user_id from two devices → both intervals merged into one tree → other party absent."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        # Same uid twice: phone + laptop, both identified as mentor
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "signedin_user_id": "uid-mentor",
                "start_time": "2026-04-07T10:00:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
            {
                "signedin_user_id": "uid-mentor",
                "start_time": "2026-04-07T10:02:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
        ]
        self.mock_google_service.get_email_by_google_user_id.return_value = (
            "mentor@example.com"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["meetings_absent"], 1)
        gm = pair.meeting_log["google_meetings"][0]
        self.assertFalse(gm["is_completed"])
        self.assertEqual(gm["absent_user_id"], self.mentee.user_id)

    async def test_conference_from_previous_round_is_skipped(self):
        """Conference's meeting code belongs to a past round's pair → not in active pair_lookup → skipped."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(space="spaces/PASTROUND")
        ]
        # Active round has a pair with a different conference_id
        active_pair = self._make_active_pair(conf_id="current-meet-code")
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [active_pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        # Conference resolves to an old meeting code not present in current round
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "old-round-meet-code"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["meetings_skipped"], 1)
        self.assertEqual(result["pairs_updated"], 0)
        self.mock_pairs_repo.upsert_pairs_batch.assert_not_called()

    async def test_zero_second_session_filtered_as_noise(self):
        """Participant whose start_time == end_time is filtered by MIN_VALID_SESSION_STRICT."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:05:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.return_value = [
            # Mentor: 0-second session → filtered
            {
                "signedin_user_id": "uid-mentor",
                "start_time": "2026-04-07T10:05:00+00:00",
                "end_time": "2026-04-07T10:05:00+00:00",
            },
            # Mentee: valid session
            {
                "signedin_user_id": "uid-mentee",
                "start_time": "2026-04-07T10:05:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
        ]
        self.mock_google_service.get_email_by_google_user_id.side_effect = lambda uid: (
            "mentor@example.com" if uid == "uid-mentor" else "mentee@example.com"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["meetings_absent"], 1)
        gm = pair.meeting_log["google_meetings"][0]
        self.assertFalse(gm["is_completed"])
        self.assertEqual(gm["absent_user_id"], self.mentor.user_id)

    async def test_ten_hour_meeting_completes_successfully(self):
        """Actual meeting runs 10 h against 1 h scheduled → is_completed=True, no crash."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T20:00:00+00:00",
            )
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        # Both present through the full 10-hour conference
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "signedin_user_id": "uid-mentor",
                "start_time": "2026-04-07T10:00:00+00:00",
                "end_time": "2026-04-07T20:00:00+00:00",
            },
            {
                "signedin_user_id": "uid-mentee",
                "start_time": "2026-04-07T10:00:00+00:00",
                "end_time": "2026-04-07T20:00:00+00:00",
            },
        ]
        self.mock_google_service.get_email_by_google_user_id.side_effect = lambda uid: (
            "mentor@example.com" if uid == "uid-mentor" else "mentee@example.com"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        # 10 h interaction >> 80% of 1 h scheduled
        self.assertEqual(result["meetings_completed"], 1)
        gm = pair.meeting_log["google_meetings"][0]
        self.assertTrue(gm["is_completed"])

    async def test_api_exception_increments_skipped_and_continues(self):
        """fetch_participants_for_record raising an exception skips the meeting without crashing."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference()
        ]
        pair = self._make_active_pair()
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.side_effect = Exception(
            "Google API unavailable"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["meetings_skipped"], 1)
        self.assertEqual(result["pairs_updated"], 0)
        self.mock_pairs_repo.upsert_pairs_batch.assert_not_called()

    async def test_batch_100_pairs_upserted_in_single_call(self):
        """100 changed pairs are all passed to upsert_pairs_batch in one call."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id

        num_pairs = 100
        conf_ids = [f"conf-{i:03d}" for i in range(num_pairs)]
        spaces = [f"spaces/S{i:03d}" for i in range(num_pairs)]
        conf_names = [f"conferenceRecords/R{i:03d}" for i in range(num_pairs)]

        self.mock_google_service.list_ended_conferences.return_value = [
            {
                "space": spaces[i],
                "name": conf_names[i],
                "start_time": "2026-04-07T10:05:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            }
            for i in range(num_pairs)
        ]
        pairs = [
            _make_pair(
                pair_id=i + 1,
                mentor_id=self.mentor.user_id,
                mentee_id=self.mentee.user_id,
                google_meetings=[_make_gm(conference_id=conf_ids[i])],
            )
            for i in range(num_pairs)
        ]
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = pairs
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]

        space_to_conf_id = {spaces[i]: conf_ids[i] for i in range(num_pairs)}

        async def _get_meeting_code(space):
            return space_to_conf_id[space]

        self.mock_google_service.get_meeting_code_for_space.side_effect = (
            _get_meeting_code
        )
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "signedin_user_id": "uid-mentor",
                "start_time": "2026-04-07T10:05:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
            {
                "signedin_user_id": "uid-mentee",
                "start_time": "2026-04-07T10:05:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
        ]
        self.mock_google_service.get_email_by_google_user_id.side_effect = lambda uid: (
            "mentor@example.com" if uid == "uid-mentor" else "mentee@example.com"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["meetings_completed"], 100)
        self.assertEqual(result["pairs_updated"], 100)
        self.mock_pairs_repo.upsert_pairs_batch.assert_called_once()
        upserted = self.mock_pairs_repo.upsert_pairs_batch.call_args[0][1]
        self.assertEqual(len(upserted), 100)

    async def test_non_utc_timestamps_correctly_detected_as_late(self):
        """Participant timestamp in UTC+8 is correctly compared against UTC scheduled_start."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair = self._make_active_pair(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        # Mentee joins at 18:08 UTC+8 = 10:08 UTC, which is 8 minutes past legal_wait_end (10:05)
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {
                "signedin_user_id": "uid-mentor",
                "start_time": "2026-04-07T10:00:00+00:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
            {
                "signedin_user_id": "uid-mentee",
                "start_time": "2026-04-07T18:08:00+08:00",
                "end_time": "2026-04-07T11:00:00+00:00",
            },
        ]
        self.mock_google_service.get_email_by_google_user_id.side_effect = lambda uid: (
            "mentor@example.com" if uid == "uid-mentor" else "mentee@example.com"
        )

        await self.service.sync_attendance(session=self.mock_session, lookback_hours=2)

        gm = pair.meeting_log["google_meetings"][0]
        # 52 min overlap = 87% of 60 min → completed
        self.assertTrue(gm["is_completed"])
        # 10:08 UTC > legal_wait_end 10:05 UTC → mentee late
        self.assertIn(self.mentee.user_id, gm["late_user_id"])
        self.assertFalse(gm["has_unknown_late"])


if __name__ == "__main__":
    unittest.main()
