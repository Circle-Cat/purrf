import unittest

from backend.common.kit_html_checks import (
    broadcast_fingerprint,
    find_invalid_hrefs,
    targets_only_tag,
)


class FindInvalidHrefsTest(unittest.TestCase):
    def test_accepts_supported_schemes_and_liquid(self):
        html = (
            '<a href="https://circlecat.org">a</a>'
            '<a href="http://x.org">b</a>'
            '<a href="mailto:outreach@circlecat.org">c</a>'
            '<a href="tel:+1">d</a><a href="#top">e</a>'
            '<a href="{{ unsubscribe_url }}">f</a>'
        )
        self.assertEqual(find_invalid_hrefs(html), [])

    def test_reports_missing_scheme_once_in_order(self):
        html = (
            '<a href="circlecat.org">logo</a>'
            '<a href="outreach@circlecat.org">mail</a>'
            '<a href="circlecat.org">again</a>'
        )
        self.assertEqual(
            find_invalid_hrefs(html), ["circlecat.org", "outreach@circlecat.org"]
        )

    def test_reports_empty_href(self):
        self.assertEqual(find_invalid_hrefs('<a href="">Send a tip</a>'), [""])

    def test_single_quoted_and_uppercase_scheme(self):
        self.assertEqual(find_invalid_hrefs("<a HREF='HTTPS://A.ORG'>x</a>"), [])


class BroadcastFingerprintTest(unittest.TestCase):
    def _fp(self, **overrides):
        base = dict(
            content="<p>Hi</p>",
            subject="S",
            email_address="notification-test@circlecat.org",
            subscriber_filter=[{"all": [{"type": "tag", "ids": [1]}]}],
        )
        base.update(overrides)
        return broadcast_fingerprint(**base)

    def test_same_input_same_fingerprint(self):
        self.assertEqual(self._fp(), self._fp())

    def test_each_field_changes_fingerprint(self):
        base = self._fp()
        self.assertNotEqual(base, self._fp(content="<p>Hi!</p>"))
        self.assertNotEqual(base, self._fp(subject="S2"))
        self.assertNotEqual(base, self._fp(email_address="outreach@circlecat.org"))
        self.assertNotEqual(
            base, self._fp(subscriber_filter=[{"all": [{"type": "tag", "ids": [2]}]}])
        )


class TargetsOnlyTagTest(unittest.TestCase):
    SENDER = "notification-test@circlecat.org"

    def _b(self, groups, sender=None):
        return {"subscriber_filter": groups, "email_address": sender or self.SENDER}

    def test_accepts_the_one_tag_as_kit_reads_it_back(self):
        self.assertTrue(
            targets_only_tag(
                self._b([{"all": [{"type": "tag", "ids": [77]}]}]), 77, self.SENDER
            )
        )

    def test_rejects_other_tag_extra_conditions_or_sender(self):
        self.assertFalse(
            targets_only_tag(
                self._b([{"all": [{"type": "tag", "ids": [1]}]}]), 77, self.SENDER
            )
        )
        self.assertFalse(
            targets_only_tag(
                self._b([
                    {
                        "all": [{"type": "tag", "ids": [77]}],
                        "any": [{"type": "tag", "ids": [2]}],
                    }
                ]),
                77,
                self.SENDER,
            )
        )
        self.assertFalse(targets_only_tag(self._b([{"all": []}]), 77, self.SENDER))
        self.assertFalse(
            targets_only_tag(
                self._b(
                    [{"all": [{"type": "tag", "ids": [77]}]}], "outreach@circlecat.org"
                ),
                77,
                self.SENDER,
            )
        )


if __name__ == "__main__":
    unittest.main()
