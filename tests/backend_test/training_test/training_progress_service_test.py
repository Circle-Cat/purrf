"""What one LMSCommit is allowed to change."""

import unittest
from unittest.mock import AsyncMock, MagicMock

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
            training_id=_TRAINING_ID, user_id=_USER_ID, course_id=3
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

    async def test_session_time_accumulates_rather_than_replaces(self):
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(training_id=_TRAINING_ID, session_time_seconds=500)
        )

        await self.service.save(self.session, _TRAINING_ID, _USER_ID, _COMMIT)

        self.assertEqual(self._saved_columns()["session_time_seconds"], 650)

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


class TestSaveRefusals(_ProgressServiceCase):
    async def test_saving_onto_somebody_elses_assignment_is_refused(self):
        self.training_repository.get_training_by_id.return_value.user_id = 999

        with self.assertRaises(PermissionError):
            await self.service.save(self.session, _TRAINING_ID, _USER_ID, _COMMIT)

        self.progress_repository.upsert.assert_not_awaited()

    async def test_saving_onto_an_assignment_that_does_not_exist_is_refused(self):
        self.training_repository.get_training_by_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.save(self.session, _TRAINING_ID, _USER_ID, _COMMIT)

        self.progress_repository.upsert.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
