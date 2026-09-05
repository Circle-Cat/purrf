"""The course catalogue: what exists, and what may be assigned."""

from backend.common.mentorship_enums import TrainingPackageState
from backend.common.training_links import external_link_for
from backend.dto.training_course_dto import (
    StagedPackageDto,
    TrainingCourseCreateDto,
    TrainingCourseDto,
    TrainingCourseLiveState,
    TrainingCourseUpdateDto,
)
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_course_package_entity import (
    TrainingCoursePackageEntity,
)


def derive_live_state(
    course: TrainingCourseEntity,
    live_package: TrainingCoursePackageEntity | None,
) -> TrainingCourseLiveState:
    """What a learner on this course can open right now.

    Only the live slot is consulted. A staged package is not a lesser kind of
    live -- it is invisible to learners entirely, which is what makes it safe
    to upload one in the middle of a working day. Whether the live package
    itself is verified does not change this answer either: an unverified live
    package still opens for a learner, it only blocks new assignments.

    A package-less row is EXTERNAL_LINK only when a link really resolves for
    its category. Two of the four seed categories never had one, and neither
    does any category in an environment that has not set its variable; naming
    the state after the category alone showed a link that could not be
    followed.

    Args:
        course (TrainingCourseEntity): The row to read.
        live_package (TrainingCoursePackageEntity | None): The course's live
            package, or None if it has none.

    Returns:
        TrainingCourseLiveState: The single state for that row.
    """
    if live_package is not None:
        return TrainingCourseLiveState.LIVE
    if external_link_for(course.category):
        return TrainingCourseLiveState.EXTERNAL_LINK
    return TrainingCourseLiveState.NO_PACKAGE


def to_course_dto(
    course: TrainingCourseEntity,
    live_package: TrainingCoursePackageEntity | None,
    pending_package: TrainingCoursePackageEntity | None,
    assigned_count: int,
    unfinished_count: int,
) -> TrainingCourseDto:
    """Project one course row, its live and pending packages, and headcounts."""
    return TrainingCourseDto(
        course_id=course.course_id,
        name=course.name,
        description=course.description,
        category=course.category,
        is_active=course.is_active,
        live_state=derive_live_state(course, live_package),
        link=(
            external_link_for(course.category) if live_package is None else None
        ),
        scorm_version=(
            live_package.scorm_version if live_package is not None else None
        ),
        package_version=(
            live_package.package_version if live_package is not None else None
        ),
        reporting_mode=(
            live_package.reporting_mode if live_package is not None else None
        ),
        package_uploaded_at=(
            live_package.uploaded_at if live_package is not None else None
        ),
        verified_completable_at=(
            live_package.verified_completable_at if live_package is not None else None
        ),
        verified_by_user_id=(
            live_package.verified_by_user_id if live_package is not None else None
        ),
        assigned_count=assigned_count,
        unfinished_count=unfinished_count,
        staged=(
            StagedPackageDto(
                package_id=pending_package.package_id,
                package_version=pending_package.package_version,
                uploaded_at=pending_package.uploaded_at,
                uploaded_by_user_id=pending_package.uploaded_by_user_id,
                verified_completable_at=pending_package.verified_completable_at,
                verified_by_user_id=pending_package.verified_by_user_id,
            )
            if pending_package is not None
            else None
        ),
    )


class TrainingCourseService:
    """Creating, listing and deactivating courses.

    Uploading a package belongs with the storage handling that arrives with it.
    """

    def __init__(
        self, logger, training_course_repository, training_course_package_repository
    ):
        """
        Args:
            logger: Injected logger.
            training_course_repository (TrainingCourseRepository): Catalogue
                reads and writes.
            training_course_package_repository (TrainingCoursePackageRepository):
                The live package behind each course.
        """
        self.logger = logger
        self.training_course_repository = training_course_repository
        self.training_course_package_repository = training_course_package_repository

    async def list_courses(
        self, session, include_inactive: bool = True
    ) -> list[TrainingCourseDto]:
        """Every course, with its derived live state, staged package, and
        headcounts.

        One batched query fetches every row's live and pending packages, not
        two lookups per row.
        """
        rows = await self.training_course_repository.list_courses(
            session, include_inactive=include_inactive
        )
        slots = await self.training_course_package_repository.packages_for(
            session, [course.course_id for course, _, _ in rows]
        )
        return [
            to_course_dto(
                course,
                slots.get(course.course_id, {}).get(TrainingPackageState.LIVE),
                slots.get(course.course_id, {}).get(TrainingPackageState.PENDING),
                assigned,
                unfinished,
            )
            for course, assigned, unfinished in rows
        ]

    async def create_course(
        self, session, payload: TrainingCourseCreateDto
    ) -> TrainingCourseDto:
        """Create a course with no package.

        Unassignable until a package is uploaded and somebody finishes it.
        """
        course = TrainingCourseEntity(
            name=payload.name,
            description=payload.description,
            is_active=True,
        )
        await self.training_course_repository.add_course(session, course)
        await session.commit()
        self.logger.info(
            "[TrainingCourseService] created course %s (%s)",
            course.course_id,
            course.name,
        )
        return to_course_dto(course, None, None, 0, 0)

    async def update_course(
        self, session, course_id: int, payload: TrainingCourseUpdateDto
    ) -> TrainingCourseDto:
        """Rename a course, or turn it on or off.

        Deactivating only stops new assignments; everybody already assigned
        keeps their access and their progress. There is no delete.

        Raises:
            ValueError: No such course.
        """
        course = await self.training_course_repository.get_course_by_id(
            session, course_id
        )
        if course is None:
            raise ValueError(f"No training course with id {course_id}.")

        if payload.name is not None:
            course.name = payload.name
        if payload.description is not None:
            course.description = payload.description
        if payload.is_active is not None:
            course.is_active = payload.is_active

        await session.commit()

        assigned_count = await self.training_course_repository.count_assignments(
            session, course_id
        )
        unfinished_count = (
            await self.training_course_repository.count_unfinished_assignments(
                session, course_id
            )
        )
        package = await self.training_course_package_repository.get_by_state(
            session, course_id, TrainingPackageState.LIVE
        )
        pending = await self.training_course_package_repository.get_by_state(
            session, course_id, TrainingPackageState.PENDING
        )
        return to_course_dto(
            course, package, pending, assigned_count, unfinished_count
        )
