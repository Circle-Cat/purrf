import unittest

from backend.common.user_enums import BlockRequestStatus
from backend.entity.block_request_entity import BlockRequestEntity


class TestBlockRequestEntity(unittest.TestCase):
    def test_table_name_and_columns(self):
        cols = set(BlockRequestEntity.__table__.columns.keys())
        self.assertEqual(BlockRequestEntity.__tablename__, "block_request")
        self.assertEqual(
            cols,
            {
                "request_id",
                "target_user_id",
                "raised_by",
                "raised_from",
                "reason",
                "reviewer_id",
                "status",
                "decided_by",
                "decided_at",
                "decision_note",
                "created_at",
            },
        )

    def test_status_defaults_to_pending(self):
        col = BlockRequestEntity.__table__.columns["status"]
        self.assertIs(col.default.arg, BlockRequestStatus.PENDING)
        self.assertFalse(col.nullable)


if __name__ == "__main__":
    unittest.main()
