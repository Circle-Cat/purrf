"""The gate between uploading a course and anybody being given it."""

import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.exc import IntegrityError

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    TrainingCategory,
    TrainingPackageState,
    TrainingStatus,
)
from backend.dto.training_course_dto import (
    TrainingAssignmentRequestDto,
    TrainingBulkAssignmentRequestDto,
)
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_entity import TrainingEntity
from backend.training.training_assignment_service import TrainingAssignmentService

_VERIFIED_AT = datetime.datetime(2026, 9, 1, 12, 7, tzinfo=datetime.timezone.utc)
_COURSE_ID = 3
_USER_ID = 11


def _course(**overrides):
    defaults = {
        "course_id": 3,
        "name": "Mentee Onboarding",
        "category": TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
        "is_active": True,
    }
    return TrainingCourseEntity(**{**defaults, **overrides})


class _AssignmentServiceCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.course = _course()
        self.courses = MagicMock()
        self.courses.get_course_by_id = AsyncMock(return_value=self.course)
        self.trainings = MagicMock()
        self.trainings.get_training_by_user_id_and_course_id = AsyncMock(
            return_value=None
        )
        self.trainings.get_training_by_user_id_and_category = AsyncMock(
            return_value=None
        )
        self.trainings.get_training_by_user_ids_and_course_id = AsyncMock(
            return_value={}
        )
        self.trainings.get_training_by_user_ids_and_categories = AsyncMock(
            return_value=[]
        )
        self.package_repository = MagicMock()
        self.package_repository.get_by_state = AsyncMock(
            return_value=MagicMock(verified_completable_at=_VERIFIED_AT)
        )
        self.service = TrainingAssignmentService(
            logger=MagicMock(),
            training_course_repository=self.courses,
            training_repository=self.trainings,
            training_course_package_repository=self.package_repository,
        )
        self.payload = TrainingAssignmentRequestDto(user_id=11, course_id=3)
        # Aliases matching the repositories' role in start_trial's tests.
        self.course_repository = self.courses
        self.training_repository = self.trainings

        # Records the order the write, the flush and the commit happen in.
        # add() is synchronous in SQLAlchemy, unlike the session itself.
        self.calls = []
        self.session.add = MagicMock(
            side_effect=lambda entity: self.calls.append(("add", entity))
        )
        # The batch path writes the whole cohort through add_all, so record it
        # the same way -- otherwise a batch looks like it wrote nothing.
        self.session.add_all = MagicMock(
            side_effect=lambda entities: self.calls.extend(
                ("add", entity) for entity in entities
            )
        )
        self.session.flush = AsyncMock(side_effect=self._stamp_training_id)
        self.session.commit = AsyncMock(
            side_effect=lambda: self.calls.append(("commit",))
        )

    async def _stamp_training_id(self):
        # flush() is what gives the new row its training_id.
        self.calls.append(("flush",))
        for call in self.session.add.call_args_list:
            call.args[0].training_id = 42

    def _slots(self, *, live=None, pending=None) -> None:
        """Makes `get_by_state` answer per state, the way the two real
        partial unique indexes keep them: a live row and a pending row,
        asked for and answered independently.
        """

        async def _get_by_state(session, course_id, state):
            return live if state == TrainingPackageState.LIVE else pending

        self.package_repository.get_by_state.side_effect = _get_by_state


