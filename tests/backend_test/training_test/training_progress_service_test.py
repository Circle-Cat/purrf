"""What one LMSCommit is allowed to change."""

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import TrainingStatus
from backend.entity.training_entity import TrainingEntity
from backend.entity.training_progress_entity import TrainingProgressEntity
from backend.training.training_content_token import issue_content_token
from backend.training.training_progress_service import TrainingProgressService

_TRAINING_ID = 42
_USER_ID = 11
_EARLIER = datetime(2026, 1, 1, tzinfo=timezone.utc)
_SIGNING_KEY = "test-signing-key"
# When the package on the course landed, and when the tab running it opened.
_PACKAGE_LANDED = datetime(2026, 2, 1, tzinfo=timezone.utc)
_OPENED_AFTER = int(datetime(2026, 2, 1, 0, 5, tzinfo=timezone.utc).timestamp())
_OPENED_BEFORE = int(datetime(2026, 1, 31, 23, 55, tzinfo=timezone.utc).timestamp())


def _session_token(opened_at: int) -> str:
    """The token a page was handed when its run opened at ``opened_at``."""
    token, _ = issue_content_token(_SIGNING_KEY, _TRAINING_ID, _USER_ID, now=opened_at)
    return token


_COMMIT = {
    "cmi.core.lesson_status": "incomplete",
    "cmi.core.lesson_location": "Summary",
    "cmi.suspend_data": "x" * 5000,
    "cmi.core.session_time": "00:02:30",
}


class _ProgressServiceCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.logger = MagicMock()
        self.training_repository = AsyncMock()
        self.training_repository.get_training_by_id.return_value = TrainingEntity(
            training_id=_TRAINING_ID,
            user_id=_USER_ID,
            course_id=3,
            status=TrainingStatus.IN_PROGRESS,
        )
        self.progress_repository = AsyncMock()
        self.progress_repository.get_by_training_id.return_value = None
        self.progress_repository.upsert.side_effect = (
            lambda session, training_id, **columns: TrainingProgressEntity(
                training_id=training_id, **columns
            )
        )
        self.course_repository = AsyncMock()
        # A course row always knows when its package landed, and a bare
        # MagicMock here would compare against a datetime rather than answer.
        self.course_repository.get_course_by_id.return_value.package_uploaded_at = (
            _PACKAGE_LANDED
        )
        self.service = TrainingProgressService(
            logger=self.logger,
            signing_key=_SIGNING_KEY,
            training_repository=self.training_repository,
            training_progress_repository=self.progress_repository,
            training_course_repository=self.course_repository,
        )

    def _saved_columns(self):
        return self.progress_repository.upsert.call_args.kwargs


class TestNonStringValues(_ProgressServiceCase):
    """The body is JSON from whoever holds the assignment, so a CMI element
    can arrive as a number, an object or null however well the course behaves."""

    async def test_a_text_element_that_is_not_a_string_is_refused(self):
        for value in (5, {"nested": "object"}, None, ["a"], True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    await self.service.save(
                        self.session,
                        _TRAINING_ID,
                        _USER_ID,
                        {"cmi.suspend_data": value},
                    )

        self.progress_repository.upsert.assert_not_called()

    async def test_a_non_string_time_is_dropped_not_a_crash(self):
        """Same treatment as a time in a format we cannot read."""
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {"cmi.core.total_time": 90, "cmi.core.lesson_location": "Summary"},
        )

        self.assertEqual(self._saved_columns(), {"lesson_location": "Summary"})
        self.logger.warning.assert_called()

    async def test_a_non_string_session_time_adds_nothing(self):
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {"cmi.core.session_time": {"minutes": 3}},
        )

        self.assertEqual(self._saved_columns()["session_time_seconds"], 0)

    async def test_a_non_string_score_is_dropped_like_an_unstorable_one(self):
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {"cmi.core.score.raw": {"value": 80}, "cmi.core.lesson_location": "End"},
        )

        self.assertEqual(self._saved_columns(), {"lesson_location": "End"})


