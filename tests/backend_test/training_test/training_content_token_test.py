"""The signed session token that stands between a learner and the content host."""

import base64
import dataclasses
import json
import unittest

from backend.training.training_content_token import (
    TOKEN_LIFETIME_SECONDS,
    ContentTokenClaims,
    InvalidContentToken,
    issue_content_token,
    read_session_start,
    verify_content_token,
)

_KEY = "s3cret-signing-key"
_OTHER_KEY = "a-different-signing-key"
_NOW = 1_756_000_000
_TRAINING_ID = 4242
_USER_ID = 77


def _split(token):
    """A token is a payload segment and a signature segment."""
    payload, _, signature = token.rpartition(".")
    return payload, signature


def _decode_segment(segment):
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _encode_segment(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _payload(token):
    payload, _ = _split(token)
    return json.loads(_decode_segment(payload))


class TestIssueAndVerify(unittest.TestCase):
    def test_a_token_verifies_back_to_the_pair_it_was_issued_for(self):
        token, _ = issue_content_token(_KEY, _TRAINING_ID, _USER_ID, now=_NOW)

        claims = verify_content_token(_KEY, token, now=_NOW)

        self.assertEqual(claims.training_id, _TRAINING_ID)
        self.assertEqual(claims.user_id, _USER_ID)

    def test_the_returned_expiry_is_the_one_the_claims_carry(self):
        token, expires_at = issue_content_token(_KEY, _TRAINING_ID, _USER_ID, now=_NOW)

        claims = verify_content_token(_KEY, token, now=_NOW)

        self.assertEqual(expires_at, claims.expires_at)

    def test_the_default_lifetime_is_twelve_hours(self):
        """Long enough that a lesson cannot outlive the token it loaded under."""
        self.assertEqual(TOKEN_LIFETIME_SECONDS, 12 * 60 * 60)

        _, expires_at = issue_content_token(_KEY, _TRAINING_ID, _USER_ID, now=_NOW)

        self.assertEqual(expires_at, _NOW + TOKEN_LIFETIME_SECONDS)

    def test_an_explicit_lifetime_overrides_the_default(self):
        _, expires_at = issue_content_token(
            _KEY, _TRAINING_ID, _USER_ID, now=_NOW, lifetime_seconds=60
        )

        self.assertEqual(expires_at, _NOW + 60)


class TestExpiry(unittest.TestCase):
    def setUp(self):
        self.token, self.expires_at = issue_content_token(
            _KEY, _TRAINING_ID, _USER_ID, now=_NOW
        )

    def test_a_token_is_still_valid_one_second_before_its_expiry(self):
        """Expiry is exclusive, as it is for a JWT `exp`."""
        claims = verify_content_token(_KEY, self.token, now=self.expires_at - 1)

        self.assertEqual(claims.expires_at, self.expires_at)

    def test_a_token_at_exactly_its_expiry_is_refused(self):
        with self.assertRaises(InvalidContentToken):
            verify_content_token(_KEY, self.token, now=self.expires_at)

    def test_a_long_expired_token_is_refused(self):
        with self.assertRaises(InvalidContentToken):
            verify_content_token(_KEY, self.token, now=self.expires_at + 86_400)


class TestForgery(unittest.TestCase):
    def setUp(self):
        self.token, _ = issue_content_token(_KEY, _TRAINING_ID, _USER_ID, now=_NOW)

    def test_a_token_signed_with_another_key_is_refused(self):
        with self.assertRaises(InvalidContentToken):
            verify_content_token(_OTHER_KEY, self.token, now=_NOW)

    def test_editing_the_payload_under_the_original_signature_is_refused(self):
        """Swapping in somebody else's training must not survive the signature."""
        payload, signature = _split(self.token)
        claims = json.loads(_decode_segment(payload))
        key = next(k for k, v in claims.items() if v == _TRAINING_ID)
        claims[key] = _TRAINING_ID + 1
        forged = _encode_segment(json.dumps(claims).encode("utf-8")) + "." + signature

        with self.assertRaises(InvalidContentToken):
            verify_content_token(_KEY, forged, now=_NOW)

    def test_editing_the_signature_is_refused(self):
        payload, signature = _split(self.token)
        flipped = ("B" if signature[0] != "B" else "C") + signature[1:]

        with self.assertRaises(InvalidContentToken):
            verify_content_token(_KEY, payload + "." + flipped, now=_NOW)

    def test_a_truncated_signature_is_refused(self):
        payload, signature = _split(self.token)

        with self.assertRaises(InvalidContentToken):
            verify_content_token(_KEY, payload + "." + signature[:-2], now=_NOW)


class TestGarbageInput(unittest.TestCase):
    def _assert_only_invalid_content_token(self, token):
        try:
            verify_content_token(_KEY, token, now=_NOW)
        except InvalidContentToken:
            return
        except Exception as exc:
            self.fail(f"{token!r} raised {type(exc).__name__}: {exc}")
        self.fail(f"{token!r} was accepted")

    def test_an_empty_token_is_refused(self):
        self._assert_only_invalid_content_token("")

    def test_a_token_with_no_separator_is_refused(self):
        self._assert_only_invalid_content_token("justonesegment")

    def test_a_token_with_too_many_segments_is_refused(self):
        self._assert_only_invalid_content_token("a.b.c.d")

    def test_a_token_whose_segments_are_not_base64_is_refused(self):
        self._assert_only_invalid_content_token("!!!!.????")

    def test_a_non_ascii_signature_is_refused_not_a_500(self):
        """hmac.compare_digest raises TypeError rather than answering False,
        and anybody can put a non-ASCII character in a URL."""
        token, _ = issue_content_token(_KEY, _TRAINING_ID, _USER_ID, now=_NOW)
        payload, _ = _split(token)
        self._assert_only_invalid_content_token(payload + ".sign\u00e9")

    def test_a_non_ascii_payload_segment_is_refused_not_a_500(self):
        token, _ = issue_content_token(_KEY, _TRAINING_ID, _USER_ID, now=_NOW)
        _, signature = _split(token)
        self._assert_only_invalid_content_token("caf\u00e9." + signature)

    def test_base64_that_is_not_the_expected_json_is_refused(self):
        token, _ = issue_content_token(_KEY, _TRAINING_ID, _USER_ID, now=_NOW)
        _, signature = _split(token)
        self._assert_only_invalid_content_token(
            _encode_segment(b"this is not json") + "." + signature
        )

    def test_json_of_the_wrong_shape_is_refused(self):
        token, _ = issue_content_token(_KEY, _TRAINING_ID, _USER_ID, now=_NOW)
        _, signature = _split(token)
        self._assert_only_invalid_content_token(
            _encode_segment(json.dumps(["not", "an", "object"]).encode())
            + "."
            + signature
        )

    def test_invalid_content_token_is_a_value_error(self):
        self.assertTrue(issubclass(InvalidContentToken, ValueError))


class TestTokenCarriesNoStoragePrefix(unittest.TestCase):
    """The prefix is looked up per request, so it must never be baked in here.

    A token minted before a re-upload would otherwise keep pointing a learner
    at the retired prefix and start 404ing mid-lesson.
    """

    def setUp(self):
        self.token, _ = issue_content_token(_KEY, _TRAINING_ID, _USER_ID, now=_NOW)

    def test_the_payload_holds_no_storage_prefix(self):
        payload = _payload(self.token)

        for key, value in payload.items():
            rendered = str(value)
            self.assertNotIn("training/", rendered, msg=f"{key} looks like a prefix")
            self.assertNotIn("/", rendered, msg=f"{key} looks like an object path")

    def test_the_claims_say_who_and_when_and_never_where(self):
        """The mint time is not the prefix in disguise: it resolves to no
        file, and the package it gets compared against is read from the
        course row."""
        names = {field.name for field in dataclasses.fields(ContentTokenClaims)}

        self.assertEqual(names, {"training_id", "user_id", "expires_at", "issued_at"})

    def test_the_claims_are_frozen(self):
        claims = verify_content_token(_KEY, self.token, now=_NOW)

        with self.assertRaises(dataclasses.FrozenInstanceError):
            claims.training_id = 1


class TestReadingWhenTheRunBegan(unittest.TestCase):
    """A commit posted back on the app origin names the run it came from, and
    the server reads its mint time from the signature rather than trusting the
    body -- otherwise a stale tab could just claim to be a fresh one."""

    def test_the_mint_time_comes_back(self):
        token, _ = issue_content_token(_KEY, _TRAINING_ID, _USER_ID, now=_NOW)

        self.assertEqual(read_session_start(_KEY, token), _NOW)

    def test_an_expired_token_still_says_when_its_run_began(self):
        """Here the token is not the credential, and refusing an overrun one
        would cost the longest sitting its stamp."""
        token, _ = issue_content_token(_KEY, _TRAINING_ID, _USER_ID, now=_NOW)

        self.assertEqual(read_session_start(_KEY, token), _NOW)
        with self.assertRaises(InvalidContentToken):
            verify_content_token(_KEY, token, now=_NOW + TOKEN_LIFETIME_SECONDS)

    def test_a_token_signed_with_another_key_is_refused(self):
        token, _ = issue_content_token(_OTHER_KEY, _TRAINING_ID, _USER_ID, now=_NOW)

        with self.assertRaises(InvalidContentToken):
            read_session_start(_KEY, token)

    def test_an_altered_mint_time_is_refused(self):
        token, _ = issue_content_token(_KEY, _TRAINING_ID, _USER_ID, now=_NOW)
        payload, signature = _split(token)
        claims = json.loads(_decode_segment(payload))
        claims["i"] = _NOW + 999

        forged = _encode_segment(json.dumps(claims).encode("utf-8")) + "." + signature
        with self.assertRaises(InvalidContentToken):
            read_session_start(_KEY, forged)


if __name__ == "__main__":
    unittest.main()
