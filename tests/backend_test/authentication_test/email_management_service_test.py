import os
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt

from backend.authentication.email_management_service import EmailManagementService
from backend.common.exceptions import ConflictError
from backend.common.identity_type import IdentityType
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


def _set_primary_state(
    user_id=_USER_ID,
    target_email_id=18,
    primary_email="old@example.com",
    flow="set_primary",
):
    now = int(time.time())
    return jwt.encode(
        {
            "user_id": user_id,
            "target_email_id": target_email_id,
            "primary_email_at_request": primary_email,
            "flow": flow,
            "iat": now,
            "exp": now + 600,
        },
        _SECRET,
        algorithm="HS256",
    )


def _unlink_state(
    user_id=_USER_ID,
    target_identity_id=7,
    primary_email="old@example.com",
    flow="unlink_identity",
):
    now = int(time.time())
    return jwt.encode(
        {
            "user_id": user_id,
            "target_identity_id": target_identity_id,
            "primary_email_at_request": primary_email,
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
        self.user_identities.list_by_user.return_value = []
        self.user_identities.exists_active_internal.return_value = False
        self.session = AsyncMock()
        self.service = EmailManagementService(
            self.auth0,
            self.user_emails,
            self.user_identities,
            MagicMock(),
        )

    def _email_row(self, email, otp_confirmed=True, is_primary=False, user_id=_USER_ID):
        row = UserEmailsEntity(
            user_id=user_id,
            email=email,
            otp_confirmed=otp_confirmed,
            is_primary=is_primary,
        )
        return row

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

    async def test_list_emails_and_identities_assembles_view(self):
        added_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        primary = UserEmailsEntity(
            user_id=_USER_ID,
            email="alice@gmail.com",
            otp_confirmed=True,
            is_primary=True,
            added_at=added_at,
        )
        primary.email_id = 12
        pending = UserEmailsEntity(
            user_id=_USER_ID,
            email="pending@old.com",
            otp_confirmed=False,
            is_primary=False,
            added_at=added_at,
        )
        pending.email_id = 25
        self.user_emails.list_by_user_id.return_value = [primary, pending]

        internal = UserIdentitiesEntity(
            user_id=_USER_ID,
            subject_identifier="google-oauth2|internal",
            identity_type="internal",
            email_claim="yuji@circlecat.org",
        )
        internal.identity_id = 5
        external_current = UserIdentitiesEntity(
            user_id=_USER_ID,
            subject_identifier=_CURRENT_SUB,
            identity_type="external",
            # mixed case to prove case-insensitive linked_identity_count match
            email_claim="Alice@Gmail.com",
        )
        external_current.identity_id = 7
        self.user_identities.list_by_user_id.return_value = [internal, external_current]

        result = await self.service.list_emails_and_identities(
            self.session, _USER_ID, _CURRENT_SUB
        )

        emails = {e.email_id: e for e in result.emails}
        self.assertEqual(emails[12].linked_identity_count, 1)
        self.assertTrue(emails[12].is_primary)
        self.assertTrue(emails[12].otp_confirmed)
        self.assertEqual(emails[25].linked_identity_count, 0)
        self.assertFalse(emails[25].otp_confirmed)

        self.assertEqual(len(result.internal_identities), 1)
        self.assertEqual(result.internal_identities[0].identity_id, 5)
        self.assertEqual(
            result.internal_identities[0].email_claim, "yuji@circlecat.org"
        )

        self.assertEqual(len(result.external_identities), 1)
        ext = result.external_identities[0]
        self.assertEqual(ext.identity_id, 7)
        # external_current carries _CURRENT_SUB -> flagged as the session's primary;
        # the internal identity (a different sub) is not.
        self.assertTrue(ext.is_current_session)
        self.assertFalse(result.internal_identities[0].is_current_session)

    async def test_list_emails_and_identities_no_internal(self):
        self.user_emails.list_by_user_id.return_value = []
        external = UserIdentitiesEntity(
            user_id=_USER_ID,
            subject_identifier="email|other",
            identity_type="external",
            email_claim="alice@gmail.com",
        )
        external.identity_id = 9
        self.user_identities.list_by_user_id.return_value = [external]

        result = await self.service.list_emails_and_identities(
            self.session, _USER_ID, _CURRENT_SUB
        )

        self.assertEqual(result.internal_identities, [])
        self.assertEqual(result.external_identities[0].identity_id, 9)
        self.assertFalse(result.external_identities[0].is_current_session)

    async def test_list_emails_and_identities_multiple_internal(self):
        # An employee may hold more than one internal identity (an SSO login plus
        # an OTP-linked corp email). All must surface, not just the last one.
        self.user_emails.list_by_user_id.return_value = []
        sso = UserIdentitiesEntity(
            user_id=_USER_ID,
            subject_identifier=_CURRENT_SUB,
            identity_type="internal",
            email_claim="yuji@circlecat.org",
        )
        sso.identity_id = 2
        otp_corp = UserIdentitiesEntity(
            user_id=_USER_ID,
            subject_identifier="email|abc123",
            identity_type="internal",
            email_claim="yuji@circlecat.org",
        )
        otp_corp.identity_id = 193
        self.user_identities.list_by_user_id.return_value = [sso, otp_corp]

        result = await self.service.list_emails_and_identities(
            self.session, _USER_ID, _CURRENT_SUB
        )

        ids = {i.identity_id: i for i in result.internal_identities}
        self.assertEqual(set(ids), {2, 193})
        self.assertEqual(result.external_identities, [])
        # The session's own identity (the SSO sub) is still flagged, not dropped.
        self.assertTrue(ids[2].is_current_session)
        self.assertFalse(ids[193].is_current_session)

    # initiate_set_primary — step 1: validate target, OTP the current primary
    async def test_initiate_set_primary_sends_otp_to_current_primary(self):
        self.user_emails.get_by_id.return_value = self._email_row(
            "new@example.com", otp_confirmed=True
        )
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )

        result = await self.service.initiate_set_primary(self.session, _USER_ID, 18)

        # OTP goes to the CURRENT primary, not the target.
        self.auth0.start_passwordless.assert_called_once_with("old@example.com")
        claims = jwt.decode(result["state"], _SECRET, algorithms=["HS256"])
        self.assertEqual(claims["flow"], "set_primary")
        self.assertEqual(claims["target_email_id"], 18)
        self.assertEqual(claims["primary_email_at_request"], "old@example.com")

    async def test_initiate_set_primary_rejects_unconfirmed_target(self):
        self.user_emails.get_by_id.return_value = self._email_row(
            "pending@old.com", otp_confirmed=False
        )

        with self.assertRaises(ValueError):
            await self.service.initiate_set_primary(self.session, _USER_ID, 25)
        self.auth0.start_passwordless.assert_not_called()

    async def test_initiate_set_primary_rejects_missing_target(self):
        self.user_emails.get_by_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.initiate_set_primary(self.session, _USER_ID, 999)
        self.auth0.start_passwordless.assert_not_called()

    async def test_initiate_set_primary_rejects_target_owned_by_other_user(self):
        self.user_emails.get_by_id.return_value = self._email_row(
            "bob@example.com", otp_confirmed=True, user_id=999
        )

        with self.assertRaises(ValueError):
            await self.service.initiate_set_primary(self.session, _USER_ID, 7)
        self.auth0.start_passwordless.assert_not_called()

    async def test_initiate_set_primary_active_employee_rejects_non_corp(self):
        self.user_emails.get_by_id.return_value = self._email_row(
            "alice.personal@gmail.com", otp_confirmed=True
        )
        self.user_identities.exists_active_internal.return_value = True

        with self.assertRaises(PermissionError):
            await self.service.initiate_set_primary(self.session, _USER_ID, 18)
        self.auth0.start_passwordless.assert_not_called()

    async def test_initiate_set_primary_active_employee_allows_microsoft_corp(self):
        # @u.circlecat.org is a company domain too -> allowed for employees.
        self.user_emails.get_by_id.return_value = self._email_row(
            "alice@u.circlecat.org", otp_confirmed=True
        )
        self.user_emails.get_primary.return_value = self._email_row(
            "old@circlecat.org", is_primary=True
        )
        self.user_identities.exists_active_internal.return_value = True

        await self.service.initiate_set_primary(self.session, _USER_ID, 5)

        self.auth0.start_passwordless.assert_called_once_with("old@circlecat.org")

    async def test_initiate_set_primary_rejects_when_no_primary(self):
        self.user_emails.get_by_id.return_value = self._email_row(
            "new@example.com", otp_confirmed=True
        )
        self.user_emails.get_primary.return_value = None

        with self.assertRaises(ValueError):
            await self.service.initiate_set_primary(self.session, _USER_ID, 18)
        self.auth0.start_passwordless.assert_not_called()

    # confirm_set_primary — step 2: recheck primary, verify OTP, swap
    async def test_confirm_set_primary_swaps_on_valid_state_and_otp(self):
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        self.user_emails.get_by_id.return_value = self._email_row(
            "new@example.com", otp_confirmed=True
        )
        state = _set_primary_state(target_email_id=18, primary_email="old@example.com")

        result = await self.service.confirm_set_primary(
            self.session, _USER_ID, 18, state, "123456"
        )

        self.auth0.exchange_otp.assert_called_once_with("old@example.com", "123456")
        self.user_emails.set_primary.assert_awaited_once_with(
            self.session, _USER_ID, 18
        )
        self.session.commit.assert_awaited_once()
        self.assertEqual(result, {"ok": True})

    async def test_confirm_set_primary_rejects_wrong_flow(self):
        state = _set_primary_state(
            target_email_id=18, primary_email="old@example.com", flow="add_email"
        )
        with self.assertRaises(ValueError):
            await self.service.confirm_set_primary(
                self.session, _USER_ID, 18, state, "123456"
            )
        self.auth0.exchange_otp.assert_not_called()
        self.user_emails.set_primary.assert_not_called()

    async def test_confirm_set_primary_rejects_state_for_other_user(self):
        state = _set_primary_state(user_id=999, target_email_id=18)
        with self.assertRaises(ValueError):
            await self.service.confirm_set_primary(
                self.session, _USER_ID, 18, state, "123456"
            )
        self.auth0.exchange_otp.assert_not_called()

    async def test_confirm_set_primary_rejects_email_id_path_mismatch(self):
        # State was minted for target 18 but the path says 99.
        state = _set_primary_state(target_email_id=18)
        with self.assertRaises(ValueError):
            await self.service.confirm_set_primary(
                self.session, _USER_ID, 99, state, "123456"
            )
        self.auth0.exchange_otp.assert_not_called()

    async def test_confirm_set_primary_rejects_when_primary_changed(self):
        # Primary moved since initiate -> refuse before consuming the OTP.
        self.user_emails.get_primary.return_value = self._email_row(
            "changed@example.com", is_primary=True
        )
        state = _set_primary_state(target_email_id=18, primary_email="old@example.com")

        with self.assertRaises(PermissionError):
            await self.service.confirm_set_primary(
                self.session, _USER_ID, 18, state, "123456"
            )
        self.auth0.exchange_otp.assert_not_called()
        self.user_emails.set_primary.assert_not_called()

    async def test_confirm_set_primary_propagates_wrong_otp(self):
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        self.auth0.exchange_otp.side_effect = ValueError("Incorrect or expired code")
        state = _set_primary_state(target_email_id=18, primary_email="old@example.com")

        with self.assertRaises(ValueError):
            await self.service.confirm_set_primary(
                self.session, _USER_ID, 18, state, "000000"
            )
        self.user_emails.set_primary.assert_not_called()
        self.session.commit.assert_not_awaited()

    # unlink step-up — shared fixtures
    def _identity(
        self,
        identity_id,
        subject_identifier,
        identity_type="external",
        email_claim=None,
    ):
        row = UserIdentitiesEntity(
            user_id=_USER_ID,
            subject_identifier=subject_identifier,
            identity_type=identity_type,
            email_claim=email_claim,
        )
        row.identity_id = identity_id
        return row

    def _arrange_unlink(self, target, others):
        """Wire the mocks for an unlink: get_by_id→target, list_by_user→all rows."""
        self.user_identities.get_by_id.return_value = target
        self.user_identities.list_by_user.return_value = [target, *others]

    # initiate_unlink — step 1: validate, OTP the current primary, sign state
    async def test_initiate_unlink_sends_otp_to_primary_and_returns_state(self):
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        keep = self._identity(5, _CURRENT_SUB, "external", "yuji@circlecat.org")
        self._arrange_unlink(target, [keep])
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )

        result = await self.service.initiate_unlink(
            self.session, _USER_ID, _CURRENT_SUB, 7
        )

        # OTP goes to the current primary, not the unlinked identity's address.
        self.auth0.start_passwordless.assert_called_once_with("old@example.com")
        claims = jwt.decode(result["state"], _SECRET, algorithms=["HS256"])
        self.assertEqual(claims["flow"], "unlink_identity")
        self.assertEqual(claims["target_identity_id"], 7)
        self.assertEqual(claims["primary_email_at_request"], "old@example.com")

    async def test_initiate_unlink_rejects_missing_identity(self):
        self.user_identities.get_by_id.return_value = None
        with self.assertRaises(ValueError):
            await self.service.initiate_unlink(self.session, _USER_ID, _CURRENT_SUB, 7)
        self.auth0.start_passwordless.assert_not_called()

    async def test_initiate_unlink_rejects_unowned_identity(self):
        target = self._identity(7, "email|todelete", "external", "x@x.com")
        target.user_id = 999
        self.user_identities.get_by_id.return_value = target
        with self.assertRaises(ValueError):
            await self.service.initiate_unlink(self.session, _USER_ID, _CURRENT_SUB, 7)
        self.auth0.start_passwordless.assert_not_called()

    async def test_initiate_unlink_rejects_last_identity(self):
        target = self._identity(7, "email|todelete", "external", "x@x.com")
        self._arrange_unlink(target, [])
        with self.assertRaises(ConflictError):
            await self.service.initiate_unlink(self.session, _USER_ID, _CURRENT_SUB, 7)
        self.auth0.start_passwordless.assert_not_called()

    async def test_initiate_unlink_rejects_current_session_identity(self):
        target = self._identity(7, _CURRENT_SUB, "external", "x@x.com")
        keep = self._identity(5, "email|other", "external", "y@y.com")
        self._arrange_unlink(target, [keep])
        with self.assertRaises(ConflictError):
            await self.service.initiate_unlink(self.session, _USER_ID, _CURRENT_SUB, 7)
        self.auth0.start_passwordless.assert_not_called()

    async def test_initiate_unlink_rejects_active_employee_internal(self):
        target = self._identity(
            7, "google-oauth2|corp", "internal", "yuji@circlecat.org"
        )
        keep = self._identity(5, _CURRENT_SUB, "external", "yuji@gmail.com")
        self._arrange_unlink(target, [keep])
        self.user_identities.exists_active_internal.return_value = True
        with self.assertRaises(PermissionError):
            await self.service.initiate_unlink(self.session, _USER_ID, _CURRENT_SUB, 7)
        self.auth0.start_passwordless.assert_not_called()

    async def test_initiate_unlink_rejects_when_no_primary(self):
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        keep = self._identity(5, _CURRENT_SUB, "external", "yuji@circlecat.org")
        self._arrange_unlink(target, [keep])
        self.user_emails.get_primary.return_value = None
        with self.assertRaises(ValueError):
            await self.service.initiate_unlink(self.session, _USER_ID, _CURRENT_SUB, 7)
        self.auth0.start_passwordless.assert_not_called()

    async def test_initiate_unlink_rejects_when_email_is_primary_contact(self):
        # Unlinking would drop the synced contact; refuse when it is the primary.
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        keep = self._identity(5, _CURRENT_SUB, "external", "yuji@circlecat.org")
        self._arrange_unlink(target, [keep])
        self.user_emails.get_primary.return_value = self._email_row(
            "Alice@Gmail.com", is_primary=True
        )
        with self.assertRaises(PermissionError):
            await self.service.initiate_unlink(self.session, _USER_ID, _CURRENT_SUB, 7)
        self.auth0.start_passwordless.assert_not_called()

    # confirm_unlink — step 2: recheck primary + preconditions, verify OTP, unlink
    async def test_confirm_unlink_happy_path_detaches_and_deletes_identity(self):
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        keep = self._identity(5, _CURRENT_SUB, "external", "yuji@circlecat.org")
        self._arrange_unlink(target, [keep])
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")

        result = await self.service.confirm_unlink(
            self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
        )

        self.auth0.exchange_otp.assert_called_once_with("old@example.com", "123456")
        self.auth0.unlink_identity.assert_called_once_with(
            primary_sub=_CURRENT_SUB, provider="email", secondary_user_id="todelete"
        )
        self.user_identities.delete.assert_awaited_once_with(self.session, 7)
        self.session.commit.assert_awaited_once()
        self.assertEqual(result, {"ok": True})

    async def test_confirm_unlink_rejects_wrong_flow(self):
        state = _unlink_state(target_identity_id=7, flow="set_primary")
        with self.assertRaises(ValueError):
            await self.service.confirm_unlink(
                self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
            )
        self.auth0.exchange_otp.assert_not_called()

    async def test_confirm_unlink_rejects_state_for_other_user(self):
        state = _unlink_state(user_id=999, target_identity_id=7)
        with self.assertRaises(ValueError):
            await self.service.confirm_unlink(
                self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
            )
        self.auth0.exchange_otp.assert_not_called()

    async def test_confirm_unlink_rejects_identity_id_path_mismatch(self):
        # State was minted for identity 7 but the path says 99.
        state = _unlink_state(target_identity_id=7)
        with self.assertRaises(ValueError):
            await self.service.confirm_unlink(
                self.session, _USER_ID, _CURRENT_SUB, 99, state, "123456"
            )
        self.auth0.exchange_otp.assert_not_called()

    async def test_confirm_unlink_rejects_when_primary_changed(self):
        # Primary moved since initiate -> refuse before consuming the OTP.
        self.user_emails.get_primary.return_value = self._email_row(
            "changed@example.com", is_primary=True
        )
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")
        with self.assertRaises(PermissionError):
            await self.service.confirm_unlink(
                self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
            )
        self.auth0.exchange_otp.assert_not_called()
        self.user_identities.delete.assert_not_awaited()

    async def test_confirm_unlink_propagates_wrong_otp(self):
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        self.auth0.exchange_otp.side_effect = ValueError("Incorrect or expired code")
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")
        with self.assertRaises(ValueError):
            await self.service.confirm_unlink(
                self.session, _USER_ID, _CURRENT_SUB, 7, state, "000000"
            )
        self.user_identities.delete.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_confirm_unlink_revalidates_last_identity_after_initiate(self):
        # TOCTOU: the user dropped their other sign-in between initiate and
        # confirm; this one is now the only one and must not be stripped.
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        self.user_identities.get_by_id.return_value = target
        self.user_identities.list_by_user.return_value = [target]
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")
        with self.assertRaises(ConflictError):
            await self.service.confirm_unlink(
                self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
            )
        # OTP was consumed (recheck happens after), but nothing was deleted.
        self.auth0.unlink_identity.assert_not_called()
        self.user_identities.delete.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_confirm_unlink_revalidates_active_employee_after_initiate(self):
        # TOCTOU: the user became an active employee; the corp sign-in is locked.
        target = self._identity(
            7, "google-oauth2|corp", "internal", "yuji@circlecat.org"
        )
        keep = self._identity(5, _CURRENT_SUB, "external", "yuji@gmail.com")
        self._arrange_unlink(target, [keep])
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        self.user_identities.exists_active_internal.return_value = True
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")
        with self.assertRaises(PermissionError):
            await self.service.confirm_unlink(
                self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
            )
        self.user_identities.delete.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_confirm_unlink_rejects_missing_identity_after_otp(self):
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        self.user_identities.get_by_id.return_value = None
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")
        with self.assertRaises(ValueError):
            await self.service.confirm_unlink(
                self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
            )
        self.auth0.unlink_identity.assert_not_called()
        self.user_identities.delete.assert_not_awaited()

    async def test_confirm_unlink_deletes_contact_email_when_unreferenced(self):
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        keep = self._identity(5, _CURRENT_SUB, "external", "yuji@circlecat.org")
        self._arrange_unlink(target, [keep])
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        email_row = self._email_row("alice@gmail.com", is_primary=False)
        email_row.email_id = 88
        self.user_emails.get_by_user_and_email.return_value = email_row
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")

        await self.service.confirm_unlink(
            self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
        )

        self.user_emails.delete.assert_awaited_once_with(self.session, 88)

    async def test_confirm_unlink_keeps_contact_email_referenced_by_other_identity(
        self,
    ):
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        # Another identity still claims the same address (case-insensitive).
        other = self._identity(5, "google-oauth2|9", "external", "Alice@Gmail.com")
        current = self._identity(9, _CURRENT_SUB, "external", "yuji@circlecat.org")
        self._arrange_unlink(target, [other, current])
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")

        await self.service.confirm_unlink(
            self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
        )

        self.user_emails.delete.assert_not_awaited()
        self.user_emails.get_by_user_and_email.assert_not_awaited()

    async def test_confirm_unlink_does_not_delete_primary_contact_email(self):
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        keep = self._identity(5, _CURRENT_SUB, "external", "yuji@circlecat.org")
        self._arrange_unlink(target, [keep])
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        self.user_emails.get_by_user_and_email.return_value = self._email_row(
            "alice@gmail.com", is_primary=True
        )
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")

        await self.service.confirm_unlink(
            self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
        )

        self.user_emails.delete.assert_not_awaited()

    async def test_confirm_unlink_succeeds_even_if_alias_sync_fails(self):
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        keep = self._identity(5, _CURRENT_SUB, "external", "yuji@circlecat.org")
        self._arrange_unlink(target, [keep])
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        self.user_emails.get_by_user_and_email.return_value = None
        self.auth0.remove_alias_email_from_primary.side_effect = RuntimeError(
            "auth0 down"
        )
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")

        result = await self.service.confirm_unlink(
            self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
        )

        self.user_identities.delete.assert_awaited_once_with(self.session, 7)
        self.session.commit.assert_awaited_once()
        self.assertEqual(result, {"ok": True})


