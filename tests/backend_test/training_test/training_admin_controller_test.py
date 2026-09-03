"""Routes for the training course catalogue and manual assignment."""

import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.permissions import Permission
from backend.dto.training_course_dto import (
    TrainingAssignmentRequestDto,
    TrainingAssignmentResultDto,
    TrainingCourseCreateDto,
    TrainingCourseDto,
    TrainingCourseState,
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
        self.controller = TrainingAdminController(
            self.course_service, self.assignment_service, self.database
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

    async def test_the_list_includes_deactivated_courses(self):
        """Or they could never be turned back on."""
        await self.controller.list_courses()

        self.course_service.list_courses.assert_awaited_once_with(self.session)


if __name__ == "__main__":
    unittest.main()
