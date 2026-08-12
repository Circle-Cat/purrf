import unittest
from datetime import datetime, timezone

from types import SimpleNamespace

from backend.common.recruiting_enums import (
    ApplicationStage,
    JobKind,
)
from backend.recruiting import notification_email_copy


def _dto(**overrides):
    """The display fields the copy functions read.

    A plain namespace, because that is what the renderers hand them: the
    fields are resolved per event rather than read off a notification row.
    """
    defaults = dict(
        id=1,
        round=1,
        job_title="Backend Engineer",
        job_kind=JobKind.EMPLOYMENT,
        applicant_name="Ada Lovelace",
        applicant_email="ada@example.com",
        actor_name="Grace Hopper",
        created_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
        # Read only by the templates that mention them; harmless elsewhere.
        reason="Not a fit",
        to_sub_status="scheduled",
        start_at=datetime(2026, 8, 5, 21, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _every_template():
    """Every copy function in the module, by name.

    Swept rather than listed so a template added later cannot quietly skip
    the rules below.
    """
    import inspect

    return [
        (name, value)
        for name, value in vars(notification_email_copy).items()
        if name.startswith("_")
        and callable(value)
        and not name.startswith("__")
        and getattr(value, "__module__", "") == notification_email_copy.__name__
        # A template takes (dto, stage); the module's small helpers do not.
        and list(inspect.signature(value).parameters) == ["dto", "stage"]
    ]


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
    def test_assigned_to_evaluate_names_the_actor_stage_and_destination(self):
        subject, body = notification_email_copy._assigned_to_evaluate(
            _dto(), ApplicationStage.TECH
        )

        self.assertEqual(
            subject, "Evaluation assigned: Ada Lovelace (Backend Engineer)"
        )
        self.assertIn(
            "Grace Hopper assigned you to evaluate Ada Lovelace for Backend Engineer.",
            body,
        )
        self.assertIn("Stage: Tech.", body)
        self.assertIn("Open My Interview Evaluations in Purrf", body)

    def test_assigned_to_evaluate_appends_the_round_only_past_the_first(self):
        _, body = notification_email_copy._assigned_to_evaluate(
            _dto(round=2), ApplicationStage.TECH
        )

        self.assertIn("Stage: Tech, session 2.", body)

    def test_assigned_to_evaluate_says_automatic_without_an_actor(self):
        _, body = notification_email_copy._assigned_to_evaluate(
            _dto(actor_name=None), ApplicationStage.RECRUITER_SCREENING
        )

        self.assertIn("You were automatically assigned to evaluate", body)

    def test_mentioned_points_at_the_comments_tab(self):
        subject, body = notification_email_copy._mentioned(_dto(), None)

        self.assertEqual(
            subject, "Grace Hopper mentioned you: Ada Lovelace (Backend Engineer)"
        )
        self.assertIn("Comments tab", body)

    def test_job_review_requested_avoids_claiming_the_posting_is_unpublished(self):
        subject, body = notification_email_copy._job_review_requested(_dto(), None)

        self.assertEqual(subject, "Posting review requested: Backend Engineer")
        self.assertIn("waiting on your decision", body)
        self.assertIn("Open My Posting Reviews in Purrf", body)
        # A CLOSE or REOPEN review is not about publishing, so the copy must
        # not promise anything about publication.
        self.assertNotIn("publish", body.lower())

    def test_job_review_approved_and_rejected_name_the_actor(self):
        _, approved = notification_email_copy._job_review_approved(_dto(), None)
        subject, rejected = notification_email_copy._job_review_rejected(_dto(), None)

        self.assertIn("Grace Hopper approved your submission", approved)
        self.assertIn("Open Job Postings in Purrf", approved)
        self.assertEqual(subject, "Posting rejected: Backend Engineer")
        self.assertIn("Open Job Postings in Purrf", rejected)
        # reject_comment is nullable, so the copy must hedge.
        self.assertIn("any comment", rejected)

    def test_application_submitted_explains_why_the_owner_got_it(self):
        subject, body = notification_email_copy._application_submitted(
            _dto(),
            ApplicationStage.RECRUITER_SCREENING,
        )

        self.assertEqual(subject, "New application: Ada Lovelace for Backend Engineer")
        self.assertIn("waiting for review at the Recruiter screening stage", body)
        self.assertIn("because you own this posting", body)
        self.assertIn("Open the Applications Board in Purrf", body)

    def test_application_auto_rejected_says_no_human_review(self):
        subject, body = notification_email_copy._application_auto_rejected(_dto(), None)

        self.assertEqual(
            subject, "Application auto-rejected: Ada Lovelace (Backend Engineer)"
        )
        self.assertIn("rejected automatically, with no human review", body)
        self.assertIn("timeline", body)

    def test_application_auto_hired_says_admitted_for_an_activity_posting(self):
        subject, body = notification_email_copy._application_auto_hired(
            _dto(
                job_kind=JobKind.ACTIVITY,
            ),
            None,
        )

        self.assertEqual(
            subject, "Application auto-admitted: Ada Lovelace (Backend Engineer)"
        )
        self.assertIn("admitted automatically", body)

    def test_application_auto_hired_says_hired_for_an_employment_posting(self):
        subject, body = notification_email_copy._application_auto_hired(
            _dto(
                job_kind=JobKind.EMPLOYMENT,
            ),
            None,
        )

        self.assertEqual(
            subject, "Application auto-hired: Ada Lovelace (Backend Engineer)"
        )
        self.assertIn("hired automatically", body)

    def test_falls_back_to_placeholders_for_missing_names(self):
        _, body = notification_email_copy._mentioned(
            _dto(actor_name="", applicant_name=""), None
        )

        self.assertIn("Someone", body)
        self.assertIn("A candidate", body)

    def test_no_body_describes_a_nested_menu_path(self):
        """The sidebar is one flat list, so "A -> B" points at nothing.

        Guards the specific mistake this copy shipped with: bodies read
        "Open Recruiting -> Postings", but Sidebar.jsx has no Recruiting
        group to open. Every destination has to be a top-level nav label.
        """
        for name, template in _every_template():
            with self.subTest(template=name):
                _, body = template(_dto(), ApplicationStage.TECH)
                self.assertNotIn("&rarr;", body)


class TestCandidateLine(unittest.TestCase):
    """The address exists in the copy to survive a renamed candidate.

    A display name is mutable and not unique, so an owner reading mail about
    "Ada Lovelace" may not be able to tell which application it means. The
    address is the handle they can paste into the board's search.
    """

    # The three job-scoped templates: a posting under review has no
    # candidate, so there is no address to print.
    _NO_CANDIDATE = {
        "_job_review_requested",
        "_job_review_approved",
        "_job_review_rejected",
    }

    def test_names_the_candidate_and_the_address(self):
        _, body = notification_email_copy._stage_changed(_dto(), ApplicationStage.TECH)

        self.assertIn("Candidate: Ada Lovelace (ada@example.com)", body)

    def test_prints_the_address_alone_when_the_name_resolves_to_nothing(self):
        """The case the line exists for: no name to show, address still known."""
        _, body = notification_email_copy._stage_changed(
            _dto(applicant_name=""), ApplicationStage.TECH
        )

        self.assertIn("Candidate: ada@example.com", body)
        self.assertNotIn("()", body)

    def test_omits_the_line_when_there_is_no_address(self):
        """A name-only line would repeat what the body already says."""
        _, body = notification_email_copy._stage_changed(
            _dto(applicant_email=None), ApplicationStage.TECH
        )

        self.assertNotIn("Candidate:", body)

    def test_omits_the_line_when_neither_is_known(self):
        _, body = notification_email_copy._stage_changed(
            _dto(applicant_name="", applicant_email=None), ApplicationStage.TECH
        )

        self.assertNotIn("Candidate:", body)

    def test_every_candidate_template_prints_the_line(self):
        """Swept, not listed, so a template added later cannot skip it.

        A template that forgot the line would send mail identifying its
        candidate by a mutable name only, and nothing else would notice.
        """
        for name, template in _every_template():
            if name in self._NO_CANDIDATE:
                continue
            with self.subTest(template=name):
                _, body = template(_dto(), ApplicationStage.TECH)
                self.assertIn("Candidate: Ada Lovelace (ada@example.com)", body)

    def test_no_job_scoped_template_prints_the_line(self):
        for name in self._NO_CANDIDATE:
            with self.subTest(template=name):
                _, body = getattr(notification_email_copy, name)(
                    _dto(), ApplicationStage.TECH
                )
                self.assertNotIn("Candidate:", body)


if __name__ == "__main__":
    unittest.main()
