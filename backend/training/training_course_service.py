"""The course catalogue: what exists, and what may be assigned."""

from backend.common.mentorship_enums import TrainingPackageState
from backend.common.training_links import external_link_for
from backend.dto.training_course_dto import (
    TrainingCourseCreateDto,
    TrainingCourseDto,
    TrainingCourseState,
    TrainingCourseUpdateDto,
)
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_course_package_entity import (
    TrainingCoursePackageEntity,
)


def derive_course_state(
    course: TrainingCourseEntity,
    package: TrainingCoursePackageEntity | None,
) -> TrainingCourseState:
    """Read a course's live package as the one status the admin page shows.

    A package without proof is NEEDS_TRIAL_RUN, never VERIFIED: a re-upload
    replaces the package row outright, so a fresh row's own unset
    ``verified_completable_at`` is what gets read.

    A package-less row is EXTERNAL_LINK only when a link really resolves for
    its category. Two of the four seed categories never had one, and neither
    does any category in an environment that has not set its variable; naming
    the state after the category alone showed a link that could not be
    followed.

    Args:
        course (TrainingCourseEntity): The row to read.
        package (TrainingCoursePackageEntity | None): The course's live
            package, or None if it has none.

    Returns:
        TrainingCourseState: The single state for that row.
    """
    if package is not None:
        if package.verified_completable_at is not None:
            return TrainingCourseState.VERIFIED
        return TrainingCourseState.NEEDS_TRIAL_RUN
    if external_link_for(course.category):
        return TrainingCourseState.EXTERNAL_LINK
    return TrainingCourseState.NO_PACKAGE


def to_course_dto(
    course: TrainingCourseEntity,
    package: TrainingCoursePackageEntity | None,
    assigned_count: int,
    unfinished_count: int,
) -> TrainingCourseDto:
    """Project one course row, plus its live package and headcounts, for the API."""
    return TrainingCourseDto(
        course_id=course.course_id,
        name=course.name,
        description=course.description,
        category=course.category,
        is_active=course.is_active,
        state=derive_course_state(course, package),
        link=(external_link_for(course.category) if package is None else None),
        scorm_version=package.scorm_version if package is not None else None,
        package_version=package.package_version if package is not None else None,
        reporting_mode=package.reporting_mode if package is not None else None,
        package_uploaded_at=package.uploaded_at if package is not None else None,
        verified_completable_at=(
            package.verified_completable_at if package is not None else None
        ),
        verified_by_user_id=(
            package.verified_by_user_id if package is not None else None
        ),
        assigned_count=assigned_count,
        unfinished_count=unfinished_count,
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
        """Every course, with its derived state and headcounts.

        One batched query fetches every row's live package, not one per row.
        """
        rows = await self.training_course_repository.list_courses(
            session, include_inactive=include_inactive
        )
        packages = await self.training_course_package_repository.live_packages_for(
            session, [course.course_id for course, _, _ in rows]
        )
        return [
            to_course_dto(course, packages.get(course.course_id), assigned, unfinished)
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
        return to_course_dto(course, None, 0, 0)

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
        return to_course_dto(course, package, assigned_count, unfinished_count)
