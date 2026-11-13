import unittest

from pydantic import ValidationError

from backend.dto.registration_create_dto import RegistrationCreateDto


def _payload(share_linkedin, linkedin_link=None):
    payload = {
        "globalPreferences": {"skillsets": {}},
        "roundPreferences": {
            "participantRole": "mentee",
            "maxPartners": 1,
            "shareLinkedin": share_linkedin,
        },
    }
    if linkedin_link is not None:
        payload["linkedinLink"] = linkedin_link
    return payload


class TestRegistrationCreateDto(unittest.TestCase):
    def test_sharing_with_a_linkedin_link_is_accepted(self):
        dto = RegistrationCreateDto.model_validate(
            _payload(True, "https://www.LinkedIn.com/in/ann-lee")
        )

        self.assertTrue(dto.round_preferences.share_linkedin)
        self.assertEqual(dto.linkedin_link, "https://www.LinkedIn.com/in/ann-lee")

    def test_sharing_without_a_link_is_rejected(self):
        with self.assertRaises(ValidationError):
            RegistrationCreateDto.model_validate(_payload(True))

    def test_sharing_with_a_blank_link_is_rejected(self):
        with self.assertRaises(ValidationError):
            RegistrationCreateDto.model_validate(_payload(True, "   "))

    def test_sharing_with_a_link_elsewhere_is_rejected(self):
        with self.assertRaises(ValidationError):
            RegistrationCreateDto.model_validate(
                _payload(True, "https://github.com/ann-lee")
            )

    def test_a_javascript_url_mentioning_linkedin_is_rejected(self):
        with self.assertRaises(ValidationError):
            RegistrationCreateDto.model_validate(
                _payload(True, "javascript:alert(1)//linkedin.com")
            )

    def test_a_lookalike_host_is_rejected(self):
        with self.assertRaises(ValidationError):
            RegistrationCreateDto.model_validate(
                _payload(True, "https://linkedin.com.evil.example/in/ann-lee")
            )

    def test_a_link_without_scheme_is_upgraded_to_https(self):
        dto = RegistrationCreateDto.model_validate(
            _payload(True, " linkedin.com/in/ann-lee ")
        )

        self.assertEqual(dto.linkedin_link, "https://linkedin.com/in/ann-lee")

    def test_not_sharing_needs_no_link(self):
        dto = RegistrationCreateDto.model_validate(_payload(False))

        self.assertFalse(dto.round_preferences.share_linkedin)
        self.assertIsNone(dto.linkedin_link)

    def test_an_unanswered_question_is_accepted_as_none(self):
        payload = _payload(None)
        del payload["roundPreferences"]["shareLinkedin"]

        dto = RegistrationCreateDto.model_validate(payload)

        self.assertIsNone(dto.round_preferences.share_linkedin)


if __name__ == "__main__":
    unittest.main()
