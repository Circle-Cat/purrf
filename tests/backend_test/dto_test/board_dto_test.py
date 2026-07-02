import unittest
import pydantic

from backend.dto.board_dto import REJECT_REASONS, StageChangeDto, SubStatusChangeDto
from backend.common.recruiting_enums import ApplicationStage


class TestStageChangeDto(unittest.TestCase):
    def test_advance_without_reason_is_fine(self):
        dto = StageChangeDto.model_validate({"toStage": ApplicationStage.TECH.value})
        self.assertIsNone(dto.reason)

    def test_reject_requires_a_reason(self):
        with self.assertRaises(pydantic.ValidationError):
            StageChangeDto.model_validate({"toStage": ApplicationStage.REJECTED.value})

    def test_reject_reason_must_be_from_fixed_list(self):
        with self.assertRaises(pydantic.ValidationError):
            StageChangeDto.model_validate({
                "toStage": ApplicationStage.REJECTED.value,
                "reason": "not a real reason",
            })

    def test_reject_with_valid_reason_is_accepted(self):
        dto = StageChangeDto.model_validate({
            "toStage": ApplicationStage.REJECTED.value,
            "reason": REJECT_REASONS[0],
            "note": "some note",
        })
        self.assertEqual(dto.reason, REJECT_REASONS[0])
        self.assertEqual(dto.note, "some note")


class TestSubStatusChangeDto(unittest.TestCase):
    def test_accepts_camel_case_field(self):
        dto = SubStatusChangeDto.model_validate({"subStatus": "in_progress"})
        self.assertEqual(dto.sub_status, "in_progress")


if __name__ == "__main__":
    unittest.main()
