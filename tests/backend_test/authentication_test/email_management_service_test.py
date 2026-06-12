import os
import time
import unittest
from unittest.mock import AsyncMock, MagicMock

import jwt

from backend.authentication.email_management_service import EmailManagementService
from backend.common.exceptions import ConflictError
from backend.common.user_role import IdentityType
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.user_identities_entity import UserIdentitiesEntity

_SECRET = "test-state-secret"
_USER_ID = 42
_CURRENT_SUB = "google-oauth2|primary"
_TARGET_EMAIL = "alice@gmail.com"
_NEW_SUB = "email|abc123"


def _state(user_id=_USER_ID, email=_TARGET_EMAIL, flow="add_email"):
    now = int(time.time())
    return jwt.encode(
        {
            "user_id": user_id,
            "sub": _CURRENT_SUB,
            "email": email,
            "flow": flow,
            "iat": now,
            "exp": now + 600,
        },
        _SECRET,
        algorithm="HS256",
    )


class TestEmailManagementService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        os.environ["EMAIL_OTP_STATE_JWT_SECRET"] = _SECRET
        self.auth0 = MagicMock()
        self.auth0.exchange_otp.return_value = {
            "sub": _NEW_SUB,
            "email": _TARGET_EMAIL,
            "email_verified": True,
        }
        self.user_emails = AsyncMock()
        self.user_emails.exists_confirmed_on_other_user.return_value = False
        self.user_emails.get_by_user_and_email.return_value = None
        self.user_emails.has_primary.return_value = False
        self.user_identities = AsyncMock()
        self.user_identities.get_by_subject_identifier.return_value = None
        self.session = AsyncMock()
        self.service = EmailManagementService(
            self.auth0, self.user_emails, self.user_identities, MagicMock()
        )

    async def test_initiate_sends_otp_and_returns_decodable_state(self):
        result = await self.service.initiate(
            self.session, _USER_ID, _CURRENT_SUB, " Alice@Gmail.com "
        )
        self.auth0.start_passwordless.assert_called_once_with(_TARGET_EMAIL)
        claims = jwt.decode(result["state"], _SECRET, algorithms=["HS256"])
        self.assertEqual(claims["email"], _TARGET_EMAIL)
        self.assertEqual(claims["user_id"], _USER_ID)

    async def test_initiate_rejects_invalid_email(self):
        with self.assertRaises(ValueError):
            await self.service.initiate(
                self.session, _USER_ID, _CURRENT_SUB, "not-an-email"
            )
        self.auth0.start_passwordless.assert_not_called()

    async def test_initiate_conflict_when_confirmed_elsewhere(self):
        self.user_emails.exists_confirmed_on_other_user.return_value = True
        with self.assertRaises(ConflictError):
            await self.service.initiate(
                self.session, _USER_ID, _CURRENT_SUB, _TARGET_EMAIL
            )
        self.auth0.start_passwordless.assert_not_called()

    async def test_verify_happy_path_confirms_email_and_links_identity(self):
        result = await self.service.verify(
            self.session, _USER_ID, _CURRENT_SUB, _state(), "123456"
        )

        self.auth0.link_identity.assert_called_once_with(
            primary_sub=_CURRENT_SUB, provider="email", secondary_user_id="abc123"
        )
        email_entity = self.user_emails.upsert_email.call_args.kwargs["entity"]
        self.assertTrue(email_entity.otp_confirmed)
        self.assertTrue(email_entity.is_primary)  # no existing primary -> auto
        identity_entity = self.user_identities.upsert_identity.call_args.kwargs[
            "entity"
        ]
        self.assertEqual(identity_entity.subject_identifier, _NEW_SUB)
        self.session.commit.assert_awaited_once()
        self.auth0.add_alias_email_to_primary.assert_called_once()
        self.assertEqual(result["linked_sub"], _NEW_SUB)

    async def test_verify_marks_external_identity_for_outside_email(self):
        """A non-company address (the default alice@gmail.com) yields an
        EXTERNAL identity."""
        await self.service.verify(
            self.session, _USER_ID, _CURRENT_SUB, _state(), "123456"
        )

        identity_entity = self.user_identities.upsert_identity.call_args.kwargs[
            "entity"
        ]
        self.assertEqual(identity_entity.identity_type, IdentityType.EXTERNAL)

    async def test_verify_marks_internal_identity_for_company_email(self):
        """Both CircleCat domains (@u.circlecat.org Microsoft, @circlecat.org
        Google) mark the new identity INTERNAL."""
        for company_email in ("bob@u.circlecat.org", "bob@circlecat.org"):
            with self.subTest(email=company_email):
                self.user_identities.upsert_identity.reset_mock()
                self.auth0.exchange_otp.return_value = {
                    "sub": _NEW_SUB,
                    "email": company_email,
                    "email_verified": True,
                }

                await self.service.verify(
                    self.session,
                    _USER_ID,
                    _CURRENT_SUB,
                    _state(email=company_email),
                    "123456",
                )

                identity_entity = self.user_identities.upsert_identity.call_args.kwargs[
                    "entity"
                ]
                self.assertEqual(identity_entity.identity_type, IdentityType.INTERNAL)
                self.assertEqual(identity_entity.email_claim, company_email)

    async def test_verify_rejects_state_for_other_user(self):
        with self.assertRaises(ValueError):
            await self.service.verify(
                self.session, _USER_ID, _CURRENT_SUB, _state(user_id=999), "123456"
            )
        self.auth0.exchange_otp.assert_not_called()

    async def test_verify_rejects_tampered_state_signature(self):
        forged = jwt.encode(
            {
                "user_id": _USER_ID,
                "sub": _CURRENT_SUB,
                "email": _TARGET_EMAIL,
                "flow": "add_email",
                "iat": int(time.time()),
                "exp": int(time.time()) + 600,
            },
            "wrong-secret",
            algorithm="HS256",
        )
        with self.assertRaises(ValueError):
            await self.service.verify(
                self.session, _USER_ID, _CURRENT_SUB, forged, "123456"
            )
        self.auth0.exchange_otp.assert_not_called()

    async def test_verify_rejects_expired_state(self):
        now = int(time.time())
        expired = jwt.encode(
            {
                "user_id": _USER_ID,
                "sub": _CURRENT_SUB,
                "email": _TARGET_EMAIL,
                "flow": "add_email",
                "iat": now - 1200,
                "exp": now - 600,
            },
            _SECRET,
            algorithm="HS256",
        )
        with self.assertRaises(ValueError):
            await self.service.verify(
                self.session, _USER_ID, _CURRENT_SUB, expired, "123456"
            )
        self.auth0.exchange_otp.assert_not_called()

    async def test_verify_rejects_wrong_flow(self):
        with self.assertRaises(ValueError):
            await self.service.verify(
                self.session,
                _USER_ID,
                _CURRENT_SUB,
                _state(flow="delete_email"),
                "123456",
            )
        self.auth0.exchange_otp.assert_not_called()

    async def test_verify_rejects_unverified_email(self):
        self.auth0.exchange_otp.return_value = {
            "sub": _NEW_SUB,
            "email": _TARGET_EMAIL,
            "email_verified": False,
        }
        with self.assertRaises(ValueError):
            await self.service.verify(
                self.session, _USER_ID, _CURRENT_SUB, _state(), "123456"
            )
        self.session.commit.assert_not_awaited()

    async def test_verify_conflict_when_sub_owned_by_other_user(self):
        self.user_identities.get_by_subject_identifier.return_value = (
            UserIdentitiesEntity(user_id=999, subject_identifier=_NEW_SUB)
        )
        with self.assertRaises(ConflictError):
            await self.service.verify(
                self.session, _USER_ID, _CURRENT_SUB, _state(), "123456"
            )
        self.auth0.link_identity.assert_not_called()

    async def test_verify_promotes_existing_unconfirmed_row_without_new_identity(self):
        existing_email = UserEmailsEntity(
            user_id=_USER_ID, email=_TARGET_EMAIL, otp_confirmed=False, is_primary=False
        )
        self.user_emails.get_by_user_and_email.return_value = existing_email
        self.user_identities.get_by_subject_identifier.return_value = (
            UserIdentitiesEntity(user_id=_USER_ID, subject_identifier=_NEW_SUB)
        )

        await self.service.verify(
            self.session, _USER_ID, _CURRENT_SUB, _state(), "123456"
        )

        self.assertTrue(existing_email.otp_confirmed)
        # Identity already present for this user -> no new identity row inserted.
        self.user_identities.upsert_identity.assert_not_called()
        self.session.commit.assert_awaited_once()

    async def test_verify_succeeds_even_if_alias_sync_fails(self):
        self.auth0.add_alias_email_to_primary.side_effect = RuntimeError("auth0 down")
        result = await self.service.verify(
            self.session, _USER_ID, _CURRENT_SUB, _state(), "123456"
        )
        # Alias sync is best-effort: DB already committed, no error surfaced.
        self.session.commit.assert_awaited_once()
        self.assertEqual(result["linked_sub"], _NEW_SUB)


if __name__ == "__main__":
    unittest.main()