class TestSave(_ProgressServiceCase):
    async def test_the_course_values_land_on_the_row(self):
        await self.service.save(self.session, _TRAINING_ID, _USER_ID, _COMMIT)

        saved = self._saved_columns()
        self.assertEqual(saved["lesson_status"], "incomplete")
        self.assertEqual(saved["lesson_location"], "Summary")
        self.assertEqual(saved["suspend_data"], "x" * 5000)

    async def test_suspend_data_is_stored_whole_however_long_it_is(self):
        """Real packages disable the 4096 cap; a rejected write is silent."""
        long_blob = "y" * 40000

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.suspend_data": long_blob},
        )

        self.assertEqual(self._saved_columns()["suspend_data"], long_blob)

    async def test_an_empty_suspend_data_is_stored_rather_than_ignored(self):
        """The course clears it to reset itself after a package change."""
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.suspend_data": "", "cmi.core.lesson_location": ""},
        )

        saved = self._saved_columns()
        self.assertEqual(saved["suspend_data"], "")
        self.assertEqual(saved["lesson_location"], "")

    async def test_session_time_falls_back_to_accumulating_when_total_time_is_absent(
        self,
    ):
        """The real player always sends total_time; this covers a payload
        that does not, so the older accumulation rule still has a test."""
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(training_id=_TRAINING_ID, session_time_seconds=500)
        )

        await self.service.save(self.session, _TRAINING_ID, _USER_ID, _COMMIT)

        self.assertEqual(self._saved_columns()["session_time_seconds"], 650)

    async def test_session_time_comes_from_total_time_when_present(self):
        """scorm-again's total_time is already seeded-total plus this
        session's elapsed time, so it replaces the stored value outright."""
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(training_id=_TRAINING_ID, session_time_seconds=500)
        )

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.total_time": "00:10:00"},
        )

        self.assertEqual(self._saved_columns()["session_time_seconds"], 600)

    async def test_two_commits_in_one_session_do_not_double_count(self):
        """Each commit's total_time already covers the whole session so far;
        summing successive commits would multiply it, not accumulate it."""
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.total_time": "00:03:00"},
        )
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(training_id=_TRAINING_ID, session_time_seconds=180)
        )

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.total_time": "00:05:00"},
        )

        self.assertEqual(self._saved_columns()["session_time_seconds"], 300)

    async def test_a_malformed_session_time_does_not_lose_the_commit(self):
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.session_time": "not a timespan"},
        )

        saved = self._saved_columns()
        self.assertEqual(saved["session_time_seconds"], 0)
        self.assertEqual(saved["lesson_location"], "Summary")

    async def test_a_malformed_total_time_leaves_the_stored_value_alone(self):
        """0 is a real elapsed time, not a stand-in for "could not read it";
        writing it over a real total would wipe accumulated time."""
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.total_time": "not a timespan"},
        )

        self.assertNotIn("session_time_seconds", self._saved_columns())

    async def test_an_unparseable_total_time_is_logged(self):
        """A course reporting time in a shape we reject would otherwise bank
        nothing, forever, with no trace anywhere."""
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.total_time": "not a timespan"},
        )

        self.logger.warning.assert_called_once()
        message = "%s" % (self.logger.warning.call_args,)
        self.assertIn(str(_TRAINING_ID), message)
        self.assertIn("not a timespan", message)

    async def test_a_single_digit_hour_total_time_is_treated_as_malformed(self):
        """SCORM 1.2's CMITimespan needs at least two digits of hours; a value
        that skips the leading zero is not one of ours to guess at, so it is
        left unparsed rather than silently read as zero."""
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.total_time": "0:02:30"},
        )

        self.assertNotIn("session_time_seconds", self._saved_columns())

    async def test_a_commit_matching_no_known_element_is_logged(self):
        """columns ends up empty and the row still gets touched -- the only
        trace of a misbehaving course is this log line."""
        await self.service.save(
            self.session, _TRAINING_ID, _USER_ID, {"cmi.objectives.0.id": "obj-1"}
        )

        self.logger.warning.assert_called_once()
        message = "%s" % (self.logger.warning.call_args,)
        self.assertIn(str(_TRAINING_ID), message)
        self.assertIn("cmi.objectives.0.id", message)

    async def test_a_commit_with_a_recognised_element_is_not_logged(self):
        await self.service.save(self.session, _TRAINING_ID, _USER_ID, _COMMIT)

        self.logger.warning.assert_not_called()

    async def test_score_fields_land_on_the_row(self):
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {
                **_COMMIT,
                "cmi.core.score.raw": "82.5",
                "cmi.core.score.min": "0",
                "cmi.core.score.max": "100",
            },
        )

        saved = self._saved_columns()
        self.assertEqual(saved["score_raw"], Decimal("82.5"))
        self.assertEqual(saved["score_min"], Decimal("0"))
        self.assertEqual(saved["score_max"], Decimal("100"))

    async def test_an_unparseable_score_does_not_lose_the_rest_of_the_commit(self):
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.score.raw": "not-a-number"},
        )

        saved = self._saved_columns()
        self.assertNotIn("score_raw", saved)
        self.assertEqual(saved["lesson_status"], "incomplete")

    async def test_an_out_of_range_score_does_not_lose_the_rest_of_the_commit(self):
        """ "12345678" parses as a Decimal fine, but overflows Numeric(8, 2)
        and would otherwise 500 the request at flush, losing suspend_data
        along with it."""
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {
                **_COMMIT,
                "cmi.core.score.raw": "12345678",
                "cmi.core.score.min": "0",
                "cmi.core.score.max": "82.5",
            },
        )

        saved = self._saved_columns()
        self.assertNotIn("score_raw", saved)
        self.assertEqual(saved["score_min"], Decimal("0"))
        self.assertEqual(saved["score_max"], Decimal("82.5"))
        self.assertEqual(saved["suspend_data"], "x" * 5000)

    async def test_a_non_finite_score_does_not_lose_the_rest_of_the_commit(self):
        """ "NaN" and "Infinity" both parse as a Decimal; storing them would
        round-trip back out to the browser as the literal string "NaN"."""
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {
                **_COMMIT,
                "cmi.core.score.raw": "NaN",
                "cmi.core.score.min": "Infinity",
                "cmi.core.score.max": "72",
            },
        )

        saved = self._saved_columns()
        self.assertNotIn("score_raw", saved)
        self.assertNotIn("score_min", saved)
        self.assertEqual(saved["score_max"], Decimal("72"))
        self.assertEqual(saved["lesson_status"], "incomplete")

    async def test_an_unstorable_score_is_logged(self):
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.score.raw": "1e400"},
        )

        self.logger.warning.assert_called_once()
        message = "%s" % (self.logger.warning.call_args,)
        self.assertIn(str(_TRAINING_ID), message)
        self.assertIn("1e400", message)

    async def test_an_empty_score_is_stored_as_no_score_rather_than_zero(self):
        """A course clears its score the same way it clears any other field:
        by writing an empty string. Numeric has no empty value, so that
        clears to NULL instead of being rejected as unparseable."""
        await self.service.save(
            self.session, _TRAINING_ID, _USER_ID, {"cmi.core.score.raw": ""}
        )

        self.assertIsNone(self._saved_columns()["score_raw"])

    async def test_a_completion_finishes_the_assignment_and_stamps_the_time(self):
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.IN_PROGRESS

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "passed"},
        )

        self.assertEqual(assignment.status, TrainingStatus.DONE)
        self.assertIsNotNone(assignment.completed_timestamp)

    async def test_the_save_reports_the_status_it_left_the_assignment_in(self):
        """The page shows this rather than judging the lesson_status itself."""
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.IN_PROGRESS

        result = await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "passed"},
        )

        self.assertEqual(result.status, TrainingStatus.DONE)

    async def test_a_save_that_moves_nothing_still_reports_where_it_stands(self):
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.IN_PROGRESS

        result = await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "incomplete"},
        )

        self.assertEqual(result.status, TrainingStatus.IN_PROGRESS)

    async def test_a_verifier_already_done_can_still_stamp_a_replaced_package(self):
        """Re-upload clears the stamp but leaves the verifier's row DONE.

        Their status moves nowhere on the next run, so a stamp gated on that
        move would leave the new package unverifiable by the one person most
        likely to be running it.
        """
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.DONE
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = None

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "completed"},
            may_verify_course=True,
            session_token=_session_token(_OPENED_AFTER),
        )

        self.assertIsNotNone(course.verified_completable_at)
        self.assertEqual(course.verified_by_user_id, _USER_ID)

    async def test_reopening_a_finished_course_does_not_undo_it(self):
        """Mentor onboarding writes `incomplete` on its way to `completed`."""
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.DONE
        assignment.completed_timestamp = _EARLIER

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "incomplete"},
        )

        self.assertEqual(assignment.status, TrainingStatus.DONE)
        self.assertEqual(assignment.completed_timestamp, _EARLIER)

    async def test_the_completion_time_is_the_first_one_not_the_latest(self):
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.DONE
        assignment.completed_timestamp = _EARLIER

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "completed"},
        )

        self.assertEqual(assignment.completed_timestamp, _EARLIER)

    async def test_a_partial_body_leaves_absent_fields_alone(self):
        """Only the elements a course actually committed are written."""
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {"cmi.core.lesson_status": "completed"},
        )

        self.assertEqual(self._saved_columns(), {"lesson_status": "completed"})

    async def test_an_explicit_empty_value_is_written_not_treated_as_absent(self):
        """A course clears a field on purpose and reads it back to check."""
        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {"cmi.suspend_data": "", "cmi.core.lesson_location": ""},
        )

        saved = self._saved_columns()
        self.assertEqual(saved, {"suspend_data": "", "lesson_location": ""})

    async def test_finishing_an_unverified_course_unlocks_it(self):
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = None
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.IN_PROGRESS

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "completed"},
            may_verify_course=True,
            session_token=_session_token(_OPENED_AFTER),
        )

        self.assertIsNotNone(course.verified_completable_at)
        self.assertEqual(course.verified_by_user_id, _USER_ID)

    async def test_a_learner_without_the_grant_cannot_unlock_the_course(self):
        """Replacing a package clears the stamp and keeps every assignment,
        so an assignee could otherwise post a finishing status and make the
        new package assignable to everybody without opening it."""
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = None
        course.verified_by_user_id = None
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.IN_PROGRESS

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "completed"},
        )

        self.assertIsNone(course.verified_completable_at)
        self.assertIsNone(course.verified_by_user_id)

    async def test_a_learner_without_the_grant_still_finishes_their_own_training(self):
        """The gate is on unlocking the course for everybody else, not on a
        learner reporting their own assignment done."""
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = None
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.IN_PROGRESS

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "completed"},
        )

        self.assertIs(assignment.status, TrainingStatus.DONE)
        self.assertIsNotNone(assignment.completed_timestamp)

    async def test_an_already_verified_course_keeps_its_first_verifier(self):
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = _EARLIER
        course.verified_by_user_id = 99
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.IN_PROGRESS

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "passed"},
            may_verify_course=True,
            session_token=_session_token(_OPENED_AFTER),
        )

        self.assertEqual(course.verified_completable_at, _EARLIER)
        self.assertEqual(course.verified_by_user_id, 99)

    async def test_not_finishing_it_leaves_the_course_locked(self):
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = None

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "incomplete"},
            may_verify_course=True,
            session_token=_session_token(_OPENED_AFTER),
        )

        self.assertIsNone(course.verified_completable_at)

    async def test_an_assignment_with_no_course_does_not_crash_the_save(self):
        """Legacy link-only rows carry no course_id."""
        self.training_repository.get_training_by_id.return_value.course_id = None

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "passed"},
        )

        self.progress_repository.upsert.assert_awaited()

    async def test_an_identical_commit_writes_nothing(self):
        """The driver commits every 20 seconds whether anything changed or not.

        Carries cmi.core.total_time, as our own player always does -- the
        session_time-only fallback below is a different, stateful case that
        must never be skipped (see
        test_a_fallback_session_time_commit_is_never_skipped).
        """
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(
                training_id=_TRAINING_ID,
                lesson_status="incomplete",
                lesson_location="Summary",
                suspend_data="x" * 5000,
                session_time_seconds=500,
            )
        )
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.IN_PROGRESS

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.total_time": "00:08:20"},
        )

        self.progress_repository.upsert.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_an_identical_commit_still_reports_success(self):
        """The course must not be told its save failed."""
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(
                training_id=_TRAINING_ID,
                lesson_status="incomplete",
                lesson_location="Summary",
                suspend_data="x" * 5000,
            )
        )

        await self.service.save(self.session, _TRAINING_ID, _USER_ID, _COMMIT)
        # No exception is the assertion; the controller answers 200 either way.

    async def test_a_growing_total_time_alone_does_not_count_as_a_change(self):
        """Otherwise an idle learner is written every 20 seconds forever."""
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(
                training_id=_TRAINING_ID,
                lesson_status="incomplete",
                lesson_location="Summary",
                suspend_data="x" * 5000,
                session_time_seconds=500,
            )
        )

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.total_time": "01:00:00"},
        )

        self.progress_repository.upsert.assert_not_awaited()

    async def test_one_changed_field_writes_all_of_them(self):
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(
                training_id=_TRAINING_ID,
                lesson_status="incomplete",
                lesson_location="Intro",
                suspend_data="x" * 5000,
            )
        )

        await self.service.save(self.session, _TRAINING_ID, _USER_ID, _COMMIT)

        saved = self.progress_repository.upsert.call_args.kwargs
        self.assertEqual(saved["lesson_location"], "Summary")
        self.assertEqual(saved["suspend_data"], "x" * 5000)

    async def test_a_completion_is_written_even_though_the_progress_matches(self):
        """The status still has to move, or a failed save is never made up."""
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(
                training_id=_TRAINING_ID,
                lesson_status="passed",
                lesson_location="Summary",
                suspend_data="x" * 5000,
            )
        )
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.IN_PROGRESS

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "passed"},
        )

        self.assertEqual(assignment.status, TrainingStatus.DONE)
        self.session.commit.assert_awaited()

    async def test_an_absent_key_is_not_a_difference(self):
        """A partial body means "do not touch", not "set it to nothing"."""
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(
                training_id=_TRAINING_ID,
                lesson_status="incomplete",
                lesson_location="Summary",
                suspend_data="x" * 5000,
            )
        )

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {"cmi.core.lesson_status": "incomplete"},
        )

        self.progress_repository.upsert.assert_not_awaited()

    async def test_an_explicit_empty_value_is_a_difference(self):
        """A course clears these to reset itself; that is a real write."""
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(
                training_id=_TRAINING_ID,
                lesson_status="incomplete",
                lesson_location="Summary",
                suspend_data="x" * 5000,
            )
        )

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.suspend_data": ""},
        )

        self.assertEqual(
            self.progress_repository.upsert.call_args.kwargs["suspend_data"], ""
        )

    async def test_the_first_commit_of_all_is_written(self):
        self.progress_repository.get_by_training_id.return_value = None

        await self.service.save(self.session, _TRAINING_ID, _USER_ID, _COMMIT)

        self.progress_repository.upsert.assert_awaited()

    async def test_a_fallback_session_time_commit_is_never_skipped(self):
        """The session_time fallback's delta lives only in this one commit --
        unlike total_time, which is recomputed fresh from a stable seed on
        every commit, skipping this write discards the delta permanently
        rather than merely delaying an accurate figure. Our own player
        always sends total_time, so this path is dormant in production
        today, but a dormant trap is exactly the one that fires years later
        when somebody revives the path."""
        fallback_commit = {
            "cmi.core.lesson_status": "incomplete",
            "cmi.core.lesson_location": "Summary",
            "cmi.suspend_data": "x" * 5000,
            "cmi.core.session_time": "00:00:30",
        }
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(
                training_id=_TRAINING_ID,
                lesson_status="incomplete",
                lesson_location="Summary",
                suspend_data="x" * 5000,
                session_time_seconds=0,
            )
        )

        await self.service.save(self.session, _TRAINING_ID, _USER_ID, fallback_commit)

        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(
                training_id=_TRAINING_ID,
                lesson_status="incomplete",
                lesson_location="Summary",
                suspend_data="x" * 5000,
                session_time_seconds=30,
            )
        )

        await self.service.save(self.session, _TRAINING_ID, _USER_ID, fallback_commit)

        self.assertEqual(self.progress_repository.upsert.call_count, 2)
        second_call = self.progress_repository.upsert.call_args_list[1].kwargs
        self.assertEqual(second_call["session_time_seconds"], 60)

    async def test_the_write_is_committed_after_the_upsert(self):
        order = []
        self.progress_repository.upsert.side_effect = None

        async def fake_upsert(session, training_id, **columns):
            order.append("upsert")
            return TrainingProgressEntity(training_id=training_id, **columns)

        async def fake_commit():
            order.append("commit")

        self.progress_repository.upsert.side_effect = fake_upsert
        self.session.commit.side_effect = fake_commit

        await self.service.save(self.session, _TRAINING_ID, _USER_ID, _COMMIT)

        self.assertEqual(order, ["upsert", "commit"])