class TestSignState(unittest.TestCase):
    def setUp(self):
        os.environ["EMAIL_OTP_STATE_JWT_SECRET"] = _SECRET
        self.service = EmailManagementService(
            MagicMock(), AsyncMock(), AsyncMock(), MagicMock()
        )

    def test_sign_state_stamps_envelope_and_roundtrips(self):
        token = self.service._sign_state(
            "set_primary", user_id=_USER_ID, target_email_id=7
        )
        claims = jwt.decode(token, _SECRET, algorithms=["HS256"])

        # Flow-specific claims are carried through verbatim.
        self.assertEqual(claims["user_id"], _USER_ID)
        self.assertEqual(claims["target_email_id"], 7)
        # The shared envelope is stamped on every state.
        self.assertEqual(claims["flow"], "set_primary")
        self.assertIn("nonce", claims)
        self.assertEqual(claims["exp"] - claims["iat"], 600)

    def test_sign_state_is_decodable_by_decode_state(self):
        token = self.service._sign_state("add_email", user_id=_USER_ID)
        self.assertEqual(self.service._decode_state(token)["flow"], "add_email")

    def test_sign_state_uses_a_fresh_nonce_each_call(self):
        a = jwt.decode(
            self.service._sign_state("add_email", user_id=_USER_ID),
            _SECRET,
            algorithms=["HS256"],
        )
        b = jwt.decode(
            self.service._sign_state("add_email", user_id=_USER_ID),
            _SECRET,
            algorithms=["HS256"],
        )
        self.assertNotEqual(a["nonce"], b["nonce"])


