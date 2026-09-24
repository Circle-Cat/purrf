import unittest
from datetime import datetime, timedelta, timezone

from backend.common.mentorship_enums import RoundStatus
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.mentorship.round_windows import (
    FeedbackWindow,
    feedback_window,
    is_feedback_editable,
    is_feedback_open,
    is_meeting_log_open,
    meeting_log_closes_at,
    round_status,
)

MICRO = timedelta(microseconds=1)


class TestRoundStatus(unittest.TestCase):
    """round_status places a round's meeting window relative to now."""

    NOW = datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc)

    def _round(
        self,
        round_id=1,
        promotion_start_at=None,
        match_notification_at=None,
        meetings_completion_deadline_at=None,
    ) -> MentorshipRoundEntity:
        return MentorshipRoundEntity(
            round_id=round_id,
            name=f"round-{round_id}",
            required_meetings=5,
            onboarding_deadline_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
            promotion_start_at=promotion_start_at,
            match_notification_at=match_notification_at,
            meetings_completion_deadline_at=meetings_completion_deadline_at,
        )

    def test_active_inside_the_window(self):
        r = self._round(
            match_notification_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )

        self.assertEqual(round_status(r, self.NOW), RoundStatus.ACTIVE)

    def test_active_on_both_bounds(self):
        r = self._round(
            match_notification_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )

        self.assertEqual(round_status(r, r.match_notification_at), RoundStatus.ACTIVE)
        self.assertEqual(
            round_status(r, r.meetings_completion_deadline_at), RoundStatus.ACTIVE
        )

    def test_upcoming_just_before_the_start(self):
        r = self._round(
            match_notification_at=self.NOW + MICRO,
            meetings_completion_deadline_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )

        self.assertEqual(round_status(r, self.NOW), RoundStatus.UPCOMING)

    def test_completed_just_after_the_end(self):
        r = self._round(
            match_notification_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=self.NOW - MICRO,
        )

        self.assertEqual(round_status(r, self.NOW), RoundStatus.COMPLETED)

    def test_falls_back_to_promotion_start_without_a_match_notification(self):
        r = self._round(
            promotion_start_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )

        self.assertEqual(round_status(r, self.NOW), RoundStatus.ACTIVE)
        self.assertEqual(
            round_status(r, r.promotion_start_at - MICRO), RoundStatus.UPCOMING
        )

    def test_match_notification_takes_precedence_over_promotion_start(self):
        """Promotion has started but matching has not, so the window has not
        opened; reading promotion_start_at would call it active."""
        r = self._round(
            promotion_start_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            match_notification_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )

        self.assertEqual(round_status(r, self.NOW), RoundStatus.UPCOMING)

    def test_upcoming_with_only_a_future_start(self):
        r = self._round(match_notification_at=datetime(2026, 4, 1, tzinfo=timezone.utc))

        self.assertEqual(round_status(r, self.NOW), RoundStatus.UPCOMING)

    def test_completed_with_only_a_past_end(self):
        r = self._round(
            meetings_completion_deadline_at=datetime(2026, 3, 1, tzinfo=timezone.utc)
        )

        self.assertEqual(round_status(r, self.NOW), RoundStatus.COMPLETED)

    def test_none_when_the_bound_a_status_needs_is_missing(self):
        cases = {
            "no bounds": self._round(),
            "started, no end": self._round(
                match_notification_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
            ),
            "end ahead, no start": self._round(
                meetings_completion_deadline_at=datetime(
                    2026, 12, 31, tzinfo=timezone.utc
                )
            ),
        }

        for label, r in cases.items():
            with self.subTest(label):
                self.assertIsNone(round_status(r, self.NOW))


