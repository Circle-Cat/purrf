import copy
import unittest
from unittest.mock import MagicMock, AsyncMock

from dateutil.parser import isoparse

from backend.common.mentorship_enums import MeetingSource
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.mentorship.meet_attendance_service import MeetAttendanceService


def _make_meeting(
    meeting_id="meeting-1",
    pair_id=101,
    google_meeting_code="abc-xxxx-xyz",
    start_datetime="2026-04-07T10:00:00+00:00",
    end_datetime="2026-04-07T11:00:00+00:00",
    is_completed=False,
    created_datetime="2026-04-01T10:00:00+00:00",
    absent_user_id=None,
    late_user_ids=None,
    has_unknown_absent=None,
    has_unknown_late=None,
    has_insufficient_duration=None,
):
    """A real MentorshipMeetingEntity (unpersisted) rather than a JSONB dict --
    this is what the attendance sweep now reads and writes directly."""
    return MentorshipMeetingEntity(
        meeting_id=meeting_id,
        pair_id=pair_id,
        source=MeetingSource.GOOGLE,
        start_datetime=isoparse(start_datetime),
        end_datetime=isoparse(end_datetime),
        is_completed=is_completed,
        created_datetime=isoparse(created_datetime),
        meet_link="https://meet.google.com/abc-xxxx-xyz",
        google_meeting_code=google_meeting_code,
        entry_points=[],
        absent_user_id=absent_user_id,
        late_user_ids=late_user_ids,
        has_unknown_absent=has_unknown_absent,
        has_unknown_late=has_unknown_late,
        has_insufficient_duration=has_insufficient_duration,
        last_sync_at=None,
    )


def _make_pair(pair_id=101, mentor_id=10, mentee_id=20, completed_count=0, meeting_log=None):
    pair = MagicMock()
    pair.pair_id = pair_id
    pair.mentor_id = mentor_id
    pair.mentee_id = mentee_id
    pair.completed_count = completed_count
    # A stand-in for the legacy JSONB blob. The sweep must never read or
    # write this -- present so the "left untouched" pin test has something
    # concrete (including a nested structure) to compare against.
    pair.meeting_log = (
        meeting_log
        if meeting_log is not None
        else {
            "meeting_time_list": [],
            "google_meetings": [{"conference_id": "legacy-blob-not-touched"}],
        }
    )
    return pair


def _make_user(user_id, primary_email):
    user = MagicMock()
    user.user_id = user_id
    user.primary_email = primary_email
    return user


