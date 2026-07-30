import unittest
from datetime import datetime, timezone

from backend.common.recruiting_enums import (
    ApplicationStage,
    JobKind,
    NotificationType,
)
from backend.dto.notification_dto import NotificationDto
from backend.recruiting import notification_email_copy


def _dto(**overrides):
    defaults = dict(
        id=1,
        type=NotificationType.ASSIGNED_TO_EVALUATE,
        application_id=10,
        job_id=3,
        round=1,
        job_title="Backend Engineer",
        job_kind=JobKind.EMPLOYMENT,
        applicant_name="Ada Lovelace",
        actor_name="Grace Hopper",
        created_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return NotificationDto(**defaults)


class TestStageLabel(unittest.TestCase):
    def test_humanizes_a_snake_case_stage(self):
        self.assertEqual(
            notification_email_copy.stage_label(
                ApplicationStage.RECRUITER_SCREENING, JobKind.EMPLOYMENT
            ),
            "Recruiter screening",
        )

    def test_renames_hired_to_admitted_for_an_activity_posting(self):
        self.assertEqual(
            notification_email_copy.stage_label(
                ApplicationStage.HIRED, JobKind.ACTIVITY
            ),
            "Admitted",
        )

    def test_keeps_hired_for_an_employment_posting(self):
        self.assertEqual(
            notification_email_copy.stage_label(
                ApplicationStage.HIRED, JobKind.EMPLOYMENT
            ),
            "Hired",
        )

    def test_returns_empty_string_for_no_stage(self):
        self.assertEqual(
            notification_email_copy.stage_label(None, JobKind.EMPLOYMENT), ""
        )


class TestRender(unittest.TestCase):
    def test_every_notification_type_has_a_template(self):
        """A type with no template would render a blank email."""
        self.assertEqual(set(notification_email_copy.TEMPLATES), set(NotificationType))

    def test_assigned_to_evaluate_names_the_actor_stage_and_destination(self):
        subject, body = notification_email_copy.render(_dto(), ApplicationStage.TECH)

        self.assertEqual(
            subject, "Evaluation assigned: Ada Lovelace (Backend Engineer)"
        )
        self.assertIn(
            "Grace Hopper assigned you to evaluate Ada Lovelace for Backend Engineer.",
            body,
        )
        self.assertIn("Stage: Tech.", body)
        self.assertIn("Recruiting &rarr; My Evaluations", body)

    def test_assigned_to_evaluate_appends_the_round_only_past_the_first(self):
        _, body = notification_email_copy.render(_dto(round=2), ApplicationStage.TECH)

        self.assertIn("Stage: Tech, round 2.", body)

    def test_assigned_to_evaluate_says_automatic_without_an_actor(self):
        _, body = notification_email_copy.render(
            _dto(actor_name=None), ApplicationStage.RECRUITER_SCREENING
        )

        self.assertIn("You were automatically assigned to evaluate", body)

    def test_mentioned_points_at_the_comments_tab(self):
        subject, body = notification_email_copy.render(
            _dto(type=NotificationType.MENTIONED), None
        )

        self.assertEqual(
            subject, "Grace Hopper mentioned you: Ada Lovelace (Backend Engineer)"
        )
        self.assertIn("Comments tab", body)

    def test_job_review_requested_avoids_claiming_the_posting_is_unpublished(self):
        subject, body = notification_email_copy.render(
            _dto(type=NotificationType.JOB_REVIEW_REQUESTED), None
        )

        self.assertEqual(subject, "Posting review requested: Backend Engineer")
        self.assertIn("waiting on your decision", body)
        # A CLOSE or REOPEN review is not about publishing, so the copy must
        # not promise anything about publication.
        self.assertNotIn("publish", body.lower())

    def test_job_review_approved_and_rejected_name_the_actor(self):
        _, approved = notification_email_copy.render(
            _dto(type=NotificationType.JOB_REVIEW_APPROVED), None
        )
        subject, rejected = notification_email_copy.render(
            _dto(type=NotificationType.JOB_REVIEW_REJECTED), None
        )

        self.assertIn("Grace Hopper approved your submission", approved)
        self.assertEqual(subject, "Posting rejected: Backend Engineer")
        # reject_comment is nullable, so the copy must hedge.
        self.assertIn("any comment", rejected)

    def test_application_submitted_explains_why_the_owner_got_it(self):
        subject, body = notification_email_copy.render(
            _dto(type=NotificationType.APPLICATION_SUBMITTED),
            ApplicationStage.RECRUITER_SCREENING,
        )

        self.assertEqual(subject, "New application: Ada Lovelace for Backend Engineer")
        self.assertIn("waiting for review at the Recruiter screening stage", body)
        self.assertIn("because you own this posting", body)

    def test_application_auto_rejected_says_no_human_review(self):
        subject, body = notification_email_copy.render(
            _dto(type=NotificationType.APPLICATION_AUTO_REJECTED), None
        )

        self.assertEqual(
            subject, "Application auto-rejected: Ada Lovelace (Backend Engineer)"
        )
        self.assertIn("rejected automatically, with no human review", body)
        self.assertIn("timeline", body)

    def test_application_auto_hired_says_admitted_for_an_activity_posting(self):
        subject, body = notification_email_copy.render(
            _dto(
                type=NotificationType.APPLICATION_AUTO_HIRED,
                job_kind=JobKind.ACTIVITY,
            ),
            None,
        )

        self.assertEqual(
            subject, "Application auto-admitted: Ada Lovelace (Backend Engineer)"
        )
        self.assertIn("admitted automatically", body)

    def test_application_auto_hired_says_hired_for_an_employment_posting(self):
        subject, body = notification_email_copy.render(
            _dto(
                type=NotificationType.APPLICATION_AUTO_HIRED,
                job_kind=JobKind.EMPLOYMENT,
            ),
            None,
        )

        self.assertEqual(
            subject, "Application auto-hired: Ada Lovelace (Backend Engineer)"
        )
        self.assertIn("hired automatically", body)

    def test_falls_back_to_placeholders_for_missing_names(self):
        _, body = notification_email_copy.render(
            _dto(actor_name="", applicant_name=""), None
        )

        self.assertIn("Someone", body)
        self.assertIn("A candidate", body)

    def test_every_body_carries_the_automated_footer(self):
        for notification_type in NotificationType:
            with self.subTest(type=notification_type):
                _, body = notification_email_copy.render(
                    _dto(type=notification_type), ApplicationStage.TECH
                )
                self.assertIn("Replies to this address aren't monitored", body)


if __name__ == "__main__":
    unittest.main()
