import unittest
import pydantic
from backend.dto.application_dto import (
    ApplicationDto,
    ApplicationEditDto,
    ApplicationSubmitDto,
)


class TestApplicationDtos(unittest.TestCase):
    def test_submit_accepts_camel_case_aliases(self):
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 7,
            "personal": {"firstName": "A"},
            "answers": {"q1": "yes"},
            "resumeSha256": "abc",
            "resumeObjectKey": "resumes/abc.pdf",
            "saveToProfile": True,
        })
        self.assertEqual(dto.job_id, 7)
        self.assertTrue(dto.save_to_profile)
        self.assertEqual(dto.resume_object_key, "resumes/abc.pdf")

    def test_submit_defaults_are_empty(self):
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        self.assertEqual(dto.education, [])
        self.assertEqual(dto.answers, {})
        self.assertFalse(dto.save_to_profile)

    def test_edit_forbids_job_id(self):
        with self.assertRaises(pydantic.ValidationError):
            ApplicationEditDto.model_validate({"jobId": 1})

    def test_application_dto_exposes_current_round(self):
        dto = ApplicationDto(
            id=1,
            job_id=1,
            user_id=2,
            stage="tech",
            current_round=2,
        )
        self.assertEqual(dto.current_round, 2)
