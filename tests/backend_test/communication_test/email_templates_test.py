"""Unit tests for the recruiting candidate-email template catalog."""

import re
import unittest

from backend.communication.email_templates import (
    EMAIL_TEMPLATES,
    ONBOARDING_FORM_URL,
    PLACEHOLDER_KEYS,
    render_all_templates,
    render_template,
)

_EXPECTED_KEYS = [
    "screening_passed_cultural_invite",
    "cultural_interview_scheduled",
    "interview_rescheduled",
    "cultural_passed_technical_invite",
    "technical_interview_scheduled",
    "feedback_complete_ask_start_date",
    "offer_onboarding",
    "rejection",
]

_EXPECTED_SUBJECTS = {
    "screening_passed_cultural_invite": "Circle Cat Program - Interview Availability",
    "cultural_interview_scheduled": "Your Circle Cat Behavioral Interview is Scheduled",
    "interview_rescheduled": "Your Circle Cat Interview — Updated Time",
    "cultural_passed_technical_invite": "Circle Cat — Technical Interview Availability",
    "technical_interview_scheduled": "Your Circle Cat Technical Interview is Scheduled",
    "feedback_complete_ask_start_date": "Circle Cat — Next Steps",
    "offer_onboarding": "Welcome to Circle Cat — Onboarding & Next Steps",
    "rejection": "Your Application to Circle Cat",
}

_VALUES = {
    "candidate_name": "Ana",
    "position_title": "Software Engineer Intern (Summer 2026)",
    "sender_name": "Jane Smith",
}


class EmailTemplatesCatalogTest(unittest.TestCase):
    def test_catalog_has_eight_templates_in_spec_order(self):
        self.assertEqual([t.key for t in EMAIL_TEMPLATES], _EXPECTED_KEYS)

    def test_subjects_match_the_catalog_table(self):
        for template in EMAIL_TEMPLATES:
            with self.subTest(key=template.key):
                self.assertEqual(template.subject, _EXPECTED_SUBJECTS[template.key])

    def test_labels_are_non_empty_ascii_english(self):
        for template in EMAIL_TEMPLATES:
            with self.subTest(key=template.key):
                self.assertTrue(template.label.strip())
                self.assertTrue(template.label.isascii())

    def test_every_placeholder_is_a_known_key(self):
        for template in EMAIL_TEMPLATES:
            found = set(re.findall(r"\{\{(\w+)\}\}", template.body_html))
            with self.subTest(key=template.key):
                self.assertTrue(
                    found <= PLACEHOLDER_KEYS, f"unknown: {found - PLACEHOLDER_KEYS}"
                )

    def test_only_templates_one_and_eight_use_position_title(self):
        using = {t.key for t in EMAIL_TEMPLATES if "{{position_title}}" in t.body_html}
        self.assertEqual(using, {"screening_passed_cultural_invite", "rejection"})

    def test_every_bracket_marker_is_uppercase(self):
        for template in EMAIL_TEMPLATES:
            for marker in re.findall(r"\[[^\]]+\]", template.body_html):
                with self.subTest(key=template.key, marker=marker):
                    self.assertEqual(marker, marker.upper())

    def test_new_interview_marker_was_merged_away(self):
        for template in EMAIL_TEMPLATES:
            with self.subTest(key=template.key):
                self.assertNotIn("[NEW INTERVIEW DATE/TIME]", template.body_html)
        reschedule = next(
            t for t in EMAIL_TEMPLATES if t.key == "interview_rescheduled"
        )
        self.assertIn("[INTERVIEW DATE/TIME]", reschedule.body_html)

    def test_signature_block_present_in_every_template(self):
        for template in EMAIL_TEMPLATES:
            with self.subTest(key=template.key):
                self.assertIn("Director of People Operations", template.body_html)
                self.assertIn("Circle Cat Inc", template.body_html)

    def test_offer_template_links_the_onboarding_form(self):
        offer = next(t for t in EMAIL_TEMPLATES if t.key == "offer_onboarding")
        self.assertIn(f'<a href="{ONBOARDING_FORM_URL}">this form</a>', offer.body_html)

    def test_known_typos_are_preserved_verbatim(self):
        technical = next(
            t for t in EMAIL_TEMPLATES if t.key == "cultural_passed_technical_invite"
        )
        self.assertIn("during yourinterview", technical.body_html)
        self.assertIn("a google doc", technical.body_html)
        screening = next(
            t for t in EMAIL_TEMPLATES if t.key == "screening_passed_cultural_invite"
        )
        self.assertIn("over the Google Meet", screening.body_html)
        self.assertIn("from a colleague", screening.body_html)


class RenderTemplateTest(unittest.TestCase):
    def test_substitutes_all_three_placeholder_classes(self):
        subject, body = render_template("rejection", _VALUES)
        self.assertEqual(subject, "Your Application to Circle Cat")
        self.assertIn("Dear Ana,", body)
        self.assertIn("Software Engineer Intern (Summer 2026)", body)
        self.assertIn("Jane Smith", body)
        self.assertNotIn("{{", body)

    def test_html_escapes_substituted_values(self):
        _, body = render_template(
            "rejection", {**_VALUES, "candidate_name": "Ana & Co"}
        )
        self.assertIn("Dear Ana &amp; Co,", body)
        self.assertNotIn("Ana & Co", body)

    def test_leaves_bracket_markers_untouched(self):
        _, body = render_template("offer_onboarding", _VALUES)
        self.assertIn("[MANAGER NAME]", body)
        self.assertIn("[MANAGER EMAIL]", body)
        self.assertIn("[START DATE]", body)
        self.assertIn("[SOFTWARE ENGINEER VOLUNTEER / SOFTWARE ENGINEER INTERN]", body)

    def test_empty_first_name_renders_bare_salutation(self):
        _, body = render_template("rejection", {**_VALUES, "candidate_name": ""})
        self.assertIn("Dear ,", body)

    def test_unknown_key_raises(self):
        with self.assertRaises(ValueError):
            render_template("no_such_template", _VALUES)

    def test_missing_value_raises(self):
        with self.assertRaises(ValueError):
            render_template("rejection", {"candidate_name": "Ana"})

    def test_render_all_returns_eight_rendered_templates(self):
        rendered = render_all_templates(_VALUES)
        self.assertEqual(len(rendered), 8)
        for template, subject, body in rendered:
            with self.subTest(key=template.key):
                self.assertEqual(subject, template.subject)
                self.assertNotIn("{{", body)


if __name__ == "__main__":
    unittest.main()
