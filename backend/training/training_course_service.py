"""The course catalogue: what exists, and what may be assigned."""

from backend.dto.training_course_dto import (
    TrainingCourseCreateDto,
    TrainingCourseDto,
    TrainingCourseState,
    TrainingCourseUpdateDto,
)
from backend.entity.training_course_entity import TrainingCourseEntity


def derive_course_state(course: TrainingCourseEntity) -> TrainingCourseState:
    """Read a course's row as the one status the admin page shows.

    Order matters. Verification is checked before the package because a
    re-upload clears ``verified_completable_at`` and leaves the prefix in
    place: a course that has a package but no proof is NEEDS_TRIAL_RUN, never
    VERIFIED.

    The two package-less states are told apart by ``category``. A seed row
    carries one and still has a working environment-variable link behind it, so
    it is EXTERNAL_LINK -- not broken, just not hosted here. A course somebody
    created and never uploaded to has no category and nowhere to send a
    learner, so it is NO_PACKAGE.

    Args:
        course (TrainingCourseEntity): The row to read.

    Returns:
        TrainingCourseState: The single state for that row.
    """
    if course.storage_prefix:
        if course.verified_completable_at is not None:
            return TrainingCourseState.VERIFIED
        return TrainingCourseState.NEEDS_TRIAL_RUN
    if course.category is not None:
        return TrainingCourseState.EXTERNAL_LINK
    return TrainingCourseState.NO_PACKAGE


def to_course_dto(
    course: TrainingCourseEntity, assigned_count: int
) -> TrainingCourseDto:
    """Project one course row, plus its assignment count, for the API."""
    return TrainingCourseDto(
        course_id=course.course_id,
        name=course.name,
        description=course.description,
        category=course.category,
        is_active=course.is_active,
        state=derive_course_state(course),
        scorm_version=course.scorm_version,
        package_version=course.package_version,
        reporting_mode=course.reporting_mode,
        package_uploaded_at=course.package_uploaded_at,
        verified_completable_at=course.verified_completable_at,
        verified_by_user_id=course.verified_by_user_id,
        assigned_count=assigned_count,
    )


class TrainingCourseService:
    """Creating, listing and deactivating courses.

    Uploading a package is not here: it belongs with the storage and manifest
    handling that arrives with it.
    """

    def __init__(self, logger, training_course_repository):
        """
        Args:
            logger: Injected logger.
            training_course_repository (TrainingCourseRepository): Catalogue
                reads and writes.
        """
        self.logger = logger
        self.training_course_repository = training_course_repository

    async def list_courses(
        self, session, include_inactive: bool = True
    ) -> list[TrainingCourseDto]:
        """Every course, with its derived state and assignment count."""
        rows = await self.training_course_repository.list_courses(
            session, include_inactive=include_inactive
        )
        return [to_course_dto(course, count) for course, count in rows]

    async def create_course(
        self, session, payload: TrainingCourseCreateDto
    ) -> TrainingCourseDto:
        """Create a course with no package.

        It starts unassignable and stays that way until a package is uploaded
        and somebody runs it to completion.
        """
        course = TrainingCourseEntity(
            name=payload.name.strip(),
            description=payload.description,
            is_active=True,
        )
        await self.training_course_repository.add_course(session, course)
        self.logger.info(
            "[TrainingCourseService] created course %s (%s)",
            course.course_id,
            course.name,
        )
        return to_course_dto(course, 0)

    async def update_course(
        self, session, course_id: int, payload: TrainingCourseUpdateDto
    ) -> TrainingCourseDto:
        """Rename a course, or turn it on or off.

        Deactivating only stops new assignments. Everybody already assigned
        keeps their access and their progress, which is why this is the whole
        of it and there is no delete.

        Raises:
            ValueError: No such course.
        """
        course = await self.training_course_repository.get_course_by_id(
            session, course_id
        )
        if course is None:
            raise ValueError(f"No training course with id {course_id}.")

        if payload.name is not None:
            course.name = payload.name.strip()
        if payload.description is not None:
            course.description = payload.description
        if payload.is_active is not None:
            course.is_active = payload.is_active

        assigned_count = await self.training_course_repository.count_assignments(
            session, course_id
        )
        return to_course_dto(course, assigned_count)
