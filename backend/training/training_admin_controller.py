"""FastAPI routes for the training course catalogue and manual assignment."""

import json
from http import HTTPStatus

from fastapi import APIRouter, File, Request, UploadFile

from backend.common.api_endpoints import (
    TRAINING_ASSIGNMENTS_ENDPOINT,
    TRAINING_COURSE_ENDPOINT,
    TRAINING_COURSE_PACKAGE_ENDPOINT,
    TRAINING_COURSE_TRIAL_ENDPOINT,
    TRAINING_COURSES_ENDPOINT,
    TRAINING_PROGRESS_ENDPOINT,
    TRAINING_SESSION_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.dto.training_course_dto import (
    TrainingAssignmentRequestDto,
    TrainingCourseCreateDto,
    TrainingCourseUpdateDto,
)
from backend.utils.permission_decorators import authenticate

# A commit is a few kilobytes; the largest element the service will store is
# 64 KB of suspend_data. The body is read against this cap rather than parsed
# first, because a length check that runs after the JSON is decoded has already
# spent the memory it exists to bound.
_MAX_PROGRESS_BODY_BYTES = 256 * 1024


async def _read_progress_body(request: Request) -> dict:
    """The commit body, refused before it is parsed if it is too large.

    Args:
        request (Request): The incoming request, unread.

    Returns:
        dict: The decoded body.

    Raises:
        ValueError: Over the cap, or not a JSON object.
    """
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > _MAX_PROGRESS_BODY_BYTES:
            raise ValueError("This progress commit is too large.")
        chunks.append(chunk)

    try:
        payload = json.loads(b"".join(chunks) or b"{}")
    except ValueError as error:
        raise ValueError("This progress commit is not valid JSON.") from error
    if not isinstance(payload, dict):
        raise ValueError("A progress commit must be an object.")
    return payload


class TrainingAdminController:
    """Admin-only training routes.

    Reading the catalogue is a separate grant from changing it: scheduling
    training needs to see what exists, assigning it is narrower.
    """

    def __init__(
        self,
        training_course_service,
        training_assignment_service,
        training_package_service,
        training_content_service,
        training_progress_service,
        database,
    ):
        """
        Args:
            training_course_service (TrainingCourseService): The catalogue.
            training_assignment_service (TrainingAssignmentService): Manual
                assignment, and the verification gate in front of it.
            training_package_service (TrainingPackageService): Uploads.
            training_content_service (TrainingContentService): Mints the
                content URL a learner's page loads the course from.
            training_progress_service (TrainingProgressService): Stores what
                the course commits back.
            database: Async session provider.
        """
        self.training_course_service = training_course_service
        self.training_assignment_service = training_assignment_service
        self.training_package_service = training_package_service
        self.training_content_service = training_content_service
        self.training_progress_service = training_progress_service
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
            TRAINING_COURSE_PACKAGE_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.TRAINING_ADMIN_WRITE])(
                self.upload_package
            ),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            TRAINING_COURSE_PACKAGE_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.TRAINING_ADMIN_READ])(
                self.read_completion_config
            ),
            methods=["GET"],
            response_model=None,
        )
        # A learner opening their own course needs no permission; holding the
        # assignment is the grant, and the service checks they hold it.
        self.router.add_api_route(
            TRAINING_SESSION_ENDPOINT,
            endpoint=authenticate()(self.open_session),
            methods=["POST"],
            response_model=None,
        )
        # Same grant as opening the session: holding the assignment. Marking
        # the course itself verified is gated separately, inside the service.
        self.router.add_api_route(
            TRAINING_PROGRESS_ENDPOINT,
            endpoint=authenticate()(self.save_progress),
            methods=["POST"],
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
        self.router.add_api_route(
            TRAINING_COURSE_TRIAL_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.TRAINING_ADMIN_WRITE])(
                self.start_trial
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
            data=courses,
        )

    async def create_course(self, payload: TrainingCourseCreateDto):
        """Create a course. It has no package and cannot be assigned yet."""
        async with self.database.session() as session:
            course = await self.training_course_service.create_course(session, payload)
        return api_response(
            message="Training course created.",
            data=course,
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
            data=course,
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
            data=result,
            status_code=HTTPStatus.CREATED if result.created else HTTPStatus.OK,
        )

    async def start_trial(self, course_id: int, current_user):
        """Open the caller's own assignment on a course so they can verify it.

        Answers the deadlock at the assignment gate: nobody may be assigned an
        unverified course, so a verifier gets one this way instead, from
        their own identity, never a named user in the request.
        """
        async with self.database.session() as session:
            result = await self.training_assignment_service.start_trial(
                session, course_id, current_user.user_id
            )
        return api_response(
            message=(
                "Trial started."
                if result.created
                else "Resuming your existing trial of this course."
            ),
            data=result,
            status_code=HTTPStatus.CREATED if result.created else HTTPStatus.OK,
        )

    async def upload_package(self, course_id: int, file: UploadFile = File(...)):
        """Store a SCORM package and point the course at it.

        Rejections come back as 400 with the rule that was broken, because the
        admin usually has to forward the reason to whoever exported the file.
        """
        archive_bytes = await file.read()
        async with self.database.session() as session:
            result = await self.training_package_service.upload_package(
                session, course_id, archive_bytes
            )
        return api_response(
            message="Package uploaded.",
            data=result,
            status_code=HTTPStatus.CREATED,
        )

    async def read_completion_config(self, course_id: int):
        """What the stored package says it takes to finish this course."""
        async with self.database.session() as session:
            config = await self.training_package_service.read_completion_config(
                session, course_id
            )
        return api_response(
            message="Package completion configuration read.",
            data=config,
        )

    async def open_session(self, training_id: int, current_user):
        """Mint the content URL for the caller's own assignment."""
        async with self.database.session() as session:
            training_session = await self.training_content_service.open_session(
                session, training_id, current_user.user_id
            )
        return api_response(message="Training session opened.", data=training_session)

    async def save_progress(self, training_id: int, request: Request, current_user):
        """Store one commit from the caller's own course.

        The body is read here rather than declared as a parameter so that its
        size is bounded before anything parses it.

        ``cmi`` is course-controlled; a shape other than an object must come
        back as a 4xx, not a TypeError from deeper in the stack.

        ``final`` marks the page's parting save as the tab closes. Only the
        page knows which save is the last one, and that save exists to bank
        elapsed time -- the one thing the service's unchanged-content check
        ignores -- so it has to say so or the write is skipped.

        Whether this commit may also mark the course verified comes from the
        permissions the middleware resolved from the database, never from the
        payload: a course reporting itself finished must not be able to claim
        the grant that unlocks it for everybody else.

        The response says where the assignment now stands. Which lesson_status
        finishes a course is decided here; a page that judged the same values
        itself would be a second answer free to disagree with this one.
        """
        payload = await _read_progress_body(request)
        cmi = payload.get("cmi", {})
        if not isinstance(cmi, dict):
            raise ValueError("cmi must be an object.")
        async with self.database.session() as session:
            saved = await self.training_progress_service.save(
                session,
                training_id,
                current_user.user_id,
                cmi,
                final=bool(payload.get("final")),
                may_verify_course=current_user.has_permission(
                    Permission.TRAINING_ADMIN_WRITE
                ),
            )
        return api_response(message="Progress saved.", data=saved)
