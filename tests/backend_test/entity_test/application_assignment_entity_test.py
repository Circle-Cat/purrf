import unittest
from backend.entity.application_assignment_entity import ApplicationAssignmentEntity
from backend.common.recruiting_enums import ApplicationStage


class TestApplicationAssignmentEntity(unittest.TestCase):
    def test_assignment_carries_application_stage_and_assignee(self):
        assignment = ApplicationAssignmentEntity(
            application_id=1,
            stage=ApplicationStage.RECRUITER_SCREENING,
            assignee_id=2,
            assigned_by=3,
        )
        self.assertEqual(assignment.__tablename__, "application_assignment")
        self.assertEqual(assignment.application_id, 1)
        self.assertEqual(assignment.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(assignment.assignee_id, 2)
        self.assertEqual(assignment.assigned_by, 3)


if __name__ == "__main__":
    unittest.main()
