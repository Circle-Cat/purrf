import unittest

from backend.communication.attachment_download import (
    attachment_disposition,
    attachment_response,
)


class AttachmentDispositionTest(unittest.TestCase):
    def test_quotes_slashes_and_non_ascii(self):
        self.assertEqual(
            attachment_disposition('../\u7b80\u5386 "v2".pdf'),
            'attachment; filename="__ v2.pdf"; '
            "filename*=UTF-8''%E7%AE%80%E5%8E%86%20v2.pdf",
        )

    def test_backslashes_and_control_characters(self):
        self.assertEqual(
            attachment_disposition("C:\\tmp\\a\r\nb\x00.txt"),
            "attachment; filename=\"C:tmpab.txt\"; filename*=UTF-8''C%3Atmpab.txt",
        )

    def test_plain_name_is_unchanged(self):
        self.assertEqual(
            attachment_disposition("resume.pdf"),
            "attachment; filename=\"resume.pdf\"; filename*=UTF-8''resume.pdf",
        )

    def test_name_left_empty_falls_back(self):
        self.assertEqual(
            attachment_disposition('/"\\'),
            "attachment; filename=\"attachment\"; filename*=UTF-8''attachment",
        )


class AttachmentResponseTest(unittest.TestCase):
    def test_bytes_download_that_is_never_sniffed(self):
        response = attachment_response(b"%PDF", "cv.pdf")

        self.assertEqual(response.body, b"%PDF")
        self.assertEqual(response.media_type, "application/octet-stream")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(
            response.headers["content-disposition"],
            "attachment; filename=\"cv.pdf\"; filename*=UTF-8''cv.pdf",
        )


if __name__ == "__main__":
    unittest.main()
