import unittest

from backend.common.approval_enums import ApprovalRequestStatus
from backend.entity.approval_request_entity import ApprovalRequestEntity


class TestApprovalRequestEntity(unittest.TestCase):
    def test_table_name_and_columns(self):
        cols = set(ApprovalRequestEntity.__table__.columns.keys())
        self.assertEqual(ApprovalRequestEntity.__tablename__, "approval_request")
        self.assertEqual(
            cols,
            {
                "request_id",
                "action",
                "target_type",
                "target_id",
                "payload",
                "reason",
                "raised_by",
                "reviewer_id",
                "status",
                "decided_by",
                "decided_at",
                "decision_comment",
                "created_at",
            },
        )

    def test_status_defaults_to_pending(self):
        col = ApprovalRequestEntity.__table__.columns["status"]
        self.assertIs(col.default.arg, ApprovalRequestStatus.PENDING)
        self.assertFalse(col.nullable)

    def test_one_pending_request_per_target(self):
        index = next(
            i
            for i in ApprovalRequestEntity.__table__.indexes
            if i.name == "ux_approval_request_pending_target"
        )
        self.assertTrue(index.unique)
        self.assertEqual(
            [c.name for c in index.columns], ["action", "target_type", "target_id"]
        )
        self.assertEqual(
            str(index.dialect_options["postgresql"]["where"]), "status = 'pending'"
        )


if __name__ == "__main__":
    unittest.main()
