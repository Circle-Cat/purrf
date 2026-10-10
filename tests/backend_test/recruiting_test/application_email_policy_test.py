import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from backend.common.communication_enums import ContextType
from backend.communication.person_email_service import BodyFormat, PersonAddress
from backend.recruiting.application_email_policy import (
    RecruitingApplicationEmailPolicy,
)


class RecruitingApplicationEmailPolicyTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = Mock()
        self.person_email = Mock()
        self.person_email.default_sender_address = "recruiting@circlecat.org"
        self.person_email.person_email_addresses = AsyncMock(
            return_value=[
                PersonAddress(address="sofia@x.com", is_primary=True),
                PersonAddress(address="sofia.old@y.com", is_primary=False),
            ]
        )
        self.user_emails = Mock()
        self.user_emails.get_contact_email = AsyncMock(return_value="Sofia@X.com")
        self.policy = RecruitingApplicationEmailPolicy(
            person_email_service=self.person_email,
            user_emails_repository=self.user_emails,
        )
        self.application = SimpleNamespace(application_id=7, user_id=40)

    async def test_an_owner_writes_to_the_contact_first_and_any_other_address(self):
        policy = await self.policy.resolve(
            self.session, self.application, may_send=True
        )

        self.assertEqual(
            (policy.user_id, policy.context_type, policy.context_id),
            (40, ContextType.APPLICATION, 7),
        )
        self.assertEqual(policy.sender_address, "recruiting@circlecat.org")
        self.assertEqual(policy.body_format, BodyFormat.RICH)
        self.assertTrue(policy.can_send)
        self.assertEqual(
            [(o.address, o.label) for o in policy.recipient_options],
            [("Sofia@X.com", "Primary contact"), ("sofia.old@y.com", "Alternative")],
        )
        self.assertEqual(policy.default_to, "Sofia@X.com")
        self.user_emails.get_contact_email.assert_awaited_once_with(self.session, 40)

    async def test_a_primary_that_is_not_the_contact_is_an_alternative(self):
        self.user_emails.get_contact_email.return_value = "sofia.old@y.com"

        policy = await self.policy.resolve(
            self.session, self.application, may_send=True
        )

        self.assertEqual(
            [(o.address, o.label) for o in policy.recipient_options],
            [("sofia.old@y.com", "Primary contact"), ("sofia@x.com", "Alternative")],
        )
        self.assertEqual(policy.default_to, "sofia.old@y.com")

    async def test_no_contact_address_offers_what_the_applicant_has_with_no_default(
        self,
    ):
        self.user_emails.get_contact_email.return_value = None

        policy = await self.policy.resolve(
            self.session, self.application, may_send=True
        )

        self.assertEqual(
            [(o.address, o.label) for o in policy.recipient_options],
            [("sofia@x.com", "Alternative"), ("sofia.old@y.com", "Alternative")],
        )
        self.assertIsNone(policy.default_to)

    async def test_a_reader_gets_no_compose_choices_and_no_lookups(self):
        policy = await self.policy.resolve(
            self.session, self.application, may_send=False
        )

        self.assertFalse(policy.can_send)
        self.assertEqual((policy.recipient_options, policy.default_to), ((), None))
        self.user_emails.get_contact_email.assert_not_awaited()
        self.person_email.person_email_addresses.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
