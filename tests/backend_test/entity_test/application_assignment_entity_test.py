import unittest
from backend.entity.application_assignment_entity import ApplicationAssignmentEntity
from backend.common.recruiting_enums import ApplicationStage


class TestApplicationAssignmentEntity(unittest.TestCase):
    def test_assignment_carries_application_stage_round_and_assignee(self):
        assignment = ApplicationAssignmentEntity(
            application_id=1,
            stage=ApplicationStage.RECRUITER_SCREENING,
            round=2,
            assignee_id=2,
            assigned_by=3,
        )
        self.assertEqual(assignment.__tablename__, "application_assignment")
        self.assertEqual(assignment.application_id, 1)
        self.assertEqual(assignment.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(assignment.round, 2)
        self.assertEqual(assignment.assignee_id, 2)
        self.assertEqual(assignment.assigned_by, 3)

    def test_round_column_default_is_one(self):
        column = ApplicationAssignmentEntity.__table__.c.round
        self.assertEqual(column.default.arg, 1)
        self.assertEqual(column.server_default.arg, "1")


if __name__ == "__main__":
    unittest.main()
