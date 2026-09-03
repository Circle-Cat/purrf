"""FastAPI routes for the training course catalogue and manual assignment."""

from http import HTTPStatus

from fastapi import APIRouter

from backend.common.api_endpoints import (
    TRAINING_ASSIGNMENTS_ENDPOINT,
    TRAINING_COURSE_ENDPOINT,
    TRAINING_COURSES_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.dto.training_course_dto import (
    TrainingAssignmentRequestDto,
    TrainingCourseCreateDto,
    TrainingCourseUpdateDto,
)
from backend.utils.permission_decorators import authenticate


class TrainingAdminController:
    """Admin-only training routes.

    Reading the catalogue is a separate grant from changing it: scheduling
    training needs to see what exists, assigning it is narrower.
    """

    def __init__(self, training_course_service, training_assignment_service, database):
        """
        Args:
            training_course_service (TrainingCourseService): The catalogue.
            training_assignment_service (TrainingAssignmentService): Manual
                assignment, and the verification gate in front of it.
            database: Async session provider.
        """
        self.training_course_service = training_course_service
        self.training_assignment_service = training_assignment_service
        self.database = database
        self.router = APIRouter(tags=["training-admin"])

        self.router.add_api_route(
            TRAINING_COURSES_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.TRAINING_ADMIN_READ])(
                self.list_courses
            ),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            TRAINING_COURSES_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.TRAINING_ADMIN_WRITE])(
                self.create_course
            ),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            TRAINING_COURSE_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.TRAINING_ADMIN_WRITE])(
                self.update_course
            ),
            methods=["PATCH"],
            response_model=None,
        )
        self.router.add_api_route(
            TRAINING_ASSIGNMENTS_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.TRAINING_ADMIN_WRITE])(
                self.assign
            ),
            methods=["POST"],
            response_model=None,
        )

    async def list_courses(self):
        """Every course, with its state and how many people hold it.

        Deactivated ones included, or they could never be turned back on.
        """
        async with self.database.session() as session:
            courses = await self.training_course_service.list_courses(session)
        return api_response(
            message="Training courses retrieved.",
            data=[course.model_dump(mode="json") for course in courses],
        )

    async def create_course(self, payload: TrainingCourseCreateDto):
        """Create a course. It has no package and cannot be assigned yet."""
        async with self.database.session() as session:
            course = await self.training_course_service.create_course(session, payload)
        return api_response(
            message="Training course created.",
            data=course.model_dump(mode="json"),
            status_code=HTTPStatus.CREATED,
        )

    async def update_course(self, course_id: int, payload: TrainingCourseUpdateDto):
        """Rename a course, or turn it on or off."""
        async with self.database.session() as session:
            course = await self.training_course_service.update_course(
                session, course_id, payload
            )
        return api_response(
            message="Training course updated.",
            data=course.model_dump(mode="json"),
        )

    async def assign(self, payload: TrainingAssignmentRequestDto):
        """Assign one course to one person.

        Answers 409 for a course nobody has finished, whatever the admin page
        shows -- the disabled button there explains the rule, it is not the rule.
        """
        async with self.database.session() as session:
            result = await self.training_assignment_service.assign(session, payload)
        return api_response(
            message=(
                "Training assigned."
                if result.created
                else "This person already has this course."
            ),
            data=result.model_dump(mode="json"),
            status_code=HTTPStatus.CREATED if result.created else HTTPStatus.OK,
        )
