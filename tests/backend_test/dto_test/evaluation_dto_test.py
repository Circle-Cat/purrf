import unittest
from datetime import datetime

import pydantic

from backend.dto.evaluation_dto import (
    EvaluationDto,
    EvaluationSubmitDto,
    MyEvaluationDto,
)
from backend.common.recruiting_enums import ApplicationStage


class TestEvaluationSubmitDto(unittest.TestCase):
    def test_round_trips_responses_and_confirm(self):
        dto = EvaluationSubmitDto.model_validate(
            {"responses": {"q1": "strong hire"}, "confirm": True}
        )
        self.assertEqual(dto.responses, {"q1": "strong hire"})
        self.assertTrue(dto.confirm)

    def test_confirm_defaults_false(self):
        dto = EvaluationSubmitDto.model_validate({"responses": {"q1": "notes"}})
        self.assertFalse(dto.confirm)

    def test_unknown_field_is_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            EvaluationSubmitDto.model_validate(
                {"responses": {}, "confirm": False, "bogus": "nope"}
            )


class TestEvaluationDto(unittest.TestCase):
    def test_constructs_with_all_fields(self):
        dto = EvaluationDto.model_validate(
            {
                "id": 1,
                "applicationId": 2,
                "stage": ApplicationStage.TECH.value,
                "evaluatorId": 3,
                "responses": {"q1": "hire"},
                "isConfirmed": True,
                "confirmedAt": "2026-07-03T00:00:00",
            }
        )
        self.assertEqual(dto.id, 1)
        self.assertEqual(dto.application_id, 2)
        self.assertEqual(dto.stage, ApplicationStage.TECH)
        self.assertEqual(dto.evaluator_id, 3)
        self.assertEqual(dto.responses, {"q1": "hire"})
        self.assertTrue(dto.is_confirmed)
        self.assertEqual(dto.confirmed_at, datetime(2026, 7, 3))

    def test_confirmed_at_defaults_none(self):
        dto = EvaluationDto.model_validate(
            {
                "id": 1,
                "applicationId": 2,
                "stage": ApplicationStage.TECH.value,
                "evaluatorId": 3,
                "responses": {},
                "isConfirmed": False,
            }
        )
        self.assertIsNone(dto.confirmed_at)


class TestMyEvaluationDto(unittest.TestCase):
    def test_constructs_with_all_fields(self):
        dto = MyEvaluationDto.model_validate(
            {
                "applicationId": 5,
                "jobTitle": "Software Engineer",
                "applicantName": "Ada Lovelace",
                "stage": ApplicationStage.BEHAVIORAL.value,
                "isConfirmed": False,
            }
        )
        self.assertEqual(dto.application_id, 5)
        self.assertEqual(dto.job_title, "Software Engineer")
        self.assertEqual(dto.applicant_name, "Ada Lovelace")
        self.assertEqual(dto.stage, ApplicationStage.BEHAVIORAL)
        self.assertFalse(dto.is_confirmed)


if __name__ == "__main__":
    unittest.main()