class TestTrainingAssignmentService(_AssignmentServiceCase):
    async def test_assigns_a_course_with_a_live_package(self):
        result = await self.service.assign(self.session, self.payload)

        self.assertTrue(result.created)
        self.assertEqual(result.user_id, 11)
        self.assertEqual(result.course_id, 3)
        added = self.session.add.call_args.args[0]
        self.assertEqual(added.status, TrainingStatus.TO_DO)
        self.assertEqual(added.course_id, 3)
        self.assertEqual([step[0] for step in self.calls], ["add", "flush", "commit"])

    async def test_refuses_to_assign_a_course_with_no_live_package(self):
        self.package_repository.get_by_state.return_value = None

        with self.assertRaises(ConflictError):
            await self.service.assign(self.session, self.payload)

        self.session.add.assert_not_called()
        self.session.commit.assert_not_awaited()

    async def test_assign_reads_the_live_slot(self):
        result = await self.service.assign(self.session, self.payload)

        self.assertTrue(result.created)
        self.package_repository.get_by_state.assert_awaited_once_with(
            self.session, 3, TrainingPackageState.LIVE
        )

    async def test_deactivated_course_is_refused(self):
        self.courses.get_course_by_id.return_value = _course(is_active=False)

        with self.assertRaisesRegex(ConflictError, "deactivated"):
            await self.service.assign(self.session, self.payload)

        self.session.add.assert_not_called()
        self.session.commit.assert_not_awaited()

    async def test_missing_course_is_a_value_error(self):
        self.courses.get_course_by_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.assign(self.session, self.payload)

        self.session.commit.assert_not_awaited()

    async def test_assigning_twice_is_a_no_op(self):
        """Not an error: (user_id, course_id) is uniquely indexed."""
        self.trainings.get_training_by_user_id_and_course_id.return_value = (
            TrainingEntity(training_id=99, user_id=11, course_id=3)
        )

        result = await self.service.assign(self.session, self.payload)

        self.assertFalse(result.created)
        self.assertEqual(result.training_id, 99)
        self.session.add.assert_not_called()
        self.session.commit.assert_not_awaited()

    async def test_repeat_assignment_never_overwrites_an_existing_deadline(self):
        """Registration stamps a deadline once; this must not be a second way
        to move it."""
        existing = TrainingEntity(
            training_id=99,
            user_id=11,
            course_id=3,
            deadline=datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc),
        )
        self.trainings.get_training_by_user_id_and_course_id.return_value = existing

        await self.service.assign(
            self.session,
            TrainingAssignmentRequestDto(
                user_id=11,
                course_id=3,
                deadline=datetime.datetime(2027, 1, 1, tzinfo=datetime.timezone.utc),
            ),
        )

        self.assertEqual(
            existing.deadline,
            datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc),
        )

    async def test_an_empty_deadline_is_allowed(self):
        """ensure_for_admitted already creates rows without one."""
        await self.service.assign(self.session, self.payload)

        self.assertIsNone(self.session.add.call_args.args[0].deadline)

    async def test_category_is_copied_from_the_course(self):
        """So registration and the matching gate read as they always did."""
        await self.service.assign(self.session, self.payload)

        self.assertEqual(
            self.session.add.call_args.args[0].category,
            TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
        )

    async def test_a_course_without_a_category_assigns_with_none(self):
        self.courses.get_course_by_id.return_value = _course(category=None)

        await self.service.assign(self.session, self.payload)

        self.assertIsNone(self.session.add.call_args.args[0].category)

    async def test_a_trial_reads_the_pending_slot_not_the_live_one(self):
        """A trial exists to verify a package before it is published, so it
        must run the staged copy, never the one already serving learners."""
        self.course_repository.get_course_by_id.return_value = TrainingCourseEntity(
            course_id=_COURSE_ID,
            name="Mentor Onboarding",
            is_active=True,
        )
        self._slots(live=None, pending=MagicMock(package_id=2))

        result = await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

        self.assertEqual(result.user_id, _USER_ID)
        self.assertEqual(result.course_id, _COURSE_ID)
        self.assertTrue(result.created)
        self.package_repository.get_by_state.assert_awaited_once_with(
            self.session, _COURSE_ID, TrainingPackageState.PENDING
        )

    async def test_a_second_trial_reuses_the_first_assignment(self):
        """So a verifier who stops and comes back resumes where they were."""
        self.training_repository.get_training_by_user_id_and_course_id.return_value = (
            TrainingEntity(training_id=42, user_id=_USER_ID, course_id=_COURSE_ID)
        )

        result = await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

        self.assertEqual(result.training_id, 42)
        self.assertFalse(result.created)

    async def test_a_trial_on_a_course_with_no_package_is_refused(self):
        self.course_repository.get_course_by_id.return_value = TrainingCourseEntity(
            course_id=_COURSE_ID,
            name="Empty",
            is_active=True,
        )
        self.package_repository.get_by_state.return_value = None

        with self.assertRaises(ConflictError):
            await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

    async def test_a_trial_carries_the_courses_category_like_an_assignment_does(self):
        """A seed course's category is what opens the mentorship gate."""
        self.course_repository.get_course_by_id.return_value = TrainingCourseEntity(
            course_id=_COURSE_ID,
            name="Mentor Onboarding",
            category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
            is_active=True,
        )

        await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

        added = self.session.add.call_args.args[0]
        self.assertEqual(added.category, TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING)

    async def test_a_deactivated_course_can_still_be_trialled(self):
        """assign checks is_active on its own, so a trial does not have to:
        stamping a deactivated course does not make it assignable."""
        self.course_repository.get_course_by_id.return_value = TrainingCourseEntity(
            course_id=_COURSE_ID,
            name="Mentor Onboarding",
            is_active=False,
        )

        result = await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

        self.assertTrue(result.created)

    async def test_a_row_held_by_category_is_adopted_rather_than_doubled(self):
        """The onboarding dispatch owns the same pairing under a category. A
        second row for one category makes every later read of it raise, and
        the partial unique index does not stop the insert."""
        by_category = TrainingEntity(
            training_id=77,
            user_id=11,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            course_id=None,
        )
        self.trainings.get_training_by_user_id_and_category.return_value = by_category

        result = await self.service.assign(self.session, self.payload)

        self.assertFalse(result.created)
        self.assertEqual(result.training_id, 77)
        self.assertEqual(by_category.course_id, 3)
        self.session.add.assert_not_called()
        self.session.commit.assert_awaited_once()

    async def test_adopting_a_category_row_leaves_the_rest_of_it_alone(self):
        stamped = datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc)
        by_category = TrainingEntity(
            training_id=77,
            user_id=11,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            course_id=None,
            status=TrainingStatus.IN_PROGRESS,
            deadline=stamped,
            link="https://mentee",
        )
        self.trainings.get_training_by_user_id_and_category.return_value = by_category

        await self.service.assign(
            self.session,
            TrainingAssignmentRequestDto(
                user_id=11,
                course_id=3,
                deadline=datetime.datetime(2027, 1, 1, tzinfo=datetime.timezone.utc),
            ),
        )

        self.assertEqual(by_category.deadline, stamped)
        self.assertEqual(by_category.status, TrainingStatus.IN_PROGRESS)
        self.assertEqual(by_category.link, "https://mentee")

    async def test_a_course_without_a_category_is_not_looked_up_by_one(self):
        self.courses.get_course_by_id.return_value = _course(category=None)

        await self.service.assign(self.session, self.payload)

        self.trainings.get_training_by_user_id_and_category.assert_not_awaited()
        self.session.add.assert_called_once()

    async def test_a_trial_adopts_a_category_row_too(self):
        """A verifier who already holds the seed course by category must not
        end up with two rows for it either."""
        by_category = TrainingEntity(
            training_id=77,
            user_id=_USER_ID,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            course_id=None,
        )
        self.trainings.get_training_by_user_id_and_category.return_value = by_category

        result = await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

        self.assertFalse(result.created)
        self.assertEqual(result.training_id, 77)
        self.assertEqual(by_category.course_id, _COURSE_ID)
        self.session.add.assert_not_called()

    async def test_adopting_a_category_row_on_a_trial_is_persisted(self):
        """The attachment is a write, so the trial path has to commit it too.

        Nothing else does: the adopt branch returns before the insert, and the
        session rolls back at the end of the request otherwise.
        """
        by_category = TrainingEntity(
            training_id=77,
            user_id=_USER_ID,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            course_id=None,
        )
        self.trainings.get_training_by_user_id_and_category.return_value = by_category

        await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

        self.session.commit.assert_awaited_once()


