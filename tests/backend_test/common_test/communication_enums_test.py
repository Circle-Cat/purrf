"""Unit tests for communication enums and Inbox-related contexts."""

import unittest

from backend.common.communication_enums import (
    INBOX_CONTEXT,
    InboundKind,
    InboxService,
)


class CommunicationEnumsTest(unittest.TestCase):
    def test_every_service_has_its_own_inbox_context(self):
        self.assertEqual(
            {s: c.value for s, c in INBOX_CONTEXT.items()},
            {
                InboxService.MENTORSHIP: "mentorship_inbox",
                InboxService.RECRUITING: "recruiting_inbox",
                InboxService.INQUIRIES: "inquiries_inbox",
            },
        )

    def test_inbound_kinds(self):
        self.assertEqual(
            [k.value for k in InboundKind], ["human", "auto_reply", "bounce"]
        )


if __name__ == "__main__":
    unittest.main()