class TestConcurrentSaves(_ProgressServiceCase):
    """Two commits for one assignment, arriving at once.

    The mentor onboarding course writes `incomplete` and then `completed`
    within the same second, and the page does not wait for the first save
    before sending the second.
    """

    async def test_the_assignment_is_read_under_a_row_lock(self):
        """Unlocked, both requests read the status the other has not written
        yet: one of them decides "not finished" from a snapshot that is
        already stale by the time it commits, and a learner who finished is
        left held at the matching gate with nothing to reopen."""
        await self.service.save(self.session, _TRAINING_ID, _USER_ID, _COMMIT)

        self.training_repository.get_training_by_id.assert_awaited_once_with(
            self.session, _TRAINING_ID, for_update=True
        )

    async def test_the_loser_of_the_race_reads_the_status_the_winner_wrote(self):
        """What the lock buys: the second request re-reads DONE rather than
        the TO_DO it would have seen, and next_training_status leaves it."""
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.DONE
        assignment.completed_timestamp = _EARLIER

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "incomplete"},
        )

        self.assertEqual(assignment.status, TrainingStatus.DONE)
        self.assertEqual(assignment.completed_timestamp, _EARLIER)


class TestFinalSave(_ProgressServiceCase):
    """The page's parting save as the tab closes."""

    def _row_matching(self, **overrides):
        return TrainingProgressEntity(
            training_id=_TRAINING_ID,
            lesson_status="incomplete",
            lesson_location="Summary",
            suspend_data="x" * 5000,
            session_time_seconds=500,
            **overrides,
        )

    async def test_a_final_save_is_written_even_though_the_content_matches(self):
        """It resends the cmi the last commit already stored, so the content
        always matches -- and the elapsed time it exists to bank is the one
        thing the content comparison leaves out. Skipped, it does nothing."""
        self.progress_repository.get_by_training_id.return_value = self._row_matching()

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.total_time": "01:00:00"},
            final=True,
        )

        self.assertEqual(self._saved_columns()["session_time_seconds"], 3600)

    async def test_an_ordinary_save_of_the_same_commit_is_still_skipped(self):
        """The 20-second rewrite of a parked tab has to stay gone."""
        self.progress_repository.get_by_training_id.return_value = self._row_matching()

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.total_time": "01:00:00"},
        )

        self.progress_repository.upsert.assert_not_awaited()

    async def test_a_skipped_save_still_reports_where_the_assignment_stands(self):
        """A parked tab gets the same answer as a tab that stored something."""
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.DONE
        self.progress_repository.get_by_training_id.return_value = self._row_matching()

        result = await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.total_time": "01:00:00"},
        )

        self.progress_repository.upsert.assert_not_awaited()
        self.assertEqual(result.status, TrainingStatus.DONE)

    async def test_a_final_save_does_not_move_a_finished_assignment(self):
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.DONE
        assignment.completed_timestamp = _EARLIER
        self.progress_repository.get_by_training_id.return_value = self._row_matching()

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.total_time": "01:00:00"},
            final=True,
        )

        self.assertEqual(assignment.status, TrainingStatus.DONE)
        self.assertEqual(assignment.completed_timestamp, _EARLIER)
        self.progress_repository.upsert.assert_awaited()