class TestTheAssignmentGateReadsTheLiveSlot(_AssignmentServiceCase):
    async def test_a_course_with_a_live_package_can_be_assigned(self):
        # Only a verified package can be published, so a live row is proof
        # enough on its own -- the stamp is an archival fact from here on.
        live = MagicMock(package_id=1, verified_completable_at=None)
        self._slots(live=live, pending=None)

        result = await self.service.assign(self.session, self.payload)

        self.assertTrue(result.created)

    async def test_a_course_with_only_a_staged_package_cannot_be_assigned(self):
        self._slots(live=None, pending=MagicMock(package_id=2))

        with self.assertRaises(ConflictError):
            await self.service.assign(self.session, self.payload)

    async def test_a_deactivated_course_still_cannot_be_assigned(self):
        self._slots(live=MagicMock(package_id=1), pending=None)
        self.course.is_active = False

        with self.assertRaises(ConflictError):
            await self.service.assign(self.session, self.payload)


class TestTrialRunsTheStagedPackage(_AssignmentServiceCase):
    async def test_a_course_with_nothing_staged_has_nothing_to_trial(self):
        self._slots(live=MagicMock(package_id=1), pending=None)

        with self.assertRaises(ConflictError):
            await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

    async def test_a_staged_package_can_be_trialled(self):
        self._slots(live=None, pending=MagicMock(package_id=2))

        result = await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

        self.assertTrue(result.created)


