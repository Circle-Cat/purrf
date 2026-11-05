import unittest

from backend.common.html_text import html_has_text, html_to_text, text_to_html


def _wrap(inner):
    return f'<div style="white-space:pre-wrap">{inner}</div>'


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
            _wrap("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; co"),
        )

    def test_each_line_break_becomes_a_br(self):
        self.assertEqual(
            text_to_html("Hi Ann,\r\n\r\nSee you.\nBo"),
            _wrap("Hi Ann,<br><br>See you.<br>Bo"),
        )

    def test_a_single_newline_is_one_br_in_a_pre_wrap_div(self):
        self.assertEqual(
            text_to_html("a\nb"), '<div style="white-space:pre-wrap">a<br>b</div>'
        )

    def test_indentation_and_space_runs_are_kept_inside_the_div(self):
        self.assertEqual(text_to_html("  a   b\n    c"), _wrap("  a   b<br>    c"))

    def test_round_trip_keeps_indentation_free_text(self):
        self.assertEqual(html_to_text(text_to_html("a\nb")), "a\nb")

    def test_round_trip_keeps_single_newlines(self):
        self.assertEqual(html_to_text(text_to_html("a\nb")), "a\nb")

    def test_round_trip_keeps_a_blank_line_as_one(self):
        self.assertEqual(html_to_text(text_to_html("a\n\nb")), "a\n\nb")

    def test_round_trip_through_the_plain_fallback_keeps_the_text(self):
        original = "Line one\n\nLine <two> & three"
        self.assertEqual(html_to_text(text_to_html(original)), original)


class HtmlHasTextTest(unittest.TestCase):
    def test_markup_alone_has_no_text(self):
        for body in ("<p></p>", "<p><br></p>", "<p>&nbsp;</p>", "<ul><li></li></ul>"):
            with self.subTest(body=body):
                self.assertFalse(html_has_text(body))

    def test_any_visible_character_counts(self):
        for body in ("<p>x</p>", "<p>&amp;</p>", '<a href="https://x.test">l</a>'):
            with self.subTest(body=body):
                self.assertTrue(html_has_text(body))


if __name__ == "__main__":
    unittest.main()
