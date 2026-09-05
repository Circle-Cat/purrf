import unittest
from datetime import datetime, timezone

import pydantic

from backend.dto.block_dto import (
    BlockDecideDto,
    BlockDirectDto,
    BlockReassignDto,
    BlockRequestCreateDto,
    DeactivateRequestDto,
)
from backend.dto.user_account_dto import (
    UserAccountRowDto,
    UserSignInMethodsDto,
)


class TestBlockRequestCreateDto(unittest.TestCase):
    def test_blank_reason_is_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            BlockRequestCreateDto.model_validate({
                "userId": 1,
                "reason": "   ",
                "reviewerId": 2,
            })

    def test_reason_is_stripped(self):
        dto = BlockRequestCreateDto.model_validate({
            "userId": 1,
            "reason": "  second no-show  ",
            "reviewerId": 2,
        })
        self.assertEqual(dto.reason, "second no-show")

    def test_reviewer_is_required(self):
        """'A queue addressed to a permission is addressed to nobody' — the
        raiser must name someone."""
        with self.assertRaises(pydantic.ValidationError):
            BlockRequestCreateDto.model_validate({"userId": 1, "reason": "r"})


class TestBlockDirectDto(unittest.TestCase):
    def test_blank_reason_is_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            BlockDirectDto.model_validate({"reason": "   "})

    def test_reason_is_stripped(self):
        dto = BlockDirectDto.model_validate({"reason": "  second no-show  "})
        self.assertEqual(dto.reason, "second no-show")


class TestDeactivateRequestDto(unittest.TestCase):
    def test_note_is_optional(self):
        """Deactivation is not a finding of fault, so it needs no reason."""
        self.assertIsNone(DeactivateRequestDto.model_validate({}).note)

    def test_note_is_carried_through(self):
        dto = DeactivateRequestDto.model_validate({"note": "requested by email"})
        self.assertEqual(dto.note, "requested by email")


class TestBlockDecideDto(unittest.TestCase):
    def test_approved_is_required(self):
        with self.assertRaises(pydantic.ValidationError):
            BlockDecideDto.model_validate({"note": "no verdict given"})

    def test_rejection_note_is_optional(self):
        dto = BlockDecideDto.model_validate({"approved": False})
        self.assertFalse(dto.approved)
        self.assertIsNone(dto.note)


class TestBlockReassignDto(unittest.TestCase):
    def test_reviewer_id_is_required(self):
        with self.assertRaises(pydantic.ValidationError):
            BlockReassignDto.model_validate({})

    def test_unknown_field_is_rejected(self):
        """BaseRequestDto forbids extras: a reassign carries no decision."""
        with self.assertRaises(pydantic.ValidationError):
            BlockReassignDto.model_validate({"reviewerId": 3, "approved": True})


class TestUserAccountRowDto(unittest.TestCase):
    def _row(self, **overrides):
        payload = {
            "userId": 1,
            "primaryEmail": "a@example.com",
            "firstName": "A",
            "lastName": "B",
            "userType": "internal",
            "isSuperAdmin": False,
            "isActive": True,
            "isBlocked": False,
            "hasPendingBlockRequest": False,
        }
        payload.update(overrides)
        return UserAccountRowDto.model_validate(payload)

    def test_audit_fields_default_to_none(self):
        row = self._row()
        self.assertIsNone(row.deactivated_by)
        self.assertIsNone(row.deactivated_at)
        self.assertIsNone(row.deactivated_reason)
        self.assertIsNone(row.blocked_by)
        self.assertIsNone(row.blocked_reason)

    def test_deactivated_and_blocked_are_independent(self):
        row = self._row(isActive=False, isBlocked=True)
        self.assertFalse(row.is_active)
        self.assertTrue(row.is_blocked)

    def test_serializes_camel_case(self):
        dumped = self._row().model_dump(by_alias=True)
        self.assertIn("hasPendingBlockRequest", dumped)
        self.assertIn("blockedByName", dumped)
        self.assertNotIn("has_pending_block_request", dumped)

    def test_has_pending_block_request_is_required(self):
        """It is answered per caller, so no default can be right."""
        payload = {
            "userId": 1,
            "primaryEmail": "a@example.com",
            "firstName": "A",
            "lastName": "B",
            "userType": "internal",
            "isSuperAdmin": False,
            "isActive": True,
            "isBlocked": False,
        }
        with self.assertRaises(pydantic.ValidationError):
            UserAccountRowDto.model_validate(payload)


class TestUserSignInMethodsDto(unittest.TestCase):
    def test_accepts_an_account_with_no_identities(self):
        dto = UserSignInMethodsDto.model_validate({
            "emails": [
                {
                    "email": "a@example.com",
                    "otpConfirmed": True,
                    "isPrimary": True,
                }
            ],
            "identities": [],
        })
        self.assertEqual(len(dto.emails), 1)
        self.assertIsNone(dto.emails[0].last_login_at)
        self.assertEqual(dto.identities, [])

    def test_identity_email_claim_is_optional(self):
        dto = UserSignInMethodsDto.model_validate({
            "emails": [],
            "identities": [
                {
                    "subjectIdentifier": "google-oauth2|1",
                    "linkedAt": datetime.now(timezone.utc),
                }
            ],
        })
        self.assertIsNone(dto.identities[0].email_claim)


if __name__ == "__main__":
    unittest.main()