class TestBulkAssignment(_AssignmentServiceCase):
    """Assigning one course to a whole cohort, in one transaction."""

    def _held_by(self, *user_ids):
        """Makes the per-course lookup answer only for these people."""
        held = {
            user_id: TrainingEntity(
                training_id=900 + user_id,
                user_id=user_id,
                course_id=_COURSE_ID,
                category=self.course.category,
                status=TrainingStatus.IN_PROGRESS,
                deadline=_VERIFIED_AT,
            )
            for user_id in user_ids
        }
        self.trainings.get_training_by_user_ids_and_course_id = AsyncMock(
            return_value=held
        )
        return held

    def _payload(self, *user_ids, deadline=None):
        return TrainingBulkAssignmentRequestDto(
            course_id=_COURSE_ID, user_ids=list(user_ids), deadline=deadline
        )

    def _added(self):
        # calls holds ("add", entity) but also bare ("flush",) / ("commit",).
        return [call[1] for call in self.calls if call[0] == "add"]

    async def test_a_course_with_nothing_live_refuses_the_whole_batch(self):
        self._slots(live=None)

        with self.assertRaises(ConflictError):
            await self.service.assign_bulk(self.session, self._payload(11, 12))

        self.assertEqual(self._added(), [])
        self.session.commit.assert_not_awaited()

    async def test_a_deactivated_course_refuses_the_whole_batch(self):
        self.courses.get_course_by_id = AsyncMock(return_value=_course(is_active=False))

        with self.assertRaises(ConflictError):
            await self.service.assign_bulk(self.session, self._payload(11, 12))

        self.assertEqual(self._added(), [])
        self.session.commit.assert_not_awaited()

    async def test_a_course_that_does_not_exist_refuses_the_whole_batch(self):
        self.courses.get_course_by_id = AsyncMock(return_value=None)

        with self.assertRaises(ValueError):
            await self.service.assign_bulk(self.session, self._payload(11, 12))

        self.assertEqual(self._added(), [])

    async def test_each_person_gets_the_row_the_dispatch_writes(self):
        deadline = _VERIFIED_AT

        await self.service.assign_bulk(
            self.session, self._payload(11, 12, deadline=deadline)
        )

        added = self._added()
        self.assertEqual([row.user_id for row in added], [11, 12])
        for row in added:
            self.assertEqual(row.course_id, _COURSE_ID)
            self.assertEqual(row.category, self.course.category)
            self.assertEqual(row.status, TrainingStatus.TO_DO)
            self.assertEqual(row.deadline, deadline)
            self.assertIsNone(row.link)

    async def test_an_empty_deadline_stays_empty(self):
        await self.service.assign_bulk(self.session, self._payload(11))

        self.assertIsNone(self._added()[0].deadline)

    async def test_somebody_who_already_holds_the_course_is_left_alone(self):
        held = self._held_by(11)

        await self.service.assign_bulk(self.session, self._payload(11, 12))

        self.assertEqual([row.user_id for row in self._added()], [12])
        self.assertEqual(held[11].deadline, _VERIFIED_AT)
        self.assertEqual(held[11].status, TrainingStatus.IN_PROGRESS)

    async def test_the_batch_reports_what_it_created_and_what_it_skipped(self):
        self._held_by(11)

        result = await self.service.assign_bulk(self.session, self._payload(11, 12, 13))

        self.assertEqual(result.course_id, _COURSE_ID)
        self.assertEqual(result.created_count, 2)
        self.assertEqual(result.already_assigned_count, 1)

    async def test_the_whole_batch_is_one_commit(self):
        await self.service.assign_bulk(self.session, self._payload(11, 12, 13))

        self.assertEqual([call[0] for call in self.calls].count("commit"), 1)
        self.assertEqual(self.calls[-1], ("commit",))

    async def test_a_failing_write_commits_nothing(self):
        self.session.flush = AsyncMock(
            side_effect=RuntimeError("the database went away")
        )

        with self.assertRaises(RuntimeError):
            await self.service.assign_bulk(self.session, self._payload(11, 12, 13))

        self.session.commit.assert_not_awaited()

    async def test_a_repeated_id_is_assigned_once(self):
        result = await self.service.assign_bulk(self.session, self._payload(11, 11))

        self.assertEqual([row.user_id for row in self._added()], [11])
        self.assertEqual(result.created_count, 1)
        self.assertEqual(result.already_assigned_count, 0)

    async def test_the_course_is_gated_once_however_many_people(self):
        await self.service.assign_bulk(self.session, self._payload(11, 12, 13))

        self.courses.get_course_by_id.assert_awaited_once()
        self.package_repository.get_by_state.assert_awaited_once()


