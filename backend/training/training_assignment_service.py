"""Assigning a course to a person, by hand.

Automatic dispatch is a later piece of work. The existing mentorship dispatch
(``OnboardingTrainingService.ensure_for_admitted``) keeps working untouched and
attaches the seed course its category stands for, so both paths write the same
shape of row.

The two paths can reach the same person for the same seed course, and only one
row may exist for a category: ``TrainingRepository.get_training_by_user_id_and_category``
reads it with ``one_or_none()``, so a second row would raise for that user for
good. Assignment therefore adopts a category row it finds rather than inserting
beside it.
"""

from sqlalchemy.exc import IntegrityError

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import TrainingPackageState, TrainingStatus
from backend.dto.training_course_dto import (
    TrainingAssignmentRequestDto,
    TrainingAssignmentResultDto,
    TrainingBulkAssignmentRequestDto,
    TrainingBulkAssignmentResultDto,
)
from backend.entity.training_entity import TrainingEntity


class TrainingAssignmentService:
    """The one gate between the admin side and the learner side."""

    def __init__(
        self,
        logger,
        training_course_repository,
        training_repository,
        training_course_package_repository,
    ):
        """
        Args:
            logger: Injected logger.
            training_course_repository (TrainingCourseRepository): Reads the
                course being assigned.
            training_repository (TrainingRepository): Reads and writes the
                assignment rows.
            training_course_package_repository (TrainingCoursePackageRepository):
                Reads the course's package slots -- the live one is what
                decides assignability, the pending one is what a trial run
                verifies.
        """
        self.logger = logger
        self.training_course_repository = training_course_repository
        self.training_repository = training_repository
        self.training_course_package_repository = training_course_package_repository

    async def _assignable_course(self, session, course_id: int):
        """The course, checked once for whether it may be assigned at all.

        A live package plus `is_active`, and a live package is proof enough on
        its own: `publish_package` only promotes a pending package that
        already carries a verification stamp, so an unverified course can no
        longer reach this point. That is what the gate is for -- an
        unfinishable course holds everyone assigned to it at the mentorship
        matching gate, silently, and looks like our bug.

        Assignability is a property of the course, not of the person, so a
        batch checks it once and either writes for everybody or nobody.

        Args:
            session: The active async database session.
            course_id (int): The course being assigned.

        Returns:
            TrainingCourseEntity: The course, safe to assign.

        Raises:
            ValueError: No such course.
            ConflictError: Nothing published yet, or deactivated. Surfaces
                as 409.
        """
        course = await self.training_course_repository.get_course_by_id(
            session, course_id
        )
        if course is None:
            raise ValueError(f"No training course with id {course_id}.")

        package = await self.training_course_package_repository.get_by_state(
            session, course.course_id, TrainingPackageState.LIVE
        )
        if package is None:
            raise ConflictError(
                "This course has nothing published yet, so it cannot be "
                "assigned. Upload a package, run it to completion, and "
                "publish it first."
            )

        if not course.is_active:
            raise ConflictError(
                "This course is deactivated and cannot be assigned to anybody new."
            )
        return course

    @staticmethod
    def _new_row(course, user_id: int, deadline) -> TrainingEntity:
        """The row both paths write, so neither can drift from the other.

        Identical to what automatic dispatch writes: the category follows the
        course so registration and the mentorship matching gate keep reading
        as they expect, and there is no link -- the course is served in app.

        Args:
            course (TrainingCourseEntity): The gated course.
            user_id (int): Who is being assigned.
            deadline (datetime | None): The deadline to stamp, or None.

        Returns:
            TrainingEntity: The unsaved row.
        """
        return TrainingEntity(
            user_id=user_id,
            course_id=course.course_id,
            category=course.category,
            status=TrainingStatus.TO_DO,
            deadline=deadline,
            link=None,
        )

    async def _assign_one(
        self, session, course, user_id: int, deadline
    ) -> tuple[TrainingAssignmentResultDto, bool]:
        """One person's row for an already-gated course, without committing.

        The transaction belongs to the caller: one person commits right after,
        a batch commits once at the end, so a batch that fails partway writes
        nothing at all.

        Args:
            session: The active async database session.
            course (TrainingCourseEntity): The gated course.
            user_id (int): Who is being assigned.
            deadline (datetime | None): The deadline to stamp on a new row.

        Returns:
            tuple[TrainingAssignmentResultDto, bool]: The assignment, and
            whether this call changed anything -- a fresh row, or a category
            row adopted. False means the person already held the course and
            nothing was touched.
        """
        existing, adopted = await self._existing_assignment(session, user_id, course)
        if existing is not None:
            return (
                TrainingAssignmentResultDto(
                    training_id=existing.training_id,
                    user_id=existing.user_id,
                    course_id=course.course_id,
                    created=False,
                ),
                adopted,
            )

        assignment = self._new_row(course, user_id, deadline)
        session.add(assignment)
        await session.flush()

        self.logger.info(
            "[TrainingAssignmentService] assigned course %s to user %s",
            course.course_id,
            user_id,
        )
        return (
            TrainingAssignmentResultDto(
                training_id=assignment.training_id,
                user_id=assignment.user_id,
                course_id=course.course_id,
                created=True,
            ),
            True,
        )

    async def assign_bulk(
        self, session, payload: TrainingBulkAssignmentRequestDto
    ) -> TrainingBulkAssignmentResultDto:
        """Give one course to a whole cohort, in one transaction.

        The course is gated once; anybody who already holds it is skipped and
        their row is left exactly as it stands, a deadline stamped by
        registration above all. Nothing is written unless everything is, so a
        failure partway leaves no half-assigned cohort -- and retrying is safe,
        because per-person assignment is idempotent.

        Args:
            session: The active async database session.
            payload (TrainingBulkAssignmentRequestDto): The course, the ids,
                and an optional deadline for the new rows.

        Returns:
            TrainingBulkAssignmentResultDto: How many rows were created, how
            many legacy category rows were pointed at the course, and how many
            people already held it.

        Raises:
            ValueError: No such course.
            ConflictError: The course has no live package, is deactivated, or
                one of the submitted people no longer exists.
        """
        course = await self._assignable_course(session, payload.course_id)

        # An id repeated in one request is one person: assigning them twice
        # would report a phantom row that was never written.
        user_ids = list(dict.fromkeys(payload.user_ids))

        # Two reads for the whole cohort rather than two per person. A batch
        # runs to a thousand people, and per-person lookups would be thousands
        # of sequential round trips with a write transaction held open.
        held_by_user_id = (
            await self.training_repository.get_training_by_user_ids_and_course_id(
                session, user_ids, course.course_id
            )
        )
        adoptable_by_user_id = {}
        if course.category is not None:
            category_rows = (
                await self.training_repository.get_training_by_user_ids_and_categories(
                    session, user_ids, [course.category]
                )
            )
            # Only a row with no course of its own is this assignment; one
            # already pointing elsewhere belongs to another course.
            adoptable_by_user_id = {
                row.user_id: row for row in category_rows if row.course_id is None
            }

        created_count = 0
        attached_count = 0
        already_assigned_count = 0
        new_rows = []
        for user_id in user_ids:
            if user_id in held_by_user_id:
                already_assigned_count += 1
                continue
            adoptable = adoptable_by_user_id.get(user_id)
            if adoptable is not None:
                # Given the course_id it was missing, and nothing else: a
                # deadline registration stamped stays as it is.
                adoptable.course_id = course.course_id
                attached_count += 1
                continue
            new_rows.append(self._new_row(course, user_id, payload.deadline))
            created_count += 1

        if new_rows:
            session.add_all(new_rows)

        if new_rows or attached_count:
            try:
                await session.flush()
            except IntegrityError as error:
                # The one referential thing a submitted id can break: somebody
                # offboarded between the search and the click. The batch is
                # lost either way, but a 409 says why where a 500 does not.
                raise ConflictError(
                    "One of the selected people no longer exists. "
                    "Search again and reassign."
                ) from error
            await session.commit()

        self.logger.info(
            "[TrainingAssignmentService] bulk assigned course %s: "
            "created %s, attached %s, already assigned %s",
            payload.course_id,
            created_count,
            attached_count,
            already_assigned_count,
        )
        return TrainingBulkAssignmentResultDto(
            course_id=payload.course_id,
            created_count=created_count,
            attached_count=attached_count,
            already_assigned_count=already_assigned_count,
        )

    async def assign(
        self, session, payload: TrainingAssignmentRequestDto
    ) -> TrainingAssignmentResultDto:
        """Give one person one course.

        The gate is a live package plus `is_active`. A live package is proof
        enough on its own: `publish_package` only promotes a pending package
        that already carries a verification stamp, so an unverified course
        can no longer reach this point at all. That is what the gate is for
        -- an unfinishable course holds everyone assigned to it at the
        mentorship matching gate, silently, and looks like our bug. A course
        with nothing live yet is refused for that same reason. Neither can a
        deactivated one.

        Assigning twice is a no-op rather than an error, and never rewrites the
        existing row -- in particular a deadline already stamped by
        registration stays put.

        Args:
            session: The active async database session.
            payload (TrainingAssignmentRequestDto): Who, which course, and an
                optional deadline.

        Returns:
            TrainingAssignmentResultDto: The assignment, and whether this call
            is what created it.

        Raises:
            ValueError: No such course.
            ConflictError: The course has no live package, or is deactivated.
                Surfaces as 409.
        """
        course = await self._assignable_course(session, payload.course_id)
        result, changed = await self._assign_one(
            session, course, payload.user_id, payload.deadline
        )
        if changed:
            await session.commit()
        return result

    async def start_trial(
        self, session, course_id: int, user_id: int
    ) -> TrainingAssignmentResultDto:
        """Open the caller's own assignment so they can verify a package.

        Reads the PENDING slot, not the LIVE one `assign` reads: a trial run
        exists to verify a package before it can be published, and a staged
        package is exactly what a trial is for -- requiring it to already be
        live would be circular. This is also why `start_trial` can skip
        `assign`'s `is_active` check: stamping a deactivated course still
        leaves it deactivated, since `assign` checks `is_active` on its own,
        so skipping it here buys no safety back -- and it supports a real
        sequence, a broken course gets deactivated, re-exported, re-uploaded,
        trialled, then reactivated. Beyond that it is an ordinary assignment,
        because a trial that ran through different code would prove less
        than one that runs through the learner's own path.

        Args:
            session: The active async database session.
            course_id (int): The course being verified.
            user_id (int): The verifier, from the authenticated caller.

        Returns:
            TrainingAssignmentResultDto: The assignment to open.

        Raises:
            ValueError: No such course.
            ConflictError: The course has no staged package to run.
        """
        course = await self.training_course_repository.get_course_by_id(
            session, course_id
        )
        if course is None:
            raise ValueError(f"No training course with id {course_id}.")

        package = await self.training_course_package_repository.get_by_state(
            session, course_id, TrainingPackageState.PENDING
        )
        if package is None:
            raise ConflictError(
                "There is no staged package on this course to run. Upload one first."
            )

        existing, adopted = await self._existing_assignment(session, user_id, course)
        if existing is not None:
            # Adopting attaches the course_id to a row that was missing it,
            # which is a write on a path that is otherwise a read.
            if adopted:
                await session.commit()
            return TrainingAssignmentResultDto(
                training_id=existing.training_id,
                user_id=existing.user_id,
                course_id=course_id,
                created=False,
            )

        assignment = TrainingEntity(
            user_id=user_id,
            course_id=course_id,
            # Kept in step with the course, same as assign: this is what lets
            # a trial run open the mentorship matching gate for its verifier.
            category=course.category,
            status=TrainingStatus.TO_DO,
            deadline=None,
            link=None,
        )
        session.add(assignment)
        await session.flush()
        await session.commit()

        self.logger.info(
            "[TrainingAssignmentService] opened a trial run of course %s for user %s",
            course_id,
            user_id,
        )
        return TrainingAssignmentResultDto(
            training_id=assignment.training_id,
            user_id=assignment.user_id,
            course_id=course_id,
            created=True,
        )

    async def _existing_assignment(self, session, user_id: int, course):
        """The row this person already holds for this course, if any.

        Looked up twice. By course first, which is the ordinary repeat
        assignment. Then, for a course carrying a category, by that category:
        the mentorship dispatch owns the same pairing under a category and
        older rows of its making carry no course at all. Such a row is this
        assignment, so it is adopted -- given the course_id it was missing --
        rather than inserted beside, which would leave the person holding two
        rows for one category and raise on every later read of it.

        Only the course_id is written. Everything else the row already
        records, a deadline registration stamped above all, is left as it is.

        Args:
            session: The active async database session.
            user_id (int): Who is being assigned.
            course (TrainingCourseEntity): The course being assigned.

        Returns:
            tuple[TrainingEntity | None, bool]: The row already standing, or
            None, and whether adopting it wrote to it. The write is left
            uncommitted: the caller owns the transaction.
        """
        existing = await self.training_repository.get_training_by_user_id_and_course_id(
            session, user_id, course.course_id
        )
        if existing is not None:
            return existing, False

        if course.category is None:
            return None, False

        by_category = (
            await self.training_repository.get_training_by_user_id_and_category(
                session, user_id, course.category
            )
        )
        if by_category is None or by_category.course_id is not None:
            return by_category, False

        by_category.course_id = course.course_id
        self.logger.info(
            "[TrainingAssignmentService] attached course %s to user %s's "
            "existing %s row",
            course.course_id,
            user_id,
            course.category.value,
        )
        return by_category, True