class _WindowFixture(unittest.TestCase):
    """Timeline dates that are all distinct, so reading the wrong column or
    the wrong fallback moves a bound.

    In order: REMINDER < MONTH_BEFORE < MEETINGS < MEETING_LOG_CLOSE <
    FEEDBACK_START < FEEDBACK_DEADLINE < MONTH_AFTER. The meetings deadline
    is a month end, so a month taken as any fixed number of days misplaces
    at least one of the two derived bounds.
    """

    REMINDER = datetime(2026, 4, 15, 6, 59, 59, tzinfo=timezone.utc)
    MONTH_BEFORE = datetime(2026, 4, 30, 6, 59, 59, tzinfo=timezone.utc)
    MEETINGS = datetime(2026, 5, 31, 6, 59, 59, tzinfo=timezone.utc)
    MEETING_LOG_CLOSE = datetime(2026, 6, 1, 6, 59, 59, tzinfo=timezone.utc)
    FEEDBACK_START = datetime(2026, 6, 5, 6, 59, 59, tzinfo=timezone.utc)
    FEEDBACK_DEADLINE = datetime(2026, 6, 20, 6, 59, 59, tzinfo=timezone.utc)
    MONTH_AFTER = datetime(2026, 6, 30, 6, 59, 59, tzinfo=timezone.utc)

    FAR_PAST = datetime(2020, 1, 1, tzinfo=timezone.utc)
    FAR_FUTURE = datetime(2030, 1, 1, tzinfo=timezone.utc)

    _UNSET = object()

    def _round(
        self,
        meeting_log_reminder_at=_UNSET,
        meetings_completion_deadline_at=_UNSET,
        feedback_start_at=_UNSET,
        feedback_deadline_at=_UNSET,
    ) -> MentorshipRoundEntity:
        """A round with every date set unless overridden, None included."""

        def pick(value, default):
            return default if value is self._UNSET else value

        return MentorshipRoundEntity(
            round_id=1,
            name="2026 Spring",
            required_meetings=5,
            promotion_start_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            onboarding_deadline_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
            match_notification_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
            first_meeting_deadline_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
            meeting_log_reminder_at=pick(meeting_log_reminder_at, self.REMINDER),
            meetings_completion_deadline_at=pick(
                meetings_completion_deadline_at, self.MEETINGS
            ),
            feedback_start_at=pick(feedback_start_at, self.FEEDBACK_START),
            feedback_deadline_at=pick(feedback_deadline_at, self.FEEDBACK_DEADLINE),
        )


class TestFeedbackWindow(_WindowFixture):
    def test_every_fallback_combination(self):
        """Each bound comes from its own column, else a month either side of
        the meetings deadline, else None."""
        cases = (
            # (reminder, meetings, deadline, expected opens, expected closes)
            (True, True, True, "REMINDER", "FEEDBACK_DEADLINE"),
            (True, True, False, "REMINDER", "MONTH_AFTER"),
            (False, True, True, "MONTH_BEFORE", "FEEDBACK_DEADLINE"),
            (False, True, False, "MONTH_BEFORE", "MONTH_AFTER"),
            (True, False, True, "REMINDER", "FEEDBACK_DEADLINE"),
            (True, False, False, "REMINDER", None),
            (False, False, True, None, "FEEDBACK_DEADLINE"),
            (False, False, False, None, None),
        )

        for reminder, meetings, deadline, opens, closes in cases:
            label = f"reminder={reminder} meetings={meetings} deadline={deadline}"
            with self.subTest(label):
                r = self._round(
                    meeting_log_reminder_at=self.REMINDER if reminder else None,
                    meetings_completion_deadline_at=(
                        self.MEETINGS if meetings else None
                    ),
                    feedback_deadline_at=self.FEEDBACK_DEADLINE if deadline else None,
                )

                self.assertEqual(
                    feedback_window(r),
                    FeedbackWindow(
                        opens_at=getattr(self, opens) if opens else None,
                        closes_at=getattr(self, closes) if closes else None,
                    ),
                )

    def test_feedback_start_is_not_the_opening(self):
        """feedback_start_at is only when the email goes out; it never opens
        the window, even when it is the only opening-side date."""
        with_meetings = self._round(meeting_log_reminder_at=None)
        alone = self._round(
            meeting_log_reminder_at=None, meetings_completion_deadline_at=None
        )

        self.assertEqual(feedback_window(with_meetings).opens_at, self.MONTH_BEFORE)
        self.assertIsNone(feedback_window(alone).opens_at)
        self.assertFalse(is_feedback_open(alone, self.FEEDBACK_START))
        self.assertTrue(is_feedback_open(self._round(), self.FEEDBACK_START - MICRO))

    def test_unpacks_as_opens_then_closes(self):
        opens_at, closes_at = feedback_window(self._round())

        self.assertEqual(opens_at, self.REMINDER)
        self.assertEqual(closes_at, self.FEEDBACK_DEADLINE)


