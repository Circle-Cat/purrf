import os
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt

from backend.authentication.email_management_service import EmailManagementService
from backend.common.exceptions import ConflictError
from backend.common.permissions import INTERNAL_EMPLOYEE_PERMISSIONS
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
        self.user_emails.exists_on_other_user.return_value = False
        self.user_emails.get_by_user_and_email.return_value = None
        self.user_emails.has_primary.return_value = False
        self.user_identities = AsyncMock()
        self.user_identities.get_by_subject_identifier.return_value = None
        self.user_identities.exists_active_internal.return_value = False
        self.user_permissions = AsyncMock()
        self.user_permissions.get_active_permission_names.return_value = []
        self.users = AsyncMock()
        self.session = AsyncMock()
        self.service = EmailManagementService(
            self.auth0,
            self.user_emails,
            self.user_identities,
            self.user_permissions,
            self.users,
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

    async def test_initiate_conflict_when_claimed_elsewhere(self):
        # Any other-account claim blocks, confirmed or not: user_emails.email
        # is globally unique, so the eventual insert could never succeed. The
        # message carries an escape hatch to the OTP-login path for a caller
        # who actually owns the address under a different account.
        self.user_emails.exists_on_other_user.return_value = True
        with self.assertRaises(ConflictError) as ctx:
            await self.service.initiate(
                self.session, _USER_ID, _CURRENT_SUB, _TARGET_EMAIL
            )
        self.assertEqual(
            str(ctx.exception),
            "Email already in use by another account. If it's yours, sign "
            "in with a code to that address instead.",
        )
        self.auth0.start_passwordless.assert_not_called()

    # remove_email — drop an unverified backup contact address, no OTP
    def _removable_row(self, email_id=12, **overrides):
        row = self._email_row("backup@gmail.com", otp_confirmed=False, **overrides)
        row.email_id = email_id
        return row

    async def test_remove_email_deletes_unverified_row(self):
        self.user_emails.get_by_id.return_value = self._removable_row()

        result = await self.service.remove_email(
            self.session, _USER_ID, _CURRENT_SUB, None, 12
        )

        self.user_emails.delete.assert_awaited_once_with(self.session, 12)
        self.session.commit.assert_awaited_once()
        self.assertEqual(result, {"ok": True})

    async def test_remove_email_rejects_missing_row(self):
        self.user_emails.get_by_id.return_value = None
        with self.assertRaises(ValueError):
            await self.service.remove_email(
                self.session, _USER_ID, _CURRENT_SUB, None, 12
            )
        self.user_emails.delete.assert_not_awaited()

    async def test_remove_email_rejects_row_owned_by_other_user(self):
        self.user_emails.get_by_id.return_value = self._removable_row(user_id=999)
        with self.assertRaises(ValueError):
            await self.service.remove_email(
                self.session, _USER_ID, _CURRENT_SUB, None, 12
            )
        self.user_emails.delete.assert_not_awaited()

    async def test_remove_email_rejects_primary(self):
        row = self._removable_row()
        row.is_primary = True
        self.user_emails.get_by_id.return_value = row
        with self.assertRaises(ConflictError):
            await self.service.remove_email(
                self.session, _USER_ID, _CURRENT_SUB, None, 12
            )
        self.user_emails.delete.assert_not_awaited()

    async def test_remove_email_deletes_confirmed_non_primary_row(self):
        # New contract: any non-primary row is removable, confirmed included —
        # deleting it also removes its use as a passwordless login identifier
        # (one action, one consequence). A google-session caller hits no guard.
        row = self._removable_row()
        row.otp_confirmed = True
        self.user_emails.get_by_id.return_value = row

        result = await self.service.remove_email(
            self.session, _USER_ID, _CURRENT_SUB, None, 12
        )

        self.user_emails.delete.assert_awaited_once_with(self.session, 12)
        self.session.commit.assert_awaited_once()
        self.assertEqual(result, {"ok": True})

    async def test_remove_email_rejects_current_passwordless_session_address(self):
        # The caller's own session is an email| passwordless login whose token
        # claim matches this row (case/whitespace-insensitive) — deleting it
        # would strand a live token whose next request can no longer resolve.
        row = self._removable_row()
        row.otp_confirmed = True
        self.user_emails.get_by_id.return_value = row

        with self.assertRaises(ConflictError):
            await self.service.remove_email(
                self.session, _USER_ID, "email|abc123", "  Backup@Gmail.com  ", 12
            )
        self.user_emails.delete.assert_not_awaited()

    async def test_remove_email_passwordless_session_can_delete_different_address(
        self,
    ):
        # Same passwordless sub, but the target row is a different address —
        # the guard protects only the address the session itself signed in with.
        row = self._removable_row()
        row.otp_confirmed = True
        self.user_emails.get_by_id.return_value = row

        result = await self.service.remove_email(
            self.session, _USER_ID, "email|abc123", "other@gmail.com", 12
        )

        self.user_emails.delete.assert_awaited_once_with(self.session, 12)
        self.assertEqual(result, {"ok": True})

    async def test_remove_email_google_session_can_delete_login_adjacent_address(
        self,
    ):
        # The guard is passwordless-session-only: a google-session caller may
        # delete a non-primary row even if it matches their token's email claim.
        row = self._removable_row()
        row.otp_confirmed = True
        self.user_emails.get_by_id.return_value = row

        result = await self.service.remove_email(
            self.session, _USER_ID, _CURRENT_SUB, "backup@gmail.com", 12
        )

        self.user_emails.delete.assert_awaited_once_with(self.session, 12)
        self.assertEqual(result, {"ok": True})

    async def test_verify_confirms_without_creating_sign_in_identity(self):
        """Normal-mode verify only confirms the address; it must not create a
        user_identities row for the OTP's email| sub — the confirmed address
        is already a valid passwordless login identifier via routing (PR1),
        and the OTP's Auth0 user stays inert (verify-to-sign-in retired)."""
        result = await self.service.verify(
            self.session, _USER_ID, _CURRENT_SUB, _state(), "123456"
        )

        # Identities are never merged on the Auth0 side: the DB row is the
        # only link between the passwordless sub and the account.
        self.auth0.link_identity.assert_not_called()
        self.auth0.add_alias_email_to_account_root.assert_not_called()
        email_entity = self.user_emails.upsert_email.call_args.kwargs["entity"]
        self.assertTrue(email_entity.otp_confirmed)
        self.assertTrue(email_entity.is_primary)  # no existing primary -> auto
        self.user_identities.upsert_identity.assert_not_awaited()
        self.session.commit.assert_awaited_once()
        self.assertEqual(result, {"ok": True, "email": _TARGET_EMAIL})

    # Corp sign-in joining an existing account mirrors the first-login
    # lifecycle hook: internal permission bundle + corp email becomes primary.
    async def test_verify_company_email_grants_bundle_and_promotes_primary(self):
        corp_email = "bob@circlecat.org"
        self.auth0.exchange_otp.return_value = {
            "sub": _NEW_SUB,
            "email": corp_email,
            "email_verified": True,
        }
        # The account already has a personal primary; the corp row is created
        # by _confirm_email (first lookup None), then re-read by the hook.
        self.user_emails.has_primary.return_value = True
        corp_row = self._email_row(corp_email, otp_confirmed=True)
        corp_row.email_id = 31
        self.user_emails.get_by_user_and_email.side_effect = [None, corp_row]

        await self.service.verify(
            self.session, _USER_ID, _CURRENT_SUB, _state(email=corp_email), "123456"
        )

        _, grant_kwargs = self.user_permissions.grant.call_args
        self.assertEqual(grant_kwargs["user_id"], _USER_ID)
        self.assertEqual(
            set(grant_kwargs["permission_names"]), set(INTERNAL_EMPLOYEE_PERMISSIONS)
        )
        self.assertEqual(grant_kwargs["granted_source"], "system_internal")
        # The corp address displaces the personal primary.
        self.user_emails.set_primary.assert_awaited_once_with(
            self.session, _USER_ID, 31
        )
        # The row-less classification signal is set alongside the bundle grant.
        self.users.set_internal.assert_awaited_once_with(self.session, _USER_ID)
        self.session.commit.assert_awaited_once()

    async def test_verify_company_email_skips_held_bundle_and_existing_primary(self):
        # Re-verifying is idempotent: bundle already held -> no new grant rows;
        # corp address already primary -> no promotion.
        corp_email = "bob@circlecat.org"
        self.auth0.exchange_otp.return_value = {
            "sub": _NEW_SUB,
            "email": corp_email,
            "email_verified": True,
        }
        self.user_permissions.get_active_permission_names.return_value = [
            str(p) for p in INTERNAL_EMPLOYEE_PERMISSIONS
        ]
        self.user_emails.has_primary.return_value = True
        self.user_emails.get_by_user_and_email.return_value = self._email_row(
            corp_email, otp_confirmed=True, is_primary=True
        )

        await self.service.verify(
            self.session, _USER_ID, _CURRENT_SUB, _state(email=corp_email), "123456"
        )

        self.user_permissions.grant.assert_not_awaited()
        self.user_emails.set_primary.assert_not_awaited()
        self.session.commit.assert_awaited_once()

    async def test_verify_external_email_grants_nothing(self):
        await self.service.verify(
            self.session, _USER_ID, _CURRENT_SUB, _state(), "123456"
        )

        self.user_permissions.grant.assert_not_awaited()
        self.user_emails.set_primary.assert_not_awaited()

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
        # Confirming never inserts a user_identities row (regardless of
        # whether one already exists for this user).
        self.user_identities.upsert_identity.assert_not_called()
        self.session.commit.assert_awaited_once()

    async def test_verify_promotes_existing_row_to_primary_when_user_has_no_primary(
        self,
    ):
        # Migration-backfilled users carry an unconfirmed, non-primary
        # user_emails row. Confirming it via OTP must also make it primary when
        # the user still has no primary, so they end up with a notification
        # target rather than a confirmed-but-orphaned address.
        existing_email = UserEmailsEntity(
            user_id=_USER_ID, email=_TARGET_EMAIL, otp_confirmed=False, is_primary=False
        )
        self.user_emails.get_by_user_and_email.return_value = existing_email
        self.user_emails.has_primary.return_value = False
        self.user_identities.get_by_subject_identifier.return_value = (
            UserIdentitiesEntity(user_id=_USER_ID, subject_identifier=_NEW_SUB)
        )

        await self.service.verify(
            self.session, _USER_ID, _CURRENT_SUB, _state(), "123456"
        )

        self.assertTrue(existing_email.otp_confirmed)
        self.assertTrue(existing_email.is_primary)

    async def test_verify_existing_row_stays_secondary_when_primary_exists(self):
        # If the user already has a primary, confirming an existing secondary
        # row must not steal primary from it.
        existing_email = UserEmailsEntity(
            user_id=_USER_ID, email=_TARGET_EMAIL, otp_confirmed=False, is_primary=False
        )
        self.user_emails.get_by_user_and_email.return_value = existing_email
        self.user_emails.has_primary.return_value = True
        self.user_identities.get_by_subject_identifier.return_value = (
            UserIdentitiesEntity(user_id=_USER_ID, subject_identifier=_NEW_SUB)
        )

        await self.service.verify(
            self.session, _USER_ID, _CURRENT_SUB, _state(), "123456"
        )

        self.assertTrue(existing_email.otp_confirmed)
        self.assertFalse(existing_email.is_primary)

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

    def _arrange_unlink(self, target):
        """Wire the mocks for an unlink: get_by_id→target."""
        self.user_identities.get_by_id.return_value = target

    # initiate_unlink — step 1: validate, OTP the current primary, sign state
    async def test_initiate_unlink_sends_otp_to_primary_and_returns_state(self):
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        self._arrange_unlink(target)
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

    async def test_initiate_unlink_rejects_current_session_identity(self):
        target = self._identity(7, _CURRENT_SUB, "external", "x@x.com")
        self._arrange_unlink(target)
        with self.assertRaises(ConflictError):
            await self.service.initiate_unlink(self.session, _USER_ID, _CURRENT_SUB, 7)
        self.auth0.start_passwordless.assert_not_called()

    async def test_initiate_unlink_rejects_active_employee_internal(self):
        target = self._identity(
            7, "google-oauth2|corp", "internal", "yuji@circlecat.org"
        )
        self._arrange_unlink(target)
        self.user_identities.exists_active_internal.return_value = True
        with self.assertRaises(PermissionError):
            await self.service.initiate_unlink(self.session, _USER_ID, _CURRENT_SUB, 7)
        self.auth0.start_passwordless.assert_not_called()

    async def test_initiate_unlink_rejects_when_no_primary(self):
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        self._arrange_unlink(target)
        self.user_emails.get_primary.return_value = None
        with self.assertRaises(ValueError):
            await self.service.initiate_unlink(self.session, _USER_ID, _CURRENT_SUB, 7)
        self.auth0.start_passwordless.assert_not_called()

    async def test_unlink_last_identity_allowed_with_confirmed_primary(self):
        # Unlinking the caller's only remaining identity row can never lock
        # them out: completing this very step-up OTP requires a confirmed
        # primary contact email, that primary row is undeletable (remove_email
        # refuses it), and a confirmed primary is itself a passwordless login
        # path (verify() no longer needs a sign-in identity to make an address
        # usable). So the chain "step-up needs a primary -> primary can't be
        # removed -> primary always logs in" makes the old only-identity
        # refusal unreachable, and it is gone.
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        self.user_identities.get_by_id.return_value = target
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )

        initiate_result = await self.service.initiate_unlink(
            self.session, _USER_ID, _CURRENT_SUB, 7
        )

        result = await self.service.confirm_unlink(
            self.session,
            _USER_ID,
            _CURRENT_SUB,
            7,
            initiate_result["state"],
            "123456",
        )

        self.user_identities.delete.assert_awaited_once_with(self.session, 7)
        self.auth0.delete_user.assert_called_once_with("email|todelete")
        self.user_emails.delete.assert_not_awaited()
        self.session.commit.assert_awaited_once()
        self.assertEqual(result, {"ok": True})

    # confirm_unlink — step 2: recheck primary + preconditions, verify OTP, unlink
    async def test_confirm_unlink_happy_path_detaches_and_deletes_identity(self):
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        self._arrange_unlink(target)
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")

        result = await self.service.confirm_unlink(
            self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
        )

        self.auth0.exchange_otp.assert_called_once_with("old@example.com", "123456")
        self.user_identities.delete.assert_awaited_once_with(self.session, 7)
        # Each sign-in method is its own Auth0 user; unlinking deletes it too.
        self.auth0.delete_user.assert_called_once_with("email|todelete")
        self.session.commit.assert_awaited_once()
        self.assertEqual(result, {"ok": True})

    async def test_confirm_unlink_auth0_delete_failure_aborts_before_commit(self):
        # The Auth0 user delete happens before the commit so a failure rolls
        # the whole unlink back instead of leaving an orphan Auth0 user.
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        self._arrange_unlink(target)
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        self.auth0.delete_user.side_effect = RuntimeError("Auth0 delete_user failed")
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")

        with self.assertRaises(RuntimeError):
            await self.service.confirm_unlink(
                self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
            )
        self.session.commit.assert_not_awaited()

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

    async def test_confirm_unlink_revalidates_active_employee_after_initiate(self):
        # TOCTOU: the user became an active employee; the corp sign-in is locked.
        target = self._identity(
            7, "google-oauth2|corp", "internal", "yuji@circlecat.org"
        )
        self._arrange_unlink(target)
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
        self.auth0.delete_user.assert_not_called()
        self.user_identities.delete.assert_not_awaited()

    async def test_confirm_unlink_leaves_contact_email_row_untouched_when_unreferenced(
        self,
    ):
        # Unlink is decoupled from user_emails entirely now: an address left
        # unreferenced by any surviving identity is still not inspected or
        # deleted — it leaves the account only via remove_email.
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        self._arrange_unlink(target)
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")

        await self.service.confirm_unlink(
            self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
        )

        self.user_emails.get_by_user_and_email.assert_not_awaited()
        self.user_emails.delete.assert_not_awaited()

    async def test_confirm_unlink_leaves_contact_email_row_untouched_when_referenced_by_other_identity(
        self,
    ):
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        # Another identity still claims the same address (case-insensitive) —
        # irrelevant now, since unlink never looks at user_emails at all.
        self._arrange_unlink(target)
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")

        await self.service.confirm_unlink(
            self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
        )

        self.user_emails.delete.assert_not_awaited()
        self.user_emails.get_by_user_and_email.assert_not_awaited()

    async def test_confirm_unlink_leaves_primary_contact_email_untouched(self):
        target = self._identity(7, "email|todelete", "external", "alice@gmail.com")
        self._arrange_unlink(target)
        self.user_emails.get_primary.return_value = self._email_row(
            "old@example.com", is_primary=True
        )
        state = _unlink_state(target_identity_id=7, primary_email="old@example.com")

        await self.service.confirm_unlink(
            self.session, _USER_ID, _CURRENT_SUB, 7, state, "123456"
        )

        self.user_emails.delete.assert_not_awaited()
        self.user_emails.get_by_user_and_email.assert_not_awaited()


class TestSignState(unittest.TestCase):
    def setUp(self):
        os.environ["EMAIL_OTP_STATE_JWT_SECRET"] = _SECRET
        self.service = EmailManagementService(
            MagicMock(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock(), MagicMock()
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
            self.auth0,
            self.user_emails,
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            MagicMock(),
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


if __name__ == "__main__":
    unittest.main()
