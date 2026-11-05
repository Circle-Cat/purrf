import unittest

from backend.entity.event_entity import EventEntity


class EventEntityTest(unittest.TestCase):
    def test_table_name(self):
        self.assertEqual(EventEntity.__tablename__, "event")

    def test_subject_is_a_free_form_type_plus_id(self):
        columns = EventEntity.__table__.columns
        self.assertIn("subject_type", columns)
        self.assertIn("subject_id", columns)
        self.assertFalse(columns["subject_type"].nullable)
        self.assertFalse(columns["subject_id"].nullable)

    def test_subject_type_is_not_an_enum(self):
        """mentorship and leave will write here too; adding a domain must not alter the table."""
        self.assertEqual(
            EventEntity.__table__.columns["subject_type"].type.python_type, str
        )

    def test_subject_is_indexed_because_the_timeline_queries_by_it(self):
        index_columns = {
            tuple(sorted(column.name for column in index.columns))
            for index in EventEntity.__table__.indexes
        }
        self.assertIn(("subject_id", "subject_type"), index_columns)


if __name__ == "__main__":
    unittest.main()
