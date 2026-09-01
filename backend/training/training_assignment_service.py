"""Assigning a course to a person, by hand.

Automatic dispatch is a later piece of work. The existing mentorship dispatch
(``OnboardingTrainingService.ensure_for_admitted``) keeps working untouched;
its rows simply carry a ``course_id`` now.
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

        existing = await self.training_repository.get_training_by_user_id_and_course_id(
            session, payload.user_id, payload.course_id
        )
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