class TestLengthLimits(_ProgressServiceCase):
    """The endpoint is open to anyone holding the assignment, and the columns
    behind it are unbounded text."""

    async def test_a_suspend_data_no_course_could_produce_is_refused(self):
        with self.assertRaises(ValueError):
            await self.service.save(
                self.session,
                _TRAINING_ID,
                _USER_ID,
                {**_COMMIT, "cmi.suspend_data": "x" * 65537},
            )

    async def test_a_refused_commit_writes_nothing_at_all(self):
        """Refused loudly, not stored short: the course is told, and the row
        is left exactly as it was."""
        with self.assertRaises(ValueError):
            await self.service.save(
                self.session,
                _TRAINING_ID,
                _USER_ID,
                {**_COMMIT, "cmi.suspend_data": "x" * 65537},
            )

        self.progress_repository.upsert.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_suspend_data_at_the_limit_is_stored_whole(self):
        """The cap is far above any real package; nothing legitimate is near
        it, and what is under it is still stored byte for byte."""
        blob = "x" * 65536

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.suspend_data": blob},
        )

        self.assertEqual(self._saved_columns()["suspend_data"], blob)

    async def test_an_oversized_lesson_location_is_refused(self):
        """String columns are unbounded too, so the same hole is open here."""
        with self.assertRaises(ValueError):
            await self.service.save(
                self.session,
                _TRAINING_ID,
                _USER_ID,
                {**_COMMIT, "cmi.core.lesson_location": "y" * 4097},
            )

    async def test_an_oversized_lesson_status_is_refused(self):
        with self.assertRaises(ValueError):
            await self.service.save(
                self.session,
                _TRAINING_ID,
                _USER_ID,
                {**_COMMIT, "cmi.core.lesson_status": "z" * 65},
            )

    async def test_the_refusal_names_the_element_and_the_limit(self):
        """The learner sees a failed save; whoever they report it to needs to
        be able to tell abuse from a course that got bigger."""
        with self.assertRaises(ValueError) as caught:
            await self.service.save(
                self.session,
                _TRAINING_ID,
                _USER_ID,
                {**_COMMIT, "cmi.suspend_data": "x" * 65537},
            )

        message = str(caught.exception)
        self.assertIn("cmi.suspend_data", message)
        self.assertIn("65536", message)

    async def test_an_empty_value_is_not_caught_by_the_cap(self):
        await self.service.save(
            self.session, _TRAINING_ID, _USER_ID, {"cmi.suspend_data": ""}
        )

        self.assertEqual(self._saved_columns()["suspend_data"], "")


