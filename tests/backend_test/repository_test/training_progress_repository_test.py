"""Resume state, and who loses it when a package is replaced."""

import unittest
from datetime import datetime, timezone

from backend.common.mentorship_enums import (
    CommunicationMethod,
    TrainingStatus,
)
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_entity import TrainingEntity
from backend.entity.training_progress_entity import TrainingProgressEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.training_progress_repository import (
    TrainingProgressRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestTrainingProgressRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = TrainingProgressRepository()
        self.now = datetime.now(timezone.utc)

        users = [self._user(f"Learner{i}") for i in range(4)]
        await self.insert_entities(users)
        self.user_ids = [u.user_id for u in users]

        courses = [
            TrainingCourseEntity(name="Mentor Onboarding", is_active=True),
            TrainingCourseEntity(name="Mentee Onboarding", is_active=True),
        ]
        await self.insert_entities(courses)
        self.course_id = courses[0].course_id
        self.other_course_id = courses[1].course_id

    def _user(self, first_name):
        return UsersEntity(
            first_name=first_name,
            last_name="Tester",
            timezone="Asia/Shanghai",
            timezone_updated_at=self.now,
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=self.now,
        )

    async def _assign(self, user_id, course_id, status):
        training = TrainingEntity(
            user_id=user_id,
            course_id=course_id,
            status=status,
            deadline=self.now,
        )
        await self.insert_entities([training])
        return training

    async def _start(self, training, *, lesson_status="incomplete"):
        progress = TrainingProgressEntity(
            training_id=training.training_id,
            lesson_status=lesson_status,
            lesson_location="Summary",
            suspend_data="x" * 5000,
            session_time_seconds=940,
            last_accessed_at=self.now,
        )
        await self.insert_entities([progress])
        return progress

    async def _reload(self, progress):
        await self.session.refresh(progress)
        return progress

    async def test_get_by_training_id_returns_the_row_for_that_assignment(self):
        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.IN_PROGRESS
        )
        progress = await self._start(training)

        found = await self.repo.get_by_training_id(self.session, training.training_id)

        self.assertIsNotNone(found)
        self.assertEqual(found.progress_id, progress.progress_id)

    async def test_get_by_training_id_returns_none_for_an_assignment_never_opened(self):
        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.TO_DO
        )

        self.assertIsNone(
            await self.repo.get_by_training_id(self.session, training.training_id)
        )

    async def test_clear_resume_state_wipes_an_unfinished_learner(self):
        """An old package's blob wedges the new one, so it has to go."""
        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.IN_PROGRESS
        )
        progress = await self._start(training)

        await self.repo.clear_resume_state(self.session, self.course_id)

        await self._reload(progress)
        self.assertIsNone(progress.suspend_data)
        self.assertIsNone(progress.lesson_location)

    async def test_clear_resume_state_wipes_a_finished_learner_too(self):
        """The verifier of the replaced package is DONE, and has to run again.

        Sparing DONE rows left the one person most likely to open the new
        package resuming it with the previous package's blob -- the exact
        wedge this clearing exists to prevent. Their status is untouched;
        only the resume data goes.
        """
        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.DONE
        )
        progress = await self._start(training, lesson_status="passed")

        await self.repo.clear_resume_state(self.session, self.course_id)

        await self._reload(progress)
        self.assertIsNone(progress.suspend_data)
        self.assertIsNone(progress.lesson_location)

    async def test_clear_resume_state_leaves_a_finished_learners_record_alone(self):
        """Only resume data goes; the completion itself stands."""
        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.DONE
        )
        progress = await self._start(training, lesson_status="passed")

        await self.repo.clear_resume_state(self.session, self.course_id)

        await self._reload(progress)
        self.assertEqual(progress.lesson_status, "passed")
        await self.session.refresh(training)
        self.assertEqual(training.status, TrainingStatus.DONE)

    async def test_clear_resume_state_wipes_a_learner_who_has_not_started(self):
        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.TO_DO
        )
        progress = await self._start(training, lesson_status="not attempted")

        await self.repo.clear_resume_state(self.session, self.course_id)

        await self._reload(progress)
        self.assertIsNone(progress.suspend_data)

    async def test_clear_resume_state_does_not_reach_another_course(self):
        mine = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.IN_PROGRESS
        )
        theirs = await self._assign(
            self.user_ids[1], self.other_course_id, TrainingStatus.IN_PROGRESS
        )
        my_progress = await self._start(mine)
        their_progress = await self._start(theirs)

        await self.repo.clear_resume_state(self.session, self.course_id)

        await self._reload(my_progress)
        await self._reload(their_progress)
        self.assertIsNone(my_progress.suspend_data)
        self.assertEqual(their_progress.suspend_data, "x" * 5000)

    async def test_clear_resume_state_counts_only_the_rows_it_cleared(self):
        """Everyone on the course, and nobody on another one."""
        unfinished = [
            await self._assign(uid, self.course_id, TrainingStatus.IN_PROGRESS)
            for uid in self.user_ids[:2]
        ]
        for training in unfinished:
            await self._start(training)
        finished = await self._assign(
            self.user_ids[2], self.course_id, TrainingStatus.DONE
        )
        await self._start(finished, lesson_status="completed")
        elsewhere = await self._assign(
            self.user_ids[3], self.other_course_id, TrainingStatus.IN_PROGRESS
        )
        await self._start(elsewhere)

        cleared = await self.repo.clear_resume_state(self.session, self.course_id)

        self.assertEqual(cleared, 3)

    async def test_clear_resume_state_keeps_everything_that_is_not_resume_state(self):
        """Only the bookmark and the blob go; the record of what happened stays."""
        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.IN_PROGRESS
        )
        progress = await self._start(training)

        await self.repo.clear_resume_state(self.session, self.course_id)

        await self._reload(progress)
        self.assertEqual(progress.lesson_status, "incomplete")
        self.assertEqual(progress.session_time_seconds, 940)
        self.assertIsNotNone(progress.last_accessed_at)

    async def test_clear_resume_state_on_a_course_nobody_started_clears_nothing(self):
        await self._assign(self.user_ids[0], self.course_id, TrainingStatus.TO_DO)

        self.assertEqual(
            await self.repo.clear_resume_state(self.session, self.course_id), 0
        )

    async def test_upsert_creates_the_row_the_first_time(self):
        """Reading through get_by_training_id would return the same
        identity-mapped object without proving anything reached the
        database; _reload forces an actual read back."""
        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.IN_PROGRESS
        )

        row = await self.repo.upsert(
            self.session,
            training.training_id,
            lesson_status="incomplete",
            lesson_location="Summary",
            suspend_data="blob",
            session_time_seconds=150,
        )
        await self._reload(row)

        self.assertEqual(row.lesson_location, "Summary")
        self.assertIsNotNone(row.last_accessed_at)

    async def test_upsert_updates_the_row_the_second_time(self):
        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.IN_PROGRESS
        )
        first = await self.repo.upsert(
            self.session, training.training_id, lesson_location="Intro"
        )
        await self._reload(first)
        first_progress_id = first.progress_id
        first_accessed_at = first.last_accessed_at

        second = await self.repo.upsert(
            self.session, training.training_id, lesson_location="Summary"
        )
        await self._reload(second)

        self.assertEqual(second.progress_id, first_progress_id)
        self.assertEqual(second.lesson_location, "Summary")
        self.assertGreater(second.last_accessed_at, first_accessed_at)

    async def test_upsert_stores_suspend_data_far_past_the_scorm_limit(self):
        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.IN_PROGRESS
        )
        blob = "z" * 40000

        row = await self.repo.upsert(
            self.session, training.training_id, suspend_data=blob
        )
        await self._reload(row)

        self.assertEqual(row.suspend_data, blob)

    async def _statements_of_upsert(self, **columns):
        """Every statement the call sends, compiled for Postgres."""
        from sqlalchemy import event
        from sqlalchemy.dialects import postgresql

        captured = []

        def capture(conn, clauseelement, multiparams, params, execution_options):
            captured.append(clauseelement)

        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.IN_PROGRESS
        )
        event.listen(self.connection.sync_connection, "before_execute", capture)
        try:
            await self.repo.upsert(self.session, training.training_id, **columns)
        finally:
            event.remove(self.connection.sync_connection, "before_execute", capture)

        return [
            str(statement.compile(dialect=postgresql.dialect()))
            for statement in captured
            if hasattr(statement, "compile")
        ]

    async def test_upsert_writes_without_reading_first(self):
        """Get-then-insert leaves a window: two overlapping first commits both
        read no row, and the second insert violates the unique constraint on
        training_id, 500s the request, and takes that learner's status write
        down with it. One statement has no such window."""
        statements = await self._statements_of_upsert(lesson_location="Intro")

        self.assertEqual(len(statements), 1, f"Expected one statement: {statements}")

    async def test_upsert_resolves_a_conflicting_insert_into_an_update(self):
        statements = await self._statements_of_upsert(lesson_location="Intro")

        self.assertIn("ON CONFLICT", statements[0])
        self.assertIn("DO UPDATE", statements[0])

    async def test_upsert_with_no_columns_still_stamps_the_row(self):
        """The service can reach here with nothing but a status decision."""
        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.IN_PROGRESS
        )

        row = await self.repo.upsert(self.session, training.training_id)
        await self._reload(row)

        self.assertIsNotNone(row.last_accessed_at)
        self.assertEqual(row.session_time_seconds, 0)

    async def test_upsert_leaves_columns_it_was_not_given_alone(self):
        """A partial commit must not blank what an earlier one stored."""
        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.IN_PROGRESS
        )
        await self.repo.upsert(
            self.session,
            training.training_id,
            lesson_location="Intro",
            suspend_data="blob",
        )

        row = await self.repo.upsert(
            self.session, training.training_id, lesson_location="Summary"
        )
        await self._reload(row)

        self.assertEqual(row.lesson_location, "Summary")
        self.assertEqual(row.suspend_data, "blob")

    async def test_upsert_returns_the_row_the_caller_already_holds(self):
        """The service reads the row before it writes; the object it is
        holding has to end up carrying what was written."""
        training = await self._assign(
            self.user_ids[0], self.course_id, TrainingStatus.IN_PROGRESS
        )
        await self.repo.upsert(
            self.session, training.training_id, lesson_location="Intro"
        )
        held = await self.repo.get_by_training_id(self.session, training.training_id)

        returned = await self.repo.upsert(
            self.session, training.training_id, lesson_location="Summary"
        )

        self.assertIs(returned, held)
        self.assertEqual(held.lesson_location, "Summary")


if __name__ == "__main__":
    unittest.main()
