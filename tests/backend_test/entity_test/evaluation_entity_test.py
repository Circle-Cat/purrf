import unittest
from backend.entity.evaluation_entity import EvaluationEntity
from backend.common.recruiting_enums import ApplicationStage


class TestEvaluationEntity(unittest.TestCase):
    def test_evaluation_carries_application_stage_evaluator_and_responses(self):
        evaluation = EvaluationEntity(
            application_id=1,
            stage=ApplicationStage.TECH,
            evaluator_id=2,
            responses={"score": 4},
        )
        self.assertEqual(evaluation.__tablename__, "evaluation")
        self.assertEqual(evaluation.application_id, 1)
        self.assertEqual(evaluation.stage, ApplicationStage.TECH)
        self.assertEqual(evaluation.evaluator_id, 2)
        self.assertEqual(evaluation.responses, {"score": 4})


if __name__ == "__main__":
    unittest.main()
