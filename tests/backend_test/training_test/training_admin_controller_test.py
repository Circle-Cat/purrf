"""Routes for the training course catalogue and manual assignment."""

import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.mentorship_enums import ScormVersion
from backend.common.permissions import Permission
from backend.dto.training_course_dto import (
    TrainingAssignmentRequestDto,
    TrainingAssignmentResultDto,
    TrainingCourseCreateDto,
    TrainingCourseDto,
    TrainingCourseState,
    TrainingPackageUploadResultDto,
)
from backend.training.training_admin_controller import TrainingAdminController


def _route_permissions(route):
    free_variables = route.endpoint.__code__.co_freevars
    if "permissions" not in free_variables:
        return None
    return route.endpoint.__closure__[free_variables.index("permissions")].cell_contents


class TestTrainingAdminController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.course_service = MagicMock()
        self.course_service.list_courses = AsyncMock(return_value=[])
        self.course_service.create_course = AsyncMock(
            return_value=TrainingCourseDto(
                course_id=7,
                name="Safety Briefing",
                is_active=True,
                state=TrainingCourseState.NO_PACKAGE,
            )
        )
        self.assignment_service = MagicMock()
        self.assignment_service.assign = AsyncMock(
            return_value=TrainingAssignmentResultDto(
                training_id=42, user_id=11, course_id=3, created=True
            )
        )
        self.package_service = MagicMock()
        self.content_service = MagicMock()
        self.controller = TrainingAdminController(
            self.course_service,
            self.assignment_service,
            self.package_service,
            self.content_service,
            self.database,
        )

        patcher = patch("backend.training.training_admin_controller.api_response")
        self.mock_api_response = patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
                "status_code": status_code,
            }
        )
        self.addCleanup(patcher.stop)

    def test_reading_the_catalogue_and_changing_it_are_separate_grants(self):
        by_method = {
            (route.path, method): _route_permissions(route)
            for route in self.controller.router.routes
            for method in route.methods
        }

        self.assertEqual(
            by_method[("/training/courses", "GET")],
            [Permission.TRAINING_ADMIN_READ],
        )
        for path, method in [
            ("/training/courses", "POST"),
            ("/training/courses/{course_id}", "PATCH"),
            ("/training/courses/{course_id}/package", "POST"),
            ("/training/assignments", "POST"),
        ]:
            self.assertEqual(
                by_method[(path, method)],
                [Permission.TRAINING_ADMIN_WRITE],
                msg=f"{method} {path}",
            )

    async def test_create_returns_created(self):
        response = await self.controller.create_course(
            TrainingCourseCreateDto(name="Safety Briefing")
        )

        self.assertEqual(response["status_code"], HTTPStatus.CREATED)
        self.assertEqual(response["data"]["state"], "no_package")

    async def test_a_fresh_assignment_is_201(self):
        response = await self.controller.assign(
            TrainingAssignmentRequestDto(user_id=11, course_id=3)
        )

        self.assertEqual(response["status_code"], HTTPStatus.CREATED)
        self.assertTrue(response["data"]["created"])

    async def test_a_repeat_assignment_is_200_and_says_so(self):
        """A no-op, not a failure -- so neither 201 nor an error."""
        self.assignment_service.assign.return_value = TrainingAssignmentResultDto(
            training_id=42, user_id=11, course_id=3, created=False
        )

        response = await self.controller.assign(
            TrainingAssignmentRequestDto(user_id=11, course_id=3)
        )

        self.assertEqual(response["status_code"], HTTPStatus.OK)
        self.assertFalse(response["data"]["created"])

    def test_opening_your_own_course_takes_no_permission(self):
        """Holding the assignment is the grant; the service checks you hold it."""
        by_method = {
            (route.path, method): _route_permissions(route)
            for route in self.controller.router.routes
            for method in route.methods
        }

        self.assertIsNone(by_method[("/training/{training_id}/session", "POST")])

    async def test_an_upload_reports_what_it_stored(self):
        self.package_service.upload_package = AsyncMock(
            return_value=TrainingPackageUploadResultDto(
                course_id=7,
                storage_prefix="training/7/abc/",
                entry_path="index.html",
                scorm_version=ScormVersion.SCORM_12,
                file_count=3,
                total_bytes=4096,
            )
        )
        upload = MagicMock()
        upload.read = AsyncMock(return_value=b"zipbytes")

        response = await self.controller.upload_package(7, upload)

        self.assertEqual(response["status_code"], HTTPStatus.CREATED)
        self.assertEqual(response["data"]["storage_prefix"], "training/7/abc/")
        self.package_service.upload_package.assert_awaited_once_with(
            self.session, 7, b"zipbytes"
        )

    async def test_a_session_is_opened_for_the_caller_not_for_a_named_user(self):
        """The user id comes from the token, never from the request."""
        self.content_service.open_session = AsyncMock(
            return_value={"contentBaseUrl": "https://content.example/p/tok/"}
        )
        current_user = MagicMock(user_id=11)

        await self.controller.open_session(42, current_user)

        self.content_service.open_session.assert_awaited_once_with(self.session, 42, 11)

    async def test_the_list_includes_deactivated_courses(self):
        """Or they could never be turned back on."""
        await self.controller.list_courses()

        self.course_service.list_courses.assert_awaited_once_with(self.session)


if __name__ == "__main__":
    unittest.main()
