import unittest

from backend.common.recruiting_enums import NotificationStatus
from backend.entity.notification_entity import NotificationEntity


class NotificationEntityTest(unittest.TestCase):
    def test_can_point_at_an_event(self):
        columns = NotificationEntity.__table__.columns
        self.assertIn("event_id", columns)

    def test_event_id_is_nullable_until_the_old_writers_are_migrated(self):
        """Expand now, contract in Task 11. Existing writers set no event_id."""
        self.assertTrue(NotificationEntity.__table__.columns["event_id"].nullable)

    def test_the_retired_columns_are_still_here_during_the_expand(self):
        """Removing them now would break seven test targets until Task 8."""
        columns = NotificationEntity.__table__.columns
        for still_needed in (
            "application_id",
            "round",
            "comment_id",
            "job_id",
            "job_review_id",
            "type",
            "actor_user_id",
            "email_sent_at",
        ):
            self.assertIn(still_needed, columns)

    def test_delivery_status_defaults_to_pending(self):
        self.assertEqual(
            NotificationEntity.__table__.columns["status"].default.arg,
            NotificationStatus.PENDING,
        )

    def test_claimed_at_is_nullable_because_an_unsent_row_has_no_claim(self):
        self.assertTrue(NotificationEntity.__table__.columns["claimed_at"].nullable)

    def test_dismissal_is_a_mark_not_a_delete(self):
        """The row also carries the email state machine, so deleting it loses the email."""
        self.assertIn("dismissed_at", NotificationEntity.__table__.columns)
        self.assertTrue(NotificationEntity.__table__.columns["dismissed_at"].nullable)


if __name__ == "__main__":
    unittest.main()
