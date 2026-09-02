"""What one LMSCommit is allowed to change."""

import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from backend.common.mentorship_enums import TrainingStatus
from backend.entity.training_entity import TrainingEntity
from backend.entity.training_progress_entity import TrainingProgressEntity
from backend.training.training_progress_service import TrainingProgressService

_TRAINING_ID = 42
_USER_ID = 11

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
        self.service = TrainingProgressService(
            logger=self.logger,
            training_repository=self.training_repository,
            training_progress_repository=self.progress_repository,
        )

    def _saved_columns(self):
        return self.progress_repository.upsert.call_args.kwargs


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

    async def test_an_empty_score_is_stored_as_no_score_rather_than_zero(self):
        """A course clears its score the same way it clears any other field:
        by writing an empty string. Numeric has no empty value, so that
        clears to NULL instead of being rejected as unparseable."""
        await self.service.save(
            self.session, _TRAINING_ID, _USER_ID, {"cmi.core.score.raw": ""}
        )

        self.assertIsNone(self._saved_columns()["score_raw"])

    async def test_it_does_not_touch_the_assignment_status(self):
        """Mapping a course's status onto DONE is the next slice's business."""
        assignment = self.training_repository.get_training_by_id.return_value
        before = assignment.status

        await self.service.save(
            self.session,
            _TRAINING_ID,
            _USER_ID,
            {**_COMMIT, "cmi.core.lesson_status": "passed"},
        )

        self.assertEqual(assignment.status, before)

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


if __name__ == "__main__":
    unittest.main()
