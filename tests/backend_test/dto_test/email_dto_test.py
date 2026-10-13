import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from backend.dto.email_dto import (
    EmailConversationDto,
    EmailMessageDto,
    EmailRecipientOptionDto,
    EmailSendRequestDto,
    EmailThreadDto,
)

_NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)


def _message(**fields):
    base = {"message_id": 1, "direction": "inbound", "created_at": _NOW}
    return SimpleNamespace(**{**base, **fields})


class EmailMessageDtoTest(unittest.TestCase):
    def test_attachments_list_name_and_size_in_stored_order(self):
        dto = EmailMessageDto.model_validate(
            _message(
                attachments=[
                    {"name": "cv.pdf", "size": 3, "gmailAttachmentId": "a"},
                    {"name": "b.png", "size": 4, "gmailAttachmentId": "b"},
                ]
            )
        )

        self.assertEqual(
            [(a.name, a.size) for a in dto.attachments],
            [("cv.pdf", 3), ("b.png", 4)],
        )
        self.assertEqual(
            dto.model_dump(by_alias=True)["attachments"][0],
            {"name": "cv.pdf", "size": 3},
        )

    def test_malformed_entries_keep_their_place(self):
        dto = EmailMessageDto.model_validate(
            _message(
                attachments=[
                    {"attachment_id": "a1", "filename": "old.pdf"},
                    {"name": None, "size": "12"},
                    "garbage",
                    {"name": "last.txt", "size": 1, "gmailAttachmentId": "z"},
                ]
            )
        )

        self.assertEqual(
            [(a.name, a.size) for a in dto.attachments],
            [("old.pdf", 0), ("attachment", 0), ("attachment", 0), ("last.txt", 1)],
        )

    def test_no_attachments_is_an_empty_list(self):
        for stored in (None, []):
            with self.subTest(stored=stored):
                dto = EmailMessageDto.model_validate(_message(attachments=stored))
                self.assertEqual(dto.attachments, [])
        self.assertEqual(EmailMessageDto.model_validate(_message()).attachments, [])

    def test_sent_by_name_is_serialised_in_camel_case(self):
        dto = EmailMessageDto.model_validate(_message(sent_by_user_id=9))
        dto.sent_by_name = "Ada"

        self.assertEqual(dto.model_dump(by_alias=True)["sentByName"], "Ada")


class EmailConversationDtoTest(unittest.TestCase):
    def test_new_fields_default_to_a_conversation_nobody_can_send_in(self):
        dumped = EmailConversationDto(threads=[]).model_dump(by_alias=True)

        self.assertEqual(
            (dumped["canSend"], dumped["senderAddress"], dumped["recipientOptions"]),
            (False, None, []),
        )

    def test_options_and_reply_to_serialise(self):
        conversation = EmailConversationDto(
            threads=[
                EmailThreadDto(
                    thread_id=1, created_at=_NOW, messages=[], reply_to="ann@x.com"
                )
            ],
            recipient_options=[
                EmailRecipientOptionDto(address="ann@x.com", label="Primary contact")
            ],
            can_send=True,
            sender_address="mentorship@circlecat.org",
        )

        dumped = conversation.model_dump(by_alias=True)

        self.assertEqual(dumped["threads"][0]["replyTo"], "ann@x.com")
        self.assertEqual(
            dumped["recipientOptions"],
            [{"address": "ann@x.com", "label": "Primary contact"}],
        )

    def test_an_unknown_label_is_rejected(self):
        with self.assertRaises(ValueError):
            EmailRecipientOptionDto(address="a@x.com", label="Work")


class EmailSendRequestDtoTest(unittest.TestCase):
    def test_a_reply_may_leave_to_empty_and_names_the_last_seen_message(self):
        dto = EmailSendRequestDto.model_validate({
            "subject": "Re: Hi",
            "body": "<p>x</p>",
            "threadId": 4,
            "lastSeenMessageId": 12,
        })

        self.assertEqual((dto.to, dto.thread_id, dto.last_seen_message_id), ([], 4, 12))


if __name__ == "__main__":
    unittest.main()
