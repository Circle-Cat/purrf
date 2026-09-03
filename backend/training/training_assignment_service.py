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

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import TrainingStatus
from backend.dto.training_course_dto import (
    TrainingAssignmentRequestDto,
    TrainingAssignmentResultDto,
)
from backend.entity.training_entity import TrainingEntity


class TrainingAssignmentService:
    """The one gate between the admin side and the learner side."""

    def __init__(self, logger, training_course_repository, training_repository):
        """
        Args:
            logger: Injected logger.
            training_course_repository (TrainingCourseRepository): Reads the
                course being assigned.
            training_repository (TrainingRepository): Reads and writes the
                assignment rows.
        """
        self.logger = logger
        self.training_course_repository = training_course_repository
        self.training_repository = training_repository

    async def assign(
        self, session, payload: TrainingAssignmentRequestDto
    ) -> TrainingAssignmentResultDto:
        """Give one person one course.

        A course nobody has finished cannot be assigned: an unfinishable course
        holds everyone assigned to it at the mentorship matching gate,
        silently, and looks like our bug. Neither can a deactivated one.

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
            ConflictError: The course is unverified or deactivated. Surfaces as
                409.
        """
        course = await self.training_course_repository.get_course_by_id(
            session, payload.course_id
        )
        if course is None:
            raise ValueError(f"No training course with id {payload.course_id}.")

        if course.verified_completable_at is None:
            raise ConflictError(
                "This course has not been run to completion yet, so it cannot "
                "be assigned. Start a trial run and finish it first."
            )

        if not course.is_active:
            raise ConflictError(
                "This course is deactivated and cannot be assigned to anybody new."
            )

        existing = await self._existing_assignment(session, payload.user_id, course)
        if existing is not None:
            return TrainingAssignmentResultDto(
                training_id=existing.training_id,
                user_id=existing.user_id,
                course_id=payload.course_id,
                created=False,
            )

        assignment = TrainingEntity(
            user_id=payload.user_id,
            course_id=payload.course_id,
            # Kept in step with the course so registration and the matching
            # gate keep reading as they expect.
            category=course.category,
            status=TrainingStatus.TO_DO,
            deadline=payload.deadline,
            link=None,
        )
        session.add(assignment)
        await session.flush()
        await session.commit()

        self.logger.info(
            "[TrainingAssignmentService] assigned course %s to user %s",
            payload.course_id,
            payload.user_id,
        )
        return TrainingAssignmentResultDto(
            training_id=assignment.training_id,
            user_id=assignment.user_id,
            course_id=payload.course_id,
            created=True,
        )

    async def start_trial(
        self, session, course_id: int, user_id: int
    ) -> TrainingAssignmentResultDto:
        """Open the caller's own assignment so they can verify a course.

        Deliberately skips two checks `assign` enforces. The verification
        gate (`verified_completable_at`) is what this call exists to answer,
        so it cannot also require it. The `is_active` check is skipped too:
        stamping a deactivated course still leaves it deactivated, since
        `assign` checks `is_active` on its own, so skipping it here buys no
        safety back -- and it supports a real sequence, a broken course gets
        deactivated, re-exported, re-uploaded, trialled, then reactivated.
        Beyond that it is an ordinary assignment, because a trial that ran
        through different code would prove less than one that runs through
        the learner's own path.

        Args:
            session: The active async database session.
            course_id (int): The course being verified.
            user_id (int): The verifier, from the authenticated caller.

        Returns:
            TrainingAssignmentResultDto: The assignment to open.

        Raises:
            ValueError: No such course.
            ConflictError: The course has no package to run.
        """
        course = await self.training_course_repository.get_course_by_id(
            session, course_id
        )
        if course is None:
            raise ValueError(f"No training course with id {course_id}.")

        if course.storage_prefix is None:
            raise ConflictError(
                "This course has no package uploaded yet, so there is nothing to run."
            )

        existing = await self._existing_assignment(session, user_id, course)
        if existing is not None:
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
            TrainingEntity | None: The row already standing, or None.
        """
        existing = await self.training_repository.get_training_by_user_id_and_course_id(
            session, user_id, course.course_id
        )
        if existing is not None:
            return existing

        if course.category is None:
            return None

        by_category = (
            await self.training_repository.get_training_by_user_id_and_category(
                session, user_id, course.category
            )
        )
        if by_category is None or by_category.course_id is not None:
            return by_category

        by_category.course_id = course.course_id
        await session.commit()
        self.logger.info(
            "[TrainingAssignmentService] attached course %s to user %s's "
            "existing %s row",
            course.course_id,
            user_id,
            course.category.value,
        )
        return by_category
