import unittest

import pydantic

from backend.dto.training_course_dto import (
    TrainingAssignmentRequestDto,
    TrainingCourseCreateDto,
    TrainingCourseUpdateDto,
)


class TestTrainingCourseCreateDto(unittest.TestCase):
    def test_a_name_of_only_spaces_is_refused(self):
        """Otherwise min_length passes and the service stores an empty name."""
        with self.assertRaises(pydantic.ValidationError):
            TrainingCourseCreateDto.model_validate({"name": "   "})

    def test_a_name_is_stored_without_its_surrounding_spaces(self):
        dto = TrainingCourseCreateDto.model_validate({"name": "  Onboarding  "})

        self.assertEqual(dto.name, "Onboarding")

    def test_an_unknown_key_is_refused(self):
        with self.assertRaises(pydantic.ValidationError):
            TrainingCourseCreateDto.model_validate(
                {"name": "Onboarding", "category": "mentorship_mentor_onboarding"}
            )


class TestTrainingCourseUpdateDto(unittest.TestCase):
    def test_a_rename_to_only_spaces_is_refused(self):
        with self.assertRaises(pydantic.ValidationError):
            TrainingCourseUpdateDto.model_validate({"name": "   "})

    def test_an_unknown_key_is_refused(self):
        with self.assertRaises(pydantic.ValidationError):
            TrainingCourseUpdateDto.model_validate({"isActive": False, "verified": True})


class TestTrainingAssignmentRequestDto(unittest.TestCase):
    def test_an_unknown_key_is_refused(self):
        """A body naming its own training_id must not be silently ignored."""
        with self.assertRaises(pydantic.ValidationError):
            TrainingAssignmentRequestDto.model_validate(
                {"userId": 1, "courseId": 2, "trainingId": 9}
            )

    def test_the_camel_case_body_the_page_sends_is_accepted(self):
        dto = TrainingAssignmentRequestDto.model_validate({"userId": 1, "courseId": 2})

        self.assertEqual(dto.user_id, 1)
        self.assertEqual(dto.course_id, 2)


if __name__ == "__main__":
    unittest.main()
