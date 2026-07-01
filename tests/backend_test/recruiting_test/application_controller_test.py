import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from backend.dto.user_context_dto import UserContextDto
from backend.recruiting.application_controller import ApplicationController


class TestApplicationController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.app_service = MagicMock()
        self.app_service.submit = AsyncMock(return_value={"id": 100})
        self.app_service.edit = AsyncMock(return_value={"id": 100})
        self.app_service.get_mine = AsyncMock(return_value=None)

        self.job_service = MagicMock()
        self.job_service.get_published_job = AsyncMock(return_value={"id": 1})

        self.resume_storage = MagicMock()
        self.resume_storage.put = MagicMock(return_value=("abc", "resumes/abc.pdf"))

        self.controller = ApplicationController(
            self.app_service, self.job_service, self.resume_storage, self.database
        )

        self.patcher = patch(
            "backend.recruiting.application_controller.api_response"
        )
        self.mock_api_response = self.patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
            }
        )
        self.addCleanup(self.patcher.stop)

        self.ctx = UserContextDto(sub="s", primary_email="a@b.com", user_id=2)

    async def test_get_public_job_delegates(self):
        resp = await self.controller.get_public_job(self.ctx, 1)
        self.job_service.get_published_job.assert_awaited_once_with(self.session, 1)
        self.assertEqual(resp["data"], {"id": 1})

    async def test_upload_resume_returns_object_key(self):
        upload = MagicMock()
        upload.read = AsyncMock(return_value=b"%PDF-1.4")
        resp = await self.controller.upload_resume(self.ctx, upload)
        self.resume_storage.put.assert_called_once_with(b"%PDF-1.4")
        self.assertEqual(
            resp["data"], {"sha256": "abc", "objectKey": "resumes/abc.pdf"}
        )

    async def test_submit_delegates_current_user(self):
        from backend.dto.application_dto import ApplicationSubmitDto

        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        resp = await self.controller.submit_application(self.ctx, dto)
        self.app_service.submit.assert_awaited_once_with(self.session, self.ctx, dto)
        self.assertEqual(resp["data"], {"id": 100})

    async def test_edit_application_delegates(self):
        from backend.dto.application_dto import ApplicationEditDto

        dto = ApplicationEditDto.model_validate({})
        resp = await self.controller.edit_application(self.ctx, 5, dto)
        self.app_service.edit.assert_awaited_once_with(self.session, self.ctx, 5, dto)
        self.assertEqual(resp["data"], {"id": 100})

    async def test_get_my_application_uses_job_id_query_param(self):
        resp = await self.controller.get_my_application(self.ctx, job_id=7)
        self.app_service.get_mine.assert_awaited_once_with(self.session, self.ctx, 7)
        self.assertIsNone(resp["data"])


if __name__ == "__main__":
    unittest.main()