class TestConsumeStepUpOtp(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        os.environ["EMAIL_OTP_STATE_JWT_SECRET"] = _SECRET
        self.auth0 = MagicMock()
        self.user_emails = AsyncMock()
        self.session = AsyncMock()
        self.service = EmailManagementService(
            self.auth0, self.user_emails, AsyncMock(), MagicMock()
        )

    def _primary(self, email):
        return UserEmailsEntity(
            user_id=_USER_ID, email=email, otp_confirmed=True, is_primary=True
        )

    async def test_consumes_otp_against_unchanged_primary(self):
        self.user_emails.get_primary.return_value = self._primary("old@example.com")
        claims = {"primary_email_at_request": "old@example.com"}

        await self.service._consume_step_up_otp(
            self.session, _USER_ID, claims, "123456", "switch"
        )

        self.auth0.exchange_otp.assert_called_once_with("old@example.com", "123456")

    async def test_rejects_when_primary_changed_since_initiate(self):
        self.user_emails.get_primary.return_value = self._primary("new@example.com")
        claims = {"primary_email_at_request": "old@example.com"}

        with self.assertRaises(PermissionError) as ctx:
            await self.service._consume_step_up_otp(
                self.session, _USER_ID, claims, "123456", "unlink"
            )
        # The operation noun customizes the message; the OTP is never consumed.
        self.assertIn("unlink", str(ctx.exception))
        self.auth0.exchange_otp.assert_not_called()

    async def test_rejects_when_no_primary(self):
        self.user_emails.get_primary.return_value = None
        claims = {"primary_email_at_request": "old@example.com"}

        with self.assertRaises(PermissionError):
            await self.service._consume_step_up_otp(
                self.session, _USER_ID, claims, "123456", "switch"
            )
        self.auth0.exchange_otp.assert_not_called()


class TestSplitSub(unittest.TestCase):
    def test_splits_provider_and_secondary_user_id(self):
        self.assertEqual(
            EmailManagementService._split_sub("google-oauth2|abc123"),
            ("google-oauth2", "abc123"),
        )

    def test_handles_sub_without_separator(self):
        # No pipe: the whole value is the provider, secondary id is empty.
        self.assertEqual(EmailManagementService._split_sub("opaque"), ("opaque", ""))


if __name__ == "__main__":
    unittest.main()