class TestSaveRefusals(_ProgressServiceCase):
    async def test_saving_onto_somebody_elses_assignment_is_refused(self):
        self.training_repository.get_training_by_id.return_value.user_id = 999

        with self.assertRaises(PermissionError):
            await self.service.save(self.session, _TRAINING_ID, _USER_ID, _COMMIT)

        self.progress_repository.upsert.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_saving_onto_an_assignment_that_does_not_exist_is_refused(self):
        self.training_repository.get_training_by_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.save(self.session, _TRAINING_ID, _USER_ID, _COMMIT)

        self.progress_repository.upsert.assert_not_awaited()
        self.session.commit.assert_not_awaited()


class TestARunAgainstAReplacedPackage(_ProgressServiceCase):
    """A tab left open across a replacement still holds the old package's CMI
    model, and the driver re-commits the whole of it every twenty seconds --
    so the database clear an upload performs is undone from the browser."""

    async def test_a_run_that_began_before_the_package_cannot_verify_it(self):
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = None
        course.verified_by_user_id = None
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.DONE

        with self.assertRaises(ConflictError):
            await self.service.save(
                self.session,
                _TRAINING_ID,
                _USER_ID,
                {**_COMMIT, "cmi.core.lesson_status": "passed"},
                may_verify_course=True,
                session_token=_session_token(_OPENED_BEFORE),
            )

        self.assertIsNone(course.verified_completable_at)
        self.assertIsNone(course.verified_by_user_id)

    async def test_the_stale_finishing_status_is_never_committed(self):
        """Storing it would put the finishing value back in the row the upload
        cleared, where the next run would seed it and report it again."""
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = None

        with self.assertRaises(ConflictError):
            await self.service.save(
                self.session,
                _TRAINING_ID,
                _USER_ID,
                {**_COMMIT, "cmi.core.lesson_status": "passed"},
                may_verify_course=True,
                session_token=_session_token(_OPENED_BEFORE),
            )

        self.session.commit.assert_not_awaited()

    async def test_a_run_opened_after_the_package_landed_verifies_it(self):
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = None

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "passed"},
            may_verify_course=True,
            session_token=_session_token(_OPENED_AFTER),
        )

        self.assertIsNotNone(course.verified_completable_at)

    async def test_a_commit_naming_no_session_stores_but_does_not_verify(self):
        """The guard rests on knowing when the tab opened. Without that the
        commit is still the learner's progress, but it vouches for nothing."""
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = None

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "passed"},
            may_verify_course=True,
        )

        self.assertIsNone(course.verified_completable_at)
        self.progress_repository.upsert.assert_awaited()

    async def test_a_forged_session_token_cannot_claim_a_fresh_run(self):
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = None
        payload, _, _ = _session_token(_OPENED_BEFORE).partition(".")
        forged, _ = issue_content_token(
            "some-other-key", _TRAINING_ID, _USER_ID, now=_OPENED_AFTER
        )

        for token in (forged, payload + ".notasignature", 12345, ""):
            with self.subTest(token=token):
                course.verified_completable_at = None
                await self.service.save(
                    self.session,
                    _TRAINING_ID,
                    _USER_ID,
                    {**_COMMIT, "cmi.core.lesson_status": "passed"},
                    may_verify_course=True,
                    session_token=token,
                )
                self.assertIsNone(course.verified_completable_at)

    async def test_a_course_with_no_package_has_nothing_to_have_moved_on(self):
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = None
        course.package_uploaded_at = None

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "passed"},
            may_verify_course=True,
            session_token=_session_token(_OPENED_BEFORE),
        )

        self.assertIsNotNone(course.verified_completable_at)


