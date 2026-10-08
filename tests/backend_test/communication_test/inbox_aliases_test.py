import os
import unittest
from unittest.mock import patch

from backend.common.communication_enums import InboxService
from backend.communication.inbox_aliases import InboxAliases


class InboxAliasesTest(unittest.TestCase):
    def setUp(self):
        self.aliases = InboxAliases(
            mentorship="Mentorship-Test@circlecat.org",
            recruiting="recruiting-test@circlecat.org",
            inquiries=None,
        )

    def test_first_claimed_recipient_wins(self):
        self.assertEqual(
            self.aliases.service_for([
                "a@example.com",
                "recruiting-test@circlecat.org",
                "mentorship-test@circlecat.org",
            ]),
            InboxService.RECRUITING,
        )

    def test_unset_service_claims_nothing(self):
        self.assertIsNone(self.aliases.service_for(["inquiries-test@circlecat.org"]))
        self.assertIsNone(self.aliases.alias_of(InboxService.INQUIRIES))

    def test_addresses_are_lowercase_and_skip_unset(self):
        self.assertEqual(
            self.aliases.addresses(),
            ["mentorship-test@circlecat.org", "recruiting-test@circlecat.org"],
        )

    def test_from_env_treats_blank_as_unset(self):
        with patch.dict(os.environ, {"GMAIL_SENDER_MENTORSHIP": "  "}, clear=False):
            self.assertIsNone(InboxAliases.from_env().mentorship)

    def test_from_env_reads_the_senders(self):
        env = {
            "GMAIL_SENDER_MENTORSHIP": " M@x.org ",
            "GMAIL_SENDER_RECRUITING": "r@x.org",
            "GMAIL_SENDER_INQUIRIES": "I@x.org",
            "GMAIL_INBOX_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            aliases = InboxAliases.from_env()
        self.assertEqual(aliases.addresses(), ["m@x.org", "r@x.org", "i@x.org"])
        self.assertEqual(aliases.service_for(["r@x.org"]), InboxService.RECRUITING)

    def test_from_env_claims_nothing_unless_enabled(self):
        for flag in ("", "false", "1"):
            env = {"GMAIL_SENDER_MENTORSHIP": "m@x.org", "GMAIL_INBOX_ENABLED": flag}
            with patch.dict(os.environ, env, clear=False):
                aliases = InboxAliases.from_env()
            self.assertIsNone(aliases.service_for(["m@x.org"]), flag)
            self.assertEqual(aliases.alias_of(InboxService.MENTORSHIP), "m@x.org")

    def test_service_for_is_case_insensitive(self):
        self.assertEqual(
            self.aliases.service_for(["MENTORSHIP-TEST@circlecat.org"]),
            InboxService.MENTORSHIP,
        )


if __name__ == "__main__":
    unittest.main()
