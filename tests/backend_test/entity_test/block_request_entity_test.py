from backend.common.user_enums import BlockRequestStatus
from backend.entity.block_request_entity import BlockRequestEntity


def test_table_name_and_columns():
    cols = set(BlockRequestEntity.__table__.columns.keys())
    assert BlockRequestEntity.__tablename__ == "block_request"
    assert cols == {
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
    }


def test_status_defaults_to_pending():
    col = BlockRequestEntity.__table__.columns["status"]
    assert col.default.arg is BlockRequestStatus.PENDING
    assert col.nullable is False