class TestIsFeedbackOpen(_WindowFixture):
    def test_opening_is_inclusive(self):
        cases = {
            "reminder": (self._round(), self.REMINDER),
            "derived": (self._round(meeting_log_reminder_at=None), self.MONTH_BEFORE),
        }

        for label, (r, opens_at) in cases.items():
            with self.subTest(label):
                self.assertFalse(is_feedback_open(r, opens_at - MICRO))
                self.assertTrue(is_feedback_open(r, opens_at))

    def test_stays_open_after_the_close(self):
        r = self._round()

        self.assertTrue(is_feedback_open(r, self.FEEDBACK_DEADLINE + MICRO))
        self.assertTrue(is_feedback_open(r, self.FAR_FUTURE))

    def test_false_without_an_opening(self):
        r = self._round(
            meeting_log_reminder_at=None, meetings_completion_deadline_at=None
        )

        for now in (self.FAR_PAST, self.FEEDBACK_START, self.FAR_FUTURE):
            with self.subTest(now=now):
                self.assertFalse(is_feedback_open(r, now))


class TestIsFeedbackEditable(_WindowFixture):
    def test_both_bounds_are_inclusive(self):
        r = self._round()
        cases = (
            (self.REMINDER - MICRO, False),
            (self.REMINDER, True),
            (self.MEETINGS, True),
            (self.FEEDBACK_DEADLINE, True),
            (self.FEEDBACK_DEADLINE + MICRO, False),
        )

        for now, expected in cases:
            with self.subTest(now=now):
                self.assertEqual(is_feedback_editable(r, now), expected)

    def test_derived_bounds_are_inclusive(self):
        r = self._round(meeting_log_reminder_at=None, feedback_deadline_at=None)
        cases = (
            (self.MONTH_BEFORE - MICRO, False),
            (self.MONTH_BEFORE, True),
            (self.MONTH_AFTER, True),
            (self.MONTH_AFTER + MICRO, False),
        )

        for now, expected in cases:
            with self.subTest(now=now):
                self.assertEqual(is_feedback_editable(r, now), expected)

    def test_missing_opening_does_not_restrict(self):
        r = self._round(
            meeting_log_reminder_at=None, meetings_completion_deadline_at=None
        )

        self.assertTrue(is_feedback_editable(r, self.FAR_PAST))
        self.assertTrue(is_feedback_editable(r, self.FEEDBACK_DEADLINE))
        self.assertFalse(is_feedback_editable(r, self.FEEDBACK_DEADLINE + MICRO))

    def test_missing_close_does_not_restrict(self):
        r = self._round(meetings_completion_deadline_at=None, feedback_deadline_at=None)

        self.assertFalse(is_feedback_editable(r, self.REMINDER - MICRO))
        self.assertTrue(is_feedback_editable(r, self.REMINDER))
        self.assertTrue(is_feedback_editable(r, self.FAR_FUTURE))

    def test_unbounded_without_any_dates(self):
        r = self._round(
            meeting_log_reminder_at=None,
            meetings_completion_deadline_at=None,
            feedback_start_at=None,
            feedback_deadline_at=None,
        )

        for now in (self.FAR_PAST, self.FAR_FUTURE):
            with self.subTest(now=now):
                self.assertTrue(is_feedback_editable(r, now))


class TestMeetingLog(_WindowFixture):
    def test_closes_a_day_after_the_meetings_deadline(self):
        self.assertEqual(meeting_log_closes_at(self._round()), self.MEETING_LOG_CLOSE)

    def test_no_close_without_a_meetings_deadline(self):
        """The feedback dates on the round do not stand in for it."""
        r = self._round(meetings_completion_deadline_at=None)

        self.assertIsNone(meeting_log_closes_at(r))

    def test_open_through_the_closing_instant(self):
        r = self._round()

        self.assertTrue(is_meeting_log_open(r, self.FAR_PAST))
        self.assertTrue(is_meeting_log_open(r, self.MEETINGS + MICRO))
        self.assertTrue(is_meeting_log_open(r, self.MEETING_LOG_CLOSE))
        self.assertFalse(is_meeting_log_open(r, self.MEETING_LOG_CLOSE + MICRO))

    def test_always_open_without_a_meetings_deadline(self):
        r = self._round(meetings_completion_deadline_at=None)

        self.assertTrue(is_meeting_log_open(r, self.FAR_FUTURE))


if __name__ == "__main__":
    unittest.main()