class TestTheSaveReportsWhetherTheCourseIsVerified(_ProgressServiceCase):
    """The trial page cannot read this off the assignment's own status: a
    verifier re-running a replaced package was already DONE, so their run
    moves nothing and the status never changes."""

    async def test_the_commit_that_stamps_the_course_says_so(self):
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = None
        assignment = self.training_repository.get_training_by_id.return_value
        assignment.status = TrainingStatus.DONE

        result = await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "completed"},
            may_verify_course=True,
            session_token=_session_token(_OPENED_AFTER),
        )

        self.assertIs(result.course_verified, True)

    async def test_an_already_stamped_course_reads_verified_too(self):
        course = self.course_repository.get_course_by_id.return_value
        course.verified_completable_at = _EARLIER

        result = await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "completed"},
            may_verify_course=True,
            session_token=_session_token(_OPENED_AFTER),
        )

        self.assertIs(result.course_verified, True)

    async def test_a_commit_that_reports_no_completion_reads_nothing(self):
        """The heartbeat arrives every twenty seconds and often stores
        nothing. It must not grow a query to answer this."""
        result = await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "incomplete"},
            may_verify_course=True,
            session_token=_session_token(_OPENED_AFTER),
        )

        self.assertIsNone(result.course_verified)
        self.course_repository.get_course_by_id.assert_not_awaited()

    async def test_a_learner_without_the_grant_is_told_nothing_either_way(self):
        result = await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "completed"},
        )

        self.assertIsNone(result.course_verified)


if __name__ == "__main__":
    unittest.main()
