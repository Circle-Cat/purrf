import unittest
import pydantic

from backend.dto.board_dto import (
    REJECT_REASONS,
    BlacklistDto,
    BoardCardDto,
    BoardJobDto,
    PipelineStageInfoDto,
    RoundChangeDto,
    StageChangeDto,
    SubStatusChangeDto,
)
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

    def test_assignee_id_defaults_none(self):
        dto = StageChangeDto.model_validate({"toStage": "hired"})
        self.assertIsNone(dto.assignee_id)

    def test_assignee_id_round_trips(self):
        dto = StageChangeDto.model_validate({"toStage": "tech", "assigneeId": 7})
        self.assertEqual(dto.assignee_id, 7)


class TestSubStatusChangeDto(unittest.TestCase):
    def test_accepts_camel_case_field(self):
        dto = SubStatusChangeDto.model_validate({"subStatus": "in_progress"})
        self.assertEqual(dto.sub_status, "in_progress")


class TestBlacklistDto(unittest.TestCase):
    def test_accepts_camel_case_fields(self):
        dto = BlacklistDto.model_validate({
            "userId": 3,
            "applicationId": 10,
            "reason": "Fabricated credentials",
        })
        self.assertEqual(dto.user_id, 3)
        self.assertEqual(dto.application_id, 10)
        self.assertEqual(dto.reason, "Fabricated credentials")

    def test_blank_reason_is_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            BlacklistDto.model_validate({
                "userId": 3,
                "applicationId": 10,
                "reason": "   ",
            })

    def test_missing_reason_is_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            BlacklistDto.model_validate({"userId": 3, "applicationId": 10})


class TestRoundChangeDto(unittest.TestCase):
    def test_accepts_a_positive_round(self):
        dto = RoundChangeDto.model_validate({"round": 2})
        self.assertEqual(dto.round, 2)

    def test_rejects_a_non_positive_round(self):
        with self.assertRaises(pydantic.ValidationError):
            RoundChangeDto.model_validate({"round": 0})


class TestBoardJobDtoStages(unittest.TestCase):
    def test_stages_is_a_list_of_stage_info(self):
        dto = BoardJobDto(
            id=1,
            title="T",
            kind="employment",
            stages=[PipelineStageInfoDto(stage="tech", rounds=2)],
        )
        self.assertEqual(dto.stages[0].stage, "tech")
        self.assertEqual(dto.stages[0].rounds, 2)


class TestBoardCardDtoRound(unittest.TestCase):
    def test_round_field_present(self):
        dto = BoardCardDto(
            id=1,
            applicant_name="A",
            applicant_email="a@b.com",
            stage="tech",
            round=2,
        )
        self.assertEqual(dto.round, 2)


if __name__ == "__main__":
    unittest.main()
