import unittest

from backend.common.recruiting_enums import NotificationStatus
from backend.entity.notification_entity import NotificationEntity


class NotificationEntityTest(unittest.TestCase):
    def test_points_at_an_event_instead_of_five_nullable_foreign_keys(self):
        """A row says only "this user needs to know about this event".

        What happened, who did it and what it was about all live on the
        event, so the columns that used to carry them here are gone and the
        pointer that replaced them is required.
        """
        columns = NotificationEntity.__table__.columns
        self.assertIn("event_id", columns)
        self.assertFalse(columns["event_id"].nullable)
        for retired in (
            "application_id",
            "round",
            "comment_id",
            "job_id",
            "job_review_id",
            "type",
            "actor_user_id",
            "email_sent_at",
        ):
            self.assertNotIn(retired, columns)

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
