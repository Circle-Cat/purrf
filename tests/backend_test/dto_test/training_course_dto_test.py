import unittest

import pydantic

from backend.dto.training_course_dto import (
    TrainingBulkAssignmentRequestDto,
    TrainingCourseCreateDto,
    TrainingCourseUpdateDto,
    TrainingProgressDto,
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
            TrainingCourseCreateDto.model_validate({
                "name": "Onboarding",
                "category": "mentorship_mentor_onboarding",
            })


class TestTrainingCourseUpdateDto(unittest.TestCase):
    def test_a_rename_to_only_spaces_is_refused(self):
        with self.assertRaises(pydantic.ValidationError):
            TrainingCourseUpdateDto.model_validate({"name": "   "})

    def test_an_unknown_key_is_refused(self):
        with self.assertRaises(pydantic.ValidationError):
            TrainingCourseUpdateDto.model_validate({
                "isActive": False,
                "verified": True,
            })


class TestTrainingBulkAssignmentRequestDto(unittest.TestCase):
    def test_an_unknown_key_is_refused(self):
        """A body naming its own training_id must not be silently ignored."""
        with self.assertRaises(pydantic.ValidationError):
            TrainingBulkAssignmentRequestDto.model_validate({
                "courseId": 2,
                "userIds": [1],
                "trainingId": 9,
            })

    def test_the_camel_case_body_the_page_sends_is_accepted(self):
        dto = TrainingBulkAssignmentRequestDto.model_validate({
            "courseId": 2,
            "userIds": [1, 3],
        })

        self.assertEqual(dto.course_id, 2)
        self.assertEqual(dto.user_ids, [1, 3])
        self.assertIsNone(dto.deadline)

    def test_a_batch_with_nobody_in_it_is_refused(self):
        """The page submits the ticked ids, so an empty list is a bug in it."""
        with self.assertRaises(pydantic.ValidationError):
            TrainingBulkAssignmentRequestDto.model_validate({
                "courseId": 2,
                "userIds": [],
            })

    def test_a_batch_over_the_cap_is_refused_rather_than_trimmed(self):
        """Same cap as selecting a whole result set. Trimming would assign a
        subset silently, and there is no undo."""
        with self.assertRaises(pydantic.ValidationError):
            TrainingBulkAssignmentRequestDto.model_validate({
                "courseId": 2,
                "userIds": list(range(1001)),
            })


class TestTrainingProgressDto(unittest.TestCase):
    def test_the_accumulated_seconds_are_never_null(self):
        """The column is NOT NULL with a default, so the wire never sees one."""
        with self.assertRaises(pydantic.ValidationError):
            TrainingProgressDto.model_validate({"sessionTimeSeconds": None})


if __name__ == "__main__":
    unittest.main()
