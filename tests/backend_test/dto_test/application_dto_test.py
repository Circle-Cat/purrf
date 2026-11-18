import unittest
import pydantic
from backend.dto.application_dto import (
    DRAFT_CONTENT_MAX_BYTES,
    ApplicationDraftDto,
    ApplicationDraftSaveDto,
    ApplicationDto,
    ApplicationEditDto,
    ApplicationSubmitDto,
    MyApplicationsDto,
)

SHA = "0123456789abcdef" * 4
KEY = f"resumes/{SHA}.pdf"


class TestApplicationDtos(unittest.TestCase):
    def test_submit_accepts_camel_case_aliases(self):
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 7,
            "personal": {"firstName": "A"},
            "answers": {"q1": "yes"},
            "resumeSha256": SHA,
            "resumeObjectKey": KEY,
            "saveToProfile": True,
        })
        self.assertEqual(dto.job_id, 7)
        self.assertTrue(dto.save_to_profile)
        self.assertEqual(dto.resume_object_key, KEY)

    def test_submit_defaults_are_empty(self):
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        self.assertEqual(dto.education, [])
        self.assertEqual(dto.answers, {})
        self.assertFalse(dto.save_to_profile)

    def test_a_resume_key_must_be_the_one_its_hash_was_stored_under(self):
        """Upload stores a file at resumes/<sha256>.pdf and hands both back.
        Any other key would point a reviewer at an object nobody uploaded for
        this application."""
        other_sha = "f" * 64
        for dto_class, base in (
            (ApplicationSubmitDto, {"jobId": 1}),
            (ApplicationEditDto, {}),
            (ApplicationDraftSaveDto, {"jobId": 1}),
        ):
            for sha, key in (
                (SHA, "resumes/../secrets.pdf"),
                (SHA, f"other/{SHA}.pdf"),
                (SHA, f"resumes/{SHA}.PDF"),
                (SHA, f"resumes/{other_sha}.pdf"),
                (None, KEY),
                ("abc", "resumes/abc.pdf"),
            ):
                with self.subTest(dto=dto_class.__name__, sha=sha, key=key):
                    with self.assertRaises(pydantic.ValidationError):
                        dto_class.model_validate({
                            **base,
                            "resumeSha256": sha,
                            "resumeObjectKey": key,
                        })

    def test_no_resume_at_all_is_fine(self):
        dto = ApplicationEditDto.model_validate({})
        self.assertIsNone(dto.resume_object_key)

    def test_a_resume_can_be_dropped_one_field_at_a_time(self):
        """The service clears both fields for a posting that collects no
        resume, one assignment after the other, and the model is revalidated
        on each."""
        dto = ApplicationEditDto.model_validate({
            "resumeSha256": SHA,
            "resumeObjectKey": KEY,
        })

        dto.resume_object_key = None
        dto.resume_sha256 = None

        self.assertIsNone(dto.resume_sha256)

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


class TestApplicationDraftDtos(unittest.TestCase):
    def test_a_draft_needs_nothing_but_the_job(self):
        dto = ApplicationDraftSaveDto.model_validate({"jobId": 12})
        self.assertEqual(dto.job_id, 12)
        self.assertEqual(dto.personal, {})
        self.assertEqual(dto.education, [])
        self.assertEqual(dto.experience, [])
        self.assertEqual(dto.answers, {})

    def test_a_draft_keeps_a_matching_resume_reference(self):
        dto = ApplicationDraftSaveDto.model_validate({
            "jobId": 12,
            "resumeSha256": SHA,
            "resumeObjectKey": KEY,
        })
        self.assertEqual(dto.resume_object_key, KEY)

    def test_a_draft_at_the_size_ceiling_is_accepted(self):
        # {"personal": {}, "education": [], "experience": [], "answers": {"q": ""}}
        # around the padding; size the padding so the total is exactly the cap.
        empty = len(
            '{"personal": {}, "education": [], "experience": [], "answers": {"q": ""}}'
        )
        padding = "x" * (DRAFT_CONTENT_MAX_BYTES - empty)
        dto = ApplicationDraftSaveDto.model_validate({
            "jobId": 12,
            "answers": {"q": padding},
        })
        self.assertEqual(len(dto.answers["q"]), len(padding))

    def test_a_draft_over_the_size_ceiling_is_refused(self):
        with self.assertRaises(pydantic.ValidationError):
            ApplicationDraftSaveDto.model_validate({
                "jobId": 12,
                "answers": {"q": "x" * DRAFT_CONTENT_MAX_BYTES},
            })

    def test_the_size_ceiling_counts_bytes_not_characters(self):
        # Three bytes per character in UTF-8, so a third of the cap in
        # characters is already over it once the keys are added.
        with self.assertRaises(pydantic.ValidationError):
            ApplicationDraftSaveDto.model_validate({
                "jobId": 12,
                "personal": {"bio": "\u4e2d" * (DRAFT_CONTENT_MAX_BYTES // 3)},
            })

    def test_draft_response_is_camel_case(self):
        dto = ApplicationDraftDto(job_id=12, resume_sha256=SHA, resume_object_key=KEY)
        dumped = dto.model_dump(by_alias=True)
        self.assertEqual(dumped["jobId"], 12)
        self.assertEqual(dumped["resumeSha256"], SHA)
        self.assertEqual(dumped["resumeObjectKey"], KEY)
        self.assertIn("updatedAt", dumped)

    def test_my_applications_defaults_to_no_drafts(self):
        dto = MyApplicationsDto(applications=[])
        self.assertEqual(dto.drafts, [])
        self.assertIn("drafts", dto.model_dump(by_alias=True))


if __name__ == "__main__":
    unittest.main()
