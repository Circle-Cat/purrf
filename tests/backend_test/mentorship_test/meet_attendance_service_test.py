import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch

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


def _make_pair(
    pair_id=101, mentor_id=10, mentee_id=20, completed_count=0, meeting_log=None
):
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
        self.mock_google_service.list_conferences_by_meeting_code = AsyncMock(
            return_value=([], 0)
        )
        self.mock_google_service.fetch_participants_for_record = AsyncMock()
        self.mock_google_service.get_email_by_google_user_id = MagicMock()

        self.mock_pairs_repo = MagicMock()
        self.mock_pairs_repo.get_active_pairs_by_round = AsyncMock()

        self.mock_meeting_repo = MagicMock()
        self.mock_meeting_repo.get_pending_google_meetings_in_window = AsyncMock(
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
        self.mock_google_service.list_conferences_by_meeting_code.assert_not_called()

    async def test_logs_one_info_line_when_not_in_a_meeting_window(self):
        """An idle run must be visible at INFO, not only at DEBUG."""
        self.mock_round_repo.get_running_round_id.return_value = None

        await self.service.sync_attendance(session=self.mock_session, lookback_hours=2)

        self.assertEqual(self.service.logger.info.call_count, 1)

    async def test_no_pending_meeting_costs_no_meet_call(self):
        """The selection set is what drives the sweep now: an active round with
        nothing pending in the window must not issue a single Meet request."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        pair, _ = self._make_active_pair_and_meeting()
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = []

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["meetings_selected"], 0)
        self.assertEqual(result["pairs_updated"], 0)
        self.mock_google_service.list_conferences_by_meeting_code.assert_not_called()

    async def test_no_pairs_returns_zero_summary(self):
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = []

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["pairs_updated"], 0)
        self.mock_meeting_repo.recalculate_completed_count.assert_not_called()
        # No pair means no selection set, and therefore no Meet call at all.
        self.mock_google_service.list_conferences_by_meeting_code.assert_not_called()

    async def test_logs_one_info_line_when_nothing_is_pending_sync(self):
        """The selection set came back empty -- no active pair had a pending
        Google meeting whose slot overlaps this run's window."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        pair, _ = self._make_active_pair_and_meeting()
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = []

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(self.service.logger.info.call_count, 1)
        self.assertEqual(result["meetings_completed"], 0)

    async def test_not_yet_due_meeting_logs_only_the_closing_info_line(self):
        """The other empty-handed run: a meeting WAS selected, Meet simply had
        no record for it yet. That path skips the early return, so its single
        INFO line has to come from the closing summary instead.

        Frozen to land inside the meeting's grace period (meetings_not_yet_due,
        which only logs at DEBUG) rather than past it -- meetings_no_show logs
        its own INFO line per meeting, which would change this test's count
        and is pinned separately by
        test_meeting_with_no_show_is_counted_and_not_written."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        pair, meeting = self._make_active_pair_and_meeting()
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [],
            0,
        )
        frozen_now = datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc)

        with patch(
            "backend.mentorship.meet_attendance_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = frozen_now
            await self.service.sync_attendance(
                session=self.mock_session, lookback_hours=2
            )

        self.assertEqual(self.service.logger.info.call_count, 1)

    async def test_selection_window_is_wider_than_lookback_on_both_sides(self):
        """The selection bounds must be derived from the affinity window, not
        from lookback alone -- a conference may start up to ATTENDANCE_WINDOW_DELTA
        after a meeting's scheduled end, and those must not be missed.

        Pinned to the exact instants against a frozen clock rather than to a
        span range: this arithmetic decides which meetings the sweep is even
        capable of seeing, so a wrong delta (one hour a side, or the delta
        applied to only one end) has to fail here."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        pair, _ = self._make_active_pair_and_meeting()
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = []
        frozen_now = datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc)

        with patch(
            "backend.mentorship.meet_attendance_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = frozen_now
            await self.service.sync_attendance(
                session=self.mock_session, lookback_hours=4
            )

        kwargs = self.mock_meeting_repo.get_pending_google_meetings_in_window.call_args.kwargs
        # now - 4h lookback - 3h affinity delta
        self.assertEqual(
            kwargs["ends_after"], datetime(2026, 4, 7, 5, 0, tzinfo=timezone.utc)
        )
        # now + 3h affinity delta (NOT clamped to now -- a conference may start
        # early, before its meeting's scheduled slot)
        self.assertEqual(
            kwargs["starts_before"], datetime(2026, 4, 7, 15, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(
            kwargs["starts_before"] - kwargs["ends_after"], timedelta(hours=10)
        )

    async def test_meet_is_queried_with_each_meeting_own_affinity_window(self):
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
            conf_id="abc-defg-hij",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [],
            0,
        )
        # Frozen so which bucket the empty conf_list falls into does not
        # silently depend on the calendar date this test happens to run on --
        # not asserted here, but the classification code still runs.
        frozen_now = datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc)

        with patch(
            "backend.mentorship.meet_attendance_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = frozen_now
            await self.service.sync_attendance(
                session=self.mock_session, lookback_hours=4
            )

        call = self.mock_google_service.list_conferences_by_meeting_code.call_args
        self.assertEqual(call.args[0], "abc-defg-hij")
        self.assertEqual(call.args[1], "2026-04-07T07:00:00+00:00")
        self.assertEqual(call.args[2], "2026-04-07T14:00:00+00:00")

    async def test_meeting_with_no_show_is_counted_and_not_written(self):
        """Grace period fully elapsed and no conference ever appeared -> the
        actionable meetings_no_show bucket, not a generic catch-all counter.
        This is the only one of the three split counters an operator can act
        on, so it must also surface at INFO (with the meeting and pair id)
        instead of DEBUG."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        pair, meeting = self._make_active_pair_and_meeting()
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [],
            0,
        )
        # Well past window_end (meeting ends 11:00, +3h grace = 14:00).
        frozen_now = datetime(2026, 4, 8, 0, 0, tzinfo=timezone.utc)

        with patch(
            "backend.mentorship.meet_attendance_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = frozen_now
            result = await self.service.sync_attendance(
                session=self.mock_session, lookback_hours=4
            )

        self.assertEqual(result["meetings_selected"], 1)
        self.assertEqual(result["meetings_no_show"], 1)
        self.assertEqual(result["meetings_reconciled"], 0)
        self.assertFalse(meeting.is_completed)
        self.mock_meeting_repo.recalculate_completed_count.assert_not_called()
        # One INFO line for the no-show itself (actionable), one for the
        # closing summary -- unlike not_yet_due/in_progress, which stay at
        # DEBUG and would leave this at just the closing line.
        self.assertEqual(self.service.logger.info.call_count, 2)
        info_messages = [
            call.args[0] for call in self.service.logger.info.call_args_list
        ]
        self.assertTrue(any("no-show" in msg for msg in info_messages), info_messages)

    async def test_summary_counts_are_additive(self):
        """selected == reconciled + not_yet_due + in_progress + no_show +
        failed, so the cron's own report can be trusted. This is the
        invariant the old meetings_skipped did not hold, and it must still
        hold now that the old single no-conference bucket is split three
        ways.

        The raising meeting is deliberately FIRST: a failure must not abandon
        the meetings queued behind it, so the second one still has to be
        queried and counted."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        pair_a, meeting_a = self._make_active_pair_and_meeting(conf_id="aaa-aaaa-aaa")
        pair_b, meeting_b = self._make_active_pair_and_meeting(
            pair_id=2, conf_id="bbb-bbbb-bbb"
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair_a, pair_b]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting_a,
            meeting_b,
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.list_conferences_by_meeting_code.side_effect = [
            RuntimeError("Meet exploded"),
            ([], 0),
        ]
        # Well past both meetings' window_end (11:00 + 3h grace = 14:00), so
        # the second meeting classifies as no_show, not not_yet_due.
        frozen_now = datetime(2026, 4, 8, 0, 0, tzinfo=timezone.utc)

        with patch(
            "backend.mentorship.meet_attendance_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = frozen_now
            result = await self.service.sync_attendance(
                session=self.mock_session, lookback_hours=4
            )

        self.assertEqual(
            result["meetings_selected"],
            result["meetings_reconciled"]
            + result["meetings_not_yet_due"]
            + result["meetings_in_progress"]
            + result["meetings_no_show"]
            + result["meetings_failed"],
        )
        self.assertEqual(result["meetings_failed"], 1)
        # The meeting queued behind the failure was still processed.
        self.assertEqual(result["meetings_no_show"], 1)
        self.assertEqual(result["meetings_not_yet_due"], 0)
        self.assertEqual(result["meetings_in_progress"], 0)
        self.assertEqual(
            self.mock_google_service.list_conferences_by_meeting_code.await_count, 2
        )

    async def test_not_yet_due_meeting_stays_out_of_no_show(self):
        """A meeting whose 3h grace period has NOT yet closed must land in
        meetings_not_yet_due, not meetings_no_show -- a conference may still
        appear on a later run, so this is pure noise, not the actionable
        signal. Fails if the `now < window_end` check were dropped or
        inverted, since it would then misfile this as a no-show."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [],
            0,
        )
        # window_end = end (11:00) + 3h grace = 14:00; one minute before it.
        frozen_now = datetime(2026, 4, 7, 13, 59, tzinfo=timezone.utc)

        with patch(
            "backend.mentorship.meet_attendance_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = frozen_now
            result = await self.service.sync_attendance(
                session=self.mock_session, lookback_hours=2
            )

        self.assertEqual(result["meetings_not_yet_due"], 1)
        self.assertEqual(result["meetings_no_show"], 0)
        self.assertEqual(result["meetings_in_progress"], 0)
        # not_yet_due stays at DEBUG -- only the closing summary logs INFO.
        self.assertEqual(self.service.logger.info.call_count, 1)

    async def test_in_progress_conference_wins_over_no_show_past_window_end(self):
        """A conference still running (no end_time, so it never reaches the
        ended-conferences list) must classify as meetings_in_progress even
        when window_end has ALREADY passed -- it must not be caught by an
        explicit `if now >= window_end: no_show` check hoisted above the
        in_progress check.

        This does NOT by itself pin in_progress ahead of not_yet_due in the
        if/elif chain: window_end has already passed here, so
        `now < window_end` is False regardless of which branch is checked
        first, and swapping the two conditions' order would not change the
        outcome. That ordering is pinned by the sibling test right below,
        which freezes `now` INSIDE the grace period so both conditions are
        true simultaneously."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        # No ended conferences, but one still-running record.
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [],
            1,
        )
        # Well past window_end (14:00).
        frozen_now = datetime(2026, 4, 8, 0, 0, tzinfo=timezone.utc)

        with patch(
            "backend.mentorship.meet_attendance_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = frozen_now
            result = await self.service.sync_attendance(
                session=self.mock_session, lookback_hours=2
            )

        self.assertEqual(result["meetings_in_progress"], 1)
        self.assertEqual(result["meetings_no_show"], 0)
        self.assertEqual(result["meetings_not_yet_due"], 0)
        # in_progress stays at DEBUG -- only the closing summary logs INFO.
        self.assertEqual(self.service.logger.info.call_count, 1)

    async def test_in_progress_wins_over_not_yet_due_during_live_conference(self):
        """The ordinary in-progress case: a live conference (in_progress_count
        > 0) while the grace period is STILL open (now < window_end) -- both
        branch conditions are true at once. This is what actually pins
        in_progress being checked before not_yet_due in the if/elif chain: if
        the two were swapped, `now < window_end` would fire first and this
        meeting would be misfiled as not_yet_due instead."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        # No ended conferences, but one still-running record.
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [],
            1,
        )
        # Inside the 10:00-11:00 slot; window_end (14:00) is still hours away.
        frozen_now = datetime(2026, 4, 7, 10, 30, tzinfo=timezone.utc)

        with patch(
            "backend.mentorship.meet_attendance_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = frozen_now
            result = await self.service.sync_attendance(
                session=self.mock_session, lookback_hours=2
            )

        self.assertEqual(result["meetings_in_progress"], 1)
        self.assertEqual(result["meetings_not_yet_due"], 0)
        self.assertEqual(result["meetings_no_show"], 0)
        # in_progress stays at DEBUG -- only the closing summary logs INFO.
        self.assertEqual(self.service.logger.info.call_count, 1)

    async def test_two_signed_in_meeting_completed(self):
        """Both mentor and mentee signed in, meeting duration >= 80% → is_completed=True."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:05:00+00:00",
                    end="2026-04-07T11:00:00+00:00",  # 55 min of 60 min
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:00:00+00:00",
                    end="2026-04-07T10:05:00+00:00",  # 5 min of 60 min
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:05:00+00:00",
                    end="2026-04-07T11:00:00+00:00",
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:00:00+00:00",
                    end="2026-04-07T10:02:00+00:00",  # 2 min of 60
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:05:00+00:00",
                    end="2026-04-07T10:10:00+00:00",
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:05:00+00:00",
                    end="2026-04-07T11:00:00+00:00",
                )
            ],
            0,
        )
        pair = _make_pair(
            pair_id=101, mentor_id=self.mentor.user_id, mentee_id=self.mentee.user_id
        )
        meeting = _make_meeting(
            pair_id=101,
            google_meeting_code="abc-xxxx-xyz",
            absent_user_id=999,
            has_unknown_absent=True,
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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

    async def test_mentee_arrives_late_sets_late_user_id(self):
        """Mentee joins >5 min after mentor → late_user_ids = [mentee]."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:00:00+00:00",
                    end="2026-04-07T11:00:00+00:00",
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:00:00+00:00",
                    end="2026-04-07T11:00:00+00:00",
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
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
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",  # 60 min scheduled
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:00:00+00:00",
                    end="2026-04-07T11:00:00+00:00",
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:10:00+00:00",
                    end="2026-04-07T10:40:00+00:00",  # 30 min of 60
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:05:00+00:00",
                    end="2026-04-07T11:00:00+00:00",
                )
            ],
            0,
        )
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
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [
            mentor_with_alt,
            self.mentee,
        ]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:00:00+00:00",
                    end="2026-04-07T11:00:00+00:00",
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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

    async def test_only_active_pairs_meeting_codes_reach_meet(self):
        """A past round's pair is not in get_active_pairs_by_round, so its ids
        never reach the selection query and its meeting code is never sent to
        Meet. Under the old direction this was a post-hoc reject of a
        conference we had already paid to list; now it is simply never asked
        for."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        active_pair, active_meeting = self._make_active_pair_and_meeting(
            conf_id="current-meet-code"
        )
        past_pair, _ = self._make_active_pair_and_meeting(
            pair_id=999, conf_id="old-round-meet-code"
        )
        # Only the current round's pair is returned; the past one is invisible.
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [active_pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            active_meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.list_conferences_by_meeting_code.return_value = ([], 0)
        # Frozen so which bucket the empty conf_list falls into does not
        # silently depend on the calendar date this test happens to run on --
        # not asserted here, but the classification code still runs.
        frozen_now = datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc)

        with patch(
            "backend.mentorship.meet_attendance_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = frozen_now
            result = await self.service.sync_attendance(
                session=self.mock_session, lookback_hours=2
            )

        selection_kwargs = self.mock_meeting_repo.get_pending_google_meetings_in_window.call_args.kwargs
        self.assertEqual(selection_kwargs["pair_ids"], [active_pair.pair_id])
        self.assertNotIn(past_pair.pair_id, selection_kwargs["pair_ids"])
        queried_codes = [
            c.args[0]
            for c in self.mock_google_service.list_conferences_by_meeting_code.call_args_list
        ]
        self.assertEqual(queried_codes, ["current-meet-code"])
        self.assertEqual(result["pairs_updated"], 0)
        self.mock_meeting_repo.recalculate_completed_count.assert_not_called()

    async def test_zero_second_session_filtered_as_noise(self):
        """Participant whose start_time == end_time is filtered by MIN_VALID_SESSION_STRICT."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:05:00+00:00",
                    end="2026-04-07T11:00:00+00:00",
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:00:00+00:00",
                    end="2026-04-07T20:00:00+00:00",
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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

    async def test_api_exception_increments_failed_and_continues(self):
        """fetch_participants_for_record raising an exception fails that one
        meeting without crashing the sweep."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [self._make_conference()],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting()
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
        self.mock_google_service.fetch_participants_for_record.side_effect = Exception(
            "Google API unavailable"
        )

        result = await self.service.sync_attendance(
            session=self.mock_session, lookback_hours=2
        )

        self.assertEqual(result["meetings_failed"], 1)
        self.assertEqual(result["pairs_updated"], 0)
        self.mock_meeting_repo.recalculate_completed_count.assert_not_called()

    async def test_batch_100_pairs_processed_via_single_batched_fetch(self):
        """100 pairs' pending meetings are still fetched in ONE batched call
        (never once per pair -- PR A's review flagged this method's batch
        behavior as untested), completed_count is recalculated once per touched
        pair, and Meet is queried exactly once per selected meeting -- the whole
        point of the reversal being that the call count now scales with OUR
        meetings and nothing else."""
        self.mock_round_repo.get_running_round_id.return_value = self.round_id

        num_pairs = 100
        conf_ids = [f"conf-{i:03d}" for i in range(num_pairs)]
        spaces = [f"spaces/S{i:03d}" for i in range(num_pairs)]
        conf_names = [f"conferenceRecords/R{i:03d}" for i in range(num_pairs)]

        pairs = []
        meetings = []
        for i in range(num_pairs):
            pair, meeting = self._make_active_pair_and_meeting(
                conf_id=conf_ids[i], pair_id=i + 1
            )
            pairs.append(pair)
            meetings.append(meeting)
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = pairs
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = (
            meetings
        )
        self.mock_meeting_repo.recalculate_completed_count.return_value = 1
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]

        # One conference record per meeting code, served back by code rather
        # than by space -- there is no space -> code hop left to mock.
        conferences_by_code = {
            conf_ids[i]: [
                {
                    "space": spaces[i],
                    "name": conf_names[i],
                    "start_time": "2026-04-07T10:05:00+00:00",
                    "end_time": "2026-04-07T11:00:00+00:00",
                }
            ]
            for i in range(num_pairs)
        }

        async def _list_conferences(meeting_code, start_time_after, start_time_before):
            return conferences_by_code[meeting_code], 0

        self.mock_google_service.list_conferences_by_meeting_code.side_effect = (
            _list_conferences
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

        self.assertEqual(result["meetings_selected"], 100)
        self.assertEqual(result["meetings_reconciled"], 100)
        self.assertEqual(result["meetings_completed"], 100)
        self.assertEqual(result["pairs_updated"], 100)
        # Pinned: exactly ONE batched call across all 100 pair ids.
        self.mock_meeting_repo.get_pending_google_meetings_in_window.assert_awaited_once()
        # ...and exactly one Meet lookup per selected meeting, no more.
        self.assertEqual(
            self.mock_google_service.list_conferences_by_meeting_code.await_count, 100
        )
        called_kwargs = self.mock_meeting_repo.get_pending_google_meetings_in_window.call_args.kwargs
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:00:00+00:00",
                    end="2026-04-07T11:00:00+00:00",
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:05:00+00:00", end="2026-04-07T11:00:00+00:00"
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        pair.completed_count = 3
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_meeting_repo.recalculate_completed_count.return_value = 42
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:05:00+00:00", end="2026-04-07T11:00:00+00:00"
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        before_meeting_log = copy.deepcopy(pair.meeting_log)
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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
        self.mock_google_service.list_conferences_by_meeting_code.return_value = (
            [
                self._make_conference(
                    start="2026-04-07T10:00:00+00:00", end="2026-04-07T11:00:00+00:00"
                )
            ],
            0,
        )
        pair, meeting = self._make_active_pair_and_meeting(
            start="2026-04-07T10:00:00+00:00",
            end="2026-04-07T11:00:00+00:00",
        )
        self.assertIsNone(meeting.late_user_ids)
        self.mock_pairs_repo.get_active_pairs_by_round.return_value = [pair]
        self.mock_meeting_repo.get_pending_google_meetings_in_window.return_value = [
            meeting
        ]
        self.mock_users_repo.get_all_by_ids.return_value = [self.mentor, self.mentee]
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

        self.assertEqual(result["meetings_failed"], 0)
        self.assertEqual(meeting.late_user_ids, [self.mentee.user_id])


if __name__ == "__main__":
    unittest.main()
