import unittest

from backend.entity.mentorship_participant_note_entity import (
    MentorshipParticipantNoteEntity,
)


class TestMentorshipParticipantNoteEntity(unittest.TestCase):
    def test_table_name_and_columns(self):
        cols = set(MentorshipParticipantNoteEntity.__table__.columns.keys())
        self.assertEqual(
            MentorshipParticipantNoteEntity.__tablename__,
            "mentorship_participant_note",
        )
        self.assertEqual(
            cols,
            {
                "note_id",
                "user_id",
                "round_id",
                "pair_id",
                "tag",
                "body",
                "author_user_id",
                "request_id",
                "created_at",
            },
        )

    def test_anchor_is_user_and_round_not_registration(self):
        table = MentorshipParticipantNoteEntity.__table__
        self.assertFalse(table.columns["user_id"].nullable)
        self.assertFalse(table.columns["round_id"].nullable)
        self.assertNotIn("participant_id", table.columns)

    def test_tag_and_pair_are_optional_author_is_not(self):
        table = MentorshipParticipantNoteEntity.__table__
        self.assertTrue(table.columns["tag"].nullable)
        self.assertTrue(table.columns["pair_id"].nullable)
        self.assertFalse(table.columns["author_user_id"].nullable)
        self.assertFalse(table.columns["body"].nullable)


if __name__ == "__main__":
    unittest.main()