class TestBulkAssignmentReadsInBatches(_AssignmentServiceCase):
    """One batch is a handful of queries, not a handful per person.

    The cap on one batch is a thousand people. Looking each of them up on
    their own would be thousands of sequential round trips inside one open
    write transaction, and a gateway timeout would discard the lot.
    """

    def _payload(self, *user_ids, deadline=None):
        return TrainingBulkAssignmentRequestDto(
            course_id=_COURSE_ID, user_ids=list(user_ids), deadline=deadline
        )

    async def test_holders_are_looked_up_in_one_query_for_the_whole_batch(self):
        await self.service.assign_bulk(self.session, self._payload(11, 12, 13))

        self.trainings.get_training_by_user_ids_and_course_id.assert_awaited_once_with(
            self.session, [11, 12, 13], _COURSE_ID
        )
        self.trainings.get_training_by_user_id_and_course_id.assert_not_awaited()

    async def test_legacy_category_rows_are_looked_up_in_one_query(self):
        await self.service.assign_bulk(self.session, self._payload(11, 12))

        self.trainings.get_training_by_user_ids_and_categories.assert_awaited_once_with(
            self.session, [11, 12], [self.course.category]
        )
        self.trainings.get_training_by_user_id_and_category.assert_not_awaited()

    async def test_a_course_with_no_category_asks_no_category_question(self):
        self.courses.get_course_by_id = AsyncMock(return_value=_course(category=None))

        await self.service.assign_bulk(self.session, self._payload(11, 12))

        self.trainings.get_training_by_user_ids_and_categories.assert_not_awaited()

    async def test_the_whole_batch_is_written_in_one_flush(self):
        await self.service.assign_bulk(self.session, self._payload(11, 12, 13))

        self.assertEqual(
            [call[0] for call in self.calls],
            ["add", "add", "add", "flush", "commit"],
        )

    async def test_a_person_who_already_holds_the_course_is_skipped(self):
        held = TrainingEntity(
            training_id=99, user_id=11, course_id=_COURSE_ID, deadline=_VERIFIED_AT
        )
        self.trainings.get_training_by_user_ids_and_course_id.return_value = {11: held}

        result = await self.service.assign_bulk(self.session, self._payload(11, 12))

        added = [call[1] for call in self.calls if call[0] == "add"]
        self.assertEqual([row.user_id for row in added], [12])
        self.assertEqual(result.created_count, 1)
        self.assertEqual(result.already_assigned_count, 1)
        self.assertEqual(held.deadline, _VERIFIED_AT)

    async def test_a_legacy_row_is_adopted_rather_than_doubled(self):
        legacy = TrainingEntity(
            training_id=77,
            user_id=11,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            course_id=None,
        )
        self.trainings.get_training_by_user_ids_and_categories.return_value = [legacy]

        result = await self.service.assign_bulk(self.session, self._payload(11))

        self.assertEqual(legacy.course_id, _COURSE_ID)
        self.assertEqual([call[0] for call in self.calls], ["flush", "commit"])
        self.assertEqual(result.attached_count, 1)

    async def test_an_adopted_row_is_reported_as_attached_not_as_already_held(self):
        """Repointing 50 legacy rows must not report "0 assigned, 50 already
        had this course" -- the operator would read that as nothing happened."""
        legacy = TrainingEntity(
            training_id=77,
            user_id=11,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            course_id=None,
        )
        self.trainings.get_training_by_user_ids_and_categories.return_value = [legacy]

        result = await self.service.assign_bulk(self.session, self._payload(11))

        self.assertEqual(result.already_assigned_count, 0)
        self.assertEqual(result.created_count, 0)
        self.assertEqual(result.attached_count, 1)

    async def test_a_legacy_row_that_already_points_somewhere_is_left_alone(self):
        legacy = TrainingEntity(
            training_id=77,
            user_id=11,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            course_id=999,
        )
        self.trainings.get_training_by_user_ids_and_categories.return_value = [legacy]

        result = await self.service.assign_bulk(self.session, self._payload(11))

        self.assertEqual(legacy.course_id, 999)
        self.assertEqual(result.created_count, 1)
        self.assertEqual(result.attached_count, 0)

    async def test_somebody_who_no_longer_exists_is_a_conflict_not_a_crash(self):
        """A person offboarded between the search and the click. The batch is
        lost either way, but a 409 says why and a 500 does not."""
        self.session.flush = AsyncMock(
            side_effect=IntegrityError("insert", {}, Exception("fk violation"))
        )

        with self.assertRaises(ConflictError):
            await self.service.assign_bulk(self.session, self._payload(11, 12))

        self.session.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
