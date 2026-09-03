"""Routes for the training course catalogue and manual assignment."""

import inspect
import json
import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.common.api_endpoints import (
    TRAINING_COURSE_PACKAGE_ENDPOINT,
    TRAINING_COURSE_TRIAL_ENDPOINT,
    TRAINING_COURSES_ENDPOINT,
    TRAINING_SESSION_ENDPOINT,
)
from backend.common.mentorship_enums import ScormVersion, TrainingStatus
from backend.common.permissions import Permission
from backend.dto.training_course_dto import (
    TrainingCompletionConfigDto,
    TrainingProgressSaveDto,
    TrainingAssignmentRequestDto,
    TrainingAssignmentResultDto,
    TrainingCourseCreateDto,
    TrainingCourseDto,
    TrainingCourseState,
    TrainingPackageUploadResultDto,
    TrainingProgressDto,
    TrainingSessionDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.training.training_admin_controller import (
    _MAX_PROGRESS_BODY_BYTES,
    TrainingAdminController,
)


def _session_dto():
    """A content session as the content service hands one back."""
    return TrainingSessionDto(
        content_base_url="https://content.example/p/tok/",
        entry_path="scormcontent/index.html",
        player_path="__player.html",
        expires_at=1788400000,
        progress=TrainingProgressDto(
            lesson_status="incomplete",
            lesson_location="Summary",
            suspend_data="blob",
            session_time_seconds=500,
            score_raw="82.50",
        ),
    )


def _request(body: bytes, chunk_size=None):
    """A request whose body arrives in chunks, as an ASGI server delivers it."""
    step = chunk_size or max(len(body), 1)

    async def stream():
        for start in range(0, max(len(body), 1), step):
            yield body[start : start + step]

    request = MagicMock()
    request.stream = stream
    return request


def _user(*permissions):
    """The caller as the middleware builds them, with grants read from the DB."""
    return UserContextDto(
        sub="auth0|learner",
        primary_email="learner@circlecat.org",
        user_id=11,
        permissions=frozenset(permissions),
    )


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
        self.assignment_service.start_trial = AsyncMock(
            return_value=TrainingAssignmentResultDto(
                training_id=42, user_id=11, course_id=3, created=True
            )
        )
        self.package_service = MagicMock()
        self.content_service = MagicMock()
        self.progress_service = MagicMock()
        self.progress_service.save = AsyncMock(
            return_value=TrainingProgressSaveDto(status=TrainingStatus.IN_PROGRESS)
        )
        self.controller = TrainingAdminController(
            self.course_service,
            self.assignment_service,
            self.package_service,
            self.content_service,
            self.progress_service,
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

    async def save_progress(self, payload, current_user=None):
        """Post one commit as a learner who holds no grant unless one is given."""
        return await self.post_progress(
            json.dumps(payload).encode(), current_user=current_user
        )

    async def post_progress(self, body, current_user=None, chunk_size=None):
        """Post a raw body, optionally split the way a client would send it."""
        return await self.controller.save_progress(
            42, _request(body, chunk_size), current_user or _user()
        )

    async def test_a_save_answers_with_where_the_assignment_now_stands(self):
        """So the page shows the server's verdict instead of reaching its own."""
        self.progress_service.save = AsyncMock(
            return_value=TrainingProgressSaveDto(status=TrainingStatus.DONE)
        )

        response = await self.save_progress({
            "cmi": {"cmi.core.lesson_status": "passed"}
        })

        self.assertEqual(response["data"].status, TrainingStatus.DONE)

    def test_reading_the_catalogue_and_changing_it_are_separate_grants(self):
        by_method = {
            (route.path, method): _route_permissions(route)
            for route in self.controller.router.routes
            for method in route.methods
        }

        for path, method in [
            ("/training/courses", "GET"),
            ("/training/courses/{course_id}/package", "GET"),
        ]:
            self.assertEqual(
                by_method[(path, method)],
                [Permission.TRAINING_ADMIN_READ],
                msg=f"{method} {path}",
            )
        for path, method in [
            ("/training/courses", "POST"),
            ("/training/courses/{course_id}", "PATCH"),
            ("/training/courses/{course_id}/package", "POST"),
            ("/training/assignments", "POST"),
            ("/training/courses/{course_id}/trial", "POST"),
        ]:
            self.assertEqual(
                by_method[(path, method)],
                [Permission.TRAINING_ADMIN_WRITE],
                msg=f"{method} {path}",
            )

    async def test_reading_a_packages_completion_config_answers_what_it_says(self):
        self.package_service.read_completion_config = AsyncMock(
            return_value=TrainingCompletionConfigDto(
                completion_percentage=100,
                completes_via_storyline=True,
                completion_config_readable=True,
            )
        )

        response = await self.controller.read_completion_config(7)

        self.package_service.read_completion_config.assert_awaited_once_with(
            self.session, 7
        )
        self.assertEqual(response["status_code"], HTTPStatus.OK)
        self.assertTrue(response["data"].completes_via_storyline)

    async def test_create_returns_created(self):
        response = await self.controller.create_course(
            TrainingCourseCreateDto(name="Safety Briefing")
        )

        self.assertEqual(response["status_code"], HTTPStatus.CREATED)
        self.assertEqual(response["data"].state, TrainingCourseState.NO_PACKAGE)

    async def test_a_fresh_assignment_is_201(self):
        response = await self.controller.assign(
            TrainingAssignmentRequestDto(user_id=11, course_id=3)
        )

        self.assertEqual(response["status_code"], HTTPStatus.CREATED)
        self.assertTrue(response["data"].created)

    async def test_a_repeat_assignment_is_200_and_says_so(self):
        """A no-op, not a failure -- so neither 201 nor an error."""
        self.assignment_service.assign.return_value = TrainingAssignmentResultDto(
            training_id=42, user_id=11, course_id=3, created=False
        )

        response = await self.controller.assign(
            TrainingAssignmentRequestDto(user_id=11, course_id=3)
        )

        self.assertEqual(response["status_code"], HTTPStatus.OK)
        self.assertFalse(response["data"].created)

    async def test_a_trial_is_opened_for_the_caller_not_for_a_named_user(self):
        """The user id comes from the token, never from the request."""
        self.assignment_service.start_trial = AsyncMock(
            return_value=TrainingAssignmentResultDto(
                training_id=42, user_id=11, course_id=3, created=True
            )
        )
        current_user = MagicMock(user_id=11)

        await self.controller.start_trial(3, current_user)

        self.assignment_service.start_trial.assert_awaited_once_with(
            self.session, 3, 11
        )

    def test_opening_your_own_course_takes_no_permission(self):
        """Holding the assignment is the grant; the service checks you hold it."""
        by_method = {
            (route.path, method): _route_permissions(route)
            for route in self.controller.router.routes
            for method in route.methods
        }

        self.assertIsNone(by_method[("/training/{training_id}/session", "POST")])
        self.assertIsNone(by_method[("/training/{training_id}/progress", "POST")])

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
        self.assertEqual(response["data"].storage_prefix, "training/7/abc/")
        self.package_service.upload_package.assert_awaited_once_with(
            self.session, 7, b"zipbytes"
        )

    async def test_a_session_is_opened_for_the_caller_not_for_a_named_user(self):
        """The user id comes from the token, never from the request."""
        self.content_service.open_session = AsyncMock(return_value=_session_dto())
        current_user = MagicMock(user_id=11)

        await self.controller.open_session(42, current_user)

        self.content_service.open_session.assert_awaited_once_with(self.session, 42, 11)

    async def test_a_commit_is_saved_for_the_caller_not_for_a_named_user(self):
        """The user id comes from the token, never from the request."""
        await self.save_progress({"cmi": {"cmi.core.lesson_location": "Summary"}})

        self.progress_service.save.assert_awaited_once_with(
            self.session,
            42,
            11,
            {"cmi.core.lesson_location": "Summary"},
            final=False,
            may_verify_course=False,
        )

    async def test_the_pages_parting_save_is_passed_through_as_final(self):
        """Only the page knows which save is the last one, and that save
        exists to bank elapsed time -- which the service's unchanged-content
        check ignores, so it is skipped unless it says so."""
        await self.save_progress({
            "cmi": {"cmi.core.lesson_location": "Summary"},
            "final": True,
        })

        self.assertIs(self.progress_service.save.await_args.kwargs["final"], True)

    async def test_a_non_object_cmi_is_a_client_error_not_a_500(self):
        """A course controls this payload; {"cmi": 5} must not reach
        payload.get("cmi", {}).items()-shaped code as a TypeError."""
        with self.assertRaises(ValueError):
            await self.save_progress({"cmi": 5})

        self.progress_service.save.assert_not_awaited()

    async def test_an_ordinary_learner_may_not_verify_the_course(self):
        """Reporting your own training done is open to anybody who holds the
        assignment; unlocking the course for everybody else is not."""
        await self.save_progress({"cmi": {"cmi.core.lesson_status": "passed"}})

        self.assertIs(
            self.progress_service.save.await_args.kwargs["may_verify_course"], False
        )

    async def test_the_grant_that_unlocks_a_course_comes_from_the_session(self):
        """Never from the payload: the course controls that, and a course
        must not be able to claim the grant that makes it assignable."""
        await self.save_progress(
            {
                "cmi": {"cmi.core.lesson_status": "passed"},
                "may_verify_course": True,
                "permissions": ["training.admin.write"],
            },
            current_user=_user(Permission.TRAINING_ADMIN_WRITE),
        )

        self.assertIs(
            self.progress_service.save.await_args.kwargs["may_verify_course"], True
        )

    def test_the_route_declares_no_body_parameter(self):
        """FastAPI reads and parses a declared body before the handler runs,
        which is exactly what the size cap has to come before."""
        route = next(
            route
            for route in self.controller.router.routes
            if route.path == "/training/{training_id}/progress"
            and "POST" in route.methods
        )

        parameters = inspect.signature(route.endpoint).parameters

        self.assertEqual(set(parameters), {"request", "training_id"})

    async def test_a_body_too_large_to_be_a_commit_is_refused(self):
        """Refused while it is being read, so the cap bounds what is held in
        memory rather than being checked once the whole thing already is."""
        oversized = json.dumps({
            "cmi": {"cmi.suspend_data": "x" * (2 * _MAX_PROGRESS_BODY_BYTES)}
        }).encode()

        with self.assertRaises(ValueError):
            await self.post_progress(oversized, chunk_size=8192)

        self.progress_service.save.assert_not_awaited()

    async def test_a_body_that_is_not_json_is_a_client_error(self):
        with self.assertRaises(ValueError):
            await self.post_progress(b"not json at all")

        self.progress_service.save.assert_not_awaited()

    async def test_a_body_that_is_not_an_object_is_a_client_error(self):
        with self.assertRaises(ValueError):
            await self.post_progress(b"[1, 2, 3]")

        self.progress_service.save.assert_not_awaited()

    async def test_an_empty_body_saves_nothing_rather_than_failing(self):
        """The page's parting keepalive fetch can arrive with nothing in it."""
        await self.post_progress(b"")

        self.progress_service.save.assert_awaited_once()
        self.assertEqual(self.progress_service.save.await_args.args[3], {})

    async def test_the_list_includes_deactivated_courses(self):
        """Or they could never be turned back on."""
        await self.controller.list_courses()

        self.course_service.list_courses.assert_awaited_once_with(self.session)


def _course_dto():
    """One catalogue row, with a field of every kind the aliaser touches."""
    return TrainingCourseDto(
        course_id=7,
        name="Safety Briefing",
        is_active=True,
        state=TrainingCourseState.VERIFIED,
        scorm_version=ScormVersion.SCORM_12,
        package_version="1.4",
        reporting_mode="passed-incomplete",
        verified_by_user_id=11,
        assigned_count=3,
    )


def _upload_dto():
    return TrainingPackageUploadResultDto(
        course_id=7,
        storage_prefix="training/7/abc/",
        entry_path="index.html",
        scorm_version=ScormVersion.SCORM_12,
        file_count=3,
        total_bytes=4096,
    )


class _FakeSession:
    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *args):
        return False


def _snake_case_keys(body, path=""):
    """Every key in a response body that is not camelCase, with where it is."""
    if isinstance(body, list):
        return [
            found
            for index, item in enumerate(body)
            for found in _snake_case_keys(item, f"{path}[{index}]")
        ]
    if not isinstance(body, dict):
        return []
    found = [f"{path}.{key}" for key in body if "_" in key]
    for key, value in body.items():
        found.extend(_snake_case_keys(value, f"{path}.{key}"))
    return found


class TestTrainingResponsesOnTheWire(unittest.TestCase):
    """What a browser receives, asserted through the router rather than the
    handler.

    Calling a handler directly returns whatever object was handed to
    api_response, which is the half of the contract the frontend never sees.
    The repo serialises DTOs by alias, so the wire is camelCase; a body built
    by hand somewhere in here would be snake_case and every reader of it
    would silently read undefined.
    """

    def setUp(self):
        self.course_service = MagicMock()
        self.course_service.list_courses = AsyncMock(return_value=[_course_dto()])
        self.course_service.create_course = AsyncMock(return_value=_course_dto())
        self.course_service.update_course = AsyncMock(return_value=_course_dto())

        self.assignment_service = MagicMock()
        self.assignment_service.assign = AsyncMock(
            return_value=TrainingAssignmentResultDto(
                training_id=42, user_id=11, course_id=3, created=True
            )
        )
        self.assignment_service.start_trial = AsyncMock(
            return_value=TrainingAssignmentResultDto(
                training_id=42, user_id=11, course_id=3, created=True
            )
        )

        self.package_service = MagicMock()
        self.package_service.upload_package = AsyncMock(return_value=_upload_dto())

        self.content_service = MagicMock()
        self.content_service.open_session = AsyncMock(return_value=_session_dto())

        self.progress_service = MagicMock()
        self.progress_service.save = AsyncMock(
            return_value=TrainingProgressSaveDto(status=TrainingStatus.IN_PROGRESS)
        )

        database = MagicMock()
        database.session = lambda: _FakeSession()
        controller = TrainingAdminController(
            self.course_service,
            self.assignment_service,
            self.package_service,
            self.content_service,
            self.progress_service,
            database,
        )

        app = FastAPI()
        current_user = _user(
            Permission.TRAINING_ADMIN_READ, Permission.TRAINING_ADMIN_WRITE
        )

        @app.middleware("http")
        async def _sign_in(request: Request, call_next):
            request.state.user = current_user
            return await call_next(request)

        app.include_router(controller.router)
        self.client = TestClient(app)

    def start_trial(self):
        return self.client.post(TRAINING_COURSE_TRIAL_ENDPOINT.format(course_id=3))

    def open_session(self):
        return self.client.post(TRAINING_SESSION_ENDPOINT.format(training_id=42))

    def test_a_trial_run_answers_with_the_training_id_the_page_opens(self):
        """The page reads trainingId off this body and can do nothing without
        it: no trial run means no course can ever be verified, and an
        unverified course cannot be assigned to anybody."""
        response = self.start_trial()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(
            response.json()["data"],
            {"trainingId": 42, "userId": 11, "courseId": 3, "created": True},
        )

    def test_a_content_session_answers_with_the_keys_the_player_loads_from(self):
        response = self.open_session()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.json()["data"],
            {
                "contentBaseUrl": "https://content.example/p/tok/",
                "entryPath": "scormcontent/index.html",
                "playerPath": "__player.html",
                "expiresAt": 1788400000,
                "progress": {
                    "lessonStatus": "incomplete",
                    "lessonLocation": "Summary",
                    "suspendData": "blob",
                    "sessionTimeSeconds": 500,
                    "scoreRaw": "82.50",
                    "scoreMin": None,
                    "scoreMax": None,
                },
            },
        )

    def test_an_untouched_assignment_opens_with_no_progress_rather_than_a_shape(self):
        """The page seeds the CMI model from `progress || {}`."""
        self.content_service.open_session = AsyncMock(
            return_value=TrainingSessionDto(
                content_base_url="https://content.example/p/tok/",
                entry_path="scormcontent/index.html",
                player_path="__player.html",
                expires_at=1788400000,
            )
        )

        self.assertIsNone(self.open_session().json()["data"]["progress"])

    def test_the_catalogue_answers_with_camel_case_rows(self):
        response = self.client.get(TRAINING_COURSES_ENDPOINT)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        row = response.json()["data"][0]
        self.assertEqual(row["courseId"], 7)
        self.assertIs(row["isActive"], True)
        self.assertEqual(row["scormVersion"], "1.2")
        self.assertEqual(row["packageVersion"], "1.4")
        self.assertEqual(row["reportingMode"], "passed-incomplete")
        self.assertEqual(row["verifiedByUserId"], 11)
        self.assertEqual(row["assignedCount"], 3)

    def test_an_upload_answers_with_camel_case(self):
        response = self.client.post(
            TRAINING_COURSE_PACKAGE_ENDPOINT.format(course_id=7),
            files={"file": ("package.zip", b"zipbytes", "application/zip")},
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(response.json()["data"]["storagePrefix"], "training/7/abc/")
        self.assertEqual(response.json()["data"]["fileCount"], 3)
        self.assertIs(response.json()["data"]["completionConfigReadable"], False)

    def test_no_training_response_carries_a_snake_case_key(self):
        """Every body this controller can send, swept in one place, so a route
        added later cannot quietly reintroduce the mismatch."""
        responses = {
            "list courses": lambda: self.client.get(TRAINING_COURSES_ENDPOINT),
            "create course": lambda: self.client.post(
                TRAINING_COURSES_ENDPOINT, json={"name": "Safety Briefing"}
            ),
            "update course": lambda: self.client.patch(
                "/training/courses/7", json={"isActive": False}
            ),
            "upload package": lambda: self.client.post(
                TRAINING_COURSE_PACKAGE_ENDPOINT.format(course_id=7),
                files={"file": ("package.zip", b"zipbytes", "application/zip")},
            ),
            "assign": lambda: self.client.post(
                "/training/assignments", json={"userId": 11, "courseId": 3}
            ),
            "start trial": self.start_trial,
            "open session": self.open_session,
            "save progress": lambda: self.client.post(
                "/training/42/progress",
                json={"cmi": {"cmi.core.lesson_status": "passed"}},
            ),
        }

        for name, send in responses.items():
            with self.subTest(name):
                body = send().json()
                self.assertTrue(body["success"], msg=body)
                self.assertEqual(_snake_case_keys(body["data"], name), [])


if __name__ == "__main__":
    unittest.main()
