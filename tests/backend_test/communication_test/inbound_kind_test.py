import unittest

from backend.common.communication_enums import InboundKind
from backend.communication.inbound_kind import classify_inbound


class ClassifyInboundTest(unittest.TestCase):
    def test_bounce_wins_over_auto_submitted(self):
        self.assertEqual(
            classify_inbound({"failed_recipients": "", "auto_submitted": "auto-replied"}),
            InboundKind.BOUNCE,
        )

    def test_out_of_office_is_auto_reply(self):
        self.assertEqual(
            classify_inbound({"failed_recipients": None, "auto_submitted": "auto-replied"}),
            InboundKind.AUTO_REPLY,
        )

    def test_precedence_bulk_is_auto_reply(self):
        self.assertEqual(
            classify_inbound({"failed_recipients": None, "precedence": "Bulk"}),
            InboundKind.AUTO_REPLY,
        )

    def test_auto_submitted_no_is_human(self):
        self.assertEqual(
            classify_inbound({"failed_recipients": None, "auto_submitted": "no"}),
            InboundKind.HUMAN,
        )

    def test_plain_message_is_human(self):
        self.assertEqual(classify_inbound({"failed_recipients": None}), InboundKind.HUMAN)


if __name__ == "__main__":
    unittest.main()
