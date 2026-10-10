import unittest

from backend.common.html_text import html_to_text, text_to_html


class HtmlToTextTest(unittest.TestCase):
    def test_paragraphs_and_breaks_become_lines(self):
        self.assertEqual(
            html_to_text("<p>One</p><p>Two<br>Three</p>"), "One\n\nTwo\nThree"
        )

    def test_a_link_keeps_its_url(self):
        self.assertEqual(
            html_to_text('<a href="https://x.test">the form</a>'),
            "the form (https://x.test)",
        )

    def test_entities_are_unescaped(self):
        self.assertEqual(html_to_text("<p>a &amp; b &lt;c&gt;</p>"), "a & b <c>")


class TextToHtmlTest(unittest.TestCase):
    def test_markup_is_escaped_not_rendered(self):
        self.assertEqual(
            text_to_html('<script>alert("x")</script> & co'),
            "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; co",
        )

    def test_each_line_break_becomes_a_br(self):
        self.assertEqual(
            text_to_html("Hi Ann,\r\n\r\nSee you.\nBo"),
            "Hi Ann,<br><br>See you.<br>Bo",
        )

    def test_round_trip_keeps_single_newlines(self):
        self.assertEqual(html_to_text(text_to_html("a\nb")), "a\nb")

    def test_round_trip_keeps_a_blank_line_as_one(self):
        self.assertEqual(html_to_text(text_to_html("a\n\nb")), "a\n\nb")

    def test_round_trip_through_the_plain_fallback_keeps_the_text(self):
        original = "Line one\n\nLine <two> & three"
        self.assertEqual(html_to_text(text_to_html(original)), original)


if __name__ == "__main__":
    unittest.main()