def _make_service(**overrides):
    defaults = dict(
        logger=MagicMock(),
        google_service=MagicMock(),
        mentorship_pairs_repository=MagicMock(),
        mentorship_round_repository=MagicMock(),
        users_repository=MagicMock(),
        user_identities_repository=MagicMock(),
        user_emails_repository=MagicMock(),
        mentorship_meeting_repository=MagicMock(),
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

        self.mock_meeting_repo = MagicMock()
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs = AsyncMock(
            return_value=[]
        )
        self.mock_meeting_repo.recalculate_completed_count = AsyncMock(return_value=0)

        self.mock_round_repo = MagicMock()
        self.mock_round_repo.get_running_round_id = AsyncMock()

        self.mock_users_repo = MagicMock()
        self.mock_users_repo.get_all_by_ids = AsyncMock()

        self.mock_identities_repo = MagicMock()
        self.mock_identities_repo.get_google_subs_by_user_ids = AsyncMock(
            return_value={}
        )

        self.mock_user_emails_repo = MagicMock()
        # All known addresses per user come from user_emails, not the legacy
        # users.primary_email column.
        self.mock_user_emails_repo.get_emails_by_user_ids = AsyncMock(
            return_value={
                10: ["mentor@example.com"],
                20: ["mentee@example.com"],
            }
        )
        self.mock_user_emails_repo.get_contact_emails_by_user_ids = AsyncMock(
            return_value={
                10: "mentor@example.com",
                20: "mentee@example.com",
            }
        )

        self.mock_session = AsyncMock()

        self.service = _make_service(
            google_service=self.mock_google_service,
            mentorship_pairs_repository=self.mock_pairs_repo,
            mentorship_round_repository=self.mock_round_repo,
            users_repository=self.mock_users_repo,
            user_identities_repository=self.mock_identities_repo,
            user_emails_repository=self.mock_user_emails_repo,
            mentorship_meeting_repository=self.mock_meeting_repo,
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

    def _make_active_pair_and_meeting(
        self,
        conf_id="abc-xxxx-xyz",
        start="2026-04-07T10:00:00+00:00",
        end="2026-04-07T11:00:00+00:00",
        pair_id=101,
        mentor_id=None,
        mentee_id=None,
    ):
        pair = _make_pair(
            pair_id=pair_id,
            mentor_id=mentor_id if mentor_id is not None else self.mentor.user_id,
            mentee_id=mentee_id if mentee_id is not None else self.mentee.user_id,
        )
        meeting = _make_meeting(
            pair_id=pair_id,
            google_meeting_code=conf_id,
            start_datetime=start,
            end_datetime=end,
        )
        return pair, meeting

    async def test_resolve_identities_local_cache_from_google_identity(self):
        """A signed-in UID matching a mentor's google-oauth2 sub suffix resolves
        from the user_identities local cache without a Google API call."""
        self.mock_identities_repo.get_google_subs_by_user_ids.return_value = {
            self.mentor.user_id: ["google-oauth2|uid-mentor"],
        }
        raw_by_conf = {
            "conferenceRecords/REC1": [{"signedin_user_id": "uid-mentor"}],
        }

        result = await self.service._resolve_identities(
            self.mock_session, raw_by_conf, [self.mentor, self.mentee]
        )

        self.assertEqual(result, {"uid-mentor": "mentor@example.com"})
        self.mock_google_service.get_email_by_google_user_id.assert_not_called()
        self.mock_identities_repo.get_google_subs_by_user_ids.assert_awaited_once_with(
            self.mock_session, [self.mentor.user_id, self.mentee.user_id]
        )

    async def test_resolve_identities_resolves_all_google_uids_of_one_user(self):
        """A user with two linked Google accounts resolves both signed-in UIDs
        locally, without any Google API call."""
        self.mock_identities_repo.get_google_subs_by_user_ids.return_value = {
            self.mentor.user_id: [
                "google-oauth2|uid-mentor-a",
                "google-oauth2|uid-mentor-b",
            ],
        }
        raw_by_conf = {
            "conferenceRecords/REC1": [
                {"signedin_user_id": "uid-mentor-a"},
                {"signedin_user_id": "uid-mentor-b"},
            ],
        }

        result = await self.service._resolve_identities(
            self.mock_session, raw_by_conf, [self.mentor, self.mentee]
        )

        self.assertEqual(
            result,
            {
                "uid-mentor-a": "mentor@example.com",
                "uid-mentor-b": "mentor@example.com",
            },
        )
        self.mock_google_service.get_email_by_google_user_id.assert_not_called()

    async def test_resolve_identities_falls_back_to_api_when_no_local_match(self):
        """A UID with no local google identity match is resolved via the Google API."""
        self.mock_identities_repo.get_google_subs_by_user_ids.return_value = {}
        self.mock_google_service.get_email_by_google_user_id.return_value = (
            "looked-up@example.com"
        )
        raw_by_conf = {
            "conferenceRecords/REC1": [{"signedin_user_id": "uid-stranger"}],
        }

        result = await self.service._resolve_identities(
            self.mock_session, raw_by_conf, [self.mentor, self.mentee]
        )

        self.assertEqual(result, {"uid-stranger": "looked-up@example.com"})

    async def test_no_active_round_returns_empty(self):
        self.mock_round_repo.get_running_round_id.return_value = None
        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )
        self.assertEqual(result, {})
        self.mock_google_service.list_ended_conferences.assert_not_called()

    async def test_logs_one_info_line_when_not_in_a_meeting_window(self):
        """An idle run must be visible at INFO, not only at DEBUG."""
        self.mock_round_repo.get_running_round_id.return_value = None

        await self.service.sync_attendance(session=self.mock_session, lookback_hours=2)

        self.assertEqual(self.service.logger.info.call_count, 1)

    async def test_no_conferences_returns_empty(self):
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = []
        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )
        self.assertEqual(result, {})
        self.mock_google_service.list_ended_conferences.assert_called_once()
        self.mock_pairs_repo.get_active_pairs_by_round.assert_not_called()

    async def test_logs_one_info_line_when_no_conferences_ended(self):
        """A run that found nothing must still say so at INFO."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = []

        await self.service.sync_attendance(session=self.mock_session, lookback_hours=2)

        self.assertEqual(self.service.logger.info.call_count, 1)

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
        self.mock_meeting_repo.recalculate_completed_count.assert_not_called()

    async def test_logs_one_info_line_when_nothing_is_pending_sync(self):
        """Conferences existed but no pair had an unsynced Google meeting."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference()
        ]
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = []

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(self.service.logger.info.call_count, 1)
        self.assertEqual(result["meetings_completed"], 0)

    async def test_unknown_meeting_code_is_skipped(self):
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(space="spaces/UNKNOWN")
        ]
        pair, meeting = self._make_active_pair_and_meeting(conf_id="abc-xxxx-xyz")
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
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
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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
        self.assertTrue(meeting.is_completed)
        self.assertIsNone(meeting.absent_user_id)
        self.assertIsNone(meeting.has_unknown_absent)
        self.assertIsNotNone(meeting.last_sync_at)

    async def test_two_signed_in_meeting_not_completed(self):
        """Both attended but duration < 80% → is_completed=False, no absence flag."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T10:05:00+00:00",  # 5 min of 60 min
            )
        ]
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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
        self.assertFalse(meeting.is_completed)
        self.assertIsNone(meeting.has_unknown_absent)
        self.assertTrue(meeting.has_insufficient_duration)

    async def test_one_signed_in_one_anonymous_completed_no_unknown_absent(self):
        """1 signed-in + 1 anon, meeting complete → anon assumed to be other party, no flag."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:05:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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
        self.assertTrue(meeting.is_completed)
        self.assertIsNone(meeting.has_unknown_absent)

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
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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

        self.assertFalse(meeting.is_completed)
        self.assertIsNone(
            meeting.has_unknown_absent
        )  # 1 known + 1 anon → anon inferred as other party
        self.assertTrue(meeting.has_insufficient_duration)

    async def test_fewer_than_two_participants_marks_absent(self):
        """Only 1 participant → absent path, mentor flagged absent."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:05:00+00:00",
                end="2026-04-07T10:10:00+00:00",
            )
        ]
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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
        self.assertFalse(meeting.is_completed)
        self.assertEqual(meeting.absent_user_id, self.mentor.user_id)

    async def test_stale_meeting_fields_are_reset_on_each_run(self):
        """Fields from a prior run (e.g. absent_user_id) must not persist when no longer applicable."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:05:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair = _make_pair(pair_id=101, mentor_id=self.mentor.user_id, mentee_id=self.mentee.user_id)
        meeting = _make_meeting(
            pair_id=101,
            google_meeting_code="abc-xxxx-xyz",
            absent_user_id=999,
            has_unknown_absent=True,
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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

        self.assertIsNone(meeting.absent_user_id)
        self.assertIsNone(meeting.has_unknown_absent)

    async def test_completed_meeting_is_not_reprocessed(self):
        """A meeting row already is_completed=True must never even be returned by
        get_pending_google_meetings_by_pairs (that's the repository's contract, not
        re-checked here) -- so it never lands in pair_lookup and its fields are left
        alone."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference()
        ]
        pair = _make_pair(pair_id=101, mentor_id=self.mentor.user_id, mentee_id=self.mentee.user_id)
        completed_meeting = _make_meeting(
            google_meeting_code="abc-xxxx-xyz", is_completed=True
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        # The repository already excludes completed rows -- simulated here by
        # simply not returning this meeting at all.
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = []
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["pairs_updated"], 0)
        self.mock_meeting_repo.recalculate_completed_count.assert_not_called()
        # untouched
        self.assertTrue(completed_meeting.is_completed)

    async def test_mentee_arrives_late_sets_late_user_id(self):
        """Mentee joins >5 min after mentor → late_user_ids = [mentee]."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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

        self.assertEqual(meeting.late_user_ids, [self.mentee.user_id])
        self.assertFalse(meeting.has_unknown_late)

    async def test_both_arrive_late_sets_both_late_user_ids(self):
        """Both mentor and mentee join >5 min after scheduled start → late_user_ids contains both."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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

        self.assertIsNotNone(meeting.late_user_ids)
        self.assertCountEqual(
            meeting.late_user_ids, [self.mentor.user_id, self.mentee.user_id]
        )
        self.assertFalse(meeting.has_unknown_late)

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
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",  # 60 min scheduled
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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
        self.assertTrue(meeting.is_completed)
        self.assertCountEqual(meeting.late_user_ids, [])
        self.assertFalse(meeting.has_unknown_late)

    async def test_only_anonymous_participant_sets_unknown_absent(self):
        """Single anonymous attendee with no sign-in → neither party identified → has_unknown_absent=True."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.get_meeting_code_for_space.return_value = (
            "abc-xxxx-xyz"
        )
        self.mock_google_service.fetch_participants_for_record.return_value = [
            {"display_name": "anonymous", "end_time": "2026-04-07T11:00:00+00:00"},
        ]

        await self.service.sync_attendance(session=self.mock_session, lookback_hours=2)

        self.assertFalse(meeting.is_completed)
        self.assertTrue(meeting.has_unknown_absent)

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
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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

        self.assertFalse(meeting.is_completed)
        self.assertFalse(meeting.has_unknown_absent)
        self.assertTrue(meeting.has_unknown_late)

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
        )
        # The alternative email is just another user_emails row.
        self.mock_user_emails_repo.get_emails_by_user_ids.return_value = {
            self.mentor.user_id: ["mentor@example.com", "mentor-alt@example.com"],
            self.mentee.user_id: ["mentee@example.com"],
        }
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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
        self.assertTrue(meeting.is_completed)
        self.assertIsNone(meeting.absent_user_id)

    async def test_identity_overlap_same_user_two_devices(self):
        """Same signedin_user_id from two devices → both intervals merged into one tree → other party absent."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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
        self.assertFalse(meeting.is_completed)
        self.assertEqual(meeting.absent_user_id, self.mentee.user_id)

    async def test_conference_from_previous_round_is_skipped(self):
        """Conference's meeting code belongs to a past round's pair → not in active pair_lookup → skipped."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(space="spaces/PASTROUND")
        ]
        # Active round has a pair with a different conference_id
        active_pair, active_meeting = self._make_active_pair_and_meeting(
            conf_id="current-meet-code"
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [active_pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            active_meeting
        ]
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
        self.mock_meeting_repo.recalculate_completed_count.assert_not_called()

    async def test_zero_second_session_filtered_as_noise(self):
        """Participant whose start_time == end_time is filtered by MIN_VALID_SESSION_STRICT."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:05:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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
        self.assertFalse(meeting.is_completed)
        self.assertEqual(meeting.absent_user_id, self.mentor.user_id)

    async def test_ten_hour_meeting_completes_successfully(self):
        """Actual meeting runs 10 h against 1 h scheduled → is_completed=True, no crash."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T20:00:00+00:00",
            )
        ]
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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
        self.assertTrue(meeting.is_completed)

    async def test_api_exception_increments_skipped_and_continues(self):
        """fetch_participants_for_record raising an exception skips the meeting without crashing."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference()
        ]
        pair, meeting = self._make_active_pair_and_meeting()
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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
        self.mock_meeting_repo.recalculate_completed_count.assert_not_called()

    async def test_batch_100_pairs_processed_via_single_batched_fetch(self):
        """100 pairs' pending meetings are fetched in ONE batched call (never once per
        pair -- PR A's review flagged this method's batch behavior as untested), and
        completed_count is recalculated once per touched pair."""
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
        pairs = []
        meetings = []
        for i in range(num_pairs):
            pair, meeting = self._make_active_pair_and_meeting(
                conf_id=conf_ids[i], pair_id=i + 1
            )
            pairs.append(pair)
            meetings.append(meeting)
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = pairs
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = (
            meetings
        )
        self.mock_meeting_repo.recalculate_completed_count.return_value = 1
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
        # Pinned: exactly ONE batched call across all 100 pair ids.
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.assert_awaited_once()
        called_kwargs = (
            self.mock_meeting_repo.get_pending_google_meetings_by_pairs.call_args.kwargs
        )
        self.assertCountEqual(called_kwargs["pair_ids"], [p.pair_id for p in pairs])
        # completed_count is recomputed per touched pair, never incremented in memory.
        self.assertEqual(
            self.mock_meeting_repo.recalculate_completed_count.await_count, 100
        )
        for pair in pairs:
            self.assertEqual(pair.completed_count, 1)

    async def test_non_utc_timestamps_correctly_detected_as_late(self):
        """Participant timestamp in UTC+8 is correctly compared against UTC scheduled_start."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00",
                end="2026-04-07T11:00:00+00:00",
            )
        ]
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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

        # 52 min overlap = 87% of 60 min → completed
        self.assertTrue(meeting.is_completed)
        # 10:08 UTC > legal_wait_end 10:05 UTC → mentee late
        self.assertIn(self.mentee.user_id, meeting.late_user_ids)
        self.assertFalse(meeting.has_unknown_late)

    # --- Task 3 pins ---

    async def test_completed_count_comes_from_recalculate_not_increment(self):
        """completed_count must equal whatever recalculate_completed_count returns,
        not (old_count + 1) -- a reinstated `+= 1` would fail this assertion since
        the mocked recalculation result (42) has no arithmetic relationship to the
        stale in-memory completed_count (3)."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:05:00+00:00", end="2026-04-07T11:00:00+00:00"
            )
        ]
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        pair.completed_count = 3
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
        self.mock_meeting_repo.recalculate_completed_count.return_value = 42
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

        self.mock_meeting_repo.recalculate_completed_count.assert_awaited_once_with(
            session=self.mock_session, pair_id=pair.pair_id
        )
        self.assertEqual(pair.completed_count, 42)

    async def test_pair_meeting_log_is_never_touched(self):
        """The sweep writes only mentorship_meeting rows; pair.meeting_log (the
        legacy JSONB blob, including its nested list) must be left byte-for-byte
        alone -- hence a deepcopy snapshot rather than a shallow one, which would
        let an in-place mutation of the nested list slip through undetected."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:05:00+00:00", end="2026-04-07T11:00:00+00:00"
            )
        ]
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        before_meeting_log = copy.deepcopy(pair.meeting_log)
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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

        self.assertEqual(pair.meeting_log, before_meeting_log)

    async def test_late_user_ids_persist_via_reassignment_not_in_place_append(self):
        """late_user_ids starts NULL (never synced). An implementation that does
        `meeting.late_user_ids.append(x)` crashes on NoneType (summary would show
        it skipped, and the field would stay None); one that guards with
        `(meeting.late_user_ids or []).append(x)` but never reassigns silently
        discards the write (field also stays None). Only a real
        `meeting.late_user_ids = [...]` assignment makes this pass."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_ended_conferences.return_value = [
            self._make_conference(
                start="2026-04-07T10:00:00+00:00", end="2026-04-07T11:00:00+00:00"
            )
        ]
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.assertIsNone(meeting.late_user_ids)
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_by_pairs.return_value = [
            meeting
        ]
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

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["meetings_skipped"], 0)
        self.assertEqual(meeting.late_user_ids, [self.mentee.user_id])

    def test_build_pair_lookup_keys_by_google_meeting_code(self):
        """_build_pair_lookup now indexes meeting ROWS, keyed on the
        google_meeting_code column (not a JSONB conference_id field)."""
        meeting_a = _make_meeting(
            meeting_id="m1", pair_id=1, google_meeting_code="code-a"
        )
        meeting_b = _make_meeting(
            meeting_id="m2", pair_id=2, google_meeting_code="code-b"
        )

        lookup = self.service._build_pair_lookup([meeting_a, meeting_b])

        self.assertEqual(lookup, {"code-a": meeting_a, "code-b": meeting_b})


if __name__ == "__main__":
    unittest.main()
